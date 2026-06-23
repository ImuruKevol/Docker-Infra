from flask import request

auth = wiz.model("struct").auth
method = wiz.request.method().upper()

if method != "POST":
    wiz.response.status(405, message="지원하지 않는 method입니다.", error_code="METHOD_NOT_ALLOWED")

body = wiz.request.query()
code = 200
payload = {}

try:
    result = auth.login(
        body.get("password", ""),
        remote_addr=request.remote_addr,
        user_agent=request.headers.get("User-Agent"),
        test_run_id=body.get("test_run_id") or request.headers.get("X-Test-Run-ID"),
    )
    wiz.session.set(
        id="operator",
        actor="operator",
        docker_infra_authenticated=True,
        docker_infra_session_token=result["session_token"],
    )
    auth.remember_session_cookie(result["session_token"], result.get("session"))
    payload = {
        "authenticated": True,
        "session": result["session"],
        "session_policy": auth.session_policy(),
    }
except auth.AuthError as exc:
    code = exc.status_code
    payload = {"message": exc.message, "error_code": exc.error_code, **exc.extra}
except RuntimeError as exc:
    code = 503
    payload = {"message": str(exc), "error_code": "DATABASE_UNAVAILABLE"}

wiz.response.status(code, **payload)
