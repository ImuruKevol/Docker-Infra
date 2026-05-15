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

        self.assertIn("redirectAuthenticated", ACCESS_TS.read_text(encoding="utf-8"))

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
