file_tree = wiz.model("struct").file_tree
nodes_model = wiz.model("struct").nodes
method = wiz.request.method().upper()
code = 200
payload = {}

if method != "POST":
    wiz.response.status(405, message="지원하지 않는 method입니다.", error_code="METHOD_NOT_ALLOWED")
else:
    try:
        body = wiz.request.query()
        action = str(body.get("action") or "list").strip().lower()
        if action == "list":
            payload = file_tree.list(body)
        elif action == "read":
            payload = file_tree.read(body)
        elif action == "download":
            payload = file_tree.download(body)
        else:
            payload = file_tree.mutate(body)
    except file_tree.FileTreeError as exc:
        code = exc.status_code
        payload = {"message": exc.message, "error_code": exc.error_code, **exc.extra}
    except nodes_model.NodeError as exc:
        code = exc.status_code
        payload = {"message": exc.message, "error_code": exc.error_code, **exc.extra}
    except RuntimeError as exc:
        code = 503
        payload = {"message": str(exc), "error_code": "DATABASE_UNAVAILABLE"}

    wiz.response.status(code, **payload)
