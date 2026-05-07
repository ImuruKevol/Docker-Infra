from pathlib import Path

from flask import Response, request


appearance = wiz.model("struct/appearance")
method = wiz.request.method().upper()

if method != "GET":
    wiz.response.status(405, message="지원하지 않는 method입니다.", error_code="METHOD_NOT_ALLOWED")

relative_path = request.path.replace("/api/system/assets/", "", 1)
asset = None
code = 200
payload = None

try:
    asset = appearance.resolve_asset(relative_path)
except FileNotFoundError:
    code = 404
    payload = {"message": "asset 파일을 찾을 수 없습니다.", "error_code": "ASSET_NOT_FOUND"}

if asset is not None:
    wiz.response.response(Response(Path(asset["path"]).read_bytes(), mimetype=asset["content_type"]))
else:
    wiz.response.status(code, **payload)
