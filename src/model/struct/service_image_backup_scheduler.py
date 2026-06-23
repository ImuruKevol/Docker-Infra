import calendar
import datetime
import threading

backup_system = wiz.model("struct/backup_system")
image_backups = wiz.model("struct/service_image_backups")
volume_backups = wiz.model("struct/service_volume_backups")
cleanup = wiz.model("struct/service_image_backup_cleanup")
operations = wiz.model("struct/operations")
shared = wiz.model("struct/services_shared")
ServiceError = shared.ServiceError


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


def _snapshot_label(item):
    metadata = item.get("metadata") or {}
    service_label = (
        metadata.get("service_name")
        or metadata.get("service_namespace")
        or metadata.get("namespace")
        or item.get("service_name")
        or item.get("service_id")
    )
    compose_label = item.get("compose_service") or metadata.get("snapshot_target_container_name") or "container"
    if service_label and compose_label and str(service_label) != str(compose_label):
        return f"{service_label} / {compose_label}"
    return str(service_label or compose_label or "container")


def _volume_label(item):
    metadata = item.get("metadata") or {}
    service_label = (
        metadata.get("service_name")
        or metadata.get("service_namespace")
        or metadata.get("namespace")
        or item.get("service_id")
    )
    compose_label = item.get("compose_service") or "service"
    volume_label = item.get("docker_volume") or item.get("volume_name") or "volume"
    return " / ".join(str(part) for part in [service_label, compose_label, volume_label] if part)


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

    def _snapshot_candidates(self, env=None):
        return image_backups.record_runtime_snapshot_targets(source="backup_policy_snapshot", env=env)

    def _volume_candidates(self, env=None):
        return volume_backups.record_runtime_volume_targets(source="backup_policy_snapshot", env=env)

    def _run_retention_cleanup(self, operation_id, policy, env=None):
        keep = int(policy.get("retention_keep_per_service") or 10)
        payload = {
            "retention_keep_per_service": keep,
            "cleanup_unused_days": int(policy.get("cleanup_unused_days") or 30),
        }
        self._append_progress(
            operation_id,
            f"보존 정책 정리를 시작합니다. 서비스별 최근 {keep}개만 유지합니다.",
            metadata={"step": "cleanup_start", **payload},
            env=env,
        )
        result = cleanup.cleanup(payload, env=env)
        summary = result.get("summary") or {}
        deleted = int(summary.get("deleted_count") or 0)
        failed = int(summary.get("failed_count") or 0)
        stream = "stderr" if failed else "system"
        self._append_progress(
            operation_id,
            f"보존 정책 정리 완료: Harbor 백업 artifact {deleted}개 삭제, 실패 {failed}개.",
            stream=stream,
            metadata={"step": "cleanup_done", "summary": summary},
            env=env,
        )
        return result

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

        snapshot_enabled = str(policy.get("backup_mode") or policy.get("state_snapshot_mode") or "full_state") != "volume_only"
        volume_enabled = True
        snapshot_pause = _as_bool(payload.get("snapshot_pause"), policy.get("snapshot_pause", True))
        if operation is None:
            operation = operations.create(
                "service.image.backup.policy",
                target_type="backup_system",
                target_id="default",
                requested_payload={"force": force, "snapshot_enabled": snapshot_enabled, "volume_enabled": volume_enabled, "snapshot_pause": snapshot_pause},
                metadata={"policy": policy},
                env=env,
            )
        mode_label = "named volume 백업만" if not snapshot_enabled else "컨테이너 스냅샷과 named volume 백업"
        self._append_progress(operation["id"], f"수동 백업을 시작합니다. 등록 서비스 전체 {mode_label}을 실행합니다.", metadata={"step": "start", "snapshot_enabled": snapshot_enabled, "volume_enabled": volume_enabled}, env=env)
        result = {"processed": 0, "succeeded": 0, "failed": 0, "skipped": 0, "failures": [], "policy": policy, "snapshots": 0, "volumes": 0}
        if snapshot_enabled:
            snapshot_candidates = self._snapshot_candidates(env=env)
            self._append_progress(operation["id"], f"등록 서비스 기준 스냅샷 대상 {len(snapshot_candidates)}개를 확인했습니다.", metadata={"step": "snapshot_targets", "count": len(snapshot_candidates)}, env=env)
            for item in snapshot_candidates:
                result["processed"] += 1
                result["snapshots"] += 1
                label = _snapshot_label(item)
                try:
                    self._append_progress(operation["id"], f"{label} 스냅샷 백업을 시작합니다.", metadata={"step": "snapshot", "backup_id": item["id"], "compose_service": item.get("compose_service"), "label": label}, env=env)
                    image_backups.snapshot_to_harbor(item["service_id"], item["id"], pause=snapshot_pause, env=env)
                    self._append_progress(operation["id"], f"{label} 스냅샷 백업을 완료했습니다.", metadata={"step": "snapshot", "backup_id": item["id"], "compose_service": item.get("compose_service"), "label": label}, env=env)
                    result["succeeded"] += 1
                except Exception as exc:
                    if not _is_service_error_like(exc):
                        raise
                    detail = _failure_detail(exc)
                    self._append_progress(operation["id"], f"{label} 스냅샷 백업 실패: {detail['message']}", stream="stderr", metadata={"step": "snapshot", "backup_id": item["id"], "compose_service": item.get("compose_service"), "label": label}, env=env)
                    result["failed"] += 1
                    result["failures"].append({"backup_id": item["id"], **detail})
        if volume_enabled:
            volume_candidates = self._volume_candidates(env=env)
            self._append_progress(operation["id"], f"등록 서비스 기준 named volume 백업 대상 {len(volume_candidates)}개를 확인했습니다.", metadata={"step": "volume_targets", "count": len(volume_candidates)}, env=env)
            for item in volume_candidates:
                result["processed"] += 1
                result["volumes"] += 1
                label = _volume_label(item)
                try:
                    self._append_progress(operation["id"], f"{label} named volume 백업을 시작합니다.", metadata={"step": "volume", "backup_id": item["id"], "compose_service": item.get("compose_service"), "volume": item.get("docker_volume"), "label": label}, env=env)
                    volume_backups.volume_to_harbor(item["service_id"], item["id"], env=env)
                    self._append_progress(operation["id"], f"{label} named volume 백업을 완료했습니다.", metadata={"step": "volume", "backup_id": item["id"], "compose_service": item.get("compose_service"), "volume": item.get("docker_volume"), "label": label}, env=env)
                    result["succeeded"] += 1
                except Exception as exc:
                    if not _is_service_error_like(exc):
                        raise
                    detail = _failure_detail(exc)
                    self._append_progress(operation["id"], f"{label} named volume 백업 실패: {detail['message']}", stream="stderr", metadata={"step": "volume", "backup_id": item["id"], "compose_service": item.get("compose_service"), "volume": item.get("docker_volume"), "label": label}, env=env)
                    result["failed"] += 1
                    result["failures"].append({"backup_id": item["id"], "backup_kind": "named_volume_snapshot", **detail})

        cleanup_failed = False
        if result["succeeded"] > 0:
            try:
                cleanup_result = self._run_retention_cleanup(operation["id"], policy, env=env)
                result["cleanup"] = cleanup_result.get("summary") or {}
                cleanup_failed = int(result["cleanup"].get("failed_count") or 0) > 0
            except Exception as exc:
                if not _is_service_error_like(exc):
                    raise
                detail = _failure_detail(exc)
                cleanup_failed = True
                result["cleanup"] = detail
                self._append_progress(operation["id"], f"보존 정책 정리 실패: {detail['message']}", stream="stderr", metadata={"step": "cleanup_failed", "error_code": detail["error_code"]}, env=env)

        status_name = "succeeded" if result["failed"] == 0 and not cleanup_failed else "failed"
        message = "실행 중인 등록 서비스 백업 대상이 없습니다." if result["processed"] == 0 else None
        self._append_progress(operation["id"], message or f"수동 백업 처리 완료: 성공 {result['succeeded']}개, 실패 {result['failed']}개.", stream="stderr" if result["failed"] else "system", metadata={"step": "done"}, env=env)
        operation = operations.transition(operation["id"], status_name, message=message, result_payload=result, env=env)
        result["operation"] = operation
        result["backup_system"] = backup_system.mark_policy_run(result, env=env)
        return result

    def run_async(self, payload=None, env=None):
        payload = {**(payload or {}), "force": True, "background": True}
        payload.pop("max_items_per_run", None)
        payload.pop("limit", None)
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
