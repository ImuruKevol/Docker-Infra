def load():
    catalog = wiz.model("struct/infra_catalog_registry")
    templates_model = wiz.model("struct").templates
    code = 200
    payload = {}

    try:
        payload = catalog.services()
        payload["templates"] = templates_model.load().get("templates", [])
    except RuntimeError as exc:
        code = 503
        payload = {"message": str(exc), "error_code": "DATABASE_UNAVAILABLE"}

    wiz.response.status(code, **payload)


def validate_compose():
    validator = wiz.model("struct").compose_validator
    code = 200
    payload = {}

    try:
        payload = {"validation": validator.validate(wiz.request.query())}
    except validator.ComposeValidationError as exc:
        code = exc.status_code
        payload = {"message": exc.message, "error_code": exc.error_code, "details": exc.details}
    except RuntimeError as exc:
        code = 503
        payload = {"message": str(exc), "error_code": "DATABASE_UNAVAILABLE"}

    wiz.response.status(code, **payload)


def template_detail():
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


def create_service():
    services_model = wiz.model("struct").services
    catalog = wiz.model("struct/infra_catalog_registry")
    code = 200
    payload = {}

    try:
        result = services_model.create(wiz.request.query())
        payload = {"result": result, **catalog.services()}
    except services_model.ComposeValidationError as exc:
        code = exc.status_code
        payload = {"message": exc.message, "error_code": exc.error_code, "details": exc.details}
    except services_model.ServiceError as exc:
        code = exc.status_code
        payload = {"message": exc.message, "error_code": exc.error_code, **exc.extra}
    except RuntimeError as exc:
        code = 503
        payload = {"message": str(exc), "error_code": "DATABASE_UNAVAILABLE"}

    wiz.response.status(code, **payload)


def detail_service():
    services_model = wiz.model("struct").services
    body = wiz.request.query()
    service_id = body.get("service_id")
    if not service_id:
        wiz.response.status(400, message="service_id는 필수입니다.", error_code="SERVICE_ID_REQUIRED")
        return

    code = 200
    payload = {}
    try:
        payload = services_model.detail(service_id)
    except services_model.ServiceError as exc:
        code = exc.status_code
        payload = {"message": exc.message, "error_code": exc.error_code, **exc.extra}
    except RuntimeError as exc:
        code = 503
        payload = {"message": str(exc), "error_code": "DATABASE_UNAVAILABLE"}

    wiz.response.status(code, **payload)


def browse_files():
    services_model = wiz.model("struct").services
    body = wiz.request.query()
    service_id = body.get("service_id")
    if not service_id:
        wiz.response.status(400, message="service_id는 필수입니다.", error_code="SERVICE_ID_REQUIRED")
        return

    code = 200
    payload = {}
    try:
        payload = services_model.browse_files(service_id, body.get("path"))
    except services_model.ServiceError as exc:
        code = exc.status_code
        payload = {"message": exc.message, "error_code": exc.error_code, **exc.extra}
    except RuntimeError as exc:
        code = 503
        payload = {"message": str(exc), "error_code": "DATABASE_UNAVAILABLE"}

    wiz.response.status(code, **payload)


def read_file():
    services_model = wiz.model("struct").services
    body = wiz.request.query()
    service_id = body.get("service_id")
    path = body.get("path")
    if not service_id:
        wiz.response.status(400, message="service_id는 필수입니다.", error_code="SERVICE_ID_REQUIRED")
        return
    if not path:
        wiz.response.status(400, message="path는 필수입니다.", error_code="SERVICE_FILE_PATH_REQUIRED")
        return

    code = 200
    payload = {}
    try:
        payload = services_model.read_file(service_id, path)
    except services_model.ServiceError as exc:
        code = exc.status_code
        payload = {"message": exc.message, "error_code": exc.error_code, **exc.extra}
    except RuntimeError as exc:
        code = 503
        payload = {"message": str(exc), "error_code": "DATABASE_UNAVAILABLE"}

    wiz.response.status(code, **payload)
