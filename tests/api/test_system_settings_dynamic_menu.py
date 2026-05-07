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
        self.assertIn("def save_webserver():", system_api)
        self.assertIn("def browse_local_files():", system_api)
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

    def test_browse_local_files_accepts_file_path_and_opens_parent_directory(self):
        file_path = str(ROOT / "src" / "app" / "page.system" / "view.ts")
        response = self.client.post(
            "/wiz/api/page.system/browse_local_files",
            json={"path": file_path, "show_hidden": False},
            validate=False,
        )
        self.assertEqual(response.status_code, 200, response.text[:500])
        data = response.json()["data"]
        self.assertEqual(data["path"], str((ROOT / "src" / "app" / "page.system").resolve()))
        item_names = {item["name"] for item in data["items"]}
        self.assertIn("view.ts", item_names)


if __name__ == "__main__":
    unittest.main()
