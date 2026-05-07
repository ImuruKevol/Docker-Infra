from flask import request

auth = wiz.model("struct").auth
setup = wiz.model("struct").setup
method = wiz.request.method().upper()

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
        payload = {
            "setup": result["setup"],
            "local_master": result["local_master"],
            "authenticated": True,
            "session": login_result["session"],
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
