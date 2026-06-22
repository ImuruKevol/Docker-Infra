from flask import request


cron = wiz.model("struct/backup_system_cron")
backup_tick = wiz.model("struct/service_image_backup_tick")
method = wiz.request.method().upper()


def request_token():
    authorization = request.headers.get("Authorization", "")
    if authorization.lower().startswith("bearer "):
        return authorization.split(" ", 1)[1].strip()
    return request.headers.get("X-Docker-Infra-Cron-Token") or wiz.request.query("cron_token", None)


code = 202
payload = {}

try:
    if method != "POST":
        raise cron.CronError(405, "지원하지 않는 method입니다.", "METHOD_NOT_ALLOWED")
    if not cron.request_allowed(request):
        raise cron.CronError(403, "로컬 자동 백업 요청만 허용됩니다.", "CRON_REQUEST_FORBIDDEN")
    if not cron.verify_token(request_token()):
        raise cron.CronError(401, "자동 백업 cron 토큰이 올바르지 않습니다.", "INVALID_CRON_TOKEN")
    payload = backup_tick.tick()
    code = 202 if payload.get("scheduled") else 200
except cron.CronError as exc:
    code = exc.status_code
    payload = {"message": exc.message, "error_code": exc.error_code, **exc.extra}
except RuntimeError as exc:
    code = 503
    payload = {"message": str(exc), "error_code": "DATABASE_UNAVAILABLE"}
except Exception as exc:
    code = getattr(exc, "status_code", 500)
    payload = {
        "message": getattr(exc, "message", str(exc)),
        "error_code": getattr(exc, "error_code", "BACKUP_TICK_FAILED"),
        **(getattr(exc, "extra", {}) or {}),
    }

wiz.response.status(code, **payload)
