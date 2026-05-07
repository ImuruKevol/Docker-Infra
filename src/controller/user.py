from flask import request


class Controller(wiz.controller("base")):
    def __init__(self):
        super().__init__()
        token = wiz.session.get("docker_infra_session_token", None)

        try:
            authenticated = wiz.model("struct").auth.is_session_valid(token)
        except RuntimeError:
            authenticated = False
        except Exception:
            authenticated = False

        if authenticated:
            return

        if request.path.startswith("/api/") or request.path.startswith("/wiz/api/"):
            wiz.response.status(401, message="로그인이 필요합니다.", error_code="AUTHENTICATION_REQUIRED")

        wiz.response.redirect("/access")
