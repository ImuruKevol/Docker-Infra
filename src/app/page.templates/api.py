import json


def _request_payload():
    body = wiz.request.query()
    raw = body.get("payload") if isinstance(body, dict) else None
    if raw:
        return json.loads(raw)
    return body


def _stream_events(events):
    flask = wiz.response._flask

    def encode(event):
        try:
            return json.dumps(event, ensure_ascii=False)
        except Exception as exc:
            return json.dumps({
                "type": "error",
                "message": "AI 스트림 이벤트를 직렬화할 수 없습니다: %s" % exc,
                "error_code": "AI_STREAM_EVENT_SERIALIZE_FAILED",
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
                "error_code": getattr(exc, "code", "AI_STREAM_INTERRUPTED"),
            }, ensure_ascii=False)

    resp = flask.Response(generate(), mimetype="text/event-stream")
    resp.headers["Cache-Control"] = "no-cache"
    resp.headers["X-Accel-Buffering"] = "no"
    wiz.response.response(resp)


def _template_response(callable_fn, *args, **kwargs):
    templates_model = wiz.model("struct").templates
    code = 200
    payload = {}
    try:
        payload = callable_fn(*args, **kwargs)
    except templates_model.TemplateError as exc:
        code = exc.status_code
        payload = {"message": exc.message, "error_code": exc.error_code, **exc.extra}
    except templates_model.ComposeValidationError as exc:
        code = exc.status_code
        payload = {"message": exc.message, "error_code": exc.error_code, "details": exc.details}
    except RuntimeError as exc:
        code = 503
        payload = {"message": str(exc), "error_code": "DATABASE_UNAVAILABLE"}
    except Exception as exc:
        code = getattr(exc, "status_code", 400)
        payload = {
            "message": getattr(exc, "message", str(exc)),
            "error_code": getattr(exc, "error_code", "TEMPLATE_API_FAILED"),
            **getattr(exc, "extra", {}),
        }
    wiz.response.status(code, **payload)


def load():
    templates_model = wiz.model("struct").templates
    _template_response(templates_model.load_summaries)


def detail():
    templates_model = wiz.model("struct").templates
    body = wiz.request.query()
    template_id = body.get("template_id") or body.get("id")
    if not template_id:
        wiz.response.status(400, message="template_id가 필요합니다.", error_code="TEMPLATE_ID_REQUIRED")
        return
    _template_response(templates_model.detail, template_id)


def save_template():
    templates_model = wiz.model("struct").templates
    _template_response(templates_model.save, wiz.request.query())


def delete_template():
    templates_model = wiz.model("struct").templates
    body = wiz.request.query()
    template_id = body.get("template_id") or body.get("id")
    if not template_id:
        wiz.response.status(400, message="template_id가 필요합니다.", error_code="TEMPLATE_ID_REQUIRED")
        return
    _template_response(templates_model.delete, template_id)


def preview_template():
    templates_model = wiz.model("struct").templates
    _template_response(templates_model.preview, wiz.request.query())


def ai_model_options():
    ai_assistant = wiz.model("struct").ai_assistant
    code = 200
    payload = {}
    try:
        payload = ai_assistant.model_options()
    except Exception as exc:
        code = getattr(exc, "status_code", 400)
        payload = {
            "message": getattr(exc, "message", str(exc)),
            "error_code": getattr(exc, "code", "AI_MODEL_OPTIONS_FAILED"),
        }
    wiz.response.status(code, **payload)


def ai_contract():
    ai_assistant = wiz.model("struct").ai_assistant
    code = 200
    payload = {}
    try:
        payload = {"contract": ai_assistant.template_contract()}
    except Exception as exc:
        code = getattr(exc, "status_code", 400)
        payload = {
            "message": getattr(exc, "message", str(exc)),
            "error_code": getattr(exc, "code", "AI_TEMPLATE_CONTRACT_FAILED"),
        }
    wiz.response.status(code, **payload)



def stream_template_ai():
    ai_assistant = wiz.model("struct").ai_assistant
    try:
        payload = _request_payload()
        events = ai_assistant.stream_template(payload)
    except Exception as exc:
        events = [{
            "type": "error",
            "message": getattr(exc, "message", str(exc)),
            "error_code": getattr(exc, "code", "AI_TEMPLATE_STREAM_FAILED"),
        }]
    _stream_events(events)
