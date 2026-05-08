def overview():
    catalog = wiz.model("struct/infra_catalog_registry")
    code = 200
    payload = {}

    try:
        payload = catalog.dashboard()
        payload["integrations"] = [
            item
            for item in payload.get("integrations", [])
            if str((item or {}).get("key") or "").strip() != "gitlab"
        ]
    except RuntimeError as exc:
        code = 503
        payload = {"message": str(exc), "error_code": "DATABASE_UNAVAILABLE"}

    wiz.response.status(code, **payload)
