auth = wiz.model("struct").auth
method = wiz.request.method().upper()

if method not in ["POST", "DELETE"]:
    wiz.response.status(405, message="지원하지 않는 method입니다.", error_code="METHOD_NOT_ALLOWED")

code = 200
payload = {}
token = wiz.session.get("docker_infra_session_token", None)

try:
    payload = {"authenticated": False, "revoked": auth.logout(token)}
except RuntimeError as exc:
    code = 503
    payload = {"message": str(exc), "error_code": "DATABASE_UNAVAILABLE"}

wiz.session.clear()
wiz.response.status(code, **payload)
