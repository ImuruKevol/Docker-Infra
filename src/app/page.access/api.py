from flask import request


def _set_operator_session(result):
    wiz.session.set(
        id="operator",
        actor="operator",
        docker_infra_authenticated=True,
        docker_infra_session_token=result["session_token"],
    )
    wiz.model("struct").auth.remember_session_cookie(result["session_token"], result.get("session"))


def _error_payload(exc, error_code):
    return {"message": str(exc), "error_code": error_code}


def setup_status():
    setup = wiz.model("struct").setup
    auth = wiz.model("struct").auth
    code = 200
    payload = {}
    try:
        status = setup.status(include_checks=True)
        payload["setup"] = status
        payload["session_policy"] = (
            auth.default_session_policy()
            if status.get("database_configured") is False
            else auth.session_policy()
        )
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
    token = auth.request_session_token(wiz.session.get("docker_infra_session_token", None))

    try:
        payload = {"authenticated": False, "revoked": auth.logout(token)}
    except RuntimeError as exc:
        code = 503
        payload = _error_payload(exc, "DATABASE_UNAVAILABLE")

    wiz.session.clear()
    auth.clear_session_cookie()
    wiz.response.status(code, **payload)


def session():
    auth = wiz.model("struct").auth
    code = 200
    payload = {}
    token = auth.request_session_token(wiz.session.get("docker_infra_session_token", None))

    try:
        current = auth.current_session(token)
        if current["authenticated"] and token:
            wiz.session.set(
                id="operator",
                actor="operator",
                docker_infra_authenticated=True,
                docker_infra_session_token=token,
            )
        elif token:
            auth.clear_session_cookie()
        payload = {
            "authenticated": current["authenticated"],
            "session": current["session"],
            "session_policy": auth.session_policy(),
        }
    except RuntimeError as exc:
        code = 503
        payload = _error_payload(exc, "DATABASE_UNAVAILABLE")

    wiz.response.status(code, **payload)
