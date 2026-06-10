def ddns_unavailable(message, error_code="DDNS_LOAD_FAILED"):
    return {
        "endpoints": [],
        "registrations": [],
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
    ddns = wiz.model("struct").domains_ddns
    code = 200
    try:
        payload = {"ddns": ddns.load(), "zones": []}
    except ddns.DomainError as exc:
        payload = {"ddns": ddns_unavailable(exc.message, exc.error_code), "zones": []}
    except RuntimeError as exc:
        code = 503
        payload = {"message": str(exc), "error_code": "DATABASE_UNAVAILABLE"}
    except Exception:
        payload = {"ddns": ddns_unavailable("DDNS 관리 서버 정보를 불러올 수 없습니다."), "zones": []}
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


def force_update_ddns_endpoint():
    ddns = wiz.model("struct").domains_ddns
    body = wiz.request.query()
    code = 200
    payload = {}
    try:
        payload = ddns.force_update_endpoint(body.get("endpoint_id") or body.get("id"))
    except ddns.DomainError as exc:
        code = exc.status_code
        payload = {"message": exc.message, "error_code": exc.error_code, **exc.extra}
    except RuntimeError as exc:
        code = 503
        payload = {"message": str(exc), "error_code": "DATABASE_UNAVAILABLE"}
    wiz.response.status(code, **payload)


def ensure_ddns_dispatcher():
    ddns = wiz.model("struct").domains_ddns
    code = 200
    payload = {}
    try:
        payload = ddns.ensure_dispatcher()
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
