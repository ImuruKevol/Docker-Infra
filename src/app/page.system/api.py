def load():
    appearance = wiz.model("struct/appearance")
    backup_system = wiz.model("struct/backup_system")
    code = 200
    payload = {}
    try:
        payload = {
            "general": appearance.public_payload(),
            "backup_system": backup_system.status(),
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


def backup_status():
    backup_system = wiz.model("struct/backup_system")
    code = 200
    payload = {}
    try:
        payload = {"backup_system": backup_system.refresh()}
    except backup_system.BackupSystemError as exc:
        code = exc.status_code
        payload = {"message": exc.message, "error_code": exc.error_code, **exc.extra}
    except RuntimeError as exc:
        code = 503
        payload = {"message": str(exc), "error_code": "DATABASE_UNAVAILABLE"}
    wiz.response.status(code, **payload)


def start_backup_system():
    backup_system = wiz.model("struct/backup_system")
    code = 200
    payload = {}
    try:
        payload = backup_system.enable()
    except backup_system.BackupSystemError as exc:
        code = exc.status_code
        payload = {"message": exc.message, "error_code": exc.error_code, **exc.extra}
    except RuntimeError as exc:
        code = 503
        payload = {"message": str(exc), "error_code": "DATABASE_UNAVAILABLE"}
    wiz.response.status(code, **payload)


def stop_backup_system():
    backup_system = wiz.model("struct/backup_system")
    code = 200
    payload = {}
    try:
        payload = backup_system.stop()
    except backup_system.BackupSystemError as exc:
        code = exc.status_code
        payload = {"message": exc.message, "error_code": exc.error_code, **exc.extra}
    except RuntimeError as exc:
        code = 503
        payload = {"message": str(exc), "error_code": "DATABASE_UNAVAILABLE"}
    wiz.response.status(code, **payload)


def restart_backup_system():
    backup_system = wiz.model("struct/backup_system")
    code = 200
    payload = {}
    try:
        payload = backup_system.restart()
    except backup_system.BackupSystemError as exc:
        code = exc.status_code
        payload = {"message": exc.message, "error_code": exc.error_code, **exc.extra}
    except RuntimeError as exc:
        code = 503
        payload = {"message": str(exc), "error_code": "DATABASE_UNAVAILABLE"}
    wiz.response.status(code, **payload)
