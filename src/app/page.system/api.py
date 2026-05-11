def load():
    ai_settings = wiz.model("struct/ai_settings")
    appearance = wiz.model("struct/appearance")
    backup_system = wiz.model("struct/backup_system")
    backup_tick = wiz.model("struct/service_image_backup_tick")
    code = 200
    payload = {}
    try:
        backup_tick.tick()
        payload = {
            "general": appearance.public_payload(),
            "backup_system": backup_system.status(),
            "ai_settings": ai_settings.public_payload(),
        }
    except ai_settings.AISettingsError as exc:
        code = exc.status_code
        payload = {"message": exc.message, "error_code": exc.error_code, **exc.extra}
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


def disable_backup_system():
    backup_system = wiz.model("struct/backup_system")
    code = 200
    payload = {}
    try:
        payload = backup_system.disable()
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


def reset_backup_system():
    backup_system = wiz.model("struct/backup_system")
    code = 200
    payload = {}
    try:
        payload = backup_system.reset(wiz.request.query())
    except backup_system.BackupSystemError as exc:
        code = exc.status_code
        payload = {"message": exc.message, "error_code": exc.error_code, **exc.extra}
    except RuntimeError as exc:
        code = 503
        payload = {"message": str(exc), "error_code": "DATABASE_UNAVAILABLE"}
    wiz.response.status(code, **payload)


def save_backup_policy():
    backup_system = wiz.model("struct/backup_system")
    code = 200
    payload = {}
    try:
        payload = {"backup_system": backup_system.save_policy(wiz.request.query())}
    except backup_system.BackupSystemError as exc:
        code = exc.status_code
        payload = {"message": exc.message, "error_code": exc.error_code, **exc.extra}
    except RuntimeError as exc:
        code = 503
        payload = {"message": str(exc), "error_code": "DATABASE_UNAVAILABLE"}
    wiz.response.status(code, **payload)


def run_backup_policy_now():
    scheduler = wiz.model("struct/service_image_backup_scheduler")
    code = 200
    payload = {}
    try:
        payload = {"result": scheduler.run({"force": True})}
    except scheduler.ServiceError as exc:
        code = exc.status_code
        payload = {"message": exc.message, "error_code": exc.error_code, **exc.extra}
    except RuntimeError as exc:
        code = 503
        payload = {"message": str(exc), "error_code": "DATABASE_UNAVAILABLE"}
    wiz.response.status(code, **payload)


def run_backup_policy_due():
    scheduler = wiz.model("struct/service_image_backup_scheduler")
    code = 200
    payload = {}
    try:
        payload = {"result": scheduler.run({})}
    except scheduler.ServiceError as exc:
        code = exc.status_code
        payload = {"message": exc.message, "error_code": exc.error_code, **exc.extra}
    except RuntimeError as exc:
        code = 503
        payload = {"message": str(exc), "error_code": "DATABASE_UNAVAILABLE"}
    wiz.response.status(code, **payload)


def backup_cleanup_plan():
    cleanup = wiz.model("struct/service_image_backup_cleanup")
    code = 200
    payload = {}
    try:
        payload = {"cleanup": cleanup.plan(wiz.request.query())}
    except cleanup.ServiceError as exc:
        code = exc.status_code
        payload = {"message": exc.message, "error_code": exc.error_code, **exc.extra}
    except RuntimeError as exc:
        code = 503
        payload = {"message": str(exc), "error_code": "DATABASE_UNAVAILABLE"}
    wiz.response.status(code, **payload)


def run_backup_cleanup():
    cleanup = wiz.model("struct/service_image_backup_cleanup")
    code = 200
    payload = {}
    try:
        payload = {"cleanup": cleanup.cleanup(wiz.request.query())}
    except cleanup.ServiceError as exc:
        code = exc.status_code
        payload = {"message": exc.message, "error_code": exc.error_code, **exc.extra}
    except RuntimeError as exc:
        code = 503
        payload = {"message": str(exc), "error_code": "DATABASE_UNAVAILABLE"}
    wiz.response.status(code, **payload)


def save_ai_settings():
    ai_settings = wiz.model("struct/ai_settings")
    code = 200
    payload = {}
    try:
        payload = {"ai_settings": ai_settings.save(wiz.request.query())}
    except ai_settings.AISettingsError as exc:
        code = exc.status_code
        payload = {"message": exc.message, "error_code": exc.error_code, **exc.extra}
    except RuntimeError as exc:
        code = 503
        payload = {"message": str(exc), "error_code": "DATABASE_UNAVAILABLE"}
    wiz.response.status(code, **payload)


def save_ai_section():
    ai_settings = wiz.model("struct/ai_settings")
    code = 200
    payload = {}
    try:
        payload = {"ai_settings": ai_settings.save_section(wiz.request.query())}
    except ai_settings.AISettingsError as exc:
        code = exc.status_code
        payload = {"message": exc.message, "error_code": exc.error_code, **exc.extra}
    except RuntimeError as exc:
        code = 503
        payload = {"message": str(exc), "error_code": "DATABASE_UNAVAILABLE"}
    wiz.response.status(code, **payload)


def ai_models():
    ai_settings = wiz.model("struct/ai_settings")
    code = 200
    payload = {}
    try:
        payload = {"result": ai_settings.list_models(wiz.request.query())}
    except ai_settings.AISettingsError as exc:
        code = exc.status_code
        payload = {"message": exc.message, "error_code": exc.error_code, **exc.extra}
    except RuntimeError as exc:
        code = 503
        payload = {"message": str(exc), "error_code": "DATABASE_UNAVAILABLE"}
    wiz.response.status(code, **payload)


def ai_resources():
    ai_settings = wiz.model("struct/ai_settings")
    code = 200
    payload = {}
    try:
        body = wiz.request.query()
        body["probe"] = True
        payload = {"resources": ai_settings.resources(body)}
    except ai_settings.AISettingsError as exc:
        code = exc.status_code
        payload = {"message": exc.message, "error_code": exc.error_code, **exc.extra}
    except RuntimeError as exc:
        code = 503
        payload = {"message": str(exc), "error_code": "DATABASE_UNAVAILABLE"}
    wiz.response.status(code, **payload)
