from flask import request


schedules = wiz.model("struct/macro_schedules")
method = wiz.request.method().upper()


def request_token():
    authorization = request.headers.get("Authorization", "")
    if authorization.lower().startswith("bearer "):
        return authorization.split(" ", 1)[1].strip()
    return request.headers.get(schedules.CRON_TOKEN_HEADER) or wiz.request.query("cron_token", None)


code = 202
payload = {}

try:
    schedule_id = wiz.request.query("schedule_id", None)
    if method != "POST":
        raise schedules.MacroError(405, "지원하지 않는 method입니다.", "METHOD_NOT_ALLOWED")
    if not schedules.request_allowed(request):
        raise schedules.MacroError(403, "로컬 매크로 스케줄 요청만 허용됩니다.", "CRON_REQUEST_FORBIDDEN")
    if not schedules.verify_token(schedule_id, request_token()):
        raise schedules.MacroError(401, "매크로 스케줄 cron 토큰이 올바르지 않습니다.", "INVALID_CRON_TOKEN")
    payload = schedules.run(schedule_id)
    code = 202 if payload.get("scheduled") else 200
except schedules.MacroError as exc:
    code = exc.status_code
    payload = {"message": exc.message, "error_code": exc.error_code, **exc.extra}
except RuntimeError as exc:
    code = 503
    payload = {"message": str(exc), "error_code": "DATABASE_UNAVAILABLE"}
except Exception as exc:
    code = getattr(exc, "status_code", 500)
    payload = {
        "message": getattr(exc, "message", str(exc)),
        "error_code": getattr(exc, "error_code", "MACRO_SCHEDULE_RUN_FAILED"),
        **(getattr(exc, "extra", {}) or {}),
    }

wiz.response.status(code, **payload)
