import json
from flask import request

assistant = wiz.model("struct").ai_assistant
history = wiz.model("struct").ai_history
method = wiz.request.method().upper()
path = request.path.replace("/api/ai-agent/", "", 1).strip("/")


def stream_events(events):
    flask = wiz.response._flask

    def encode(event):
        try:
            return json.dumps(event, ensure_ascii=False)
        except Exception as exc:
            return json.dumps({
                "type": "error",
                "message": "AI Agent 스트림 이벤트를 직렬화할 수 없습니다: %s" % exc,
                "error_code": "AI_AGENT_STREAM_EVENT_SERIALIZE_FAILED",
            }, ensure_ascii=False)

    def generate():
        yield ": stream-start\n\n"
        try:
            for event in events:
                yield "data: %s\n\n" % encode(event)
            yield ": stream-end\n\n"
        except GeneratorExit:
            return
        except (BrokenPipeError, ConnectionError):
            return
        except Exception as exc:
            yield "data: %s\n\n" % json.dumps({
                "type": "error",
                "message": getattr(exc, "message", str(exc)),
                "error_code": getattr(exc, "code", "AI_AGENT_STREAM_INTERRUPTED"),
            }, ensure_ascii=False)

    response = flask.Response(generate(), mimetype="text/event-stream")
    response.headers["Cache-Control"] = "no-cache"
    response.headers["X-Accel-Buffering"] = "no"
    wiz.response.response(response)


def json_value(value, default):
    if isinstance(value, (dict, list)):
        return value
    if value is None or value == "":
        return default
    try:
        parsed = json.loads(value)
    except Exception:
        return default
    return parsed if isinstance(parsed, type(default)) else default


def request_body():
    body = wiz.request.query()
    return {
        "message": body.get("message") or "",
        "request_id": body.get("request_id") or body.get("idempotency_key") or "",
        "session_id": body.get("session_id") or "",
        "client_session_id": body.get("client_session_id") or "",
        "session_title": body.get("session_title") or "",
        "history": json_value(body.get("history"), []),
        "screen": json_value(body.get("screen"), {}),
        "events": json_value(body.get("events"), []),
        "selection": json_value(body.get("selection"), {}),
        "request_meta": request_metadata(),
    }


def request_metadata():
    forwarded_for = request.headers.get("X-Forwarded-For") or ""
    real_ip = request.headers.get("X-Real-IP") or ""
    remote_addr = request.remote_addr or ""
    ip = (forwarded_for.split(",", 1)[0].strip() if forwarded_for else "") or real_ip or remote_addr
    return {
        "ip": ip,
        "remote_addr": remote_addr,
        "forwarded_for": forwarded_for,
        "user_agent": request.headers.get("User-Agent") or "",
    }


def download_history(body):
    export = history.export(filters=body, export_format=body.get("format") or "json")
    flask = wiz.response._flask
    response = flask.Response(export["content"], content_type=export["content_type"])
    response.headers["Content-Disposition"] = "attachment; filename=\"%s\"" % export["filename"]
    response.headers["Cache-Control"] = "no-store"
    wiz.response.response(response)


code = 200
payload = {}
streamed = False

try:
    if path == "status" and method in ["GET", "POST"]:
        payload = assistant.chat_status()
    elif path == "capabilities" and method in ["GET", "POST"]:
        payload = assistant.openapi_capabilities()
    elif path == "plan" and method == "POST":
        payload = assistant.plan_chat(request_body())
    elif path == "chat" and method == "POST":
        payload = assistant.chat(request_body())
    elif path == "stream" and method == "POST":
        stream_events(assistant.stream_chat(request_body()))
        streamed = True
    elif path == "history" and method in ["GET", "POST"]:
        payload = history.list(filters=wiz.request.query())
    elif path == "history/sessions" and method in ["GET", "POST"]:
        payload = history.sessions(filters=wiz.request.query())
    elif path == "history/download" and method in ["GET", "POST"]:
        download_history(wiz.request.query())
        streamed = True
    elif path == "history/session/delete" and method in ["POST", "DELETE"]:
        body = wiz.request.query()
        payload = history.delete_session(body.get("session_id"), body.get("agent") or body.get("agent_type"))
    elif path == "history/session" and method in ["GET", "POST"]:
        body = wiz.request.query()
        payload = history.session(body.get("session_id"), body.get("agent") or body.get("agent_type"))
    elif path in ["history/delete", "history/delete-range"] and method in ["POST", "DELETE"]:
        body = wiz.request.query()
        if path == "history/delete" and body.get("id"):
            payload = history.delete(body.get("id"))
        else:
            payload = history.delete_range(body)
    elif path.startswith("history/") and method in ["GET", "POST", "DELETE"]:
        parts = [part for part in path.split("/") if part]
        history_id = parts[1] if len(parts) >= 2 else ""
        if len(parts) >= 3 and parts[2] == "delete":
            payload = history.delete(history_id)
        elif method == "DELETE":
            payload = history.delete(history_id)
        elif method == "GET":
            payload = history.detail(history_id)
        else:
            payload = { "message": "AI Agent 히스토리 API 경로를 찾을 수 없습니다.", "error_code": "AI_HISTORY_ROUTE_NOT_FOUND" }
            code = 404
    else:
        code = 404 if method in ["GET", "POST", "DELETE"] else 405
        payload = {"message": "AI Agent API 경로를 찾을 수 없습니다.", "error_code": "AI_AGENT_ROUTE_NOT_FOUND"}
except assistant.AIAssistantError as exc:
    code = exc.status_code
    payload = {"message": exc.message, "error_code": exc.code, "details": exc.details}
except history.AIHistoryError as exc:
    code = exc.status_code
    payload = {"message": exc.message, "error_code": exc.error_code, **exc.extra}
except RuntimeError as exc:
    code = 503
    payload = {"message": str(exc), "error_code": "AI_AGENT_UNAVAILABLE"}

if not streamed:
    wiz.response.status(code, **payload)
