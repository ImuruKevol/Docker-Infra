auth = wiz.model("struct").auth
method = wiz.request.method().upper()

if method not in ["GET", "DELETE"]:
    wiz.response.status(405, message="지원하지 않는 method입니다.", error_code="METHOD_NOT_ALLOWED")

code = 200
payload = {}
token = wiz.session.get("docker_infra_session_token", None)

try:
    if method == "GET":
        current = auth.current_session(token)
        payload = {"authenticated": current["authenticated"], "session": current["session"]}
    else:
        payload = {"authenticated": False, "revoked": auth.logout(token)}
        wiz.session.clear()
except RuntimeError as exc:
    code = 503
    payload = {"message": str(exc), "error_code": "DATABASE_UNAVAILABLE"}
    if method == "DELETE":
        wiz.session.clear()

wiz.response.status(code, **payload)
