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


def load():
    domains_model = wiz.model("struct").domains
    webserver = wiz.model("struct/webserver")
    code = 200
    payload = {}
    try:
        zones = []
        for zone in domains_model.service_options().get("zones", []):
            if zone.get("provider") == "ddns":
                zones.append(zone)
                continue
            certs = webserver.certificates_for_domain(zone.get("domain"), zone_id=zone.get("id"))
            zones.append({**zone, "certificate_summary": certs.get("summary") or {}})
        payload = {"zones": zones}
    except RuntimeError as exc:
        code = 503
        payload = {"message": str(exc), "error_code": "DATABASE_UNAVAILABLE"}
    wiz.response.status(code, **payload)


def prepare_compose_draft():
    wizard = wiz.model("struct").services_wizard
    body = wiz.request.query()
    code = 200
    payload = {}
    try:
        payload = wizard.prepare_manual(body)
    except wizard.ComposeValidationError as exc:
        code = exc.status_code
        payload = {"message": exc.message, "error_code": exc.error_code, "details": exc.details}
    except wizard.ServiceError as exc:
        code = exc.status_code
        payload = {"message": exc.message, "error_code": exc.error_code, **exc.extra}
    except RuntimeError as exc:
        code = 503
        payload = {"message": str(exc), "error_code": "DATABASE_UNAVAILABLE"}
    wiz.response.status(code, **payload)


def load_import():
    nodes_model = wiz.model("struct").nodes
    wizard = wiz.model("struct").services_wizard
    body = wiz.request.query()
    node_id = body.get("node_id")
    path = body.get("path")
    if not node_id:
        wiz.response.status(400, message="node_id는 필수입니다.", error_code="NODE_ID_REQUIRED")
        return
    if not path:
        wiz.response.status(400, message="path는 필수입니다.", error_code="NODE_PATH_REQUIRED")
        return

    code = 200
    payload = {}
    try:
        filename = str(path).split("/")[-1] or "docker-compose.yaml"
        content = nodes_model.read_file_text(node_id, path)
        payload = wizard.prepare_import({
            "node_id": node_id,
            "path": path,
            "source_path": path,
            "filename": filename,
            "content": content,
            "suggested_name": body.get("suggested_name"),
        })
    except nodes_model.NodeError as exc:
        code = exc.status_code
        payload = {"message": exc.message, "error_code": exc.error_code, **exc.extra}
    except wizard.ComposeValidationError as exc:
        code = exc.status_code
        payload = {"message": exc.message, "error_code": exc.error_code, "details": exc.details}
    except wizard.ServiceError as exc:
        code = exc.status_code
        payload = {"message": exc.message, "error_code": exc.error_code, **exc.extra}
    except RuntimeError as exc:
        code = 503
        payload = {"message": str(exc), "error_code": "DATABASE_UNAVAILABLE"}
    except Exception as exc:
        code = 400
        payload = {"message": str(exc), "error_code": "SERVICE_IMPORT_LOAD_FAILED"}
    wiz.response.status(code, **payload)


def check_image():
    wizard = wiz.model("struct").services_wizard
    body = wiz.request.query()
    wiz.response.status(200, **wizard.check_image(body.get("image_ref")))


def ai_contract():
    ai_assistant = wiz.model("struct").ai_assistant
    wiz.response.status(200, contract=ai_assistant.service_contract())


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


def generate_service_ai():
    ai_assistant = wiz.model("struct").ai_assistant
    code = 200
    payload = {}
    try:
        payload = ai_assistant.generate_service(wiz.request.query())
    except Exception as exc:
        code = getattr(exc, "status_code", 400)
        payload = {
            "message": getattr(exc, "message", str(exc)),
            "error_code": getattr(exc, "code", "AI_SERVICE_GENERATE_FAILED"),
            **getattr(exc, "details", {}),
        }
    wiz.response.status(code, **payload)


def stream_service_ai():
    ai_assistant = wiz.model("struct").ai_assistant
    try:
        payload = _request_payload()
        events = ai_assistant.stream_service(payload)
    except Exception as exc:
        events = [{
            "type": "error",
            "message": getattr(exc, "message", str(exc)),
            "error_code": getattr(exc, "code", "AI_SERVICE_STREAM_FAILED"),
        }]
    _stream_events(events)


def preflight():
    wizard = wiz.model("struct").services_wizard
    code = 200
    payload = {}
    try:
        result = wizard.preflight(wiz.request.query())
        payload = {"namespace": result.get("namespace"), "preflight": result.get("preflight")}
    except wizard.ServiceError as exc:
        code = exc.status_code
        payload = {"message": exc.message, "error_code": exc.error_code, **exc.extra}
    except wizard.ComposeValidationError as exc:
        code = exc.status_code
        payload = {"message": exc.message, "error_code": exc.error_code, "details": exc.details}
    except RuntimeError as exc:
        code = 503
        payload = {"message": str(exc), "error_code": "DATABASE_UNAVAILABLE"}
    except Exception as exc:
        code = 400
        payload = {"message": str(exc), "error_code": "SERVICE_PREFLIGHT_FAILED"}
    wiz.response.status(code, **payload)


def create_service():
    wizard = wiz.model("struct").services_wizard
    code = 200
    payload = {}
    try:
        result = wizard.create(wiz.request.query())
        payload = {"result": result}
    except Exception as exc:
        code = getattr(exc, "status_code", 400)
        payload = {
            "message": getattr(exc, "message", str(exc)),
            "error_code": getattr(exc, "error_code", "SERVICE_CREATE_FAILED"),
            **getattr(exc, "extra", {}),
        }
    wiz.response.status(code, **payload)


def deploy_service():
    services_model = wiz.model("struct").services
    code = 200
    payload = {}
    try:
        result = services_model.deploy(wiz.request.query())
        payload = {"result": result}
    except services_model.ServiceError as exc:
        code = exc.status_code
        payload = {"message": exc.message, "error_code": exc.error_code, **exc.extra}
    except RuntimeError as exc:
        code = 503
        payload = {"message": str(exc), "error_code": "DATABASE_UNAVAILABLE"}
    wiz.response.status(code, **payload)


def deploy_service_background():
    services_model = wiz.model("struct").services
    code = 202
    payload = {}
    try:
        result = services_model.deploy_background(wiz.request.query())
        payload = {"result": result}
    except services_model.ServiceError as exc:
        code = exc.status_code
        payload = {"message": exc.message, "error_code": exc.error_code, **exc.extra}
    except RuntimeError as exc:
        code = 503
        payload = {"message": str(exc), "error_code": "DATABASE_UNAVAILABLE"}
    wiz.response.status(code, **payload)
