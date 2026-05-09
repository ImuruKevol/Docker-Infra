import re


DEFAULT_BACKUP_POLICY = {
    "enabled": False,
    "mode": "manual",
    "interval_days": 7,
    "window_start": "02:00",
    "window_end": "05:00",
    "max_items_per_run": 3,
    "retention_keep_per_service": 10,
    "cleanup_unused_days": 30,
    "method": "image_ref",
    "snapshot_enabled": False,
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


def normalize(value=None, base=None):
    source = {**DEFAULT_BACKUP_POLICY, **(base or {}), **(value or {})}
    enabled = bool(source.get("enabled"))
    return {
        "enabled": enabled,
        "mode": "scheduled" if enabled else "manual",
        "interval_days": _clamp_int(source.get("interval_days"), DEFAULT_BACKUP_POLICY["interval_days"], 1, 365),
        "window_start": _time_text(source.get("window_start"), DEFAULT_BACKUP_POLICY["window_start"]),
        "window_end": _time_text(source.get("window_end"), DEFAULT_BACKUP_POLICY["window_end"]),
        "max_items_per_run": _clamp_int(source.get("max_items_per_run"), DEFAULT_BACKUP_POLICY["max_items_per_run"], 1, 50),
        "retention_keep_per_service": _clamp_int(source.get("retention_keep_per_service"), DEFAULT_BACKUP_POLICY["retention_keep_per_service"], 1, 200),
        "cleanup_unused_days": _clamp_int(source.get("cleanup_unused_days"), DEFAULT_BACKUP_POLICY["cleanup_unused_days"], 1, 3650),
        "method": "image_ref",
        "snapshot_enabled": bool(source.get("snapshot_enabled")),
        "snapshot_pause": bool(source.get("snapshot_pause", True)),
        "last_run_at": source.get("last_run_at"),
        "last_result": source.get("last_result"),
    }


class BackupSystemPolicyDefaults:
    DEFAULT_BACKUP_POLICY = DEFAULT_BACKUP_POLICY
    normalize = staticmethod(normalize)


Model = BackupSystemPolicyDefaults()
