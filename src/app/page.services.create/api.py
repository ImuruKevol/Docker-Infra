import secrets
import string

import yaml


SECRET_ALPHABET = string.ascii_letters + string.digits


def _random_secret(length=28):
    return "".join(secrets.choice(SECRET_ALPHABET) for _ in range(length))


def _apply_runtime_template_values(templates_model, payload):
    template = payload.get("template") or {}
    metadata = template.get("metadata") or {}
    generated = [str(key) for key in metadata.get("generated_secrets") or [] if str(key)]
    if not generated:
        return payload
    files = payload.get("files") or {}
    values = yaml.safe_load(files.get("values.default.yaml") or "{}") or {}
    for key in generated:
        values[key] = _random_secret()
    payload["preview"] = templates_model.preview({
        "namespace": template.get("namespace"),
        "compose": files.get("docker-compose.yaml") or "",
        "values_default": yaml.safe_dump(values, sort_keys=False, allow_unicode=False),
    })
    payload["generated_secret_keys"] = generated
    return payload


def load():
    templates_model = wiz.model("struct").templates
    domains_model = wiz.model("struct").domains
    webserver = wiz.model("struct/webserver")
    code = 200
    payload = {}
    try:
        zones = []
        for zone in domains_model.load().get("zones", []):
            if zone.get("usable_for_service") is False or zone.get("enabled") is False:
                continue
            certs = webserver.certificates_for_domain(zone.get("domain"), zone_id=zone.get("id"))
            zones.append({**zone, "certificate_summary": certs.get("summary") or {}})
        payload = {
            "templates": templates_model.load().get("templates", []),
            "zones": zones,
        }
    except RuntimeError as exc:
        code = 503
        payload = {"message": str(exc), "error_code": "DATABASE_UNAVAILABLE"}
    wiz.response.status(code, **payload)


def template_detail():
    templates_model = wiz.model("struct").templates
    wizard = wiz.model("struct").services_wizard
    template_id = str(wiz.request.query().get("template_id") or "").strip()
    if not template_id:
        wiz.response.status(400, message="template_id가 필요합니다.", error_code="TEMPLATE_ID_REQUIRED")
        return
    code = 200
    payload = {}
    try:
        payload = templates_model.detail(template_id)
        payload = _apply_runtime_template_values(templates_model, payload)
        metadata = (payload.get("template") or {}).get("metadata") or {}
        content = payload.get("preview", {}).get("rendered_compose") or payload.get("files", {}).get("docker-compose.yaml") or ""
        payload["components"] = wizard.components_from_content(content, metadata=metadata)
    except templates_model.TemplateError as exc:
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
