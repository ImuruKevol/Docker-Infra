import json
import unittest
from pathlib import Path

from tests.fixtures.api_client import DockerInfraApiClient, password_only_login


ROOT = Path(__file__).resolve().parents[2]
SETTINGS_ROUTE = ROOT / "src" / "route" / "api-system-settings" / "controller.py"
APPEARANCE_ROUTE = ROOT / "src" / "route" / "api-system-appearance" / "controller.py"
SIDEBAR_TS = ROOT / "src" / "app" / "component.nav.sidebar" / "view.ts"
ASSET_ROUTE = ROOT / "src" / "route" / "api-system-assets" / "controller.py"
AUTH_ROUTE = ROOT / "src" / "portal" / "season" / "route" / "auth" / "controller.py"
DOMAINS_API = ROOT / "src" / "app" / "page.domains" / "api.py"
SYSTEM_API = ROOT / "src" / "app" / "page.system" / "api.py"
SYSTEM_VIEW = ROOT / "src" / "app" / "page.system" / "view.pug"
SYSTEM_TS = ROOT / "src" / "app" / "page.system" / "view.ts"
CODEX_RUNTIME_MODEL = ROOT / "src" / "model" / "struct" / "codex_runtime.py"
AUTH_MODEL = ROOT / "src" / "model" / "struct" / "auth.py"
SETUP_MODEL = ROOT / "src" / "model" / "struct" / "setup.py"
DASHBOARD_VIEW = ROOT / "src" / "app" / "page.dashboard" / "view.pug"
APP_MODULE = ROOT / "src" / "angular" / "app" / "app.module.ts"
APP_INITIALIZER = ROOT / "src" / "angular" / "app" / "appearance.initializer.ts"
APPEARANCE_RUNTIME = ROOT / "src" / "portal" / "season" / "libs" / "appearance.ts"


class SystemSettingsStaticContractTest(unittest.TestCase):
    def test_settings_routes_and_domains_contract_are_declared(self):
        controller = SETTINGS_ROUTE.read_text(encoding="utf-8")
        appearance_route = APPEARANCE_ROUTE.read_text(encoding="utf-8")
        sidebar = SIDEBAR_TS.read_text(encoding="utf-8")
        assets = ASSET_ROUTE.read_text(encoding="utf-8")
        auth_route = AUTH_ROUTE.read_text(encoding="utf-8")
        domains_api = DOMAINS_API.read_text(encoding="utf-8")
        system_api = SYSTEM_API.read_text(encoding="utf-8")
        system_view = SYSTEM_VIEW.read_text(encoding="utf-8")
        system_ts = SYSTEM_TS.read_text(encoding="utf-8")
        codex_runtime = CODEX_RUNTIME_MODEL.read_text(encoding="utf-8")
        auth_model = AUTH_MODEL.read_text(encoding="utf-8")
        setup_model = SETUP_MODEL.read_text(encoding="utf-8")
        dashboard_view = DASHBOARD_VIEW.read_text(encoding="utf-8")
        app_module = APP_MODULE.read_text(encoding="utf-8")
        app_initializer = APP_INITIALIZER.read_text(encoding="utf-8")
        appearance_runtime = APPEARANCE_RUNTIME.read_text(encoding="utf-8")

        self.assertIn("settings.upsert", controller)
        self.assertIn("def as_bool(value):", controller)
        self.assertIn("AppearanceRuntime.read()", sidebar)
        self.assertIn("appearance.store_asset", assets)
        self.assertNotIn("appearance.public_payload()", auth_route)
        self.assertIn("appearance.public_payload()", appearance_route)
        self.assertIn("APPEARANCE_INITIALIZER_PROVIDER", app_module)
        self.assertIn("APP_INITIALIZER", app_initializer)
        self.assertIn("/api/system/appearance", appearance_runtime)
        self.assertIn("def sync_zone():", domains_api)
        self.assertIn("def save_record():", domains_api)
        self.assertIn("def delete_record():", domains_api)
        self.assertIn("def change_admin_password():", system_api)
        self.assertIn("auth.change_password", system_api)
        self.assertIn("def change_password(", auth_model)
        self.assertIn("INVALID_CURRENT_PASSWORD", auth_model)
        self.assertIn("system-admin-current-password", system_view)
        self.assertIn("system-admin-new-password", system_view)
        self.assertIn("system-admin-password-save", system_view)
        self.assertIn("changeAdminPassword()", system_ts)
        for token in ["def ai_codex_device_login_start():", "def ai_codex_device_login_status():", "def ai_codex_device_login_cancel():"]:
            self.assertIn(token, system_api)
        for token in ["startCodexDeviceLogin()", "codexDeviceLogin()", "copyCodexDeviceCode()", "브라우저 로그인", "One-time code"]:
            self.assertIn(token, system_view + system_ts)
        for token in ["def start_device_login", "codex login --device-auth", "verification_uri", "user_code", "cancel_device_login", "pty.openpty", "_read_device_login_pty"]:
            self.assertIn(token, codex_runtime)
        self.assertNotIn("public_url", setup_model)
        self.assertNotIn("public_url", dashboard_view)


class SystemSettingsLiveFlowTest(unittest.TestCase):
    def setUp(self):
        self.client = DockerInfraApiClient.from_env(self)
        password_only_login(self.client, testcase=self)

    def test_setting_create_read_and_delete_flow_masks_secret_values(self):
        key = f"integration.test.secret.{self.client.test_run_id}"
        upsert = self.client.post(
            "/api/system/settings",
            json={
                "key": key,
                "value": "plain-secret-value",
                "value_type": "secret",
                "is_secret": True,
                "test_run_id": self.client.test_run_id,
            },
            validate=False,
        )
        read = self.client.get(f"/api/system/settings?key={key}", validate=False)
        delete = self.client.request("DELETE", "/api/system/settings", json={"key": key}, validate=False)

        for response in [upsert, read, delete]:
            self.assertEqual(response.status_code, 200, response.text[:500])
            self.assertNotIn("plain-secret-value", json.dumps(response.json(), ensure_ascii=False))
        self.assertEqual(upsert.json()["data"]["setting"]["secret"]["masked_value"], "********")
        self.assertTrue(delete.json()["data"]["deleted"])

    def test_public_appearance_endpoint_returns_general_branding(self):
        response = self.client.get("/api/system/appearance", validate=False)
        self.assertEqual(response.status_code, 200, response.text[:500])
        appearance = response.json()["data"]["appearance"]
        self.assertIn("browser_title", appearance)
        self.assertIn("favicon_url", appearance)
        self.assertIn("logo_url", appearance)

if __name__ == "__main__":
    unittest.main()
