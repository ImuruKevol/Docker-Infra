MAX_CAPTURE_CHARS = 20000
DEFAULT_TIMEOUT_SECONDS = 120
MAX_TIMEOUT_SECONDS = 1800
MAX_MACRO_FILES = 20
MAX_MACRO_FILE_BYTES = 10 * 1024 * 1024
MAX_MACRO_TOTAL_FILE_BYTES = 50 * 1024 * 1024
SCOPE_GLOBAL = "global"
SCOPE_NODE = "node"
VALID_SCOPE_TYPES = {SCOPE_GLOBAL, SCOPE_NODE}


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


def macro_row(row):
    if row is None:
        return None
    files = normalize_macro_files(row_value(row, "files", []))
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
    macro_row = staticmethod(macro_row)
    trim_output = staticmethod(trim_output)
    normalize_script_text = staticmethod(normalize_script_text)
    normalize_enabled = staticmethod(normalize_enabled)
    normalize_scope_type = staticmethod(normalize_scope_type)
    normalize_timeout = staticmethod(normalize_timeout)


Model = MacrosShared()
