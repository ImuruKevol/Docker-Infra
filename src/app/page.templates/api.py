import json


def _request_payload():
    body = wiz.request.query()
    raw = body.get("payload") if isinstance(body, dict) else None
    if raw:
        return json.loads(raw)
    return body


def _stream_events(events):
    flask = wiz.response._flask

    def generate():
        for event in events:
            yield "data: %s\n\n" % json.dumps(event, ensure_ascii=False)

    resp = flask.Response(generate(), mimetype="text/event-stream")
    resp.headers["Cache-Control"] = "no-cache"
    resp.headers["X-Accel-Buffering"] = "no"
    wiz.response.response(resp)


def load():
    templates_model = wiz.model("struct").templates
    code = 200
    payload = {}

    try:
        payload = templates_model.load()
    except templates_model.TemplateError as exc:
        code = exc.status_code
        payload = {"message": exc.message, "error_code": exc.error_code, **exc.extra}
    except RuntimeError as exc:
        code = 503
        payload = {"message": str(exc), "error_code": "DATABASE_UNAVAILABLE"}

    wiz.response.status(code, **payload)


def detail():
    templates_model = wiz.model("struct").templates
    template_id = str(wiz.request.query().get("template_id") or "").strip()
    if not template_id:
        wiz.response.status(400, message="template_id가 필요합니다.", error_code="TEMPLATE_ID_REQUIRED")
        return

    code = 200
    payload = {}
    try:
        payload = templates_model.detail(template_id)
    except templates_model.TemplateError as exc:
        code = exc.status_code
        payload = {"message": exc.message, "error_code": exc.error_code, **exc.extra}
    except RuntimeError as exc:
        code = 503
        payload = {"message": str(exc), "error_code": "DATABASE_UNAVAILABLE"}

    wiz.response.status(code, **payload)


def save_template():
    templates_model = wiz.model("struct").templates
    code = 200
    payload = {}
    try:
        payload = templates_model.save(wiz.request.query())
    except templates_model.TemplateError as exc:
        code = exc.status_code
        payload = {"message": exc.message, "error_code": exc.error_code, **exc.extra}
    except RuntimeError as exc:
        code = 503
        payload = {"message": str(exc), "error_code": "DATABASE_UNAVAILABLE"}

    wiz.response.status(code, **payload)


def release_template():
    templates_model = wiz.model("struct").templates
    code = 200
    payload = {}
    try:
        payload = templates_model.release(wiz.request.query())
    except templates_model.TemplateError as exc:
        code = exc.status_code
        payload = {"message": exc.message, "error_code": exc.error_code, **exc.extra}
    except RuntimeError as exc:
        code = 503
        payload = {"message": str(exc), "error_code": "DATABASE_UNAVAILABLE"}

    wiz.response.status(code, **payload)


def preview_template():
    templates_model = wiz.model("struct").templates
    code = 200
    payload = {}
    try:
        payload = {"preview": templates_model.preview(wiz.request.query())}
    except templates_model.TemplateError as exc:
        code = exc.status_code
        payload = {"message": exc.message, "error_code": exc.error_code, **exc.extra}
    except RuntimeError as exc:
        code = 503
        payload = {"message": str(exc), "error_code": "DATABASE_UNAVAILABLE"}

    wiz.response.status(code, **payload)


def ai_contract():
    ai_assistant = wiz.model("struct").ai_assistant
    wiz.response.status(200, contract=ai_assistant.template_contract())


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


def generate_template_ai():
    ai_assistant = wiz.model("struct").ai_assistant
    code = 200
    payload = {}
    try:
        payload = ai_assistant.generate_template(wiz.request.query())
    except Exception as exc:
        code = getattr(exc, "status_code", 400)
        payload = {
            "message": getattr(exc, "message", str(exc)),
            "error_code": getattr(exc, "code", "AI_TEMPLATE_GENERATE_FAILED"),
            **getattr(exc, "details", {}),
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


def delete_template():
    templates_model = wiz.model("struct").templates
    template_id = str(wiz.request.query().get("template_id") or "").strip()
    if not template_id:
        wiz.response.status(400, message="template_id가 필요합니다.", error_code="TEMPLATE_ID_REQUIRED")
        return

    code = 200
    payload = {}
    try:
        templates_model.delete(template_id)
        payload = {"deleted": True}
    except templates_model.TemplateError as exc:
        code = exc.status_code
        payload = {"message": exc.message, "error_code": exc.error_code, **exc.extra}
    except RuntimeError as exc:
        code = 503
        payload = {"message": str(exc), "error_code": "DATABASE_UNAVAILABLE"}

    wiz.response.status(code, **payload)


def version_detail():
    templates_model = wiz.model("struct").templates
    version_id = str(wiz.request.query().get("version_id") or "").strip()
    if not version_id:
        wiz.response.status(400, message="version_id가 필요합니다.", error_code="TEMPLATE_VERSION_ID_REQUIRED")
        return

    code = 200
    payload = {}
    try:
        payload = templates_model.version_detail(version_id)
    except templates_model.TemplateError as exc:
        code = exc.status_code
        payload = {"message": exc.message, "error_code": exc.error_code, **exc.extra}
    except RuntimeError as exc:
        code = 503
        payload = {"message": str(exc), "error_code": "DATABASE_UNAVAILABLE"}

    wiz.response.status(code, **payload)
