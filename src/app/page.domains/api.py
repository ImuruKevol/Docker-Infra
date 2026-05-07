def load():
    catalog = wiz.model("struct").infra_catalog
    code = 200
    payload = {}

    try:
        payload = catalog.domains()
    except RuntimeError as exc:
        code = 503
        payload = {"message": str(exc), "error_code": "DATABASE_UNAVAILABLE"}

    wiz.response.status(code, **payload)
