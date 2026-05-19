import datetime
import shutil
from pathlib import Path

import yaml
from psycopg.types.json import Jsonb


connect = wiz.model("db/postgres").connect
operations = wiz.model("struct/operations")
runner = wiz.model("struct/service_image_backup_runner")
snapshot_runner = wiz.model("struct/service_image_snapshot_runner")
shared = wiz.model("struct/services_shared")
ServiceError = shared.ServiceError
_row = shared.row


def _utc_id():
    return datetime.datetime.utcnow().strftime("%Y%m%d_%H%M%S")


class ServiceImageBackupActions:
    def restore(self, service_id, backup_id, env=None):
        self.ensure_schema(env=env)
        with connect(env=env) as connection:
            with connection.cursor() as cursor:
                cursor.execute("SELECT * FROM services WHERE id = %s", (service_id,))
                service = cursor.fetchone()
                if service is None:
                    raise ServiceError(404, "서비스를 찾을 수 없습니다.", "SERVICE_NOT_FOUND")
                service = _row(service)
                cursor.execute("SELECT * FROM service_image_backups WHERE id = %s AND service_id = %s", (backup_id, service_id))
                backup = cursor.fetchone()
                if backup is None:
                    raise ServiceError(404, "이미지 이력을 찾을 수 없습니다.", "SERVICE_IMAGE_BACKUP_NOT_FOUND")
                backup = _row(backup)

        compose_path = Path(service["compose_path"]).expanduser()
        if not compose_path.is_file():
            raise ServiceError(404, "서비스 Compose 파일을 찾을 수 없습니다.", "SERVICE_COMPOSE_NOT_FOUND")
        compose = yaml.safe_load(compose_path.read_text(encoding="utf-8")) or {}
        compose_service = backup["compose_service"]
        if compose_service not in (compose.get("services") or {}):
            raise ServiceError(409, "Compose에서 대상 서비스를 찾을 수 없습니다.", "SERVICE_COMPOSE_TARGET_NOT_FOUND")

        target_image = backup.get("backup_ref") or backup["image_ref"]
        compose["services"][compose_service]["image"] = target_image
        content = yaml.safe_dump(compose, sort_keys=False, allow_unicode=False)
        history_dir = compose_path.parent / ".history" / f"restore_{_utc_id()}"
        history_dir.mkdir(parents=True, exist_ok=True)
        shutil.copy2(compose_path, history_dir / compose_path.name)
        compose_path.write_text(content, encoding="utf-8")
        restored_path = history_dir / f"restored_{compose_path.name}"
        shutil.copy2(compose_path, restored_path)

        with connect(env=env) as connection:
            with connection.cursor() as cursor:
                cursor.execute("UPDATE services SET updated_at = now(), status = 'draft' WHERE id = %s RETURNING *", (service_id,))
                restored_service = _row(cursor.fetchone())

        operation = operations.create(
            "service.image.restore",
            target_type="service",
            target_id=service_id,
            status="succeeded",
            message="서비스 Compose 이미지 복원",
            requested_payload={"service_id": service_id, "backup_id": backup_id},
            result_payload={"target_image": target_image, "history_path": str(restored_path)},
            metadata={"service_id": service_id, "namespace": restored_service.get("namespace")},
            env=env,
        )
        return {"service": restored_service, "operation": operation, "target_image": target_image, "history_path": str(restored_path)}

    def backup_to_harbor(self, service_id, backup_id, env=None):
        service, backup = self._backup_target(service_id, backup_id, env=env)
        deduplicated = self._deduplicate_by_digest(backup, env=env)
        if deduplicated:
            return deduplicated
        try:
            result = runner.execute(service, backup, env=env)
            return self._mark_backup_succeeded(backup_id, result["backup_ref"], result["operation"], env=env)
        except ServiceError as exc:
            self._mark_backup_failed(backup_id, exc.message, env=env)
            raise

    def snapshot_to_harbor(self, service_id, backup_id, pause=True, env=None):
        service, backup = self._fetch_backup_target(service_id, backup_id, env=env)
        try:
            result = snapshot_runner.execute(service, backup, pause=pause, env=env)
            image_backup = self.record_snapshot(service, backup, result, env=env)
            return {"image_backup": image_backup, "operation": result["operation"], "container": result["container"]}
        except ServiceError as exc:
            raise

    def _backup_target(self, service_id, backup_id, env=None):
        self.ensure_schema(env=env)
        with connect(env=env) as connection:
            with connection.cursor() as cursor:
                cursor.execute("SELECT * FROM services WHERE id = %s", (service_id,))
                service = cursor.fetchone()
                if service is None:
                    raise ServiceError(404, "서비스를 찾을 수 없습니다.", "SERVICE_NOT_FOUND")
                cursor.execute("SELECT * FROM service_image_backups WHERE id = %s AND service_id = %s", (backup_id, service_id))
                backup = cursor.fetchone()
                if backup is None:
                    raise ServiceError(404, "이미지 이력을 찾을 수 없습니다.", "SERVICE_IMAGE_BACKUP_NOT_FOUND")
                cursor.execute("UPDATE service_image_backups SET backup_status = 'backup_pending', backup_error = NULL WHERE id = %s", (backup_id,))
                return _row(service), _row(backup)

    def _fetch_backup_target(self, service_id, backup_id, env=None):
        self.ensure_schema(env=env)
        with connect(env=env) as connection:
            with connection.cursor() as cursor:
                cursor.execute("SELECT * FROM services WHERE id = %s", (service_id,))
                service = cursor.fetchone()
                if service is None:
                    raise ServiceError(404, "서비스를 찾을 수 없습니다.", "SERVICE_NOT_FOUND")
                cursor.execute("SELECT * FROM service_image_backups WHERE id = %s AND service_id = %s", (backup_id, service_id))
                backup = cursor.fetchone()
                if backup is None:
                    raise ServiceError(404, "이미지 이력을 찾을 수 없습니다.", "SERVICE_IMAGE_BACKUP_NOT_FOUND")
                return _row(service), _row(backup)

    def _deduplicate_by_digest(self, backup, env=None):
        if not backup.get("digest"):
            return None
        with connect(env=env) as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT * FROM service_image_backups
                    WHERE digest = %s AND backup_status = 'backup_succeeded' AND backup_ref IS NOT NULL
                    ORDER BY created_at DESC LIMIT 1
                    """,
                    (backup["digest"],),
                )
                existing = cursor.fetchone()
                if existing is None:
                    return None
                existing = _row(existing)
                cursor.execute(
                    """
                    UPDATE service_image_backups
                    SET backup_ref = %s, backup_status = 'backup_succeeded', backup_error = NULL, metadata = metadata || %s::jsonb
                    WHERE id = %s RETURNING *
                    """,
                    (existing["backup_ref"], Jsonb({"deduplicated_from": existing["id"]}), backup["id"]),
                )
                return {"image_backup": _row(cursor.fetchone()), "operation": None}

    def _mark_backup_succeeded(self, backup_id, backup_ref, operation, env=None):
        with connect(env=env) as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    "UPDATE service_image_backups SET backup_ref = %s, backup_status = 'backup_succeeded', backup_error = NULL WHERE id = %s RETURNING *",
                    (backup_ref, backup_id),
                )
                return {"image_backup": _row(cursor.fetchone()), "operation": operation}

    def _mark_backup_failed(self, backup_id, message, env=None):
        with connect(env=env) as connection:
            with connection.cursor() as cursor:
                cursor.execute("UPDATE service_image_backups SET backup_status = 'backup_failed', backup_error = %s WHERE id = %s", (message, backup_id))


Model = ServiceImageBackupActions
