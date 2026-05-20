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
webserver = wiz.model("struct/webserver")


OPERATION_LABELS = {
    "service.deploy": "서비스 배포",
    "service.rollback": "서비스 되돌리기",
    "service.delete": "서비스 삭제",
    "service.action": "서비스 제어",
    "service.image.backup": "서비스 이미지 백업",
    "service.image.snapshot": "컨테이너 스냅샷",
    "macro.run": "매크로 실행",
    "container.action": "컨테이너 제어",
    "domain.zone.save": "도메인 저장",
    "domain.zone.delete": "도메인 삭제",
    "domain.record.ensure_service": "서비스 DNS 적용",
    "domain.record.delete_service": "서비스 DNS 삭제",
    "backup.harbor.enable": "백업 시스템 시작",
    "backup.harbor.stop": "백업 시스템 중지",
    "backup.harbor.disable": "백업 시스템 비활성화",
    "backup.harbor.restart": "백업 시스템 재시작",
    "backup.harbor.reset": "백업 시스템 초기화",
    "node.monitoring.collector.ensure": "모니터링 구성",
    "node.monitoring.collector.repair": "모니터링 복구",
}

ACTION_LABELS = {
    "start": "시작",
    "stop": "중지",
    "restart": "재시작",
    "delete": "삭제",
}


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


def _dict(value):
    return dict(value) if isinstance(value, dict) else {}


def _int(value, fallback=0):
    try:
        return int(value)
    except Exception:
        return fallback


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

    def backup_status(self):
        backup = backup_system.status()
        return {
            "enabled": bool(backup.get("enabled")),
            "status": backup.get("status") or "disabled",
            "harbor_url": backup.get("harbor_url") or "",
            "secret_configured": bool(backup.get("secret_configured")),
            "installed": bool(backup.get("installed")),
        }

    def domain_usage(self):
        with connect() as connection:
            with connection.cursor() as cursor:
                registered_domain_count = _count(cursor, "cloudflare_zones")
                registered_domains = _rows(
                    cursor,
                    """
                    SELECT
                        z.id::text AS id,
                        z.domain,
                        z.enabled,
                        z.usable_for_service,
                        z.last_sync_status,
                        z.last_sync_at,
                        z.record_count,
                        COALESCE(links.service_count, 0) AS service_count,
                        COALESCE(links.binding_count, 0) AS binding_count,
                        COALESCE(links.host_count, 0) AS host_count,
                        links.latest_linked_at,
                        COALESCE(links.service_names, ARRAY[]::text[]) AS service_names
                    FROM cloudflare_zones z
                    LEFT JOIN LATERAL (
                        SELECT
                            count(DISTINCT sd.service_id) AS service_count,
                            count(sd.id) AS binding_count,
                            count(DISTINCT sd.domain) AS host_count,
                            max(sd.updated_at) AS latest_linked_at,
                            array_remove(array_agg(DISTINCT COALESCE(s.name, s.namespace)), NULL) AS service_names
                        FROM service_domains sd
                        LEFT JOIN services s ON s.id = sd.service_id
                        WHERE lower(sd.domain) = lower(z.domain)
                           OR lower(sd.domain) LIKE lower('%%.' || z.domain)
                    ) links ON true
                    ORDER BY z.domain ASC
                    LIMIT 80
                    """,
                )
                if registered_domain_count > 0 and not registered_domains:
                    registered_domains = _rows(
                        cursor,
                        """
                        SELECT
                            z.id::text AS id,
                            z.domain,
                            z.enabled,
                            z.usable_for_service,
                            z.last_sync_status,
                            z.last_sync_at,
                            z.record_count,
                            0 AS service_count,
                            0 AS binding_count,
                            0 AS host_count,
                            NULL AS latest_linked_at,
                            ARRAY[]::text[] AS service_names
                        FROM cloudflare_zones z
                        ORDER BY z.domain ASC
                        LIMIT 80
                        """,
                    )
                cursor.execute(
                    """
                    SELECT count(*) AS count
                    FROM cloudflare_zones z
                    WHERE EXISTS (
                        SELECT 1
                        FROM service_domains sd
                        WHERE lower(sd.domain) = lower(z.domain)
                           OR lower(sd.domain) LIKE lower('%%.' || z.domain)
                    )
                    """
                )
                linked_domain_count = int(cursor.fetchone()["count"])
                cursor.execute(
                    """
                    SELECT count(DISTINCT sd.service_id) AS count
                    FROM service_domains sd
                    """
                )
                linked_service_count = int(cursor.fetchone()["count"])
                cursor.execute(
                    """
                    SELECT count(DISTINCT sd.domain) AS count
                    FROM service_domains sd
                    """
                )
                service_domain_count = int(cursor.fetchone()["count"])
                unmatched_service_domains = _rows(
                    cursor,
                    """
                    SELECT
                        min(sd.id::text) AS id,
                        sd.domain,
                        true AS enabled,
                        true AS usable_for_service,
                        'registered' AS last_sync_status,
                        max(sd.updated_at) AS last_sync_at,
                        0 AS record_count,
                        count(DISTINCT sd.service_id) AS service_count,
                        count(sd.id) AS binding_count,
                        count(DISTINCT sd.domain) AS host_count,
                        max(sd.updated_at) AS latest_linked_at,
                        array_remove(array_agg(DISTINCT COALESCE(s.name, s.namespace)), NULL) AS service_names
                    FROM service_domains sd
                    LEFT JOIN services s ON s.id = sd.service_id
                    WHERE NOT EXISTS (
                        SELECT 1
                        FROM cloudflare_zones z
                        WHERE lower(sd.domain) = lower(z.domain)
                           OR lower(sd.domain) LIKE lower('%%.' || z.domain)
                    )
                    GROUP BY sd.domain
                    ORDER BY sd.domain ASC
                    LIMIT 80
                    """,
                )

        domains = [*registered_domains, *unmatched_service_domains]
        for row in domains:
            row["service_count"] = int(row.get("service_count") or 0)
            row["binding_count"] = int(row.get("binding_count") or 0)
            row["host_count"] = int(row.get("host_count") or 0)
            row["record_count"] = int(row.get("record_count") or 0)
            row["service_names"] = [name for name in (row.get("service_names") or []) if name]

        return {
            "domains": domains,
            "summary": {
                "domain_count": len(domains),
                "linked_service_count": linked_service_count,
                "used_domain_count": len([row for row in domains if int(row.get("service_count") or 0) > 0]),
                "unregistered_domain_count": 0,
            },
        }

    def _operation_filter_parts(self, filters=None):
        filters = filters or {}
        clauses = []
        params = []
        status = str(filters.get("status") or "").strip()
        operation_type = str(filters.get("type") or "").strip()
        target_type = str(filters.get("target_type") or "").strip()
        query = str(filters.get("query") or "").strip()
        operation_id = str(filters.get("id") or "").strip()
        if operation_id:
            clauses.append("op.id::text = %s")
            params.append(operation_id)
        if status:
            clauses.append("op.status = %s")
            params.append(status)
        if operation_type:
            clauses.append("op.type = %s")
            params.append(operation_type)
        if target_type:
            clauses.append("op.target_type = %s")
            params.append(target_type)
        if query:
            needle = f"%{query}%"
            clauses.append(
                """
                (
                    op.type ILIKE %s
                    OR op.message ILIKE %s
                    OR op.target_id ILIKE %s
                    OR s.name ILIKE %s
                    OR s.namespace ILIKE %s
                    OR target_node.name ILIKE %s
                    OR target_node.host ILIKE %s
                    OR payload_node.name ILIKE %s
                    OR payload_node.host ILIKE %s
                    OR metadata_node.name ILIKE %s
                    OR metadata_node.host ILIKE %s
                )
                """
            )
            params.extend([needle] * 11)
        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        return where, params

    def _operation_from_clause(self):
        return """
            FROM operation_logs op
            LEFT JOIN services s ON s.id::text = NULLIF(COALESCE(
                CASE WHEN op.target_type = 'service' THEN op.target_id ELSE NULL END,
                op.metadata->>'service_id',
                op.requested_payload->>'service_id',
                op.result_payload->>'service_id'
            ), '')
            LEFT JOIN nodes target_node ON op.target_type = 'node' AND target_node.id::text = op.target_id
            LEFT JOIN nodes payload_node ON payload_node.id::text = NULLIF(op.requested_payload->>'node_id', '')
            LEFT JOIN nodes metadata_node ON metadata_node.id::text = NULLIF(COALESCE(op.metadata->>'node_id', op.metadata->>'macro_node_id'), '')
        """

    def _operation_count(self, cursor, filters=None):
        where, params = self._operation_filter_parts(filters)
        cursor.execute(
            f"""
            SELECT count(*) AS count
            {self._operation_from_clause()}
            {where}
            """,
            params,
        )
        return int(cursor.fetchone()["count"])

    def _operation_rows(self, cursor, filters=None, limit=80, offset=0, include_output=False):
        where, params = self._operation_filter_parts(filters)
        output_column = "op.output," if include_output else ""
        cursor.execute(
            f"""
            SELECT
                op.id,
                op.type,
                op.target_type,
                op.target_id,
                op.status,
                op.message,
                op.requested_payload,
                op.result_payload,
                op.metadata,
                {output_column}
                op.test_run_id,
                op.started_at,
                op.finished_at,
                op.created_at,
                op.updated_at,
                jsonb_array_length(COALESCE(op.output, '[]'::jsonb)) AS output_count,
                s.name AS service_name,
                s.namespace AS service_namespace,
                s.status AS service_status,
                COALESCE(target_node.name, payload_node.name, metadata_node.name) AS node_name,
                COALESCE(target_node.host, payload_node.host, metadata_node.host) AS node_host,
                output_node.node AS output_node
            {self._operation_from_clause()}
            LEFT JOIN LATERAL (
                SELECT item->'metadata'->'node' AS node
                FROM jsonb_array_elements(COALESCE(op.output, '[]'::jsonb)) WITH ORDINALITY AS out(item, ord)
                WHERE item->'metadata' ? 'node'
                ORDER BY ord DESC
                LIMIT 1
            ) output_node ON true
            {where}
            ORDER BY op.created_at DESC
            LIMIT %s
            OFFSET %s
            """,
            [*params, max(1, min(int(limit or 80), 200)), max(0, int(offset or 0))],
        )
        return [self._normalize_operation(_serialize(dict(row))) for row in cursor.fetchall()]

    def _operation_server(self, operation):
        metadata = _dict(operation.get("metadata"))
        result = _dict(operation.get("result_payload"))
        output_node = _dict(operation.get("output_node"))
        name = (
            output_node.get("name")
            or metadata.get("node_name")
            or result.get("node_name")
            or operation.get("node_name")
        )
        host = (
            output_node.get("host")
            or metadata.get("node_host")
            or result.get("node_host")
            or operation.get("node_host")
        )
        if not name and not host and operation.get("target_type") == "nodes":
            return {"name": "전체 서버", "host": "", "label": "전체 서버"}
        if not name and not host and operation.get("target_type") == "backup_system":
            return {"name": "로컬 마스터", "host": "", "label": "로컬 마스터"}
        if not name and not host:
            return {"name": "", "host": "", "label": "-"}
        label = name or host
        if name and host and name != host:
            label = f"{name} · {host}"
        return {"name": name or "", "host": host or "", "label": label}

    def _operation_target_label(self, operation, server):
        if operation.get("service_name") or operation.get("service_namespace"):
            name = operation.get("service_name") or operation.get("service_namespace")
            namespace = operation.get("service_namespace")
            return f"{name} · {namespace}" if namespace and namespace != name else name
        if operation.get("target_type") == "node":
            return server.get("label") or "서버"
        if operation.get("target_type") == "backup_system":
            return "서비스 백업 시스템"
        if operation.get("target_type") == "domain":
            return operation.get("target_id") or "도메인"
        target_type = operation.get("target_type") or ""
        target_id = operation.get("target_id") or ""
        if target_type and target_id:
            return f"{target_type} · {target_id}"
        return target_type or target_id or "-"

    def _operation_action_text(self, operation, target_label):
        operation_type = operation.get("type") or ""
        label = OPERATION_LABELS.get(operation_type) or operation_type or "작업"
        metadata = _dict(operation.get("metadata"))
        request = _dict(operation.get("requested_payload"))
        result = _dict(operation.get("result_payload"))
        if operation_type == "macro.run":
            name = metadata.get("macro_name") or result.get("macro_name") or request.get("macro_id") or "-"
            return f"매크로 실행: {name}"
        if operation_type == "service.deploy":
            return f"서비스 배포: {target_label}"
        if operation_type == "service.action":
            action = ACTION_LABELS.get(str(request.get("action") or ""), request.get("action") or "제어")
            service = request.get("service_namespace") or target_label
            return f"서비스 {action}: {service}"
        if operation_type == "container.action":
            action = ACTION_LABELS.get(str(request.get("action") or ""), request.get("action") or "제어")
            container_id = str(request.get("container_id") or "")
            return f"컨테이너 {action}: {container_id[:12] or '-'}"
        if operation_type.startswith("backup.harbor."):
            return label
        if operation_type.startswith("domain."):
            domain = request.get("domain") or result.get("domain") or target_label
            return f"{label}: {domain}"
        if operation.get("message"):
            return operation["message"]
        return f"{label}: {target_label}" if target_label != "-" else label

    def _normalize_operation(self, operation):
        server = self._operation_server(operation)
        target_label = self._operation_target_label(operation, server)
        operation["operation_label"] = OPERATION_LABELS.get(operation.get("type")) or operation.get("type") or "-"
        operation["server"] = server
        operation["target_label"] = target_label
        operation["action_text"] = self._operation_action_text(operation, target_label)
        operation["output_count"] = int(operation.get("output_count") or 0)
        return operation

    def operation_logs(self, filters=None, limit=80, page=1):
        try:
            limit = max(1, min(int(limit or 80), 200))
        except Exception:
            limit = 80
        try:
            page = max(1, int(page or 1))
        except Exception:
            page = 1
        with connect() as connection:
            with connection.cursor() as cursor:
                total = self._operation_count(cursor, filters=filters)
                total_pages = max(1, (total + limit - 1) // limit)
                current = min(page, total_pages)
                offset = (current - 1) * limit
                operations = self._operation_rows(cursor, filters=filters, limit=limit, offset=offset)
                cursor.execute("SELECT status, count(*) AS count FROM operation_logs GROUP BY status ORDER BY status")
                status_counts = {row["status"]: int(row["count"]) for row in cursor.fetchall()}
        pagination = {
            "current": current,
            "start": ((current - 1) // 10) * 10 + 1,
            "end": total_pages,
            "total": total,
            "limit": limit,
        }
        return {
            "operations": operations,
            "status_counts": status_counts,
            "pagination": pagination,
            "total": total,
            "page": current,
            "pages": total_pages,
            "page_size": limit,
        }

    def operation_detail(self, operation_id):
        if not operation_id:
            raise ValueError("operation_id is required")
        with connect() as connection:
            with connection.cursor() as cursor:
                rows = self._operation_rows(cursor, filters={"id": operation_id}, limit=1, include_output=True)
        if not rows:
            raise KeyError(operation_id)
        return rows[0]

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

    def dashboard_status(self):
        return {
            "counts": self.counts(),
            "health": system.health(),
            "setup": setup.status(include_checks=False),
            "backup_system": self.backup_status(),
        }

    def dashboard_nodes(self):
        with connect() as connection:
            with connection.cursor() as cursor:
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
        return {"nodes": nodes, "node_metric_history": metric_history.dashboard_summary()}

    def _dashboard_service_warning(self, service):
        runtime = _dict(service.get("runtime_status"))
        containers = _dict(_dict(runtime.get("containers")).get("summary"))
        health = _dict(_dict(runtime.get("containers")).get("health"))
        stack = _dict(_dict(runtime.get("stack")).get("summary"))
        status = str(service.get("status") or "").lower()

        container_total = _int(containers.get("total"))
        container_running = _int(containers.get("running"))
        stack_desired = _int(stack.get("desired"))
        stack_running = _int(stack.get("running"))

        if _int(health.get("unhealthy")) > 0:
            return True
        if _int(stack.get("task_errors")) > 0:
            return True
        if stack_desired > 0 and stack_running < stack_desired:
            return True
        if container_total > 0 and container_running < container_total:
            return True
        return status in {"failed", "canceled", "error"}

    def dashboard_services(self):
        with connect() as connection:
            with connection.cursor() as cursor:
                services = _rows(
                    cursor,
                    """
                    SELECT
                        s.id::text AS id,
                        s.namespace,
                        s.name,
                        s.status,
                        s.stack_name,
                        s.metadata->'runtime_status' AS runtime_status,
                        s.created_at,
                        s.updated_at,
                        COALESCE(d.domain_count, 0) AS domain_count,
                        d.primary_domain,
                        COALESCE(d.domains, ARRAY[]::text[]) AS domains,
                        COALESCE(v.version_count, 0) AS compose_version_count
                    FROM services s
                    LEFT JOIN LATERAL (
                        SELECT
                            count(*) AS domain_count,
                            min(domain) AS primary_domain,
                            array_remove(array_agg(domain ORDER BY domain), NULL) AS domains
                        FROM service_domains
                        WHERE service_id = s.id
                    ) d ON true
                    LEFT JOIN LATERAL (
                        SELECT count(*) AS version_count
                        FROM compose_versions
                        WHERE service_id = s.id
                    ) v ON true
                    ORDER BY
                        CASE WHEN s.status IN ('failed', 'canceled', 'error') THEN 0 ELSE 1 END,
                        s.updated_at DESC,
                        s.created_at DESC
                    LIMIT 6
                    """,
                )
                cursor.execute(
                    """
                    SELECT status, count(*) AS count
                    FROM services
                    GROUP BY status
                    ORDER BY status
                    """
                )
                status_counts = {row["status"]: int(row["count"]) for row in cursor.fetchall()}
                warning_rows = _rows(
                    cursor,
                    """
                    SELECT
                        status,
                        metadata->'runtime_status' AS runtime_status
                    FROM services
                    """,
                )

        for service in services:
            service["runtime_status"] = service.get("runtime_status") or {}
            service["domain_count"] = _int(service.get("domain_count"))
            service["compose_version_count"] = _int(service.get("compose_version_count"))
            service["domains"] = [domain for domain in (service.get("domains") or []) if domain]
            service["needs_attention"] = self._dashboard_service_warning(service)
        warning_count = len([
            row
            for row in warning_rows
            if self._dashboard_service_warning({"status": row.get("status"), "runtime_status": row.get("runtime_status") or {}})
        ])

        return {
            "service_usage": {
                "services": services,
                "summary": {
                    "service_count": sum(status_counts.values()),
                    "warning_count": warning_count,
                    "status_counts": status_counts,
                },
            }
        }

    def dashboard_operations(self):
        with connect() as connection:
            with connection.cursor() as cursor:
                recent_operations = self._operation_rows(cursor, limit=6)
                cursor.execute(
                    """
                    SELECT status, count(*) AS count
                    FROM operation_logs
                    GROUP BY status
                    ORDER BY status
                    """
                )
                operation_statuses = {row["status"]: int(row["count"]) for row in cursor.fetchall()}
        return {"recent_operations": recent_operations, "operation_statuses": operation_statuses}

    def dashboard_domains(self):
        return {"domain_usage": self.domain_usage()}

    def dashboard_resources(self, start_date=None, end_date=None, start_at=None, end_at=None):
        resource_chart = metric_history.dashboard_chart(start_date=start_date, end_date=end_date, start_at=start_at, end_at=end_at)
        node_resource_charts = []
        with connect() as connection:
            with connection.cursor() as cursor:
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
                db_metric_rows = self._node_metric_rows_for_chart(cursor, resource_chart)
                if db_metric_rows:
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
                        db_node_charts_by_id.get(str(chart.get("node_id")), chart)
                        for chart in node_resource_charts
                    ]
                    for chart in node_resource_charts:
                        chart["node"] = chart_nodes_by_id.get(str(chart.get("node_id"))) or chart.get("node") or {}
        return {
            "node_metric_history": metric_history.dashboard_summary(),
            "node_resource_chart": resource_chart,
            "node_resource_charts": node_resource_charts,
        }

    def dashboard(self, start_date=None, end_date=None, start_at=None, end_at=None):
        resource_chart = metric_history.dashboard_chart(start_date=start_date, end_date=end_date, start_at=start_at, end_at=end_at)
        node_resource_charts = []
        counts = self.counts()
        with connect() as connection:
            with connection.cursor() as cursor:
                recent_operations = self._operation_rows(cursor, limit=6)
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
                db_metric_rows = self._node_metric_rows_for_chart(cursor, resource_chart)
                if db_metric_rows:
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
                        db_node_charts_by_id.get(str(chart.get("node_id")), chart)
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
            "backup_system": self.backup_status(),
            "domain_usage": self.domain_usage(),
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
                    FROM (
                        SELECT *
                        FROM services
                        ORDER BY created_at DESC
                        LIMIT 80
                    ) s
                    LEFT JOIN LATERAL (
                        SELECT
                            count(*) AS domain_count,
                            min(domain) AS primary_domain,
                            min(port) AS primary_port
                        FROM service_domains
                        WHERE service_id = s.id
                    ) d ON true
                    LEFT JOIN LATERAL (
                        SELECT count(*) AS version_count
                        FROM compose_versions
                        WHERE service_id = s.id
                    ) v ON true
                    ORDER BY s.created_at DESC
                    """,
                )
        return {"services": services}

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
                certificates = webserver.load().get("certificates", [])
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
        return {"commands": specs, "backups": [], "health": system.health()}


Model = InfraCatalog()
