import calendar
import datetime
import threading


connect = wiz.model("db/postgres").connect
backup_system = wiz.model("struct/backup_system")
image_backups = wiz.model("struct/service_image_backups")
operations = wiz.model("struct/operations")
shared = wiz.model("struct/services_shared")
ServiceError = shared.ServiceError
_row = shared.row


def _parse_time(value):
    if not value:
        return None
    try:
        parsed = datetime.datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=datetime.datetime.now().astimezone().tzinfo)
    return parsed.astimezone()


def _as_bool(value, default=False):
    if value is None:
        return bool(default)
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"1", "true", "yes", "y", "on"}


def _is_service_error_like(exc):
    return all(hasattr(exc, key) for key in ("status_code", "message", "error_code"))


def _failure_detail(exc):
    return {
        "message": getattr(exc, "message", str(exc)),
        "error_code": getattr(exc, "error_code", "SERVICE_IMAGE_BACKUP_FAILED"),
        **(getattr(exc, "extra", {}) or {}),
    }


def _scheduled_at(policy, now):
    try:
        hour, minute = str(policy.get("schedule_time") or "02:00").split(":", 1)
        hour = int(hour)
        minute = int(minute)
        if hour < 0 or hour > 23 or minute < 0 or minute > 59:
            raise ValueError("invalid schedule time")
    except (TypeError, ValueError):
        hour, minute = 2, 0
    schedule_type = str(policy.get("schedule_type") or "weekly")
    if schedule_type == "monthly":
        try:
            requested_day = int(policy.get("schedule_month_day") or 1)
        except (TypeError, ValueError):
            requested_day = 1
        day = min(max(1, requested_day), calendar.monthrange(now.year, now.month)[1])
        return now.replace(day=day, hour=hour, minute=minute, second=0, microsecond=0)
    try:
        weekday = int(policy.get("schedule_weekday") or 0)
    except (TypeError, ValueError):
        weekday = 0
    days_since = (now.weekday() - weekday) % 7
    scheduled_date = now.date() - datetime.timedelta(days=days_since)
    return datetime.datetime.combine(scheduled_date, datetime.time(hour, minute), tzinfo=now.tzinfo)


class ServiceImageBackupScheduler:
    ServiceError = ServiceError

    def _append_progress(self, operation_id, message, stream="system", metadata=None, env=None):
        if not operation_id or not message:
            return
        operations.append_output(operation_id, message if message.endswith("\n") else f"{message}\n", stream=stream, metadata=metadata or {}, env=env)

    def _finish_skipped(self, operation, result, env=None):
        if operation:
            self._append_progress(operation["id"], result.get("message") or "처리할 백업이 없습니다.", metadata={"step": "skip"}, env=env)
            operation = operations.transition(operation["id"], "succeeded", message=result.get("message"), result_payload=result, env=env)
            result["operation"] = operation
        return result

    def _skip_reason(self, policy, force=False):
        if force:
            return None
        if not policy.get("enabled"):
            return "자동 백업이 꺼져 있습니다."
        now = datetime.datetime.now().astimezone()
        scheduled_at = _scheduled_at(policy, now)
        if now.date() != scheduled_at.date():
            return "오늘은 자동 백업 예약 실행일이 아닙니다."
        if now < scheduled_at:
            return "자동 백업 예약 시간이 아직 지나지 않았습니다."
        last_run_at = _parse_time(policy.get("last_run_at"))
        if last_run_at and last_run_at >= scheduled_at:
            return "이번 예약 백업은 이미 실행되었습니다."
        return None

    def _candidates(self, limit, env=None):
        image_backups.ensure_schema(env=env)
        with connect(env=env) as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT b.*
                    FROM service_image_backups b
                    JOIN services s ON s.id = b.service_id
                    WHERE b.backup_ref IS NULL
                      AND b.backup_status IN ('recorded', 'backup_failed')
                    ORDER BY b.created_at ASC
                    LIMIT %s
                    """,
                    (limit,),
                )
                return [_row(row) for row in cursor.fetchall()]

    def _snapshot_candidates(self, limit, env=None):
        if limit <= 0:
            return []
        image_backups.ensure_schema(env=env)
        with connect(env=env) as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT DISTINCT ON (b.service_id, b.compose_service) b.*
                    FROM service_image_backups b
                    JOIN services s ON s.id = b.service_id
                    WHERE b.source <> 'container_snapshot'
                    ORDER BY b.service_id, b.compose_service, b.created_at DESC
                    LIMIT %s
                    """,
                    (limit,),
                )
                return [_row(row) for row in cursor.fetchall()]

    def run(self, payload=None, env=None):
        payload = payload or {}
        force = bool(payload.get("force"))
        operation_id = payload.get("operation_id")
        operation = operations.detail(operation_id, env=env) if operation_id else None
        status = backup_system.status(env=env)
        policy = status.get("backup_policy") or {}
        skip_reason = self._skip_reason(policy, force=force)
        if skip_reason:
            return self._finish_skipped(operation, {"processed": 0, "succeeded": 0, "failed": 0, "skipped": 1, "message": skip_reason, "policy": policy, "backup_system": status}, env=env)
        if status.get("status") != "running":
            message = "서비스 백업 시스템이 실행 중이 아닙니다."
            if force:
                raise ServiceError(409, message, "BACKUP_SYSTEM_NOT_RUNNING")
            return self._finish_skipped(operation, {"processed": 0, "succeeded": 0, "failed": 0, "skipped": 1, "message": message, "policy": policy, "backup_system": status}, env=env)

        limit = int(policy.get("max_items_per_run") or 3)
        snapshot_enabled = bool(policy.get("snapshot_enabled"))
        if force:
            if "include_snapshots" in payload:
                snapshot_enabled = _as_bool(payload.get("include_snapshots"), snapshot_enabled)
            elif "snapshot_enabled" in payload:
                snapshot_enabled = _as_bool(payload.get("snapshot_enabled"), snapshot_enabled)
            else:
                snapshot_enabled = True
        snapshot_pause = _as_bool(payload.get("snapshot_pause"), policy.get("snapshot_pause", True))
        candidates = self._candidates(limit, env=env)
        if operation is None:
            operation = operations.create(
                "service.image.backup.policy",
                target_type="backup_system",
                target_id="default",
                requested_payload={"force": force, "limit": limit, "snapshot_enabled": snapshot_enabled, "snapshot_pause": snapshot_pause},
                metadata={"policy": policy},
                env=env,
            )
        self._append_progress(operation["id"], f"수동 백업을 시작합니다. 이미지 {len(candidates)}개, 스냅샷 {'포함' if snapshot_enabled else '제외'}.", metadata={"step": "start", "image_count": len(candidates), "snapshot_enabled": snapshot_enabled}, env=env)
        result = {"processed": 0, "succeeded": 0, "failed": 0, "skipped": 0, "failures": [], "policy": policy, "snapshots": 0}
        for item in candidates:
            result["processed"] += 1
            try:
                self._append_progress(operation["id"], f"{item.get('compose_service') or 'image'} 이미지 백업을 시작합니다.", metadata={"step": "image", "backup_id": item["id"], "compose_service": item.get("compose_service")}, env=env)
                image_backups.backup_to_harbor(item["service_id"], item["id"], env=env)
                self._append_progress(operation["id"], f"{item.get('compose_service') or 'image'} 이미지 백업을 완료했습니다.", metadata={"step": "image", "backup_id": item["id"], "compose_service": item.get("compose_service")}, env=env)
                result["succeeded"] += 1
            except Exception as exc:
                if not _is_service_error_like(exc):
                    raise
                detail = _failure_detail(exc)
                self._append_progress(operation["id"], f"{item.get('compose_service') or 'image'} 이미지 백업 실패: {detail['message']}", stream="stderr", metadata={"step": "image", "backup_id": item["id"], "compose_service": item.get("compose_service")}, env=env)
                result["failed"] += 1
                result["failures"].append({"backup_id": item["id"], **detail})

        snapshot_limit = limit if force else max(0, limit - result["processed"])
        if snapshot_enabled and snapshot_limit > 0:
            snapshot_candidates = self._snapshot_candidates(snapshot_limit, env=env)
            self._append_progress(operation["id"], f"스냅샷 대상 {len(snapshot_candidates)}개를 확인했습니다.", metadata={"step": "snapshot_targets", "count": len(snapshot_candidates)}, env=env)
            for item in snapshot_candidates:
                result["processed"] += 1
                result["snapshots"] += 1
                try:
                    self._append_progress(operation["id"], f"{item.get('compose_service') or 'container'} 스냅샷 백업을 시작합니다.", metadata={"step": "snapshot", "backup_id": item["id"], "compose_service": item.get("compose_service")}, env=env)
                    image_backups.snapshot_to_harbor(item["service_id"], item["id"], pause=snapshot_pause, env=env)
                    self._append_progress(operation["id"], f"{item.get('compose_service') or 'container'} 스냅샷 백업을 완료했습니다.", metadata={"step": "snapshot", "backup_id": item["id"], "compose_service": item.get("compose_service")}, env=env)
                    result["succeeded"] += 1
                except Exception as exc:
                    if not _is_service_error_like(exc):
                        raise
                    detail = _failure_detail(exc)
                    self._append_progress(operation["id"], f"{item.get('compose_service') or 'container'} 스냅샷 백업 실패: {detail['message']}", stream="stderr", metadata={"step": "snapshot", "backup_id": item["id"], "compose_service": item.get("compose_service")}, env=env)
                    result["failed"] += 1
                    result["failures"].append({"backup_id": item["id"], **detail})

        status_name = "succeeded" if result["failed"] == 0 else "failed"
        message = "처리할 이미지 백업이 없습니다." if result["processed"] == 0 else None
        self._append_progress(operation["id"], message or f"수동 백업 처리 완료: 성공 {result['succeeded']}개, 실패 {result['failed']}개.", stream="stderr" if result["failed"] else "system", metadata={"step": "done"}, env=env)
        operation = operations.transition(operation["id"], status_name, message=message, result_payload=result, env=env)
        result["operation"] = operation
        result["backup_system"] = backup_system.mark_policy_run(result, env=env)
        return result

    def run_async(self, payload=None, env=None):
        payload = {**(payload or {}), "force": True, "background": True}
        operation = operations.create(
            "service.image.backup.policy",
            target_type="backup_system",
            target_id="default",
            message="수동 백업을 시작합니다.",
            requested_payload=payload,
            metadata={"background": True},
            env=env,
        )

        def worker():
            try:
                self.run({**payload, "operation_id": operation["id"]}, env=env)
            except Exception as exc:
                if _is_service_error_like(exc):
                    detail = _failure_detail(exc)
                else:
                    detail = {"message": str(exc), "error_code": "BACKUP_POLICY_RUN_FAILED"}
                self._append_progress(operation["id"], detail["message"], stream="stderr", metadata={"step": "failed", "error_code": detail["error_code"]}, env=env)
                try:
                    operations.transition(operation["id"], "failed", message=detail["message"], result_payload=detail, env=env)
                except Exception:
                    pass

        threading.Thread(target=worker, daemon=True).start()
        return {"operation": operation, "backup_system": backup_system.status(env=env)}


Model = ServiceImageBackupScheduler()
