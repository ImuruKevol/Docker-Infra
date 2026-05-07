from flask import request

nodes = wiz.model("struct").nodes
method = wiz.request.method().upper()


def reporter_token():
    authorization = request.headers.get("Authorization", "")
    if authorization.lower().startswith("bearer "):
        return authorization.split(" ", 1)[1].strip()
    return request.headers.get("X-Reporter-Token") or wiz.request.query("reporter_token", None)


if method != "POST":
    wiz.response.status(405, message="지원하지 않는 method입니다.", error_code="METHOD_NOT_ALLOWED")

code = 200
payload = {}

try:
    payload = nodes.ingest_metric(reporter_token(), wiz.request.query())
except nodes.NodeError as exc:
    code = exc.status_code
    payload = {"message": exc.message, "error_code": exc.error_code, **exc.extra}
except RuntimeError as exc:
    code = 503
    payload = {"message": str(exc), "error_code": "DATABASE_UNAVAILABLE"}

wiz.response.status(code, **payload)
