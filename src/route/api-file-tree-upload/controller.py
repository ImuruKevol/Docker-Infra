import json

from flask import request


file_tree = wiz.model("struct").file_tree
nodes_model = wiz.model("struct").nodes
method = wiz.request.method().upper()
code = 200
payload = {}

if method != "POST":
    wiz.response.status(405, message="지원하지 않는 method입니다.", error_code="METHOD_NOT_ALLOWED")
else:
    try:
        scope = request.form.get("scope", "")
        destination = request.form.get("destination", ".")
        context = json.loads(request.form.get("context") or "{}")
        files = request.files.getlist("files")
        if not files:
            raise file_tree.FileTreeError(400, "업로드할 파일이 없습니다.", "FILE_TREE_UPLOAD_EMPTY")
        payload = file_tree.upload(scope, context, destination, files)
    except file_tree.FileTreeError as exc:
        code = exc.status_code
        payload = {"message": exc.message, "error_code": exc.error_code, **exc.extra}
    except nodes_model.NodeError as exc:
        code = exc.status_code
        payload = {"message": exc.message, "error_code": exc.error_code, **exc.extra}
    except RuntimeError as exc:
        code = 503
        payload = {"message": str(exc), "error_code": "DATABASE_UNAVAILABLE"}
    except Exception as exc:
        code = 400
        payload = {"message": str(exc), "error_code": "FILE_TREE_UPLOAD_FAILED"}

    wiz.response.status(code, **payload)
