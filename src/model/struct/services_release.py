import datetime
import hashlib
import shutil
from pathlib import Path

from psycopg.types.json import Jsonb


connect = wiz.model("db/postgres").connect
validator = wiz.model("struct/compose_validator")
operations = wiz.model("struct/operations")
shared = wiz.model("struct/services_shared")
ServiceError = shared.ServiceError
_row = shared.row


def _utc_id():
    return datetime.datetime.utcnow().strftime("%Y%m%d_%H%M%S")


def _checksum(content):
    return hashlib.sha256(str(content or "").encode("utf-8")).hexdigest()


def _truthy(value):
    if isinstance(value, bool):
        return value
    return str(value or "").strip().lower() in {"1", "true", "yes", "on"}


class ServiceReleaseMixin:
    def release(self, payload, env=None):
        payload = payload or {}
        service_id = payload.get("service_id")
        if not service_id:
            raise ServiceError(400, "service_id는 필수입니다.", "SERVICE_ID_REQUIRED")

        include_snapshots = _truthy(payload.get("include_snapshots"))
        comment = str(payload.get("comment") or "").strip()

        with connect(env=env) as connection:
            with connection.cursor() as cursor:
                service = self._service_row(cursor, service_id)

        compose_path = Path(service.get("compose_path") or "").expanduser()
        if not compose_path.is_file():
            raise ServiceError(404, "서비스 Compose 파일을 찾을 수 없습니다.", "SERVICE_COMPOSE_NOT_FOUND")

        current_content = compose_path.read_text(encoding="utf-8")
        validation = validator.validate({
            "namespace": service["namespace"],
            "filename": compose_path.name,
            "content": current_content,
        })
        checksum = _checksum(current_content)

        history_id = f"release_{_utc_id()}"
        history_dir = compose_path.parent / ".history" / history_id
        history_dir.mkdir(parents=True, exist_ok=True)
        release_path = history_dir / compose_path.name
        shutil.copy2(compose_path, release_path)

        with connect(env=env) as connection:
            with connection.cursor() as cursor:
                service = self._service_row(cursor, service_id)
                cursor.execute(
                    "SELECT COALESCE(max(version), 0) + 1 AS next_version FROM compose_versions WHERE service_id = %s",
                    (service_id,),
                )
                version_number = int(cursor.fetchone()["next_version"])
                version_metadata = {
                    "source": "manual_release",
                    "history_id": history_id,
                    "include_snapshots": include_snapshots,
                }
                if comment:
                    version_metadata["comment"] = comment
                cursor.execute(
                    """
                    INSERT INTO compose_versions(service_id, version, path, checksum, test_run_id, metadata)
                    VALUES (%s, %s, %s, %s, %s, %s)
                    RETURNING *
                    """,
                    (
                        service_id,
                        version_number,
                        str(release_path),
                        checksum,
                        service.get("test_run_id"),
                        Jsonb(version_metadata),
                    ),
                )
                compose_version = _row(cursor.fetchone())

                metadata = dict(service.get("metadata") or {})
                metadata["last_release"] = {
                    "history_id": history_id,
                    "compose_version_id": compose_version["id"],
                    "compose_version": compose_version["version"],
                    "include_snapshots": include_snapshots,
                    "comment": comment,
                }
                cursor.execute(
                    """
                    UPDATE services
                    SET metadata = %s, updated_at = now()
                    WHERE id = %s
                    RETURNING *
                    """,
                    (Jsonb(metadata), service_id),
                )
                updated_service = _row(cursor.fetchone())

        operation = operations.create(
            "service.compose.release",
            target_type="service",
            target_id=service_id,
            status="succeeded",
            message=(
                f"Compose 버전 {compose_version['version']} 릴리즈"
                + (" · 스냅샷 백업 요청 포함" if include_snapshots else "")
            ),
            requested_payload={
                "service_id": service_id,
                "include_snapshots": include_snapshots,
                "comment": comment,
            },
            result_payload={
                "compose_version": compose_version["version"],
                "compose_version_id": compose_version["id"],
                "include_snapshots": include_snapshots,
                "history_id": history_id,
            },
            metadata={"service_id": service_id, "namespace": updated_service.get("namespace")},
            env=env,
        )

        return {
            "service": updated_service,
            "compose_version": compose_version,
            "operation": operation,
            "validation": validation,
            "paths": {
                "history_dir": str(history_dir),
                "compose_version_path": str(release_path),
            },
        }


Model = ServiceReleaseMixin
