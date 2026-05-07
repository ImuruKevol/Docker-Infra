nodes = wiz.model("struct").nodes
method = wiz.request.method().upper()


def _error_payload(exc, default_code=500, default_error="UNEXPECTED_ERROR"):
    if hasattr(exc, "status_code") and hasattr(exc, "message") and hasattr(exc, "error_code"):
        return exc.status_code, {"message": exc.message, "error_code": exc.error_code, **(getattr(exc, "extra", {}) or {})}
    return default_code, {"message": str(exc), "error_code": default_error}

if method not in ["GET", "POST"]:
    wiz.response.status(405, message="지원하지 않는 method입니다.", error_code="METHOD_NOT_ALLOWED")

code = 200
payload = {}

try:
    if method == "GET":
        payload = {"nodes": nodes.overview_summary(auto_sync_local_master=False)["nodes"]}
    else:
        payload = {"node": nodes.save_slave(wiz.request.query())}
except nodes.NodeError as exc:
    code = exc.status_code
    payload = {"message": exc.message, "error_code": exc.error_code, **exc.extra}
except nodes.LocalCommandError as exc:
    code = exc.status_code
    payload = {"message": exc.message, "error_code": exc.error_code, **exc.extra}
except RuntimeError as exc:
    code = 503
    payload = {"message": str(exc), "error_code": "DATABASE_UNAVAILABLE"}
except Exception as exc:
    code, payload = _error_payload(exc)

wiz.response.status(code, **payload)
