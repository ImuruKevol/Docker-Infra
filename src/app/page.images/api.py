def load():
    images_model = wiz.model("struct").images
    code = 200
    payload = {}

    try:
        payload = images_model.load()
    except images_model.ImageError as exc:
        code = exc.status_code
        payload = {"message": exc.message, "error_code": exc.error_code, **exc.extra}
    except RuntimeError as exc:
        code = 503
        payload = {"message": str(exc), "error_code": "DATABASE_UNAVAILABLE"}

    wiz.response.status(code, **payload)


def harbor_detail():
    images_model = wiz.model("struct").images
    project_name = str(wiz.request.query().get("project_name") or "").strip()
    if not project_name:
        wiz.response.status(400, message="project_name이 필요합니다.", error_code="HARBOR_PROJECT_REQUIRED")
        return

    code = 200
    payload = {}
    try:
        payload = images_model.harbor_project_detail(project_name)
    except images_model.ImageError as exc:
        code = exc.status_code
        payload = {"message": exc.message, "error_code": exc.error_code, **exc.extra}
    except RuntimeError as exc:
        code = 503
        payload = {"message": str(exc), "error_code": "DATABASE_UNAVAILABLE"}

    wiz.response.status(code, **payload)


def harbor_overview():
    images_model = wiz.model("struct").images
    code = 200
    payload = {}
    try:
        payload = images_model.harbor_overview()
    except images_model.ImageError as exc:
        code = exc.status_code
        payload = {"message": exc.message, "error_code": exc.error_code, **exc.extra}
    except RuntimeError as exc:
        code = 503
        payload = {"message": str(exc), "error_code": "DATABASE_UNAVAILABLE"}

    wiz.response.status(code, **payload)


def local_detail():
    images_model = wiz.model("struct").images
    node_id = str(wiz.request.query().get("node_id") or "").strip()
    if not node_id:
        wiz.response.status(400, message="node_id가 필요합니다.", error_code="NODE_ID_REQUIRED")
        return

    code = 200
    payload = {}
    try:
        payload = images_model.local_node_detail(node_id)
    except images_model.ImageError as exc:
        code = exc.status_code
        payload = {"message": exc.message, "error_code": exc.error_code, **exc.extra}
    except RuntimeError as exc:
        code = 503
        payload = {"message": str(exc), "error_code": "DATABASE_UNAVAILABLE"}

    wiz.response.status(code, **payload)


def delete_harbor():
    images_model = wiz.model("struct").images
    code = 200
    payload = {}
    try:
        payload = images_model.delete_harbor_artifact(wiz.request.query())
    except images_model.ImageError as exc:
        code = exc.status_code
        payload = {"message": exc.message, "error_code": exc.error_code, **exc.extra}
    except RuntimeError as exc:
        code = 503
        payload = {"message": str(exc), "error_code": "DATABASE_UNAVAILABLE"}

    wiz.response.status(code, **payload)


def delete_harbor_project():
    images_model = wiz.model("struct").images
    code = 200
    payload = {}
    try:
        payload = images_model.delete_harbor_project(wiz.request.query())
    except images_model.ImageError as exc:
        code = exc.status_code
        payload = {"message": exc.message, "error_code": exc.error_code, **exc.extra}
    except RuntimeError as exc:
        code = 503
        payload = {"message": str(exc), "error_code": "DATABASE_UNAVAILABLE"}

    wiz.response.status(code, **payload)


def delete_local():
    images_model = wiz.model("struct").images
    code = 200
    payload = {}
    try:
        payload = images_model.delete_local_image(wiz.request.query())
    except images_model.ImageError as exc:
        code = exc.status_code
        payload = {"message": exc.message, "error_code": exc.error_code, **exc.extra}
    except RuntimeError as exc:
        code = 503
        payload = {"message": str(exc), "error_code": "DATABASE_UNAVAILABLE"}

    wiz.response.status(code, **payload)
