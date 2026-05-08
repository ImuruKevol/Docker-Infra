from pathlib import Path


connect = wiz.model("db/postgres").connect
shared = wiz.model("struct/services_shared")
ServiceError = shared.ServiceError
_row = shared.row


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

    def detail(self, service_id, env=None):
        with connect(env=env) as connection:
            with connection.cursor() as cursor:
                service = self._service_row(cursor, service_id)
                cursor.execute(
                    "SELECT * FROM service_domains WHERE service_id = %s ORDER BY created_at ASC",
                    (service_id,),
                )
                domains = [_row(row) for row in cursor.fetchall()]
                cursor.execute(
                    "SELECT * FROM compose_versions WHERE service_id = %s ORDER BY version DESC, created_at DESC LIMIT 20",
                    (service_id,),
                )
                versions = [_row(row) for row in cursor.fetchall()]
                cursor.execute(
                    """
                    SELECT id, type, status, message, created_at, started_at, finished_at, metadata, requested_payload, result_payload, output
                    FROM operation_logs
                    WHERE requested_payload->>'service_id' = %s
                       OR metadata->>'service_id' = %s
                       OR requested_payload->>'namespace' = %s
                       OR metadata->>'namespace' = %s
                    ORDER BY created_at DESC
                    LIMIT 20
                    """,
                    (service_id, service_id, service.get("namespace"), service.get("namespace")),
                )
                operations = [_row(row) for row in cursor.fetchall()]

        compose_content = ""
        compose_path = Path(service["compose_path"]).expanduser()
        if compose_path.is_file():
            compose_content = compose_path.read_text(encoding="utf-8")
        root = self._service_root(service)
        return {
            "service": service,
            "domains": domains,
            "versions": versions,
            "operations": operations,
            "compose_content": compose_content,
            "file_root": str(root),
        }

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


Model = ServiceRuntimeMixin
