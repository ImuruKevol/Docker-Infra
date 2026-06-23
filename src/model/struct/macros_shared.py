import json


MAX_CAPTURE_CHARS = 20000
DEFAULT_TIMEOUT_SECONDS = 120
MAX_TIMEOUT_SECONDS = 1800
MAX_MACRO_FILES = 20
MAX_MACRO_FILE_BYTES = 10 * 1024 * 1024
MAX_MACRO_TOTAL_FILE_BYTES = 50 * 1024 * 1024
SCOPE_GLOBAL = "global"
SCOPE_NODE = "node"
VALID_SCOPE_TYPES = {SCOPE_GLOBAL, SCOPE_NODE}
VALID_SCHEDULE_TYPES = {"weekly", "monthly"}
VALID_TARGET_TYPES = {"server", "service"}


class MacroError(Exception):
    def __init__(self, status_code, message, error_code, **extra):
        super().__init__(message)
        self.status_code = status_code
        self.message = message
        self.error_code = error_code
        self.extra = extra


def row_value(row, key, default=None):
    try:
        return row[key]
    except Exception:
        return default


def macro_file_row(row):
    if row is None:
        return None
    return {
        "id": str(row["id"]),
        "filename": row["filename"],
        "content_type": row_value(row, "content_type", "") or "",
        "size_bytes": int(row_value(row, "size_bytes", 0) or 0),
        "created_at": row_value(row, "created_at"),
    }


def normalize_macro_files(value):
    rows = value or []
    files = []
    for item in rows:
        if item is None:
            continue
        files.append(
            {
                "id": str(item.get("id") or ""),
                "filename": item.get("filename") or "",
                "content_type": item.get("content_type") or "",
                "size_bytes": int(item.get("size_bytes") or 0),
                "created_at": item.get("created_at"),
            }
        )
    return [item for item in files if item["id"] and item["filename"]]


def _json_rows(value):
    if value in (None, ""):
        return []
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except Exception:
            return []
    return value if isinstance(value, list) else []


def normalize_schedule_targets(value):
    targets = []
    for item in _json_rows(value):
        if not isinstance(item, dict):
            continue
        target_type = str(item.get("target_type") or "").strip().lower()
        if target_type not in VALID_TARGET_TYPES:
            target_type = "service" if item.get("service_target_id") else "server"
        target = {
            "target_type": target_type,
            "node_id": str(item.get("node_id") or "").strip(),
            "label": str(item.get("label") or "").strip(),
        }
        if target_type == "service":
            target.update(
                {
                    "service_target_id": str(item.get("service_target_id") or item.get("id") or "").strip(),
                    "service_id": str(item.get("service_id") or "").strip(),
                    "service_name": str(item.get("service_name") or "").strip(),
                    "service_namespace": str(item.get("service_namespace") or "").strip(),
                    "container_id": str(item.get("container_id") or "").strip(),
                    "container_name": str(item.get("container_name") or "").strip(),
                    "container_display_name": str(item.get("container_display_name") or "").strip(),
                }
            )
        if target["node_id"]:
            targets.append(target)
    return targets


def normalize_schedule_weekdays(value, fallback=None):
    rows = _json_rows(value)
    if not rows and fallback not in (None, ""):
        rows = [fallback]
    days = []
    seen = set()
    for item in rows:
        try:
            day = int(item)
        except (TypeError, ValueError):
            day = 0
        day = max(0, min(6, day))
        if day in seen:
            continue
        seen.add(day)
        days.append(day)
    return days or [0]


def normalize_schedule_history(value):
    rows = []
    for item in _json_rows(value):
        if not isinstance(item, dict):
            continue
        rows.append(
            {
                "id": str(item.get("id") or ""),
                "status": item.get("status") or "",
                "message": item.get("message") or "",
                "target_id": item.get("target_id"),
                "requested_payload": item.get("requested_payload") or {},
                "result_payload": item.get("result_payload") or {},
                "output": item.get("output") or [],
                "metadata": item.get("metadata") or {},
                "started_at": item.get("started_at"),
                "finished_at": item.get("finished_at"),
                "created_at": item.get("created_at"),
                "updated_at": item.get("updated_at"),
            }
        )
    return [item for item in rows if item["id"]]


def macro_schedule_row(row):
    if row is None:
        return None
    targets = normalize_schedule_targets(row_value(row, "targets", []))
    schedule_weekdays = normalize_schedule_weekdays(
        row_value(row, "schedule_weekdays", []),
        fallback=row_value(row, "schedule_weekday", 0),
    )
    schedule_type = str(row_value(row, "schedule_type", "weekly") or "weekly").strip().lower()
    target_type = str(row_value(row, "target_type", "server") or "server").strip().lower()
    return {
        "id": str(row["id"]),
        "macro_id": str(row["macro_id"]),
        "name": row_value(row, "name", "") or "",
        "enabled": bool(row_value(row, "enabled", True)),
        "schedule_type": schedule_type if schedule_type in VALID_SCHEDULE_TYPES else "weekly",
        "schedule_weekday": schedule_weekdays[0],
        "schedule_weekdays": schedule_weekdays,
        "schedule_month_day": int(row_value(row, "schedule_month_day", 1) or 1),
        "schedule_time": row_value(row, "schedule_time", "02:00") or "02:00",
        "target_type": target_type if target_type in VALID_TARGET_TYPES else "server",
        "targets": targets,
        "target_count": len(targets),
        "args": row_value(row, "args", "") or "",
        "cron_file": row_value(row, "cron_file", "") or "",
        "last_run_at": row_value(row, "last_run_at"),
        "last_result": row_value(row, "last_result", {}) or {},
        "history": normalize_schedule_history(row_value(row, "history", [])),
        "test_run_id": row_value(row, "test_run_id"),
        "metadata": row_value(row, "metadata", {}) or {},
        "created_at": row_value(row, "created_at"),
        "updated_at": row_value(row, "updated_at"),
    }


def normalize_macro_schedules(value):
    rows = []
    for item in _json_rows(value):
        if not isinstance(item, dict):
            continue
        try:
            rows.append(macro_schedule_row(item))
        except Exception:
            continue
    return [item for item in rows if item and item["id"]]


def macro_row(row):
    if row is None:
        return None
    files = normalize_macro_files(row_value(row, "files", []))
    schedules = normalize_macro_schedules(row_value(row, "schedules", []))
    return {
        "id": str(row["id"]),
        "name": row["name"],
        "description": row["description"],
        "script": row["script"],
        "enabled": bool(row["enabled"]),
        "scope_type": row_value(row, "scope_type", SCOPE_GLOBAL),
        "node_id": None if row_value(row, "node_id") is None else str(row["node_id"]),
        "node_name": row_value(row, "node_name"),
        "node_host": row_value(row, "node_host"),
        "test_run_id": row["test_run_id"],
        "metadata": row["metadata"] or {},
        "files": files,
        "file_count": len(files),
        "schedules": schedules,
        "schedule_count": int(row_value(row, "schedule_count", len(schedules)) or len(schedules)),
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
    }


def trim_output(value):
    text = "" if value is None else str(value)
    if len(text) <= MAX_CAPTURE_CHARS:
        return text
    return text[:MAX_CAPTURE_CHARS] + "\n[truncated]"


def normalize_script_text(value):
    return str(value or "").replace("\r\n", "\n").replace("\r", "\n")


def normalize_enabled(value):
    if value is None:
        return True
    return str(value).strip().lower() not in {"0", "false", "no", "off"}


def normalize_scope_type(value, default=SCOPE_GLOBAL):
    scope_type = str(value or default).strip().lower() or default
    if scope_type not in VALID_SCOPE_TYPES:
        raise MacroError(400, "지원하지 않는 매크로 범위입니다.", "INVALID_MACRO_SCOPE")
    return scope_type


def normalize_timeout(timeout_seconds):
    if timeout_seconds in (None, ""):
        return DEFAULT_TIMEOUT_SECONDS
    try:
        value = int(timeout_seconds)
    except (TypeError, ValueError):
        raise MacroError(400, "timeout_seconds는 정수여야 합니다.", "INVALID_MACRO_TIMEOUT")
    return max(1, min(value, MAX_TIMEOUT_SECONDS))


class MacrosShared:
    MacroError = MacroError
    SCOPE_GLOBAL = SCOPE_GLOBAL
    SCOPE_NODE = SCOPE_NODE
    VALID_SCOPE_TYPES = VALID_SCOPE_TYPES
    MAX_CAPTURE_CHARS = MAX_CAPTURE_CHARS
    DEFAULT_TIMEOUT_SECONDS = DEFAULT_TIMEOUT_SECONDS
    MAX_TIMEOUT_SECONDS = MAX_TIMEOUT_SECONDS
    MAX_MACRO_FILES = MAX_MACRO_FILES
    MAX_MACRO_FILE_BYTES = MAX_MACRO_FILE_BYTES
    MAX_MACRO_TOTAL_FILE_BYTES = MAX_MACRO_TOTAL_FILE_BYTES
    row_value = staticmethod(row_value)
    macro_file_row = staticmethod(macro_file_row)
    normalize_macro_files = staticmethod(normalize_macro_files)
    normalize_schedule_targets = staticmethod(normalize_schedule_targets)
    normalize_schedule_weekdays = staticmethod(normalize_schedule_weekdays)
    normalize_schedule_history = staticmethod(normalize_schedule_history)
    macro_schedule_row = staticmethod(macro_schedule_row)
    normalize_macro_schedules = staticmethod(normalize_macro_schedules)
    macro_row = staticmethod(macro_row)
    trim_output = staticmethod(trim_output)
    normalize_script_text = staticmethod(normalize_script_text)
    normalize_enabled = staticmethod(normalize_enabled)
    normalize_scope_type = staticmethod(normalize_scope_type)
    normalize_timeout = staticmethod(normalize_timeout)


Model = MacrosShared()
