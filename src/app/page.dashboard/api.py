def overview():
    catalog = wiz.model("struct/infra_catalog_registry")
    backup_tick = wiz.model("struct/service_image_backup_tick")
    monitoring_tick = wiz.model("struct").nodes_monitoring
    code = 200
    payload = {}

    try:
        backup_tick.tick()
        monitoring_tick.tick()
        payload = catalog.dashboard()
    except RuntimeError as exc:
        code = 503
        payload = {"message": str(exc), "error_code": "DATABASE_UNAVAILABLE"}

    wiz.response.status(code, **payload)
