from flask import request

auth = wiz.model("struct").auth
setup = wiz.model("struct").setup
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
    if method == "GET":
        payload = {"setup": setup.status(include_checks=True)}
    else:
        body = wiz.request.query()
        result = setup.complete(body)
        monitoring_result = None
        local_master = result["local_master"] or {}
        if local_master.get("id"):
            try:
                monitoring_result = monitoring.ensure_exporters({"node_id": local_master["id"], "reporter_base_url": _request_base_url()})
                result["local_master"] = wiz.model("struct").nodes.detail(local_master["id"])
            except Exception as exc:
                monitoring_result = {"status": "failed", "message": str(exc)}
        login_result = auth.login(
            body.get("password", ""),
            remote_addr=request.remote_addr,
            user_agent=request.headers.get("User-Agent"),
            test_run_id=body.get("test_run_id") or request.headers.get("X-Test-Run-ID"),
        )
        wiz.session.set(
            id="operator",
            actor="operator",
            docker_infra_authenticated=True,
            docker_infra_session_token=login_result["session_token"],
        )
        auth.remember_session_cookie(login_result["session_token"], login_result.get("session"))
        payload = {
            "setup": result["setup"],
            "local_master": result["local_master"],
            "monitoring_auto_configure": monitoring_result,
            "authenticated": True,
            "session": login_result["session"],
            "session_policy": auth.session_policy(),
        }
except setup.SetupError as exc:
    code = exc.status_code
    payload = {"message": exc.message, "error_code": exc.error_code, **exc.extra}
except auth.AuthError as exc:
    code = exc.status_code
    payload = {"message": exc.message, "error_code": exc.error_code, **exc.extra}
except RuntimeError as exc:
    code = 503
    payload = {"message": str(exc), "error_code": "DATABASE_UNAVAILABLE"}

wiz.response.status(code, **payload)
