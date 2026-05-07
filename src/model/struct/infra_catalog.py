import datetime
import decimal
import uuid


connect = wiz.model("db/postgres").connect
settings = wiz.model("struct/settings")
setup = wiz.model("struct/setup")
system = wiz.model("struct/system")
local_command_catalog = wiz.model("struct/local_command_catalog")


def _serialize(value):
    if isinstance(value, (datetime.datetime, datetime.date)):
        return value.isoformat()
    if isinstance(value, uuid.UUID):
        return str(value)
    if isinstance(value, decimal.Decimal):
        return float(value)
    if isinstance(value, list):
        return [_serialize(item) for item in value]
    if isinstance(value, dict):
        return {key: _serialize(item) for key, item in value.items()}
    return value


def _rows(cursor, query, params=None):
    cursor.execute(query, params or [])
    return [_serialize(dict(row)) for row in cursor.fetchall()]


def _count(cursor, table):
    cursor.execute(f"SELECT count(*) AS count FROM {table}")
    return int(cursor.fetchone()["count"])


def _setting_map():
    return {row["key"]: row for row in settings.list()}


def _setting_value(mapped, key, fallback=None):
    row = mapped.get(key)
    if row is None:
        return fallback
    value = row.get("value")
    return fallback if value is None else value


def _secret_configured(mapped, key):
    row = mapped.get(key)
    if row is None:
        return False
    return bool((row.get("secret") or {}).get("is_configured"))


class InfraCatalog:
    def counts(self):
        with connect() as connection:
            with connection.cursor() as cursor:
                return {
                    "nodes": _count(cursor, "nodes"),
                    "services": _count(cursor, "services"),
                    "service_domains": _count(cursor, "service_domains"),
                    "templates": _count(cursor, "templates"),
                    "images": _count(cursor, "images"),
                    "image_builds": _count(cursor, "image_builds"),
                    "jobs": _count(cursor, "jobs"),
                    "cloudflare_zones": _count(cursor, "cloudflare_zones"),
                    "certificates": _count(cursor, "certificates"),
                }

    def integrations(self):
        mapped = _setting_map()
        return [
            {
                "key": "harbor",
                "label": "Harbor",
                "enabled": bool(_setting_value(mapped, "integration.harbor.enabled", False)),
                "primary": _setting_value(mapped, "integration.harbor.url", ""),
                "secondary": _setting_value(mapped, "integration.harbor.username", ""),
                "secret_configured": _secret_configured(mapped, "integration.harbor.password"),
            },
            {
                "key": "gitlab",
                "label": "GitLab",
                "enabled": bool(_setting_value(mapped, "integration.gitlab.enabled", False)),
                "primary": _setting_value(mapped, "integration.gitlab.url", ""),
                "secondary": "",
                "secret_configured": _secret_configured(mapped, "integration.gitlab.token"),
            },
            {
                "key": "cloudflare",
                "label": "Cloudflare",
                "enabled": bool(_setting_value(mapped, "integration.cloudflare.enabled", False)),
                "primary": _setting_value(mapped, "integration.cloudflare.domain", ""),
                "secondary": _setting_value(mapped, "integration.cloudflare.zone_id", ""),
                "secret_configured": _secret_configured(mapped, "integration.cloudflare.api_token"),
            },
        ]

    def dashboard(self):
        counts = self.counts()
        with connect() as connection:
            with connection.cursor() as cursor:
                recent_jobs = _rows(
                    cursor,
                    """
                    SELECT id, type, status, created_at, finished_at
                    FROM jobs
                    ORDER BY created_at DESC
                    LIMIT 6
                    """,
                )
                nodes = _rows(
                    cursor,
                    """
                    SELECT id, name, role, host, status, is_local_master, updated_at
                    FROM nodes
                    ORDER BY is_local_master DESC, created_at DESC
                    LIMIT 6
                    """,
                )
                cursor.execute(
                    """
                    SELECT status, count(*) AS count
                    FROM jobs
                    GROUP BY status
                    ORDER BY status
                    """
                )
                job_statuses = {row["status"]: int(row["count"]) for row in cursor.fetchall()}
        setup_status = setup.status(include_checks=False)
        return {
            "counts": counts,
            "health": system.health(),
            "setup": setup_status,
            "nodes": nodes,
            "recent_jobs": recent_jobs,
            "job_statuses": job_statuses,
            "integrations": self.integrations(),
        }

    def services(self):
        with connect() as connection:
            with connection.cursor() as cursor:
                services = _rows(
                    cursor,
                    """
                    SELECT
                        s.*,
                        COALESCE(d.domain_count, 0) AS domain_count,
                        COALESCE(v.version_count, 0) AS compose_version_count
                    FROM services s
                    LEFT JOIN (
                        SELECT service_id, count(*) AS domain_count
                        FROM service_domains
                        GROUP BY service_id
                    ) d ON d.service_id = s.id
                    LEFT JOIN (
                        SELECT service_id, count(*) AS version_count
                        FROM compose_versions
                        GROUP BY service_id
                    ) v ON v.service_id = s.id
                    ORDER BY s.created_at DESC
                    LIMIT 80
                    """,
                )
                domains = _rows(
                    cursor,
                    """
                    SELECT sd.*, s.name AS service_name, s.namespace AS service_namespace
                    FROM service_domains sd
                    LEFT JOIN services s ON s.id = sd.service_id
                    ORDER BY sd.created_at DESC
                    LIMIT 80
                    """,
                )
                jobs = _rows(
                    cursor,
                    """
                    SELECT id, type, status, created_at, finished_at
                    FROM jobs
                    WHERE type ILIKE %s OR type ILIKE %s OR type ILIKE %s
                    ORDER BY created_at DESC
                    LIMIT 20
                    """,
                    ["%service%", "%deploy%", "%compose%"],
                )
        return {"services": services, "domains": domains, "jobs": jobs, "counts": self.counts()}

    def images(self):
        with connect() as connection:
            with connection.cursor() as cursor:
                images = _rows(cursor, "SELECT * FROM images ORDER BY created_at DESC LIMIT 80")
                builds = _rows(
                    cursor,
                    """
                    SELECT b.*, i.name AS image_name, i.tag AS image_tag, s.name AS service_name
                    FROM image_builds b
                    LEFT JOIN images i ON i.id = b.image_id
                    LEFT JOIN services s ON s.id = b.service_id
                    ORDER BY b.created_at DESC
                    LIMIT 80
                    """,
                )
        return {"images": images, "builds": builds, "integrations": self.integrations(), "counts": self.counts()}

    def templates(self):
        with connect() as connection:
            with connection.cursor() as cursor:
                templates = _rows(
                    cursor,
                    """
                    SELECT
                        t.*,
                        COALESCE(v.version_count, 0) AS version_count,
                        v.latest_version
                    FROM templates t
                    LEFT JOIN (
                        SELECT template_id, count(*) AS version_count, max(version) AS latest_version
                        FROM template_versions
                        GROUP BY template_id
                    ) v ON v.template_id = t.id
                    ORDER BY t.created_at DESC
                    LIMIT 80
                    """,
                )
                versions = _rows(cursor, "SELECT * FROM template_versions ORDER BY created_at DESC LIMIT 80")
        return {"templates": templates, "versions": versions, "setup": setup.status(include_checks=False)}

    def domains(self):
        with connect() as connection:
            with connection.cursor() as cursor:
                zones = _rows(cursor, "SELECT * FROM cloudflare_zones ORDER BY created_at DESC LIMIT 80")
                domains = _rows(
                    cursor,
                    """
                    SELECT sd.*, s.name AS service_name, s.namespace AS service_namespace
                    FROM service_domains sd
                    LEFT JOIN services s ON s.id = sd.service_id
                    ORDER BY sd.created_at DESC
                    LIMIT 80
                    """,
                )
                certificates = _rows(
                    cursor,
                    """
                    SELECT c.*, sd.domain
                    FROM certificates c
                    LEFT JOIN service_domains sd ON sd.id = c.service_domain_id
                    ORDER BY c.created_at DESC
                    LIMIT 80
                    """,
                )
        return {
            "zones": zones,
            "domains": domains,
            "certificates": certificates,
            "integrations": self.integrations(),
            "counts": self.counts(),
        }

    def tools(self):
        specs = []
        for command_id, spec in sorted(local_command_catalog.COMMAND_SPECS.items()):
            specs.append(
                {
                    "id": command_id,
                    "category": spec["category"],
                    "destructive": bool(spec.get("destructive")),
                    "default_timeout_seconds": spec.get("default_timeout_seconds"),
                }
            )
        with connect() as connection:
            with connection.cursor() as cursor:
                backups = _rows(cursor, "SELECT * FROM electron_setting_backups ORDER BY created_at DESC LIMIT 80")
        return {"commands": specs, "backups": backups, "health": system.health()}


Model = InfraCatalog()
