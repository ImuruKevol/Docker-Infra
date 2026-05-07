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
