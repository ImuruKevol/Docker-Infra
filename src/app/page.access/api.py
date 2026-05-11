from flask import request


def _set_operator_session(result):
    wiz.session.set(
        id="operator",
        actor="operator",
        docker_infra_authenticated=True,
        docker_infra_session_token=result["session_token"],
    )


def _error_payload(exc, error_code):
    return {"message": str(exc), "error_code": error_code}


def _request_base_url():
    forwarded_proto = (request.headers.get("X-Forwarded-Proto") or "").split(",")[0].strip()
    forwarded_host = (request.headers.get("X-Forwarded-Host") or "").split(",")[0].strip()
    proto = forwarded_proto or request.scheme
    host = forwarded_host or request.headers.get("Host")
    if host:
        return f"{proto}://{host}".rstrip("/")
    return request.url_root.rstrip("/")


def setup_status():
    setup = wiz.model("struct").setup
    code = 200
    payload = {}
    try:
        payload["setup"] = setup.status(include_checks=True)
    except RuntimeError as exc:
        code = 503
        payload = _error_payload(exc, "DATABASE_UNAVAILABLE")
    wiz.response.status(code, **payload)


def setup():
    setup_model = wiz.model("struct").setup
    auth = wiz.model("struct").auth
    monitoring = wiz.model("struct").nodes_monitoring
    body = wiz.request.query()
    code = 200
    payload = {}

    try:
        result = setup_model.complete(body)
        monitoring_result = None
        local_master = result["local_master"] or {}
        if local_master.get("id"):
            try:
                monitoring_result = monitoring.ensure_exporters({"node_id": local_master["id"], "reporter_base_url": _request_base_url()})
                result["local_master"] = wiz.model("struct").nodes.detail(local_master["id"])
            except Exception as exc:
                monitoring_result = {"status": "failed", "message": str(exc)}
        login_result = auth.login(
            body.get("password", ""),
            remote_addr=request.remote_addr,
            user_agent=request.headers.get("User-Agent"),
            test_run_id=body.get("test_run_id") or request.headers.get("X-Test-Run-ID"),
        )
        _set_operator_session(login_result)
        payload = {
            "setup": result["setup"],
            "local_master": result["local_master"],
            "backup_system": result["backup_system"],
            "backup_error": result.get("backup_error"),
            "monitoring_auto_configure": monitoring_result,
            "authenticated": True,
            "session": login_result["session"],
        }
    except setup_model.SetupError as exc:
        code = exc.status_code
        payload = {"message": exc.message, "error_code": exc.error_code, **exc.extra}
    except auth.AuthError as exc:
        code = exc.status_code
        payload = {"message": exc.message, "error_code": exc.error_code, **exc.extra}
    except RuntimeError as exc:
        code = 503
        payload = _error_payload(exc, "DATABASE_UNAVAILABLE")

    wiz.response.status(code, **payload)


def disable_backup_system():
    backup_system = wiz.model("struct").backup_system
    code = 200
    payload = {}
    try:
        payload = backup_system.disable()
    except backup_system.BackupSystemError as exc:
        code = exc.status_code
        payload = {"message": exc.message, "error_code": exc.error_code, **exc.extra}
    except RuntimeError as exc:
        code = 503
        payload = _error_payload(exc, "DATABASE_UNAVAILABLE")
    wiz.response.status(code, **payload)


def login():
    auth = wiz.model("struct").auth
    body = wiz.request.query()
    code = 200
    payload = {}

    try:
        result = auth.login(
            body.get("password", ""),
            remote_addr=request.remote_addr,
            user_agent=request.headers.get("User-Agent"),
            test_run_id=body.get("test_run_id") or request.headers.get("X-Test-Run-ID"),
        )
        _set_operator_session(result)
        payload = {
            "authenticated": True,
            "session": result["session"],
        }
    except auth.AuthError as exc:
        code = exc.status_code
        payload = {"message": exc.message, "error_code": exc.error_code, **exc.extra}
    except RuntimeError as exc:
        code = 503
        payload = _error_payload(exc, "DATABASE_UNAVAILABLE")

    wiz.response.status(code, **payload)


def logout():
    auth = wiz.model("struct").auth
    code = 200
    payload = {}
    token = wiz.session.get("docker_infra_session_token", None)

    try:
        payload = {"authenticated": False, "revoked": auth.logout(token)}
    except RuntimeError as exc:
        code = 503
        payload = _error_payload(exc, "DATABASE_UNAVAILABLE")

    wiz.session.clear()
    wiz.response.status(code, **payload)


def session():
    auth = wiz.model("struct").auth
    code = 200
    payload = {}
    token = wiz.session.get("docker_infra_session_token", None)

    try:
        current = auth.current_session(token)
        payload = {"authenticated": current["authenticated"], "session": current["session"]}
    except RuntimeError as exc:
        code = 503
        payload = _error_payload(exc, "DATABASE_UNAVAILABLE")

    wiz.response.status(code, **payload)
