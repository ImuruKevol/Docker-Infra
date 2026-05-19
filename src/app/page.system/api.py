def _ai_settings_payload(ai_settings):
    payload = ai_settings.public_payload()
    try:
        codex_runtime = wiz.model("struct/codex_runtime")
        payload["codex_status"] = codex_runtime.status((payload.get("config") or {}).get("codex") or {})
    except Exception as exc:
        payload["codex_status"] = {
            "checked_at": None,
            "login": {
                "status": "error",
                "logged_in": False,
                "message": str(exc),
            },
        }
    return payload


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
            "ai_settings": _ai_settings_payload(ai_settings),
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


def change_admin_password():
    auth = wiz.model("struct/auth")
    body = wiz.request.query()
    code = 200
    payload = {}
    try:
        row = auth.change_password(
            body.get("current_password", ""),
            body.get("new_password", ""),
            confirm_password=body.get("confirm_password", ""),
            test_run_id=body.get("test_run_id"),
        )
        payload = {
            "password": {
                "changed": True,
                "changed_at": row["password_changed_at"],
            }
        }
    except auth.AuthError as exc:
        code = exc.status_code
        payload = {"message": exc.message, "error_code": exc.error_code, **exc.extra}
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
    body = wiz.request.query()
    code = 200
    payload = {}
    try:
        if body.get("background"):
            payload = backup_system.enable_async()
        else:
            payload = backup_system.enable()
    except backup_system.BackupSystemError as exc:
        code = exc.status_code
        payload = {"message": exc.message, "error_code": exc.error_code, **exc.extra}
    except RuntimeError as exc:
        code = 503
        payload = {"message": str(exc), "error_code": "DATABASE_UNAVAILABLE"}
    wiz.response.status(code, **payload)


def backup_operation_status():
    operations = wiz.model("struct/operations")
    body = wiz.request.query()
    operation_id = body.get("operation_id")
    if not operation_id:
        wiz.response.status(400, message="operation_id는 필수입니다.", error_code="OPERATION_ID_REQUIRED")
        return
    code = 200
    payload = {}
    try:
        payload = {"operation": operations.detail(operation_id)}
    except operations.OperationError as exc:
        code = exc.status_code
        payload = {"message": exc.message, "error_code": exc.error_code, **exc.extra}
    except RuntimeError as exc:
        code = 503
        payload = {"message": str(exc), "error_code": "DATABASE_UNAVAILABLE"}
    wiz.response.status(code, **payload)


def apply_backup_registry_nodes():
    nodes = wiz.model("struct/nodes")
    code = 200
    payload = {}
    try:
        payload = nodes.ensure_backup_registry_all()
    except nodes.NodeError as exc:
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
    body = wiz.request.query()
    run_payload = {**body, "force": True}
    run_payload.setdefault("include_snapshots", True)
    code = 200
    payload = {}
    try:
        if body.get("background"):
            payload = scheduler.run_async(run_payload)
        else:
            payload = {"result": scheduler.run(run_payload)}
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
        ai_settings.save(wiz.request.query())
        payload = {"ai_settings": _ai_settings_payload(ai_settings)}
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
        ai_settings.save_section(wiz.request.query())
        payload = {"ai_settings": _ai_settings_payload(ai_settings)}
    except ai_settings.AISettingsError as exc:
        code = exc.status_code
        payload = {"message": exc.message, "error_code": exc.error_code, **exc.extra}
    except RuntimeError as exc:
        code = 503
        payload = {"message": str(exc), "error_code": "DATABASE_UNAVAILABLE"}
    wiz.response.status(code, **payload)


def ai_codex_status():
    ai_settings = wiz.model("struct/ai_settings")
    codex_runtime = wiz.model("struct/codex_runtime")
    code = 200
    payload = {}
    try:
        body = wiz.request.query()
        current = ai_settings._normalize_config(ai_settings._saved_config())
        codex_config = body.get("codex") if isinstance(body.get("codex"), dict) else body
        codex_config = {**(current.get("codex") or {}), **(codex_config or {})}
        payload = {"codex_status": codex_runtime.status(codex_config)}
    except codex_runtime.CodexRuntimeError as exc:
        code = exc.status_code
        payload = {"message": exc.message, "error_code": exc.error_code, **exc.details}
    except RuntimeError as exc:
        code = 503
        payload = {"message": str(exc), "error_code": "DATABASE_UNAVAILABLE"}
    wiz.response.status(code, **payload)


def ai_codex_test():
    ai_settings = wiz.model("struct/ai_settings")
    codex_runtime = wiz.model("struct/codex_runtime")
    code = 200
    payload = {}
    try:
        body = wiz.request.query()
        current = ai_settings._normalize_config(ai_settings._saved_config())
        codex_config = body.get("codex") if isinstance(body.get("codex"), dict) else body
        codex_config = {**(current.get("codex") or {}), **(codex_config or {})}
        payload = {"result": codex_runtime.test_login(codex_config, prompt=body.get("prompt"))}
    except codex_runtime.CodexRuntimeError as exc:
        code = exc.status_code
        payload = {"message": exc.message, "error_code": exc.error_code, **exc.details}
    except RuntimeError as exc:
        code = 503
        payload = {"message": str(exc), "error_code": "DATABASE_UNAVAILABLE"}
    wiz.response.status(code, **payload)


def ai_codex_device_login_start():
    ai_settings = wiz.model("struct/ai_settings")
    codex_runtime = wiz.model("struct/codex_runtime")
    code = 200
    payload = {}
    try:
        body = wiz.request.query()
        current = ai_settings._normalize_config(ai_settings._saved_config())
        codex_config = body.get("codex") if isinstance(body.get("codex"), dict) else body
        codex_config = {**(current.get("codex") or {}), **(codex_config or {})}
        payload = codex_runtime.start_device_login(codex_config)
    except codex_runtime.CodexRuntimeError as exc:
        code = exc.status_code
        payload = {"message": exc.message, "error_code": exc.error_code, **exc.details}
    except RuntimeError as exc:
        code = 503
        payload = {"message": str(exc), "error_code": "DATABASE_UNAVAILABLE"}
    wiz.response.status(code, **payload)


def ai_codex_device_login_status():
    ai_settings = wiz.model("struct/ai_settings")
    codex_runtime = wiz.model("struct/codex_runtime")
    code = 200
    payload = {}
    try:
        body = wiz.request.query()
        current = ai_settings._normalize_config(ai_settings._saved_config())
        codex_config = body.get("codex") if isinstance(body.get("codex"), dict) else body
        codex_config = {**(current.get("codex") or {}), **(codex_config or {})}
        payload = codex_runtime.device_login_status(codex_config)
    except codex_runtime.CodexRuntimeError as exc:
        code = exc.status_code
        payload = {"message": exc.message, "error_code": exc.error_code, **exc.details}
    except RuntimeError as exc:
        code = 503
        payload = {"message": str(exc), "error_code": "DATABASE_UNAVAILABLE"}
    wiz.response.status(code, **payload)


def ai_codex_device_login_cancel():
    ai_settings = wiz.model("struct/ai_settings")
    codex_runtime = wiz.model("struct/codex_runtime")
    code = 200
    payload = {}
    try:
        body = wiz.request.query()
        current = ai_settings._normalize_config(ai_settings._saved_config())
        codex_config = body.get("codex") if isinstance(body.get("codex"), dict) else body
        codex_config = {**(current.get("codex") or {}), **(codex_config or {})}
        payload = codex_runtime.cancel_device_login(codex_config)
    except codex_runtime.CodexRuntimeError as exc:
        code = exc.status_code
        payload = {"message": exc.message, "error_code": exc.error_code, **exc.details}
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
