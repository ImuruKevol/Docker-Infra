def _as_bool(value):
    if value is None:
        return False
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"1", "true", "yes", "on"}


def _ai_settings_payload(ai_settings, include_status=False):
    payload = ai_settings.public_payload(include_status=include_status)
    if include_status:
        payload["codex_status"] = (payload.get("agent_statuses") or {}).get("codex") or {}
    return payload


def load():
    ai_settings = wiz.model("struct/ai_settings")
    appearance = wiz.model("struct/appearance")
    body = wiz.request.query()
    section = str(body.get("section") or "").strip().lower()
    include_backup = section == "backup" or _as_bool(body.get("include_backup"))
    include_ai_status = _as_bool(body.get("include_ai_status"))
    code = 200
    payload = {}
    try:
        payload = {
            "general": appearance.public_payload(),
            "ai_settings": _ai_settings_payload(ai_settings, include_status=include_ai_status),
        }
        if include_backup:
            backup_system = wiz.model("struct/backup_system")
            payload["backup_system"] = backup_system.status()
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
        ai_settings.save(wiz.request.query(), include_status=False)
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
        ai_settings.save_section(wiz.request.query(), include_status=False)
        payload = {"ai_settings": _ai_settings_payload(ai_settings)}
    except ai_settings.AISettingsError as exc:
        code = exc.status_code
        payload = {"message": exc.message, "error_code": exc.error_code, **exc.extra}
    except RuntimeError as exc:
        code = 503
        payload = {"message": str(exc), "error_code": "DATABASE_UNAVAILABLE"}
    wiz.response.status(code, **payload)


def save_ai_default_agent():
    ai_settings = wiz.model("struct/ai_settings")
    code = 200
    payload = {}
    try:
        ai_settings.save_default_agent(wiz.request.query(), include_status=False)
        payload = {"ai_settings": _ai_settings_payload(ai_settings)}
    except ai_settings.AISettingsError as exc:
        code = exc.status_code
        payload = {"message": exc.message, "error_code": exc.error_code, **exc.extra}
    except RuntimeError as exc:
        code = 503
        payload = {"message": str(exc), "error_code": "DATABASE_UNAVAILABLE"}
    wiz.response.status(code, **payload)


def _current_agent_config(ai_settings, body, agent):
    current = ai_settings._normalize_config(ai_settings._saved_config())
    agent_payload = body.get(agent) if isinstance(body.get(agent), dict) else body
    return {**(current.get(agent) or {}), **(agent_payload or {})}


def _normalize_agent_key(body):
    agent = str(body.get("agent") or body.get("provider") or "").strip().lower().replace("-", "_")
    if agent in {"claude", "claudecode"}:
        agent = "claude_code"
    if agent == "hermes_agent":
        agent = "hermes"
    return agent


def _persist_agent_update(ai_settings, agent, update):
    if not isinstance(update, dict) or not update:
        return None
    return ai_settings.save_agent_update(agent, update)


def ai_agent_status():
    ai_settings = wiz.model("struct/ai_settings")
    codex_runtime = wiz.model("struct/codex_runtime")
    body = wiz.request.query()
    agent = _normalize_agent_key(body)
    code = 200
    payload = {}
    try:
        config = _current_agent_config(ai_settings, body, agent)
        payload = {"agent_status": codex_runtime.agent_status(agent, config)}
    except codex_runtime.CodexRuntimeError as exc:
        code = exc.status_code
        payload = {"message": exc.message, "error_code": exc.error_code, **exc.details}
    except RuntimeError as exc:
        code = 503
        payload = {"message": str(exc), "error_code": "DATABASE_UNAVAILABLE"}
    wiz.response.status(code, **payload)


def ai_agent_model_catalog():
    ai_settings = wiz.model("struct/ai_settings")
    codex_runtime = wiz.model("struct/codex_runtime")
    body = wiz.request.query()
    agent = _normalize_agent_key(body)
    code = 200
    payload = {}
    try:
        config = _current_agent_config(ai_settings, body, agent)
        payload = {"catalog": codex_runtime.agent_model_catalog(agent, config)}
    except codex_runtime.CodexRuntimeError as exc:
        code = exc.status_code
        payload = {"message": exc.message, "error_code": exc.error_code, **exc.details}
    except RuntimeError as exc:
        code = 503
        payload = {"message": str(exc), "error_code": "DATABASE_UNAVAILABLE"}
    wiz.response.status(code, **payload)


def ai_agent_update_check():
    ai_settings = wiz.model("struct/ai_settings")
    codex_runtime = wiz.model("struct/codex_runtime")
    body = wiz.request.query()
    agent = _normalize_agent_key(body)
    code = 200
    payload = {}
    try:
        config = _current_agent_config(ai_settings, body, agent)
        update = codex_runtime.agent_update_status(agent, config)
        payload = {"update": _persist_agent_update(ai_settings, agent, update)}
    except ai_settings.AISettingsError as exc:
        code = exc.status_code
        payload = {"message": exc.message, "error_code": exc.error_code, **exc.extra}
    except codex_runtime.CodexRuntimeError as exc:
        code = exc.status_code
        payload = {"message": exc.message, "error_code": exc.error_code, **exc.details}
    except RuntimeError as exc:
        code = 503
        payload = {"message": str(exc), "error_code": "DATABASE_UNAVAILABLE"}
    wiz.response.status(code, **payload)


def ai_agent_test():
    ai_settings = wiz.model("struct/ai_settings")
    codex_runtime = wiz.model("struct/codex_runtime")
    body = wiz.request.query()
    agent = _normalize_agent_key(body)
    code = 200
    payload = {}
    try:
        config = _current_agent_config(ai_settings, body, agent)
        payload = {"result": codex_runtime.test_agent(agent, config, prompt=body.get("prompt"))}
    except codex_runtime.CodexRuntimeError as exc:
        code = exc.status_code
        payload = {"message": exc.message, "error_code": exc.error_code, **exc.details}
    except RuntimeError as exc:
        code = 503
        payload = {"message": str(exc), "error_code": "DATABASE_UNAVAILABLE"}
    wiz.response.status(code, **payload)


def ai_agent_install():
    ai_settings = wiz.model("struct/ai_settings")
    codex_runtime = wiz.model("struct/codex_runtime")
    body = wiz.request.query()
    agent = _normalize_agent_key(body)
    code = 200
    payload = {}
    try:
        config = _current_agent_config(ai_settings, body, agent)
        payload = codex_runtime.install_agent_async(agent, config)
        if payload.get("update"):
            payload["update"] = _persist_agent_update(ai_settings, agent, payload.get("update"))
    except codex_runtime.CodexRuntimeError as exc:
        code = exc.status_code
        payload = {"message": exc.message, "error_code": exc.error_code, **exc.details}
    except RuntimeError as exc:
        code = 503
        payload = {"message": str(exc), "error_code": "DATABASE_UNAVAILABLE"}
    wiz.response.status(code, **payload)


def ai_agent_install_status():
    ai_settings = wiz.model("struct/ai_settings")
    operations = wiz.model("struct/operations")
    body = wiz.request.query()
    operation_id = body.get("operation_id")
    if not operation_id:
        wiz.response.status(400, message="operation_id는 필수입니다.", error_code="OPERATION_ID_REQUIRED")
        return
    code = 200
    payload = {}
    try:
        operation = operations.detail(operation_id)
        payload = {"operation": operation}
        if operation.get("status") in {"succeeded", "failed", "canceled"}:
            result_payload = operation.get("result_payload") or {}
            agent = result_payload.get("agent") or operation.get("target_id")
            update = result_payload.get("after_update")
            if agent and isinstance(update, dict):
                payload["update"] = _persist_agent_update(ai_settings, agent, update)
    except operations.OperationError as exc:
        code = exc.status_code
        payload = {"message": exc.message, "error_code": exc.error_code, **exc.extra}
    except ai_settings.AISettingsError as exc:
        code = exc.status_code
        payload = {"message": exc.message, "error_code": exc.error_code, **exc.extra}
    except RuntimeError as exc:
        code = 503
        payload = {"message": str(exc), "error_code": "DATABASE_UNAVAILABLE"}
    wiz.response.status(code, **payload)


def ai_hermes_apply_settings():
    ai_settings = wiz.model("struct/ai_settings")
    codex_runtime = wiz.model("struct/codex_runtime")
    body = wiz.request.query()
    code = 200
    payload = {}
    try:
        current = ai_settings._normalize_config(ai_settings._saved_config())
        hermes_payload = body.get("hermes") if isinstance(body.get("hermes"), dict) else body
        config = {**(current.get("hermes") or {}), **(hermes_payload or {})}
        secret_value = body.get("api_key") or (hermes_payload or {}).get("api_key")
        apply_result = codex_runtime.apply_hermes_settings(config, secret_value=secret_value)
        safe_config = dict(config)
        safe_config.pop("api_key", None)
        ai_settings.save_section({"section": "hermes", "hermes": safe_config}, include_status=False)
        payload = {"result": apply_result, "ai_settings": _ai_settings_payload(ai_settings)}
    except ai_settings.AISettingsError as exc:
        code = exc.status_code
        payload = {"message": exc.message, "error_code": exc.error_code, **exc.extra}
    except codex_runtime.CodexRuntimeError as exc:
        code = exc.status_code
        payload = {"message": exc.message, "error_code": exc.error_code, **exc.details}
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


def ai_codex_cli_update_check():
    ai_settings = wiz.model("struct/ai_settings")
    codex_runtime = wiz.model("struct/codex_runtime")
    code = 200
    payload = {}
    try:
        body = wiz.request.query()
        current = ai_settings._normalize_config(ai_settings._saved_config())
        codex_config = body.get("codex") if isinstance(body.get("codex"), dict) else body
        codex_config = {**(current.get("codex") or {}), **(codex_config or {})}
        update = codex_runtime.cli_update_status(codex_config)
        payload = {"update": _persist_agent_update(ai_settings, "codex", update)}
    except ai_settings.AISettingsError as exc:
        code = exc.status_code
        payload = {"message": exc.message, "error_code": exc.error_code, **exc.extra}
    except codex_runtime.CodexRuntimeError as exc:
        code = exc.status_code
        payload = {"message": exc.message, "error_code": exc.error_code, **exc.details}
    except RuntimeError as exc:
        code = 503
        payload = {"message": str(exc), "error_code": "DATABASE_UNAVAILABLE"}
    wiz.response.status(code, **payload)


def ai_codex_cli_upgrade():
    ai_settings = wiz.model("struct/ai_settings")
    codex_runtime = wiz.model("struct/codex_runtime")
    code = 200
    payload = {}
    try:
        body = wiz.request.query()
        current = ai_settings._normalize_config(ai_settings._saved_config())
        codex_config = body.get("codex") if isinstance(body.get("codex"), dict) else body
        codex_config = {**(current.get("codex") or {}), **(codex_config or {})}
        payload = codex_runtime.upgrade_cli_async(codex_config)
        if payload.get("update"):
            payload["update"] = _persist_agent_update(ai_settings, "codex", payload.get("update"))
    except ai_settings.AISettingsError as exc:
        code = exc.status_code
        payload = {"message": exc.message, "error_code": exc.error_code, **exc.extra}
    except codex_runtime.CodexRuntimeError as exc:
        code = exc.status_code
        payload = {"message": exc.message, "error_code": exc.error_code, **exc.details}
    except RuntimeError as exc:
        code = 503
        payload = {"message": str(exc), "error_code": "DATABASE_UNAVAILABLE"}
    wiz.response.status(code, **payload)


def ai_codex_cli_upgrade_status():
    ai_settings = wiz.model("struct/ai_settings")
    operations = wiz.model("struct/operations")
    body = wiz.request.query()
    operation_id = body.get("operation_id")
    if not operation_id:
        wiz.response.status(400, message="operation_id는 필수입니다.", error_code="OPERATION_ID_REQUIRED")
        return
    code = 200
    payload = {}
    try:
        operation = operations.detail(operation_id)
        payload = {"operation": operation}
        if operation.get("status") in {"succeeded", "failed", "canceled"}:
            update = (operation.get("result_payload") or {}).get("after")
            if isinstance(update, dict):
                payload["update"] = _persist_agent_update(ai_settings, "codex", update)
    except operations.OperationError as exc:
        code = exc.status_code
        payload = {"message": exc.message, "error_code": exc.error_code, **exc.extra}
    except ai_settings.AISettingsError as exc:
        code = exc.status_code
        payload = {"message": exc.message, "error_code": exc.error_code, **exc.extra}
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


def ai_claude_code_login_start():
    ai_settings = wiz.model("struct/ai_settings")
    codex_runtime = wiz.model("struct/codex_runtime")
    code = 200
    payload = {}
    try:
        body = wiz.request.query()
        current = ai_settings._normalize_config(ai_settings._saved_config())
        claude_config = body.get("claude_code") if isinstance(body.get("claude_code"), dict) else body
        claude_config = {**(current.get("claude_code") or {}), **(claude_config or {})}
        payload = codex_runtime.start_claude_login(claude_config)
    except codex_runtime.CodexRuntimeError as exc:
        code = exc.status_code
        payload = {"message": exc.message, "error_code": exc.error_code, **exc.details}
    except RuntimeError as exc:
        code = 503
        payload = {"message": str(exc), "error_code": "DATABASE_UNAVAILABLE"}
    wiz.response.status(code, **payload)


def ai_claude_code_login_status():
    ai_settings = wiz.model("struct/ai_settings")
    codex_runtime = wiz.model("struct/codex_runtime")
    code = 200
    payload = {}
    try:
        body = wiz.request.query()
        current = ai_settings._normalize_config(ai_settings._saved_config())
        claude_config = body.get("claude_code") if isinstance(body.get("claude_code"), dict) else body
        claude_config = {**(current.get("claude_code") or {}), **(claude_config or {})}
        payload = codex_runtime.claude_login_status(claude_config)
    except codex_runtime.CodexRuntimeError as exc:
        code = exc.status_code
        payload = {"message": exc.message, "error_code": exc.error_code, **exc.details}
    except RuntimeError as exc:
        code = 503
        payload = {"message": str(exc), "error_code": "DATABASE_UNAVAILABLE"}
    wiz.response.status(code, **payload)


def ai_claude_code_login_submit():
    ai_settings = wiz.model("struct/ai_settings")
    codex_runtime = wiz.model("struct/codex_runtime")
    code = 200
    payload = {}
    try:
        body = wiz.request.query()
        current = ai_settings._normalize_config(ai_settings._saved_config())
        claude_config = body.get("claude_code") if isinstance(body.get("claude_code"), dict) else body
        claude_config = {**(current.get("claude_code") or {}), **(claude_config or {})}
        payload = codex_runtime.submit_claude_login_code(body.get("code"), claude_config)
    except codex_runtime.CodexRuntimeError as exc:
        code = exc.status_code
        payload = {"message": exc.message, "error_code": exc.error_code, **exc.details}
    except RuntimeError as exc:
        code = 503
        payload = {"message": str(exc), "error_code": "DATABASE_UNAVAILABLE"}
    wiz.response.status(code, **payload)


def ai_claude_code_login_cancel():
    ai_settings = wiz.model("struct/ai_settings")
    codex_runtime = wiz.model("struct/codex_runtime")
    code = 200
    payload = {}
    try:
        body = wiz.request.query()
        current = ai_settings._normalize_config(ai_settings._saved_config())
        claude_config = body.get("claude_code") if isinstance(body.get("claude_code"), dict) else body
        claude_config = {**(current.get("claude_code") or {}), **(claude_config or {})}
        payload = codex_runtime.cancel_claude_login(claude_config)
    except codex_runtime.CodexRuntimeError as exc:
        code = exc.status_code
        payload = {"message": exc.message, "error_code": exc.error_code, **exc.details}
    except RuntimeError as exc:
        code = 503
        payload = {"message": str(exc), "error_code": "DATABASE_UNAVAILABLE"}
    wiz.response.status(code, **payload)
