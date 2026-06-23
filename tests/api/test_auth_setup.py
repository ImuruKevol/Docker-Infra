import json
import unittest
from pathlib import Path

from tests.fixtures.api_client import DockerInfraApiClient


ROOT = Path(__file__).resolve().parents[2]
BASE_CONTROLLER = ROOT / "src" / "controller" / "base.py"
USER_CONTROLLER = ROOT / "src" / "controller" / "user.py"
ACCESS_VIEW = ROOT / "src" / "app" / "page.access" / "view.pug"
ACCESS_TS = ROOT / "src" / "app" / "page.access" / "view.ts"
ACCESS_API = ROOT / "src" / "app" / "page.access" / "api.py"
AUTH_MODEL = ROOT / "src" / "model" / "struct" / "auth.py"
AUTH_SESSION_ROUTE = ROOT / "src" / "route" / "api-auth-session" / "controller.py"
AUTH_LOGIN_ROUTE = ROOT / "src" / "route" / "api-auth-login" / "controller.py"
SYSTEM_API = ROOT / "src" / "app" / "page.system" / "api.py"
SYSTEM_TS = ROOT / "src" / "app" / "page.system" / "view.ts"
SIDEBAR_VIEW = ROOT / "src" / "app" / "component.nav.sidebar" / "view.pug"
SIDEBAR_TS = ROOT / "src" / "app" / "component.nav.sidebar" / "view.ts"
LAYOUT_TS = ROOT / "src" / "app" / "layout.sidebar" / "view.ts"
BOOT_CONFIG = ROOT.parents[1] / "config" / "boot.py"


class AuthSetupStaticContractTest(unittest.TestCase):
    def test_cookie_policy_lives_in_boot_and_auth_guard_lives_in_user_controller(self):
        base_controller = BASE_CONTROLLER.read_text(encoding="utf-8")
        user_controller = USER_CONTROLLER.read_text(encoding="utf-8")
        boot = BOOT_CONFIG.read_text(encoding="utf-8")

        self.assertIn('SESSION_COOKIE_NAME = "docker_infra_session"', boot)
        self.assertIn('flask_app.config["SESSION_COOKIE_HTTPONLY"] = True', boot)
        self.assertIn('flask_app.config["SESSION_COOKIE_SAMESITE"] = "Lax"', boot)
        self.assertIn("def bootstrap(app, config):", boot)
        self.assertIn("def before_request(wiz):", boot)
        self.assertIn("def after_request(wiz, response):", boot)
        self.assertNotIn("SESSION_COOKIE", base_controller)
        self.assertNotIn("enforce_access", base_controller)
        self.assertNotIn('wiz.model("struct").setup', base_controller)
        self.assertIn("AUTHENTICATION_REQUIRED", user_controller)
        self.assertIn('wiz.controller("base")', user_controller)

    def test_protected_pages_use_user_controller(self):
        protected_apps = [
            "layout.sidebar",
            "page.dashboard",
            "page.servers",
            "page.services",
            "page.services.create",
            "page.domains",
            "page.images",
            "page.macros",
            "page.operations",
            "page.system",
        ]
        for app in protected_apps:
            with self.subTest(app=app):
                app_json = ROOT / "src" / "app" / app / "app.json"
                self.assertEqual(json.loads(app_json.read_text(encoding="utf-8"))["controller"], "user")

    def test_access_page_contains_installer_notice_and_login_selectors(self):
        view = ACCESS_VIEW.read_text(encoding="utf-8")
        api = ACCESS_API.read_text(encoding="utf-8")

        for token in [
            'data-testid="installer-open"',
            'data-testid="password-input"',
            'data-testid="login-submit"',
        ]:
            self.assertIn(token, view)

        self.assertNotIn('data-testid="setup-password-input"', view)
        self.assertNotIn('data-testid="setup-submit"', view)

        for token in ["def setup_status()", "def login()", "def logout()"]:
            self.assertIn(token, api)
        self.assertNotIn("def setup()", api)
        self.assertNotIn("def disable_backup_system()", api)

        view_ts = ACCESS_TS.read_text(encoding="utf-8")
        self.assertIn("redirectAuthenticated", view_ts)
        self.assertNotIn("sessionDurationLabel", view_ts)
        self.assertNotIn("세션 지속시간", view)

    def test_session_duration_policy_is_configurable_and_displayed(self):
        auth_model = AUTH_MODEL.read_text(encoding="utf-8")
        access_api = ACCESS_API.read_text(encoding="utf-8")
        login_route = AUTH_LOGIN_ROUTE.read_text(encoding="utf-8")
        session_route = AUTH_SESSION_ROUTE.read_text(encoding="utf-8")
        system_api = SYSTEM_API.read_text(encoding="utf-8")
        system_ts = SYSTEM_TS.read_text(encoding="utf-8")
        sidebar_view = SIDEBAR_VIEW.read_text(encoding="utf-8")
        sidebar_ts = SIDEBAR_TS.read_text(encoding="utf-8")

        for token in [
            "SESSION_TTL_SETTING_KEY",
            "auth.session_ttl_hours",
            "save_session_policy",
            "session_policy",
            "SESSION_TOKEN_COOKIE_NAME",
            "remember_session_cookie",
            "extend_session",
            "remaining_seconds",
        ]:
            self.assertIn(token, auth_model)
        self.assertIn("session_policy", access_api)
        self.assertIn("auth.remember_session_cookie", access_api)
        self.assertIn("auth.remember_session_cookie", login_route)
        self.assertIn("auth.request_session_token", session_route)
        self.assertIn('method not in ["GET", "POST", "DELETE"]', session_route)
        self.assertIn("auth.extend_session", session_route)
        self.assertIn("auth.extend_session", system_api)
        self.assertIn("docker-infra:session-updated", system_ts)
        self.assertIn("세션 남은 시간", sidebar_view)
        self.assertIn('data-testid="session-extend"', sidebar_view)
        self.assertIn("fa-arrow-rotate-right", sidebar_view)
        self.assertIn("sessionRemainingLabel", sidebar_ts)
        self.assertIn("extendSession", sidebar_ts)
        self.assertIn("sessionExtending", sidebar_ts)
        self.assertIn("handleSessionUpdated", sidebar_ts)
        self.assertIn("remaining_seconds", sidebar_ts)
        self.assertIn("/api/auth/session", sidebar_ts)

    def test_layout_sidebar_uses_existing_auth_check_without_extra_session_route(self):
        layout = LAYOUT_TS.read_text(encoding="utf-8")

        self.assertIn("this.service.auth?.check?.()", layout)
        self.assertNotIn("/api/auth/session", layout)


class AuthSetupLiveFlowTest(unittest.TestCase):
    def setUp(self):
        self.client = DockerInfraApiClient.from_env()

    def test_access_setup_status_returns_runtime_checks_as_json(self):
        response = self.client.post("/wiz/api/page.access/setup_status", json={}, validate=False)

        self.assertEqual(response.status_code, 200, response.text[:500])
        self.assertEqual(response.headers.get("content-type", "").split(";")[0], "application/json")
        payload = response.json()
        self.assertEqual(payload["code"], 200)
        setup = payload["data"]["setup"]
        self.assertIn("requires_setup", setup)
        checks = setup["checks"]
        self.assertIn(checks["docker"]["daemon"], {"ok", "missing", "timeout", "error"})
        self.assertNotEqual(checks["docker"]["daemon"], "unknown")
        self.assertIn(checks["proxy"]["nginx"]["status"], {"ok", "missing", "timeout", "error"})
        apache2 = checks["proxy"].get("apache2") or {"status": "missing"}
        self.assertIn(apache2["status"], {"ok", "missing", "timeout", "error"})

    def test_empty_password_login_returns_validation_error_json(self):
        response = self.client.post("/wiz/api/page.access/login", json={"password": ""}, validate=False)

        self.assertIn(response.status_code, {200, 400}, response.text[:500])
        payload = response.json()
        self.assertEqual(payload["code"], 400)
        self.assertEqual(payload["data"]["error_code"], "PASSWORD_REQUIRED")

    def test_protected_dashboard_redirects_without_session(self):
        response = self.client.get("/dashboard", allow_redirects=False, validate=False)

        self.assertIn(response.status_code, {200, 302, 303})
        if response.status_code in {302, 303}:
            self.assertIn("/access", response.headers.get("location", ""))
        else:
            self.assertIn("text/html", response.headers.get("content-type", ""))


if __name__ == "__main__":
    unittest.main()
