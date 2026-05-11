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

    def _node_metric_rows_for_chart(self, cursor, chart_range):
        params = []
        where = []
        if chart_range.get("start_at") and chart_range.get("end_at"):
            where.append("reported_at >= %s::timestamptz")
            where.append("reported_at <= %s::timestamptz")
            params.extend([chart_range.get("start_at"), chart_range.get("end_at")])
        else:
            where.append("reported_at::date >= %s::date")
            where.append("reported_at::date <= %s::date")
            params.extend([chart_range.get("start_date"), chart_range.get("end_date")])
        cursor.execute(
            f"""
            SELECT
                node_id,
                cpu_percent,
                memory,
                storage,
                containers,
                reported_at,
                metadata
            FROM node_metrics
            WHERE {" AND ".join(where)}
            ORDER BY reported_at DESC, created_at DESC
            LIMIT 10000
            """,
            params,
        )
        return [_serialize(dict(row)) for row in cursor.fetchall()]

    def dashboard(self, start_date=None, end_date=None, start_at=None, end_at=None):
        resource_chart = metric_history.dashboard_chart(start_date=start_date, end_date=end_date, start_at=start_at, end_at=end_at)
        node_resource_charts = []
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
                chart_nodes = _rows(
                    cursor,
                    """
                    SELECT id, name, role, host, status, is_local_master
                    FROM nodes
                    ORDER BY is_local_master DESC, created_at DESC
                    """,
                )
                chart_nodes_by_id = {str(node["id"]): node for node in chart_nodes}
                node_ids = [node["id"] for node in chart_nodes if node.get("id")]
                node_resource_charts = metric_history.dashboard_node_charts(
                    node_ids,
                    start_date=resource_chart.get("start_date"),
                    end_date=resource_chart.get("end_date"),
                    start_at=resource_chart.get("start_at"),
                    end_at=resource_chart.get("end_at"),
                )
                for chart in node_resource_charts:
                    chart["node"] = chart_nodes_by_id.get(str(chart.get("node_id"))) or {}
                cursor.execute(
                    """
                    SELECT status, count(*) AS count
                    FROM operation_logs
                    GROUP BY status
                    ORDER BY status
                    """
                )
                operation_statuses = {row["status"]: int(row["count"]) for row in cursor.fetchall()}
                db_metric_rows = None
                if (not resource_chart.get("rows")) or any(not chart.get("rows") for chart in node_resource_charts):
                    db_metric_rows = self._node_metric_rows_for_chart(cursor, resource_chart)
                if not resource_chart.get("rows") and db_metric_rows:
                    db_resource_chart = metric_history.dashboard_chart_from_metrics(
                        db_metric_rows,
                        start_date=resource_chart.get("start_date"),
                        end_date=resource_chart.get("end_date"),
                        start_at=resource_chart.get("start_at"),
                        end_at=resource_chart.get("end_at"),
                    )
                    if db_resource_chart.get("rows"):
                        resource_chart = db_resource_chart
                if db_metric_rows and node_resource_charts:
                    db_node_charts = metric_history.dashboard_node_charts_from_metrics(
                        node_ids,
                        db_metric_rows,
                        start_date=resource_chart.get("start_date"),
                        end_date=resource_chart.get("end_date"),
                        start_at=resource_chart.get("start_at"),
                        end_at=resource_chart.get("end_at"),
                    )
                    db_node_charts_by_id = {str(chart.get("node_id")): chart for chart in db_node_charts if chart.get("rows")}
                    node_resource_charts = [
                        db_node_charts_by_id.get(str(chart.get("node_id")), chart) if not chart.get("rows") else chart
                        for chart in node_resource_charts
                    ]
                    for chart in node_resource_charts:
                        chart["node"] = chart_nodes_by_id.get(str(chart.get("node_id"))) or chart.get("node") or {}
        setup_status = setup.status(include_checks=False)
        return {
            "counts": counts,
            "health": system.health(),
            "setup": setup_status,
            "nodes": nodes,
            "node_metric_history": metric_history.dashboard_summary(),
            "node_resource_chart": resource_chart,
            "node_resource_charts": node_resource_charts,
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
