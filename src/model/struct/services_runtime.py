from pathlib import Path

from psycopg.types.json import Jsonb


connect = wiz.model("db/postgres").connect
local_executor = wiz.model("struct/local_executor")
webserver = wiz.model("struct/webserver")
shared = wiz.model("struct/services_shared")
image_backups = wiz.model("struct/service_image_backups")
backup_system = wiz.model("struct/backup_system")
ServiceError = shared.ServiceError
_row = shared.row


def _backup_system_status(env=None):
    try:
        status = backup_system.status(env=env) or {}
    except Exception:
        status = {}
    return {
        "enabled": bool(status.get("enabled")),
        "status": status.get("status") or "disabled",
        "harbor_url": status.get("harbor_url") or "",
    }


class ServiceRuntimeMixin:
    def _service_row(self, cursor, service_id):
        cursor.execute("SELECT * FROM services WHERE id = %s", (service_id,))
        row = cursor.fetchone()
        if row is None:
            raise ServiceError(404, "서비스를 찾을 수 없습니다.", "SERVICE_NOT_FOUND")
        return _row(row)

    def _service_root(self, service):
        compose_path = service.get("compose_path")
        if not compose_path:
            raise ServiceError(409, "서비스 Compose 경로가 없습니다.", "SERVICE_COMPOSE_PATH_MISSING")
        return Path(compose_path).expanduser().resolve().parent

    def _resolve_service_path(self, service, relative_path=""):
        root = self._service_root(service)
        target = (root / str(relative_path or ".")).resolve()
        if target != root and not target.is_relative_to(root):
            raise ServiceError(400, "서비스 디렉토리 밖의 경로에는 접근할 수 없습니다.", "SERVICE_FILE_PATH_INVALID")
        return root, target

    def _managed_nginx_path(self, path):
        target = Path(str(path or "")).expanduser()
        if not target.name.startswith("docker-infra-") or target.suffix != ".conf":
            return None
        available = Path(webserver.nginx_defaults().get("available_site_path") or "/etc/nginx/sites-available").expanduser()
        try:
            resolved = target.resolve()
            available_resolved = available.resolve()
            if resolved != available_resolved and not resolved.is_relative_to(available_resolved):
                return None
        except Exception:
            return None
        return target

    def _nginx_configs(self, service_id, env=None):
        with connect(env=env) as connection:
            with connection.cursor() as cursor:
                self._service_row(cursor, service_id)
                cursor.execute("SELECT * FROM service_domains WHERE service_id = %s ORDER BY domain ASC", (service_id,))
                rows = [_row(row) for row in cursor.fetchall()]
        configs = []
        for row in rows:
            metadata = dict(row.get("metadata") or {})
            config_path = metadata.get("nginx_config_path")
            target = self._managed_nginx_path(config_path)
            content = ""
            readable = False
            if target and target.is_file():
                content = target.read_text(encoding="utf-8")
                readable = True
            configs.append({
                "domain_id": row["id"],
                "domain": row["domain"],
                "path": str(target or config_path or ""),
                "enabled_path": metadata.get("nginx_enabled_path") or "",
                "content": content,
                "readable": readable,
                "editable": bool(target),
                "managed": True,
            })
        return configs

    def _domains(self, cursor, service_id):
        cursor.execute(
            "SELECT * FROM service_domains WHERE service_id = %s ORDER BY created_at ASC",
            (service_id,),
        )
        return [_row(row) for row in cursor.fetchall()]

    def _versions(self, cursor, service_id):
        cursor.execute(
            "SELECT * FROM compose_versions WHERE service_id = %s ORDER BY version DESC, created_at DESC LIMIT 20",
            (service_id,),
        )
        return [_row(row) for row in cursor.fetchall()]

    def _operation_select_columns(self, include_output=True):
        output_column = ", output" if include_output else ""
        return f"id, type, status, message, created_at, started_at, finished_at, metadata, requested_payload, result_payload{output_column}"

    def _operation_rows(self, cursor, where_sql, params, limit, include_output=True):
        cursor.execute(
            f"""
            SELECT {self._operation_select_columns(include_output=include_output)}
            FROM operation_logs
            WHERE {where_sql}
            ORDER BY created_at DESC
            LIMIT %s
            """,
            [*params, limit],
        )
        return [_row(row) for row in cursor.fetchall()]

    def _operations(self, cursor, service_id, namespace, limit=20, include_output=True, allow_legacy=True):
        limit = max(1, min(int(limit or 20), 100))
        rows = self._operation_rows(
            cursor,
            "target_type = 'service' AND target_id = %s",
            [str(service_id)],
            limit,
            include_output=include_output,
        )
        if len(rows) >= limit or not allow_legacy:
            return rows

        # Older operation rows did not always set target_type/target_id. Keep a small
        # compatibility fallback, but avoid it on the common indexed path above.
        seen_ids = {str(row.get("id")) for row in rows if row.get("id")}
        remaining = limit - len(rows)
        where = [
            "(",
            "requested_payload->>'service_id' = %s",
            "OR metadata->>'service_id' = %s",
            "OR requested_payload->>'namespace' = %s",
            "OR metadata->>'namespace' = %s",
            ")",
        ]
        params = [str(service_id), str(service_id), str(namespace or ""), str(namespace or "")]
        if seen_ids:
            where.append("AND id::text <> ALL(%s)")
            params.append(list(seen_ids))
        rows.extend(
            self._operation_rows(
                cursor,
                " ".join(where),
                params,
                remaining,
                include_output=include_output,
            )
        )
        return sorted(rows, key=lambda item: item.get("created_at") or "", reverse=True)[:limit]

    def _compose_content(self, service):
        compose_path = Path(service["compose_path"]).expanduser()
        if compose_path.is_file():
            return compose_path.read_text(encoding="utf-8")
        return ""

    def detail_overview(self, service_id, env=None):
        with connect(env=env) as connection:
            with connection.cursor() as cursor:
                service = self._service_row(cursor, service_id)
                domains = self._domains(cursor, service_id)
                operations = self._operations(
                    cursor,
                    service_id,
                    service.get("namespace"),
                    limit=5,
                    include_output=False,
                    allow_legacy=False,
                )
        try:
            free_certificates = self.service_certificates(domains, env=env)
        except Exception:
            free_certificates = []
        root = self._service_root(service)
        return {
            "service": service,
            "domains": domains,
            "free_certificates": free_certificates,
            "operations": operations,
            "file_root": str(root),
            "runtime_status": (service.get("metadata") or {}).get("runtime_status") or {},
        }

    def detail_logs(self, service_id, env=None):
        with connect(env=env) as connection:
            with connection.cursor() as cursor:
                service = self._service_row(cursor, service_id)
                operations = self._operations(cursor, service_id, service.get("namespace"), limit=20, include_output=True)
        return {"operations": operations}

    def detail_backups(self, service_id, env=None):
        with connect(env=env) as connection:
            with connection.cursor() as cursor:
                self._service_row(cursor, service_id)
        return {"image_backups": image_backups.list_for_service(service_id, env=env)}

    def detail_advanced(self, service_id, env=None):
        with connect(env=env) as connection:
            with connection.cursor() as cursor:
                service = self._service_row(cursor, service_id)
                versions = self._versions(cursor, service_id)
        return {
            "service": service,
            "versions": versions,
            "compose_content": self._compose_content(service),
            "file_root": str(self._service_root(service)),
            "runtime_status": (service.get("metadata") or {}).get("runtime_status") or {},
            "nginx_configs": self._nginx_configs(service_id, env=env),
            "backup_system": _backup_system_status(env=env),
        }

    def detail(self, service_id, env=None):
        payload = self.detail_overview(service_id, env=env)
        payload.update(self.detail_logs(service_id, env=env))
        payload.update(self.detail_backups(service_id, env=env))
        payload.update(self.detail_advanced(service_id, env=env))
        return payload

    def update_nginx_config(self, payload, env=None):
        body = payload or {}
        service_id = body.get("service_id")
        domain_id = body.get("domain_id")
        content = str(body.get("content") or "")
        if not service_id:
            raise ServiceError(400, "service_id는 필수입니다.", "SERVICE_ID_REQUIRED")
        if not domain_id:
            raise ServiceError(400, "domain_id는 필수입니다.", "SERVICE_DOMAIN_ID_REQUIRED")
        with connect(env=env) as connection:
            with connection.cursor() as cursor:
                self._service_row(cursor, service_id)
                cursor.execute("SELECT * FROM service_domains WHERE id = %s AND service_id = %s", (domain_id, service_id))
                domain = cursor.fetchone()
                if domain is None:
                    raise ServiceError(404, "서비스 도메인 설정을 찾을 수 없습니다.", "SERVICE_DOMAIN_NOT_FOUND")
                domain = _row(domain)
        metadata = dict(domain.get("metadata") or {})
        target = self._managed_nginx_path(metadata.get("nginx_config_path"))
        if target is None:
            raise ServiceError(400, "Docker Infra가 관리하는 nginx 설정만 수정할 수 있습니다.", "NGINX_CONFIG_NOT_MANAGED")
        target.parent.mkdir(parents=True, exist_ok=True)
        previous = target.read_text(encoding="utf-8") if target.is_file() else ""
        target.write_text(content, encoding="utf-8")
        configtest = local_executor.run("proxy.nginx.configtest", timeout_seconds=20, env=env)
        if configtest.get("status") != "ok":
            target.write_text(previous, encoding="utf-8")
            raise ServiceError(400, "nginx 설정 검사를 통과하지 못해 이전 내용으로 되돌렸습니다.", "NGINX_CONFIGTEST_FAILED", check=configtest)
        reload_result = local_executor.run("proxy.nginx.reload", timeout_seconds=20, env=env)
        if reload_result.get("status") != "ok":
            target.write_text(previous, encoding="utf-8")
            local_executor.run("proxy.nginx.configtest", timeout_seconds=20, env=env)
            raise ServiceError(400, "nginx reload에 실패해 이전 내용으로 되돌렸습니다.", "NGINX_RELOAD_FAILED", check=reload_result)
        metadata.update({"manual_nginx_config_edited": True, "manual_nginx_config_path": str(target)})
        with connect(env=env) as connection:
            with connection.cursor() as cursor:
                cursor.execute("UPDATE service_domains SET metadata = %s, updated_at = now() WHERE id = %s", (Jsonb(metadata), domain_id))
        return {"nginx_configs": self._nginx_configs(service_id, env=env), "configtest": configtest, "reload": reload_result}

    def browse_files(self, service_id, relative_path="", env=None):
        with connect(env=env) as connection:
            with connection.cursor() as cursor:
                service = self._service_row(cursor, service_id)
        root, target = self._resolve_service_path(service, relative_path)
        if not target.exists():
            raise ServiceError(404, "선택한 경로를 찾을 수 없습니다.", "SERVICE_FILE_PATH_NOT_FOUND")
        if not target.is_dir():
            raise ServiceError(400, "폴더만 열 수 있습니다.", "SERVICE_FILE_PATH_NOT_DIRECTORY")

        items = []
        for child in sorted(target.iterdir(), key=lambda item: (not item.is_dir(), item.name.lower())):
            items.append(
                {
                    "name": child.name,
                    "path": child.relative_to(root).as_posix(),
                    "type": "folder" if child.is_dir() else "file",
                    "size": child.stat().st_size if child.is_file() else 0,
                }
            )

        current = "." if target == root else target.relative_to(root).as_posix()
        parent = None
        if target != root:
            parent = "." if target.parent == root else target.parent.relative_to(root).as_posix()
        return {"path": current, "parent": parent, "items": items}

    def read_file(self, service_id, relative_path, env=None):
        if not relative_path:
            raise ServiceError(400, "파일 경로가 필요합니다.", "SERVICE_FILE_PATH_REQUIRED")
        with connect(env=env) as connection:
            with connection.cursor() as cursor:
                service = self._service_row(cursor, service_id)
        _, target = self._resolve_service_path(service, relative_path)
        if not target.exists() or not target.is_file():
            raise ServiceError(404, "선택한 파일을 찾을 수 없습니다.", "SERVICE_FILE_NOT_FOUND")
        return {"path": relative_path, "content": target.read_text(encoding="utf-8")}

    def refresh_image_records(self, payload, env=None):
        payload = payload or {}
        service_id = payload.get("service_id")
        if not service_id:
            raise ServiceError(400, "service_id는 필수입니다.", "SERVICE_ID_REQUIRED")
        with connect(env=env) as connection:
            with connection.cursor() as cursor:
                service = self._service_row(cursor, service_id)
                cursor.execute("SELECT * FROM compose_versions WHERE service_id = %s ORDER BY version DESC LIMIT 1", (service_id,))
                version = cursor.fetchone()
        compose_path = Path(service["compose_path"]).expanduser()
        if not compose_path.is_file():
            raise ServiceError(404, "서비스 Compose 파일을 찾을 수 없습니다.", "SERVICE_COMPOSE_NOT_FOUND")
        image_backups.record(
            service,
            compose_path.read_text(encoding="utf-8"),
            compose_version_id=str(version["id"]) if version else None,
            source="manual_refresh",
            test_run_id=service.get("test_run_id"),
            metadata={"namespace": service.get("namespace")},
            env=env,
        )
        return self.detail(service_id, env=env)

    def restore_image_backup(self, payload, env=None):
        payload = payload or {}
        service_id = payload.get("service_id")
        backup_id = payload.get("backup_id")
        if not service_id:
            raise ServiceError(400, "service_id는 필수입니다.", "SERVICE_ID_REQUIRED")
        if not backup_id:
            raise ServiceError(400, "backup_id는 필수입니다.", "SERVICE_IMAGE_BACKUP_ID_REQUIRED")
        image_backups.restore(service_id, backup_id, env=env)
        return self.detail(service_id, env=env)

    def backup_service_image(self, payload, env=None):
        payload = payload or {}
        service_id = payload.get("service_id")
        backup_id = payload.get("backup_id")
        if not service_id:
            raise ServiceError(400, "service_id는 필수입니다.", "SERVICE_ID_REQUIRED")
        if not backup_id:
            raise ServiceError(400, "backup_id는 필수입니다.", "SERVICE_IMAGE_BACKUP_ID_REQUIRED")
        image_backups.backup_to_harbor(service_id, backup_id, env=env)
        return self.detail(service_id, env=env)

    def snapshot_service_image(self, payload, env=None):
        payload = payload or {}
        service_id = payload.get("service_id")
        backup_id = payload.get("backup_id")
        if not service_id:
            raise ServiceError(400, "service_id는 필수입니다.", "SERVICE_ID_REQUIRED")
        if not backup_id:
            raise ServiceError(400, "backup_id는 필수입니다.", "SERVICE_IMAGE_BACKUP_ID_REQUIRED")
        image_backups.snapshot_to_harbor(service_id, backup_id, pause=payload.get("pause", True), env=env)
        return self.detail(service_id, env=env)


Model = ServiceRuntimeMixin
