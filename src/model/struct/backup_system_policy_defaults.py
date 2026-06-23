import re


DEFAULT_BACKUP_POLICY = {
    "enabled": False,
    "mode": "manual",
    "schedule_type": "weekly",
    "schedule_weekday": 0,
    "schedule_month_day": 1,
    "schedule_time": "02:00",
    "interval_days": 7,
    "window_start": "00:00",
    "window_end": "00:00",
    "retention_keep_per_service": 10,
    "cleanup_unused_days": 30,
    "method": "service_state_snapshot",
    "backup_mode": "full_state",
    "snapshot_enabled": True,
    "snapshot_pause": True,
    "last_run_at": None,
    "last_result": None,
}


def _clamp_int(value, default, minimum, maximum):
    try:
        number = int(value)
    except (TypeError, ValueError):
        number = default
    return max(minimum, min(maximum, number))


def _time_text(value, default):
    value = str(value or "").strip()
    if re.fullmatch(r"([01]\d|2[0-3]):[0-5]\d", value):
        return value
    return default


def _schedule_type(value):
    value = str(value or "").strip().lower()
    return value if value in {"weekly", "monthly"} else DEFAULT_BACKUP_POLICY["schedule_type"]


def normalize(value=None, base=None):
    source = {**DEFAULT_BACKUP_POLICY, **(base or {}), **(value or {})}
    enabled = bool(source.get("enabled"))
    schedule_type = _schedule_type(source.get("schedule_type"))
    return {
        "enabled": enabled,
        "mode": "scheduled" if enabled else "manual",
        "schedule_type": schedule_type,
        "schedule_weekday": _clamp_int(source.get("schedule_weekday"), DEFAULT_BACKUP_POLICY["schedule_weekday"], 0, 6),
        "schedule_month_day": _clamp_int(source.get("schedule_month_day"), DEFAULT_BACKUP_POLICY["schedule_month_day"], 1, 31),
        "schedule_time": _time_text(source.get("schedule_time"), DEFAULT_BACKUP_POLICY["schedule_time"]),
        "interval_days": _clamp_int(source.get("interval_days"), DEFAULT_BACKUP_POLICY["interval_days"], 1, 365),
        "window_start": _time_text(source.get("window_start"), DEFAULT_BACKUP_POLICY["window_start"]),
        "window_end": _time_text(source.get("window_end"), DEFAULT_BACKUP_POLICY["window_end"]),
        "retention_keep_per_service": _clamp_int(source.get("retention_keep_per_service"), DEFAULT_BACKUP_POLICY["retention_keep_per_service"], 1, 200),
        "cleanup_unused_days": _clamp_int(source.get("cleanup_unused_days"), DEFAULT_BACKUP_POLICY["cleanup_unused_days"], 1, 3650),
        "method": "service_state_snapshot",
        "backup_mode": "volume_only" if str(source.get("backup_mode") or source.get("state_snapshot_mode") or "").strip() == "volume_only" else "full_state",
        "snapshot_enabled": True,
        "snapshot_pause": bool(source.get("snapshot_pause", True)),
        "last_run_at": source.get("last_run_at"),
        "last_result": source.get("last_result"),
    }


class BackupSystemPolicyDefaults:
    DEFAULT_BACKUP_POLICY = DEFAULT_BACKUP_POLICY
    normalize = staticmethod(normalize)


Model = BackupSystemPolicyDefaults()
