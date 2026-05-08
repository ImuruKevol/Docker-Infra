def _visible_integrations(items):
    result = []
    for item in items or []:
        if str((item or {}).get("key") or "").strip() == "gitlab":
            continue
        result.append(item)
    return result


def load():
    appearance = wiz.model("struct/appearance")
    integrations = wiz.model("struct/integrations_registry")
    code = 200
    payload = {}
    try:
        loaded = _visible_integrations(integrations.load())
        payload = {
            "general": appearance.public_payload(),
            "integrations": loaded,
        }
    except RuntimeError as exc:
        code = 503
        payload = {"message": str(exc), "error_code": "DATABASE_UNAVAILABLE"}
    wiz.response.status(code, **payload)


def save_general():
    appearance = wiz.model("struct/appearance")
    body = wiz.request.query()
    code = 200
    payload = {}
    try:
        payload = {"general": appearance.save(body, test_run_id=body.get("test_run_id"))}
    except RuntimeError as exc:
        code = 503
        payload = {"message": str(exc), "error_code": "DATABASE_UNAVAILABLE"}
    wiz.response.status(code, **payload)


def save_integration():
    integrations = wiz.model("struct/integrations_registry")
    body = wiz.request.query()
    code = 200
    payload = {}
    try:
        key = body.get("key")
        if key != "harbor":
            code = 400
            payload = {"message": "지원하지 않는 연동입니다.", "error_code": "INVALID_INTEGRATION"}
        else:
            payload = {
                "integration": integrations.save(
                    key,
                    body,
                    test_run_id=body.get("test_run_id"),
                ),
                "integrations": _visible_integrations(integrations.load()),
            }
    except integrations.IntegrationError as exc:
        code = exc.status_code
        payload = {"message": exc.message, "error_code": exc.error_code, **exc.extra}
    except RuntimeError as exc:
        code = 503
        payload = {"message": str(exc), "error_code": "DATABASE_UNAVAILABLE"}
    wiz.response.status(code, **payload)


def test_integration():
    integrations = wiz.model("struct/integrations_registry")
    body = wiz.request.query()
    code = 200
    payload = {}
    try:
        if body.get("key") != "harbor":
            code = 400
            payload = {"message": "지원하지 않는 연동입니다.", "error_code": "INVALID_INTEGRATION"}
        else:
            payload = integrations.test_connection(body.get("key"), body)
    except integrations.IntegrationError as exc:
        code = exc.status_code
        payload = {"message": exc.message, "error_code": exc.error_code, **exc.extra}
    wiz.response.status(code, **payload)
