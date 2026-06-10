import datetime
import decimal
import uuid


connect = wiz.model("db/postgres").connect
setup = wiz.model("struct/setup")
system = wiz.model("struct/system")
local_command_catalog = wiz.model("struct/local_command_catalog")
ddns_model = wiz.model("struct/domains_ddns")
backup_system = wiz.model("struct/backup_system")
webserver = wiz.model("struct/webserver")


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


def _optional_count(cursor, table):
    cursor.execute("SELECT to_regclass(%s) AS table_name", (table,))
    if not cursor.fetchone().get("table_name"):
        return 0
    return _count(cursor, table)


class InfraCatalog:
    def counts(self):
        with connect() as connection:
            with connection.cursor() as cursor:
                return {
                    "nodes": _count(cursor, "nodes"),
                    "services": _count(cursor, "services"),
                    "service_domains": _count(cursor, "service_domains"),
                    "images": _count(cursor, "images"),
                    "operations": _count(cursor, "operation_logs"),
                    "ddns_endpoints": _optional_count(cursor, "ddns_endpoints"),
                }

    def integrations(self):
        backup = backup_system.status()
        items = [{
            "key": "backup_system",
            "label": "서비스 백업 시스템",
            "enabled": bool(backup.get("enabled")),
            "primary": backup.get("harbor_url") or "",
            "secondary": backup.get("status") or "",
            "secret_configured": bool(backup.get("secret_configured")),
        }]
        domain_overview = ddns_model.load()
        endpoints = domain_overview.get("endpoints", [])
        first_endpoint = endpoints[0] if endpoints else {}
        items.append(
            {
                "key": "ddns",
                "label": "DDNS",
                "enabled": len([endpoint for endpoint in endpoints if endpoint.get("enabled")]) > 0,
                "primary": first_endpoint.get("domain_suffix", ""),
                "secondary": first_endpoint.get("api_url", ""),
                "secret_configured": len([endpoint for endpoint in endpoints if endpoint.get("secret_configured")]) > 0,
            }
        )
        return items

    def dashboard(self):
        counts = self.counts()
        with connect() as connection:
            with connection.cursor() as cursor:
                recent_operations = _rows(
                    cursor,
                    """
                    SELECT id, type, status, message, created_at, finished_at
                    FROM operation_logs
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
                    FROM operation_logs
                    GROUP BY status
                    ORDER BY status
                    """
                )
                operation_statuses = {row["status"]: int(row["count"]) for row in cursor.fetchall()}
        setup_status = setup.status(include_checks=False)
        return {
            "counts": counts,
            "health": system.health(),
            "setup": setup_status,
            "nodes": nodes,
            "recent_operations": recent_operations,
            "operation_statuses": operation_statuses,
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
                operations = _rows(
                    cursor,
                    """
                    SELECT id, type, status, message, created_at, finished_at
                    FROM operation_logs
                    WHERE type ILIKE %s OR type ILIKE %s OR type ILIKE %s
                    ORDER BY created_at DESC
                    LIMIT 20
                    """,
                    ["%service%", "%deploy%", "%compose%"],
                )
        return {"services": services, "domains": domains, "operations": operations, "counts": self.counts()}

    def images(self):
        with connect() as connection:
            with connection.cursor() as cursor:
                images = _rows(cursor, "SELECT * FROM images ORDER BY created_at DESC LIMIT 80")
        return {"images": images, "integrations": self.integrations(), "counts": self.counts()}

    def domains(self):
        ddns = ddns_model.load()
        certificates = webserver.load().get("certificates", [])
        return {
            "zones": ddns.get("endpoints", []),
            "domains": ddns.get("registrations", []),
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
        return {"commands": specs, "backups": [], "health": system.health()}


Model = InfraCatalog()
