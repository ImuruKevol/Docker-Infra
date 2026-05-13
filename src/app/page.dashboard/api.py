from flask import request


def _request_base_url():
    forwarded_proto = (request.headers.get("X-Forwarded-Proto") or "").split(",")[0].strip()
    forwarded_host = (request.headers.get("X-Forwarded-Host") or "").split(",")[0].strip()
    proto = forwarded_proto or request.scheme
    host = forwarded_host or request.headers.get("Host")
    if host:
        return f"{proto}://{host}".rstrip("/")
    return request.url_root.rstrip("/")


def _run_dashboard_bootstrap():
    backup_tick = wiz.model("struct/service_image_backup_tick")
    monitoring = wiz.model("struct").nodes_monitoring
    backup_tick.tick()
    monitoring.ensure_collectors_if_needed_async({"reporter_base_url": _request_base_url()})


def _dashboard_response(loader, error_code):
    code = 200
    payload = {}

    try:
        payload = loader() or {}
    except RuntimeError as exc:
        code = 503
        payload = {"message": str(exc), "error_code": "DATABASE_UNAVAILABLE"}
    except Exception as exc:
        code = getattr(exc, "status_code", 500)
        payload = {
            "message": getattr(exc, "message", str(exc)),
            "error_code": getattr(exc, "error_code", error_code),
            **(getattr(exc, "extra", {}) or {}),
        }

    wiz.response.status(code, **payload)


def overview():
    catalog = wiz.model("struct/infra_catalog_registry")
    body = wiz.request.query()

    def load():
        _run_dashboard_bootstrap()
        return catalog.dashboard(
            start_date=body.get("start_date"),
            end_date=body.get("end_date"),
            start_at=body.get("start_at"),
            end_at=body.get("end_at"),
        )

    _dashboard_response(load, "DASHBOARD_LOAD_FAILED")


def summary():
    catalog = wiz.model("struct/infra_catalog_registry")

    def load():
        _run_dashboard_bootstrap()
        return catalog.dashboard_status()

    _dashboard_response(load, "DASHBOARD_SUMMARY_LOAD_FAILED")


def resources():
    catalog = wiz.model("struct/infra_catalog_registry")
    body = wiz.request.query()

    def load():
        return catalog.dashboard_resources(
            start_date=body.get("start_date"),
            end_date=body.get("end_date"),
            start_at=body.get("start_at"),
            end_at=body.get("end_at"),
        )

    _dashboard_response(load, "DASHBOARD_RESOURCES_LOAD_FAILED")


def servers():
    catalog = wiz.model("struct/infra_catalog_registry")
    _dashboard_response(lambda: catalog.dashboard_nodes(), "DASHBOARD_SERVERS_LOAD_FAILED")


def domains():
    catalog = wiz.model("struct/infra_catalog_registry")
    _dashboard_response(lambda: catalog.dashboard_domains(), "DASHBOARD_DOMAINS_LOAD_FAILED")


def operations():
    catalog = wiz.model("struct/infra_catalog_registry")
    _dashboard_response(lambda: catalog.dashboard_operations(), "DASHBOARD_OPERATIONS_LOAD_FAILED")
