def load():
    storage = wiz.model("struct/storage")
    code = 200
    payload = {}
    try:
        payload = storage.load_overview()
    except storage.StorageError as exc:
        code = exc.status_code
        payload = {"message": exc.message, "error_code": exc.error_code, **exc.extra}
    except RuntimeError as exc:
        code = 503
        payload = {"message": str(exc), "error_code": "DATABASE_UNAVAILABLE"}
    except Exception as exc:
        code = getattr(exc, "status_code", 500)
        payload = {
            "message": getattr(exc, "message", str(exc)),
            "error_code": getattr(exc, "error_code", "STORAGE_LOAD_FAILED"),
            **(getattr(exc, "extra", {}) or {}),
        }
    wiz.response.status(code, **payload)


def _storage_action(callback):
    storage = wiz.model("struct/storage")
    body = wiz.request.query()
    code = 200
    payload = {}
    try:
        payload = callback(storage, body)
        operation = payload.get("operation") if isinstance(payload, dict) else None
        if isinstance(operation, dict) and operation.get("status") == "failed":
            code = 409
    except storage.StorageError as exc:
        code = exc.status_code
        payload = {"message": exc.message, "error_code": exc.error_code, **exc.extra}
    except RuntimeError as exc:
        code = 503
        payload = {"message": str(exc), "error_code": "DATABASE_UNAVAILABLE"}
    except Exception as exc:
        code = getattr(exc, "status_code", 500)
        payload = {
            "message": getattr(exc, "message", str(exc)),
            "error_code": getattr(exc, "error_code", "STORAGE_ACTION_FAILED"),
            **(getattr(exc, "extra", {}) or {}),
        }
    wiz.response.status(code, **payload)


def cluster_preflight():
    _storage_action(lambda storage, body: storage.cluster_preflight(body))


def cluster_bootstrap():
    _storage_action(lambda storage, body: storage.cluster_bootstrap(body))


def cluster_master_bootstrap():
    _storage_action(lambda storage, body: storage.cluster_master_bootstrap(body))


def osd_nodes():
    _storage_action(lambda storage, body: storage.osd_nodes(body))


def osd_slot_plan():
    _storage_action(lambda storage, body: storage.osd_slot_plan(body))


def osd_slot_create():
    _storage_action(lambda storage, body: storage.osd_slot_create(body))


def ensure_node_mount():
    _storage_action(lambda storage, body: storage.ensure_node_mount(body))


def operation_status():
    _storage_action(lambda storage, body: storage.operation_status(body.get("operation_id")))
