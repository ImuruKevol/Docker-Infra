from flask import request


def _request_base_url():
    forwarded_proto = (request.headers.get("X-Forwarded-Proto") or "").split(",")[0].strip()
    forwarded_host = (request.headers.get("X-Forwarded-Host") or "").split(",")[0].strip()
    proto = forwarded_proto or request.scheme
    host = forwarded_host or request.headers.get("Host")
    if host:
        return f"{proto}://{host}".rstrip("/")
    return request.url_root.rstrip("/")


def overview():
    catalog = wiz.model("struct/infra_catalog_registry")
    backup_tick = wiz.model("struct/service_image_backup_tick")
    monitoring = wiz.model("struct").nodes_monitoring
    body = wiz.request.query()
    code = 200
    payload = {}

    try:
        backup_tick.tick()
        monitoring.ensure_collectors_if_needed_async({"reporter_base_url": _request_base_url()})
        payload = catalog.dashboard(
            start_date=body.get("start_date"),
            end_date=body.get("end_date"),
            start_at=body.get("start_at"),
            end_at=body.get("end_at"),
        )
    except RuntimeError as exc:
        code = 503
        payload = {"message": str(exc), "error_code": "DATABASE_UNAVAILABLE"}
    except Exception as exc:
        code = getattr(exc, "status_code", 500)
        payload = {
            "message": getattr(exc, "message", str(exc)),
            "error_code": getattr(exc, "error_code", "DASHBOARD_LOAD_FAILED"),
            **(getattr(exc, "extra", {}) or {}),
        }

    wiz.response.status(code, **payload)
