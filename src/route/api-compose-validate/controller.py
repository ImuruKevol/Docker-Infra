validator = wiz.model("struct").compose_validator
method = wiz.request.method().upper()

if method != "POST":
    wiz.response.status(405, message="지원하지 않는 method입니다.", error_code="METHOD_NOT_ALLOWED")

code = 200
payload = {}

try:
    payload = {"validation": validator.validate(wiz.request.query())}
except validator.ComposeValidationError as exc:
    code = exc.status_code
    payload = {
        "message": exc.message,
        "error_code": exc.error_code,
        "details": exc.details,
    }
except RuntimeError as exc:
    code = 503
    payload = {"message": str(exc), "error_code": "COMPOSE_VALIDATION_UNAVAILABLE"}

wiz.response.status(code, **payload)
