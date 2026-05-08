from flask import request

nodes = wiz.model("struct").nodes
method = wiz.request.method().upper()
parts = [part for part in request.path.replace("/api/nodes/", "", 1).split("/") if part]

if not parts:
    wiz.response.status(404, message="node path를 찾을 수 없습니다.", error_code="NODE_PATH_NOT_FOUND")

node_id = parts[0]
code = 200
payload = {}

try:
    if len(parts) == 1:
        if method != "GET":
            code = 405
            payload = {"message": "지원하지 않는 method입니다.", "error_code": "METHOD_NOT_ALLOWED"}
        else:
            payload = {"node": nodes.detail(node_id)}
    else:
        action = parts[1]
        if action == "check" and method == "POST":
            payload = nodes.check_slave(node_id)
        elif action == "reporter-token" and method == "POST":
            payload = nodes.issue_reporter_token(node_id)
        elif action == "metrics" and method == "GET":
            payload = {
                "metrics": nodes.metrics(node_id, limit=wiz.request.query("limit", 50)),
                "latest_metric": nodes.latest_metric(node_id),
            }
        elif action == "containers" and method == "GET":
            payload = nodes.containers(node_id)
        elif action == "join" and method == "POST":
            payload = nodes.join_slave(node_id, wiz.request.query())
        else:
            code = 404
            payload = {"message": "node action을 찾을 수 없습니다.", "error_code": "NODE_ACTION_NOT_FOUND"}
except nodes.NodeError as exc:
    code = exc.status_code
    payload = {"message": exc.message, "error_code": exc.error_code, **exc.extra}
except nodes.LocalCommandError as exc:
    code = exc.status_code
    payload = {"message": exc.message, "error_code": exc.error_code, **exc.extra}
except RuntimeError as exc:
    code = 503
    payload = {"message": str(exc), "error_code": "DATABASE_UNAVAILABLE"}

wiz.response.status(code, **payload)
