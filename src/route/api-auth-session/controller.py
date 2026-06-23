auth = wiz.model("struct").auth
method = wiz.request.method().upper()

if method not in ["GET", "POST", "DELETE"]:
    wiz.response.status(405, message="지원하지 않는 method입니다.", error_code="METHOD_NOT_ALLOWED")

code = 200
payload = {}
token = auth.request_session_token(wiz.session.get("docker_infra_session_token", None))

try:
    if method == "GET":
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
    elif method == "POST":
        session_policy = auth.session_policy()
        refreshed_session = auth.extend_session(token, ttl_seconds=session_policy["ttl_seconds"])
        if refreshed_session and token:
            wiz.session.set(
                id="operator",
                actor="operator",
                docker_infra_authenticated=True,
                docker_infra_session_token=token,
            )
            auth.remember_session_cookie(token, refreshed_session)
            payload = {
                "authenticated": True,
                "session": refreshed_session,
                "session_policy": session_policy,
            }
        else:
            code = 401
            wiz.session.clear()
            auth.clear_session_cookie()
            payload = {
                "authenticated": False,
                "session": None,
                "session_policy": session_policy,
                "message": "세션이 만료되었습니다.",
                "error_code": "AUTHENTICATION_REQUIRED",
            }
    else:
        payload = {"authenticated": False, "revoked": auth.logout(token)}
        wiz.session.clear()
        auth.clear_session_cookie()
except RuntimeError as exc:
    code = 503
    payload = {"message": str(exc), "error_code": "DATABASE_UNAVAILABLE"}
    if method in ["POST", "DELETE"]:
        wiz.session.clear()
        auth.clear_session_cookie()

wiz.response.status(code, **payload)
