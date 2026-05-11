from flask import request

nodes = wiz.model("struct").nodes
monitoring = wiz.model("struct").nodes_monitoring
method = wiz.request.method().upper()


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
    payload = nodes.ensure_local_master(wiz.request.query())
    local_master = payload.get("local_master") or {}
    if local_master.get("id"):
        try:
            payload["monitoring_auto_configure"] = monitoring.ensure_exporters({"node_id": local_master["id"], "reporter_base_url": _request_base_url()})
            payload["local_master"] = nodes.detail(local_master["id"])
        except Exception as exc:
            payload["monitoring_auto_configure"] = {"status": "failed", "message": str(exc)}
    payload["monitoring"] = monitoring.state()
except nodes.NodeError as exc:
    code = exc.status_code
    payload = {"message": exc.message, "error_code": exc.error_code, **exc.extra}
except nodes.LocalCommandError as exc:
    code = exc.status_code
    payload = {"message": exc.message, "error_code": exc.error_code, **exc.extra}
except RuntimeError as exc:
    code = 503
    payload = {"message": str(exc), "error_code": "DATABASE_UNAVAILABLE"}

wiz.response.status(code, **payload)
