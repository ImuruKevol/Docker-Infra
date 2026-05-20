import datetime
import shutil
import threading
from pathlib import Path

import yaml
from psycopg.types.json import Jsonb


connect = wiz.model("db/postgres").connect
operations = wiz.model("struct/operations")
image_backups = wiz.model("struct/service_image_backups")
volume_migration = wiz.model("struct/service_volume_migration")
shared = wiz.model("struct/services_shared")
ServiceError = shared.ServiceError
_row = shared.row
_serialize = shared.serialize


def _utc_id():
    return datetime.datetime.utcnow().strftime("%Y%m%d_%H%M%S")


def _truthy(value, default=False):
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    return str(value or "").strip().lower() in {"1", "true", "yes", "on"}


def _node_summary(node):
    node = node or {}
    return {
        "id": str(node.get("id") or ""),
        "name": str(node.get("name") or ""),
        "host": str(node.get("host") or ""),
        "swarm_node_id": str(node.get("swarm_node_id") or ""),
        "is_local_master": bool(node.get("is_local_master")),
    }


def _operation_output(operation_id, message, stream="system", metadata=None, env=None):
    if not operation_id or not message:
        return
    operations.append_output(operation_id, message, stream=stream, metadata=metadata or {}, env=env)


class ServiceMigrationMixin:
    def _migration_target_node(self, node_id, env=None):
        node_id = str(node_id or "").strip()
        if not node_id:
            raise ServiceError(400, "마이그레이션할 대상 서버를 선택해주세요.", "SERVICE_MIGRATION_TARGET_REQUIRED")
        with connect(env=env) as connection:
            with connection.cursor() as cursor:
                cursor.execute("SELECT * FROM nodes WHERE id = %s LIMIT 1", (node_id,))
                row = cursor.fetchone()
        if row is None:
            raise ServiceError(404, "마이그레이션할 대상 서버를 찾을 수 없습니다.", "SERVICE_MIGRATION_TARGET_NOT_FOUND")
        return _row(row)

    def _active_migration_operation(self, service_id, env=None):
        with connect(env=env) as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT id
                    FROM operation_logs
                    WHERE type = 'service.migrate'
                      AND status IN ('pending', 'running')
                      AND target_type = 'service'
                      AND target_id = %s
                    ORDER BY created_at DESC
                    LIMIT 1
                    """,
                    (str(service_id),),
                )
                row = cursor.fetchone()
        if row is None:
            return None
        return operations.detail(row["id"], env=env)

    def migrate_background(self, payload, env=None):
        payload = dict(payload or {})
        service_id = payload.get("service_id")
        if not service_id:
            raise ServiceError(400, "service_id는 필수입니다.", "SERVICE_ID_REQUIRED")

        with connect(env=env) as connection:
            with connection.cursor() as cursor:
                service = self._service_row(cursor, service_id)
        target_node = self._migration_target_node(payload.get("target_node_id"), env=env)
        active = self._active_migration_operation(service_id, env=env)
        if active:
            return {
                "accepted": True,
                "service": service,
                "target_node": _node_summary(target_node),
                "operation": active,
                "deduplicated": True,
            }

        operation = operations.create(
            "service.migrate",
            target_type="service",
            target_id=service_id,
            status="pending",
            message="서비스 마이그레이션을 준비했습니다.",
            requested_payload={
                "service_id": str(service_id),
                "target_node_id": target_node["id"],
                "pause": _truthy(payload.get("pause"), default=True),
            },
            metadata={
                "service_id": str(service_id),
                "namespace": service.get("namespace"),
                "target_node_id": target_node["id"],
                "target_node": _node_summary(target_node),
                "background": True,
            },
            env=env,
        )
        thread = threading.Thread(
            target=self._migration_background_worker,
            args=(payload, operation["id"], env),
            name=f"service-migrate-{operation['id']}",
            daemon=True,
        )
        thread.start()
        return {"accepted": True, "service": service, "target_node": _node_summary(target_node), "operation": operation}

    def _compose_image_service_names(self, compose_path):
        compose_path = Path(compose_path).expanduser()
        if not compose_path.is_file():
            raise ServiceError(404, "서비스 Compose 파일을 찾을 수 없습니다.", "SERVICE_COMPOSE_NOT_FOUND")
        compose = yaml.safe_load(compose_path.read_text(encoding="utf-8") or "{}") or {}
        services = compose.get("services") or {}
        names = [
            str(name)
            for name, item in services.items()
            if isinstance(item, dict) and str(item.get("image") or "").strip()
        ]
        return compose, names

    def _latest_snapshot_refs(self, service_id, compose_services, env=None):
        image_backups.ensure_schema(env=env)
        if not compose_services:
            return {}
        with connect(env=env) as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT *
                    FROM service_image_backups
                    WHERE service_id = %s
                      AND compose_service = ANY(%s)
                      AND source = 'container_snapshot'
                      AND backup_status = 'backup_succeeded'
                      AND backup_ref IS NOT NULL
                    ORDER BY created_at DESC, updated_at DESC
                    """,
                    (service_id, list(compose_services)),
                )
                rows = [_row(row) for row in cursor.fetchall()]
        by_service = {}
        for row in rows:
            service_name = str(row.get("compose_service") or "")
            if service_name and service_name not in by_service:
                by_service[service_name] = row
        return by_service

    def _apply_migration_snapshot_refs(self, service, target_node, operation_id, volume_result=None, env=None):
        compose_path = Path(service.get("compose_path") or "").expanduser()
        compose, compose_services = self._compose_image_service_names(compose_path)
        if not compose_services:
            raise ServiceError(409, "스냅샷으로 옮길 이미지 구성이 없습니다.", "SERVICE_MIGRATION_IMAGE_EMPTY")

        snapshots = self._latest_snapshot_refs(service["id"], compose_services, env=env)
        missing = [name for name in compose_services if name not in snapshots]
        if missing:
            raise ServiceError(
                409,
                "마이그레이션에 사용할 스냅샷을 찾을 수 없는 구성이 있습니다.",
                "SERVICE_MIGRATION_SNAPSHOT_MISSING",
                missing_services=missing,
            )

        history_id = f"migration_{_utc_id()}"
        history_dir = compose_path.parent / ".history" / history_id
        history_dir.mkdir(parents=True, exist_ok=True)
        previous_path = history_dir / f"previous-{compose_path.name}"
        if compose_path.exists():
            shutil.copy2(compose_path, previous_path)

        services = compose.setdefault("services", {})
        applied = []
        for service_name in compose_services:
            snapshot = snapshots[service_name]
            services[service_name]["image"] = snapshot["backup_ref"]
            applied.append({
                "compose_service": service_name,
                "backup_id": snapshot.get("id"),
                "backup_ref": snapshot.get("backup_ref"),
                "source_image_ref": snapshot.get("image_ref"),
            })
        compose_path.write_text(yaml.safe_dump(compose, sort_keys=False, allow_unicode=False), encoding="utf-8")
        applied_path = history_dir / compose_path.name
        shutil.copy2(compose_path, applied_path)

        target_summary = _node_summary(target_node)
        with connect(env=env) as connection:
            with connection.cursor() as cursor:
                current = self._service_row(cursor, service["id"])
                metadata = dict(current.get("metadata") or {})
                previous_policy = dict(current.get("target_node_policy") or {})
                previous_placement = dict(metadata.get("placement") or {})
                previous_node_id = str(previous_policy.get("node_id") or previous_placement.get("node_id") or "").strip()
                policy = {
                    **previous_policy,
                    "mode": previous_policy.get("mode") or "swarm",
                    "replicas": previous_policy.get("replicas") or 1,
                    "placement": "manual",
                    "node_id": target_node["id"],
                    "auto_selected": False,
                }
                metadata["placement"] = {
                    **previous_placement,
                    "mode": "manual",
                    "node_id": target_node["id"],
                    "auto_selected": False,
                    "migration": {
                        "operation_id": operation_id,
                        "target_node": target_summary,
                        "previous_node_id": previous_node_id,
                    },
                }
                metadata["last_migration"] = {
                    "operation_id": operation_id,
                    "history_id": history_id,
                    "target_node": target_summary,
                    "previous_node_id": previous_node_id,
                    "snapshot_count": len(applied),
                    "snapshot_refs": applied,
                    "volume_migration": volume_result or {"status": "skipped", "reason": "not_requested"},
                    "previous_path": str(previous_path) if previous_path.exists() else "",
                    "compose_path": str(applied_path),
                }
                cursor.execute(
                    """
                    UPDATE services
                    SET status = 'draft',
                        target_node_policy = %s,
                        metadata = %s,
                        updated_at = now()
                    WHERE id = %s
                    RETURNING *
                    """,
                    (Jsonb(_serialize(policy)), Jsonb(_serialize(metadata)), service["id"]),
                )
                updated_service = _row(cursor.fetchone())

        _operation_output(
            operation_id,
            f"스냅샷 이미지 {len(applied)}개를 Compose에 반영하고 대상 서버를 {target_summary.get('name') or target_summary.get('host')}로 변경했습니다.",
            metadata={"step": "snapshot compose apply", "target_node": target_summary, "snapshot_refs": applied},
            env=env,
        )
        return {
            "service": updated_service,
            "history_id": history_id,
            "history_dir": str(history_dir),
            "compose_path": str(applied_path),
            "previous_path": str(previous_path) if previous_path.exists() else "",
            "snapshot_refs": applied,
            "target_node": target_summary,
        }

    def _migration_background_worker(self, payload, operation_id, env=None):
        payload = dict(payload or {})
        service_id = payload.get("service_id")
        try:
            operations.transition(
                operation_id,
                "running",
                message="서비스 마이그레이션을 시작했습니다.",
                metadata={"service_id": str(service_id), "background": True},
                env=env,
            )
            target_node = self._migration_target_node(payload.get("target_node_id"), env=env)
            target_summary = _node_summary(target_node)
            _operation_output(
                operation_id,
                f"대상 서버: {target_summary.get('name') or target_summary.get('host') or target_summary.get('id')}",
                metadata={"step": "target node", "target_node": target_summary},
                env=env,
            )
            _operation_output(
                operation_id,
                "실행 중인 컨테이너 스냅샷을 생성합니다.",
                metadata={"step": "snapshot start"},
                env=env,
            )
            snapshot_detail = self.snapshot_service_image(
                {
                    "service_id": service_id,
                    "pause": _truthy(payload.get("pause"), default=True),
                    "source": "service_migration_snapshot",
                    "progress_operation_id": operation_id,
                    "background": False,
                },
                env=env,
            )
            service = snapshot_detail.get("service")
            volume_result = volume_migration.migrate_service_volumes(service, target_node, operation_id=operation_id, env=env)
            apply_result = self._apply_migration_snapshot_refs(service, target_node, operation_id, volume_result=volume_result, env=env)
            deploy_result = self.deploy(
                {
                    "service_id": service_id,
                    "operation_id": operation_id,
                    "force_recreate": True,
                    "ensure_backup_registry": True,
                    "deployment_reason": "service_migration",
                    "runtime_ready_timeout_seconds": payload.get("runtime_ready_timeout_seconds") or 180,
                },
                env=env,
            )
            operation = operations.transition(
                operation_id,
                "succeeded",
                message="서비스 마이그레이션을 완료했습니다.",
                result_payload={
                    "service_id": str(service_id),
                    "target_node": target_summary,
                    "snapshot_refs": apply_result.get("snapshot_refs") or [],
                    "volume_migration": volume_result,
                    "history_id": apply_result.get("history_id"),
                    "deploy_operation": (deploy_result.get("operation") or {}).get("id"),
                },
                env=env,
            )
            return operation
        except Exception as exc:
            message = getattr(exc, "message", str(exc))
            error_code = getattr(exc, "error_code", "SERVICE_MIGRATION_FAILED")
            extra = getattr(exc, "extra", {}) or {}
            _operation_output(
                operation_id,
                message,
                stream="stderr",
                metadata={"step": "failed", "error_code": error_code},
                env=env,
            )
            try:
                operations.transition(
                    operation_id,
                    "failed",
                    message=message,
                    result_payload={"error_code": error_code, **extra},
                    env=env,
                )
            except Exception:
                pass


Model = ServiceMigrationMixin
