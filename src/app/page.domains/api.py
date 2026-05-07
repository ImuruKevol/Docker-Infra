def load():
    domains = wiz.model("struct").domains
    code = 200
    payload = {}
    try:
        payload = domains.load()
    except RuntimeError as exc:
        code = 503
        payload = {"message": str(exc), "error_code": "DATABASE_UNAVAILABLE"}
    wiz.response.status(code, **payload)


def detail():
    domains = wiz.model("struct").domains
    body = wiz.request.query()
    code = 200
    payload = {}
    try:
        payload = domains.detail(body.get("zone_id"))
    except domains.DomainError as exc:
        code = exc.status_code
        payload = {"message": exc.message, "error_code": exc.error_code, **exc.extra}
    except RuntimeError as exc:
        code = 503
        payload = {"message": str(exc), "error_code": "DATABASE_UNAVAILABLE"}
    wiz.response.status(code, **payload)


def save_zone():
    domains = wiz.model("struct").domains
    body = wiz.request.query()
    code = 200
    payload = {}
    try:
        payload = {"zone": domains.save_zone(body, test_run_id=body.get("test_run_id"))}
    except domains.DomainError as exc:
        code = exc.status_code
        payload = {"message": exc.message, "error_code": exc.error_code, **exc.extra}
    except RuntimeError as exc:
        code = 503
        payload = {"message": str(exc), "error_code": "DATABASE_UNAVAILABLE"}
    wiz.response.status(code, **payload)


def delete_zone():
    domains = wiz.model("struct").domains
    body = wiz.request.query()
    code = 200
    payload = {}
    try:
        payload = domains.delete_zone(body.get("zone_id") or body.get("id"))
    except domains.DomainError as exc:
        code = exc.status_code
        payload = {"message": exc.message, "error_code": exc.error_code, **exc.extra}
    except RuntimeError as exc:
        code = 503
        payload = {"message": str(exc), "error_code": "DATABASE_UNAVAILABLE"}
    wiz.response.status(code, **payload)


def sync_zone():
    domains = wiz.model("struct").domains
    body = wiz.request.query()
    code = 200
    payload = {}
    try:
        payload = domains.sync_zone(body.get("zone_id") or body.get("id"))
    except domains.DomainError as exc:
        code = exc.status_code
        payload = {"message": exc.message, "error_code": exc.error_code, **exc.extra}
    except RuntimeError as exc:
        code = 503
        payload = {"message": str(exc), "error_code": "DATABASE_UNAVAILABLE"}
    wiz.response.status(code, **payload)


def sync_all():
    domains = wiz.model("struct").domains
    code = 200
    payload = {}
    try:
        payload = domains.sync_all()
    except domains.DomainError as exc:
        code = exc.status_code
        payload = {"message": exc.message, "error_code": exc.error_code, **exc.extra}
    except RuntimeError as exc:
        code = 503
        payload = {"message": str(exc), "error_code": "DATABASE_UNAVAILABLE"}
    wiz.response.status(code, **payload)


def save_record():
    domains = wiz.model("struct").domains
    body = wiz.request.query()
    code = 200
    payload = {}
    try:
        payload = domains.save_record(body.get("zone_id"), body)
    except domains.DomainError as exc:
        code = exc.status_code
        payload = {"message": exc.message, "error_code": exc.error_code, **exc.extra}
    except RuntimeError as exc:
        code = 503
        payload = {"message": str(exc), "error_code": "DATABASE_UNAVAILABLE"}
    wiz.response.status(code, **payload)


def delete_record():
    domains = wiz.model("struct").domains
    body = wiz.request.query()
    code = 200
    payload = {}
    try:
        payload = domains.delete_record(body.get("zone_id"), body.get("record_id") or body.get("id"))
    except domains.DomainError as exc:
        code = exc.status_code
        payload = {"message": exc.message, "error_code": exc.error_code, **exc.extra}
    except RuntimeError as exc:
        code = 503
        payload = {"message": str(exc), "error_code": "DATABASE_UNAVAILABLE"}
    wiz.response.status(code, **payload)
