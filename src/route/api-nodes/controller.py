from flask import request

nodes = wiz.model("struct").nodes
monitoring = wiz.model("struct").nodes_monitoring
method = wiz.request.method().upper()


def _error_payload(exc, default_code=500, default_error="UNEXPECTED_ERROR"):
    if hasattr(exc, "status_code") and hasattr(exc, "message") and hasattr(exc, "error_code"):
        return exc.status_code, {"message": exc.message, "error_code": exc.error_code, **(getattr(exc, "extra", {}) or {})}
    return default_code, {"message": str(exc), "error_code": default_error}


def _request_base_url():
    forwarded_proto = (request.headers.get("X-Forwarded-Proto") or "").split(",")[0].strip()
    forwarded_host = (request.headers.get("X-Forwarded-Host") or "").split(",")[0].strip()
    proto = forwarded_proto or request.scheme
    host = forwarded_host or request.headers.get("Host")
    if host:
        return f"{proto}://{host}".rstrip("/")
    return request.url_root.rstrip("/")


if method not in ["GET", "POST"]:
    wiz.response.status(405, message="지원하지 않는 method입니다.", error_code="METHOD_NOT_ALLOWED")

code = 200
payload = {}

try:
    if method == "GET":
        payload = {"nodes": nodes.overview_summary(auto_sync_local_master=False)["nodes"]}
    else:
        body = wiz.request.query()
        is_new = not body.get("node_id")
        node = nodes.save_slave(body)
        monitoring_result = None
        if is_new:
            try:
                monitoring_result = monitoring.ensure_exporters({"node_id": node["id"], "reporter_base_url": _request_base_url()})
                node = nodes.detail(node["id"])
            except Exception as exc:
                monitoring_result = {"status": "failed", "message": str(exc)}
        payload = {"node": node, "monitoring_auto_configure": monitoring_result, "monitoring": monitoring.state()}
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
