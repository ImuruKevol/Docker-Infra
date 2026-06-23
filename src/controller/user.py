from flask import request


class Controller(wiz.controller("base")):
    def __init__(self):
        super().__init__()
        auth = wiz.model("struct").auth
        token = auth.request_session_token(wiz.session.get("docker_infra_session_token", None))

        try:
            authenticated = auth.is_session_valid(token)
        except RuntimeError:
            authenticated = False
        except Exception:
            authenticated = False

        if authenticated:
            wiz.session.set(
                id="operator",
                actor="operator",
                docker_infra_authenticated=True,
                docker_infra_session_token=token,
            )
            return

        if token:
            auth.clear_session_cookie()

        if request.path.startswith("/api/") or request.path.startswith("/wiz/api/"):
            wiz.response.status(401, message="로그인이 필요합니다.", error_code="AUTHENTICATION_REQUIRED")

        wiz.response.redirect("/access")
