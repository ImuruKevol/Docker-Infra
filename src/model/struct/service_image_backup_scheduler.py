import datetime


connect = wiz.model("db/postgres").connect
backup_system = wiz.model("struct/backup_system")
image_backups = wiz.model("struct/service_image_backups")
operations = wiz.model("struct/operations")
shared = wiz.model("struct/services_shared")
ServiceError = shared.ServiceError
_row = shared.row


def _minutes(value):
    hour, minute = str(value or "00:00").split(":", 1)
    return int(hour) * 60 + int(minute)


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


def _inside_window(policy, now):
    start = _minutes(policy.get("window_start"))
    end = _minutes(policy.get("window_end"))
    current = now.hour * 60 + now.minute
    if start == end:
        return True
    if start < end:
        return start <= current <= end
    return current >= start or current <= end


class ServiceImageBackupScheduler:
    ServiceError = ServiceError

    def _skip_reason(self, policy, force=False):
        if force:
            return None
        if not policy.get("enabled"):
            return "자동 백업이 꺼져 있습니다."
        now = datetime.datetime.now().astimezone()
        if not _inside_window(policy, now):
            return "현재 시간이 자동 백업 허용 시간대가 아닙니다."
        last_run_at = _parse_time(policy.get("last_run_at"))
        interval = datetime.timedelta(days=int(policy.get("interval_days") or 1))
        if last_run_at and now - last_run_at < interval:
            return "다음 자동 백업 주기 전입니다."
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
        status = backup_system.status(env=env)
        policy = status.get("backup_policy") or {}
        skip_reason = self._skip_reason(policy, force=force)
        if skip_reason:
            return {"processed": 0, "succeeded": 0, "failed": 0, "skipped": 1, "message": skip_reason, "policy": policy, "backup_system": status}
        if status.get("status") != "running":
            message = "서비스 백업 시스템이 실행 중이 아닙니다."
            if force:
                raise ServiceError(409, message, "BACKUP_SYSTEM_NOT_RUNNING")
            return {"processed": 0, "succeeded": 0, "failed": 0, "skipped": 1, "message": message, "policy": policy, "backup_system": status}

        limit = int(policy.get("max_items_per_run") or 3)
        candidates = self._candidates(limit, env=env)
        operation = operations.create(
            "service.image.backup.policy",
            target_type="backup_system",
            target_id="default",
            requested_payload={"force": force, "limit": limit, "snapshot_enabled": bool(policy.get("snapshot_enabled"))},
            metadata={"policy": policy},
            env=env,
        )
        result = {"processed": 0, "succeeded": 0, "failed": 0, "skipped": 0, "failures": [], "policy": policy, "snapshots": 0}
        for item in candidates:
            result["processed"] += 1
            try:
                image_backups.backup_to_harbor(item["service_id"], item["id"], env=env)
                result["succeeded"] += 1
            except ServiceError as exc:
                result["failed"] += 1
                result["failures"].append({"backup_id": item["id"], "message": exc.message, "error_code": exc.error_code})

        remaining = limit - result["processed"]
        if policy.get("snapshot_enabled") and remaining > 0:
            for item in self._snapshot_candidates(remaining, env=env):
                result["processed"] += 1
                result["snapshots"] += 1
                try:
                    image_backups.snapshot_to_harbor(item["service_id"], item["id"], pause=policy.get("snapshot_pause", True), env=env)
                    result["succeeded"] += 1
                except ServiceError as exc:
                    result["failed"] += 1
                    result["failures"].append({"backup_id": item["id"], "message": exc.message, "error_code": exc.error_code})

        status_name = "succeeded" if result["failed"] == 0 else "failed"
        message = "처리할 이미지 백업이 없습니다." if result["processed"] == 0 else None
        operation = operations.transition(operation["id"], status_name, message=message, result_payload=result, env=env)
        result["operation"] = operation
        result["backup_system"] = backup_system.mark_policy_run(result, env=env)
        return result


Model = ServiceImageBackupScheduler()
