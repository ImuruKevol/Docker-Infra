executor = wiz.model("struct").local_executor
method = wiz.request.method().upper()

if method not in ["GET", "POST"]:
    wiz.response.status(405, message="지원하지 않는 method입니다.", error_code="METHOD_NOT_ALLOWED")

body = wiz.request.query()
code = 200
payload = {}

try:
    payload = {
        "result": executor.check(
            target=body.get("target") or body.get("command_id") or "docker.version",
            timeout_seconds=body.get("timeout_seconds"),
            params=body.get("params") or {},
        )
    }
except executor.LocalCommandError as exc:
    code = exc.status_code
    payload = {"message": exc.message, "error_code": exc.error_code, **exc.extra}
except RuntimeError as exc:
    code = 503
    payload = {"message": str(exc), "error_code": "LOCAL_COMMAND_UNAVAILABLE"}

wiz.response.status(code, **payload)
