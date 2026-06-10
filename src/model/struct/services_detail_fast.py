from pathlib import Path


connect = wiz.model("db/postgres").connect
shared = wiz.model("struct/services_shared")
ServiceError = shared.ServiceError
_row = shared.row


def _backup_system_status(env=None):
    try:
        with connect(env=env) as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    "SELECT enabled, status, harbor_url FROM backup_system_settings WHERE singleton_key = 'default'"
                )
                row = cursor.fetchone()
    except Exception:
        row = None
    if row is None:
        return {"enabled": False, "status": "disabled", "harbor_url": ""}
    item = _row(row)
    return {
        "enabled": bool(item.get("enabled")),
        "status": item.get("status") or "disabled",
        "harbor_url": item.get("harbor_url") or "",
    }


class ServiceDetailFast:
    ServiceError = ServiceError

    def _service_row(self, cursor, service_id):
        cursor.execute("SELECT * FROM services WHERE id = %s", (service_id,))
        row = cursor.fetchone()
        if row is None:
            raise ServiceError(404, "서비스를 찾을 수 없습니다.", "SERVICE_NOT_FOUND")
        return _row(row)

    def _domains(self, cursor, service_id):
        cursor.execute(
            "SELECT * FROM service_domains WHERE service_id = %s ORDER BY created_at ASC",
            (service_id,),
        )
        return [_row(row) for row in cursor.fetchall()]

    def _service_root(self, service):
        compose_path = service.get("compose_path")
        if not compose_path:
            raise ServiceError(409, "서비스 Compose 경로가 없습니다.", "SERVICE_COMPOSE_PATH_MISSING")
        return Path(compose_path).expanduser().parent

    def _runtime_status_payload(self, service):
        return dict((service.get("metadata") or {}).get("runtime_status") or {})

    def _operations(self, cursor, service_id, limit=5):
        cursor.execute(
            """
            SELECT id, type, status, message, created_at, started_at, finished_at, metadata, requested_payload, result_payload
            FROM operation_logs
            WHERE target_type = 'service'
              AND target_id = %s
            ORDER BY created_at DESC
            LIMIT %s
            """,
            (str(service_id), max(1, min(int(limit or 5), 20))),
        )
        return [_row(row) for row in cursor.fetchall()]

    def overview(self, service_id, env=None):
        with connect(env=env) as connection:
            with connection.cursor() as cursor:
                service = self._service_row(cursor, service_id)
                domains = self._domains(cursor, service_id)
                operations = self._operations(cursor, service_id)
        return {
            "service": service,
            "domains": domains,
            "operations": operations,
            "file_root": str(self._service_root(service)),
            "runtime_status": self._runtime_status_payload(service),
        }

    def _certificate_targets(self, domains):
        rows = []
        for row in domains or []:
            domain = str(row.get("domain") or "").strip().lower()
            if not domain:
                continue
            metadata = dict(row.get("metadata") or {})
            requested = row.get("ssl_mode") == "certbot"
            applied = metadata.get("nginx_ssl_mode") == "certbot"
            if not requested and not applied:
                continue
            rows.append({
                "domain_id": str(row.get("id") or ""),
                "domain": domain,
                "requested_ssl_mode": row.get("ssl_mode"),
                "applied_ssl_mode": metadata.get("nginx_ssl_mode"),
                "certificate": None,
                "auto_renewal": {"status": "deferred", "configured": None},
                "manual_renew_enabled": False,
            })
        return rows

    def extras(self, service_id, env=None):
        with connect(env=env) as connection:
            with connection.cursor() as cursor:
                self._service_row(cursor, service_id)
                domains = self._domains(cursor, service_id)
        return {
            "domains": domains,
            "backup_system": _backup_system_status(env=env),
            "free_certificates": self._certificate_targets(domains),
        }


Model = ServiceDetailFast()
