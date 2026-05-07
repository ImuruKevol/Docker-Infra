from flask import request


appearance = wiz.model("struct/appearance")
method = wiz.request.method().upper()

if method != "POST":
    wiz.response.status(405, message="지원하지 않는 method입니다.", error_code="METHOD_NOT_ALLOWED")

kind = request.form.get("kind", "")
file_storage = request.files.get("file")
code = 200
payload = {}

try:
    payload = {"asset": appearance.store_asset(kind, file_storage)}
except ValueError as exc:
    code = 400
    payload = {"message": str(exc), "error_code": "INVALID_ASSET_UPLOAD"}

wiz.response.status(code, **payload)
