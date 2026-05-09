import datetime
import decimal
import uuid


connect = wiz.model("db/postgres").connect
setup = wiz.model("struct/setup")
system = wiz.model("struct/system")
local_command_catalog = wiz.model("struct/local_command_catalog")
domains_model = wiz.model("struct/domains")
backup_system = wiz.model("struct/backup_system")
metric_history = wiz.model("struct/nodes_metric_history")


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
                    "operations": _count(cursor, "operation_logs"),
                    "cloudflare_zones": _count(cursor, "cloudflare_zones"),
                    "certificates": _count(cursor, "certificates"),
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
        domain_overview = domains_model.load()
        zones = domain_overview.get("zones", [])
        first_zone = zones[0] if zones else {}
        items.append(
            {
                "key": "cloudflare",
                "label": "Cloudflare",
                "enabled": len([zone for zone in zones if zone.get("enabled")]) > 0,
                "primary": first_zone.get("domain", ""),
                "secondary": first_zone.get("zone_id", ""),
                "secret_configured": len([zone for zone in zones if zone.get("secret_configured")]) > 0,
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
                    SELECT
                        n.id,
                        n.name,
                        n.role,
                        n.host,
                        n.status,
                        n.is_local_master,
                        n.updated_at,
                        m.cpu_percent AS latest_cpu_percent,
                        m.memory AS latest_memory,
                        m.storage AS latest_storage,
                        m.containers AS latest_containers,
                        m.reported_at AS latest_reported_at
                    FROM nodes n
                    LEFT JOIN LATERAL (
                        SELECT cpu_percent, memory, storage, containers, reported_at
                        FROM node_metrics
                        WHERE node_id = n.id
                        ORDER BY reported_at DESC, created_at DESC
                        LIMIT 1
                    ) m ON true
                    ORDER BY n.is_local_master DESC, n.created_at DESC
                    LIMIT 6
                    """,
                )
                for node in nodes:
                    node["latest_metric"] = {
                        "cpu_percent": node.pop("latest_cpu_percent", None),
                        "memory": node.pop("latest_memory", None) or {},
                        "storage": node.pop("latest_storage", None) or {},
                        "containers": node.pop("latest_containers", None) or {},
                        "reported_at": node.pop("latest_reported_at", None),
                    }
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
            "node_metric_history": metric_history.dashboard_summary(),
            "node_resource_chart": metric_history.dashboard_chart(),
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
                        d.primary_domain,
                        d.primary_port,
                        COALESCE(v.version_count, 0) AS compose_version_count
                    FROM services s
                    LEFT JOIN (
                        SELECT
                            service_id,
                            count(*) AS domain_count,
                            min(domain) AS primary_domain,
                            min(port) AS primary_port
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
