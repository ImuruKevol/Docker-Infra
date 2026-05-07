settings = wiz.model("struct").settings
method = wiz.request.method().upper()


def as_bool(value):
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.lower() in ["1", "true", "yes", "on"]
    return bool(value)


if method not in ["GET", "POST", "PUT", "PATCH", "DELETE"]:
    wiz.response.status(405, message="지원하지 않는 method입니다.", error_code="METHOD_NOT_ALLOWED")

code = 200
payload = {}

try:
    if method == "GET":
        key = wiz.request.query("key", None)
        if key:
            setting = settings.get(key)
            if setting is None:
                code = 404
                payload = {"message": "설정을 찾을 수 없습니다.", "error_code": "SETTING_NOT_FOUND"}
            else:
                payload = {"setting": setting}
        else:
            payload = {"settings": settings.list(test_run_id=wiz.request.query("test_run_id", None))}
    elif method in ["POST", "PUT", "PATCH"]:
        body = wiz.request.query()
        key = body.get("key")
        if not key:
            code = 400
            payload = {"message": "key는 필수입니다.", "error_code": "SETTING_KEY_REQUIRED"}
        else:
            payload = {
                "setting": settings.upsert(
                    key=key,
                    value=body.get("value"),
                    value_type=body.get("value_type", "string"),
                    is_secret=as_bool(body.get("is_secret", False)),
                    description=body.get("description"),
                    test_run_id=body.get("test_run_id"),
                    metadata=body.get("metadata") or {},
                )
            }
    else:
        key = wiz.request.query("key", None)
        if not key:
            code = 400
            payload = {"message": "key는 필수입니다.", "error_code": "SETTING_KEY_REQUIRED"}
        else:
            payload = {"deleted": settings.delete(key)}
except RuntimeError as exc:
    code = 503
    payload = {"message": str(exc), "error_code": "DATABASE_UNAVAILABLE"}

wiz.response.status(code, **payload)
