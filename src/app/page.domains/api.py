def ddns_unavailable(message, error_code="DDNS_LOAD_FAILED"):
    return {
        "endpoints": [],
        "summary": {
            "endpoint_count": 0,
            "enabled_endpoint_count": 0,
            "registration_count": 0,
        },
        "available": False,
        "message": message,
        "error_code": error_code,
    }


def load():
    domains = wiz.model("struct").domains
    ddns = wiz.model("struct").domains_ddns
    code = 200
    payload = {}
    try:
        payload = domains.load()
        try:
            payload["ddns"] = ddns.load()
        except ddns.DomainError as exc:
            payload["ddns"] = ddns_unavailable(exc.message, exc.error_code)
        except Exception:
            payload["ddns"] = ddns_unavailable("DDNS 관리 서버 정보를 불러올 수 없습니다.")
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


def save_ddns_endpoint():
    ddns = wiz.model("struct").domains_ddns
    body = wiz.request.query()
    code = 200
    payload = {}
    try:
        payload = {"endpoint": ddns.save_endpoint(body, test_run_id=body.get("test_run_id"))}
    except ddns.DomainError as exc:
        code = exc.status_code
        payload = {"message": exc.message, "error_code": exc.error_code, **exc.extra}
    except RuntimeError as exc:
        code = 503
        payload = {"message": str(exc), "error_code": "DATABASE_UNAVAILABLE"}
    wiz.response.status(code, **payload)


def delete_ddns_endpoint():
    ddns = wiz.model("struct").domains_ddns
    body = wiz.request.query()
    code = 200
    payload = {}
    try:
        payload = ddns.delete_endpoint(body.get("endpoint_id") or body.get("id"))
    except ddns.DomainError as exc:
        code = exc.status_code
        payload = {"message": exc.message, "error_code": exc.error_code, **exc.extra}
    except RuntimeError as exc:
        code = 503
        payload = {"message": str(exc), "error_code": "DATABASE_UNAVAILABLE"}
    wiz.response.status(code, **payload)


def check_ddns_endpoint():
    ddns = wiz.model("struct").domains_ddns
    body = wiz.request.query()
    code = 200
    payload = {}
    try:
        payload = ddns.check_endpoint(body.get("endpoint_id") or body.get("id"))
    except ddns.DomainError as exc:
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


def delete_certificate():
    domains = wiz.model("struct").domains
    body = wiz.request.query()
    code = 200
    payload = {}
    try:
        payload = domains.delete_certificate(
            body.get("zone_id"),
            body.get("certificate_id") or body.get("id"),
            test_run_id=body.get("test_run_id"),
        )
    except domains.DomainError as exc:
        code = exc.status_code
        payload = {"message": exc.message, "error_code": exc.error_code, **exc.extra}
    except ValueError as exc:
        code = 400
        payload = {"message": str(exc), "error_code": "CERTIFICATE_DELETE_FAILED"}
    except RuntimeError as exc:
        code = 503
        payload = {"message": str(exc), "error_code": "DATABASE_UNAVAILABLE"}
    wiz.response.status(code, **payload)
