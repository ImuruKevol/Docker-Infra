nodes = wiz.model("struct").nodes
monitoring = wiz.model("struct").nodes_monitoring
method = wiz.request.method().upper()

if method not in ["GET", "POST"]:
    wiz.response.status(405, message="지원하지 않는 method입니다.", error_code="METHOD_NOT_ALLOWED")

code = 200
payload = {}

try:
    payload = nodes.ensure_local_master(wiz.request.query())
    local_master = payload.get("local_master") or {}
    if local_master.get("id"):
        try:
            payload["monitoring_auto_configure"] = monitoring.ensure_exporters({"node_id": local_master["id"]})
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
