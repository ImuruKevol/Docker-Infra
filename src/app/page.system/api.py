from pathlib import Path, PurePosixPath

def _normalize_local_path(value):
    path = str(PurePosixPath(value or "/"))
    return path if path.startswith("/") else f"/{path}"


def _default_local_path():
    return _normalize_local_path(str(Path.home()))


def _resolve_local_path(value):
    raw = str(value or "").strip()
    if raw in {"", "~"}:
        return _default_local_path()
    if raw.startswith("~/"):
        home = _default_local_path().rstrip("/")
        suffix = raw[2:].strip("/")
        return _normalize_local_path(f"{home}/{suffix}") if suffix else home or "/"
    return _normalize_local_path(raw)


def _show_hidden(value):
    return str(value or "").strip().lower() in {"1", "true", "yes", "on"}


def load():
    appearance = wiz.model("struct/appearance")
    integrations = wiz.model("struct").integrations
    webserver = wiz.model("struct").webserver
    code = 200
    payload = {}
    try:
        payload = {
            "general": appearance.public_payload(),
            "integrations": integrations.load(),
            "webserver": webserver.load(),
        }
    except RuntimeError as exc:
        code = 503
        payload = {"message": str(exc), "error_code": "DATABASE_UNAVAILABLE"}
    wiz.response.status(code, **payload)


def save_general():
    appearance = wiz.model("struct/appearance")
    body = wiz.request.query()
    code = 200
    payload = {}
    try:
        payload = {"general": appearance.save(body, test_run_id=body.get("test_run_id"))}
    except RuntimeError as exc:
        code = 503
        payload = {"message": str(exc), "error_code": "DATABASE_UNAVAILABLE"}
    wiz.response.status(code, **payload)


def browse_local_files():
    body = wiz.request.query()
    code = 200
    payload = {}
    try:
        path = _resolve_local_path(body.get("path"))
        current_path = Path(path).expanduser().resolve()
        if current_path.is_file():
            current_path = current_path.parent
        if current_path.is_dir() is not True:
            code = 404
            payload = {"message": "선택한 경로를 열 수 없습니다.", "error_code": "LOCAL_PATH_NOT_FOUND"}
        else:
            current = _resolve_local_path(str(current_path))
            parent = str(PurePosixPath(current).parent) if current != "/" else None
            items = []
            for entry in sorted(current_path.iterdir(), key=lambda item: (not item.is_dir(), item.name.lower())):
                name = str(entry.name or "").strip()
                if not _show_hidden(body.get("show_hidden")) and name.startswith("."):
                    continue
                items.append({
                    "name": name,
                    "path": _resolve_local_path(str(entry.resolve())),
                    "type": "folder" if entry.is_dir() else "file",
                    "size": 0 if entry.is_dir() else int(entry.stat().st_size),
                })
            payload = {"path": current, "parent": None if parent == current else parent, "items": items}
    except (OSError, RuntimeError, ValueError):
        code = 404
        payload = {"message": "선택한 경로를 열 수 없습니다.", "error_code": "LOCAL_PATH_NOT_FOUND"}
    wiz.response.status(code, **payload)


def save_integration():
    integrations = wiz.model("struct").integrations
    body = wiz.request.query()
    code = 200
    payload = {}
    try:
        key = body.get("key")
        payload = {
            "integration": integrations.save(
                key,
                body,
                test_run_id=body.get("test_run_id"),
            ),
            "integrations": integrations.load(),
        }
    except integrations.IntegrationError as exc:
        code = exc.status_code
        payload = {"message": exc.message, "error_code": exc.error_code, **exc.extra}
    except RuntimeError as exc:
        code = 503
        payload = {"message": str(exc), "error_code": "DATABASE_UNAVAILABLE"}
    wiz.response.status(code, **payload)


def save_webserver():
    webserver = wiz.model("struct").webserver
    body = wiz.request.query()
    code = 200
    payload = {}
    try:
        payload = {"webserver": webserver.save(body, test_run_id=body.get("test_run_id"))}
    except RuntimeError as exc:
        code = 503
        payload = {"message": str(exc), "error_code": "DATABASE_UNAVAILABLE"}
    wiz.response.status(code, **payload)


def test_integration():
    integrations = wiz.model("struct").integrations
    body = wiz.request.query()
    code = 200
    payload = {}
    try:
        payload = integrations.test_connection(body.get("key"), body)
    except integrations.IntegrationError as exc:
        code = exc.status_code
        payload = {"message": exc.message, "error_code": exc.error_code, **exc.extra}
    wiz.response.status(code, **payload)
