def _filters(body):
    return {
        "status": body.get("status") or "",
        "type": body.get("type") or "",
        "target_type": body.get("target_type") or "",
        "query": body.get("query") or "",
    }


def _limit(value):
    try:
        return max(1, min(int(value or 20), 200))
    except Exception:
        return 20


def _page(value):
    try:
        return max(1, int(value or 1))
    except Exception:
        return 1


def load():
    catalog = wiz.model("struct/infra_catalog_registry")
    body = wiz.request.query()
    code = 200
    payload = {}

    try:
        payload = catalog.operation_logs(filters=_filters(body), limit=_limit(body.get("limit")), page=_page(body.get("page")))
    except RuntimeError as exc:
        code = 503
        payload = {"message": str(exc), "error_code": "DATABASE_UNAVAILABLE"}
    except Exception as exc:
        code = getattr(exc, "status_code", 500)
        payload = {
            "message": getattr(exc, "message", str(exc)),
            "error_code": getattr(exc, "error_code", "OPERATION_LOG_LOAD_FAILED"),
            **(getattr(exc, "extra", {}) or {}),
        }

    wiz.response.status(code, **payload)


def detail():
    catalog = wiz.model("struct/infra_catalog_registry")
    body = wiz.request.query()
    operation_id = body.get("operation_id")
    if not operation_id:
        wiz.response.status(400, message="operation_id는 필수입니다.", error_code="OPERATION_ID_REQUIRED")
        return

    code = 200
    payload = {}
    try:
        payload = {"operation": catalog.operation_detail(operation_id)}
    except KeyError:
        code = 404
        payload = {"message": "작업 로그를 찾을 수 없습니다.", "error_code": "OPERATION_NOT_FOUND"}
    except RuntimeError as exc:
        code = 503
        payload = {"message": str(exc), "error_code": "DATABASE_UNAVAILABLE"}
    except Exception as exc:
        code = getattr(exc, "status_code", 500)
        payload = {
            "message": getattr(exc, "message", str(exc)),
            "error_code": getattr(exc, "error_code", "OPERATION_DETAIL_LOAD_FAILED"),
            **(getattr(exc, "extra", {}) or {}),
        }

    wiz.response.status(code, **payload)
