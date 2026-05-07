import json
import unittest
from pathlib import Path

from tests.fixtures.api_client import DockerInfraApiClient, password_only_login


ROOT = Path(__file__).resolve().parents[2]
SETTINGS_ROUTE = ROOT / "src" / "route" / "api-system-settings" / "controller.py"
SIDEBAR_TS = ROOT / "src" / "app" / "component.nav.sidebar" / "view.ts"


class SystemSettingsStaticContractTest(unittest.TestCase):
    def test_settings_route_and_sidebar_dynamic_menu_contract_are_declared(self):
        controller = SETTINGS_ROUTE.read_text(encoding="utf-8")
        sidebar = SIDEBAR_TS.read_text(encoding="utf-8")

        self.assertIn("settings.upsert", controller)
        self.assertIn("def as_bool(value):", controller)
        self.assertIn("integration.cloudflare.enabled", sidebar)
        self.assertIn("integration.harbor.enabled", sidebar)
        self.assertIn("sidebarSettingsPromise", sidebar)
        self.assertIn("sidebarSettingsCache", sidebar)


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
        delete = self.client.request("DELETE", f"/api/system/settings?key={key}", validate=False)

        for response in [upsert, read, delete]:
            self.assertEqual(response.status_code, 200, response.text[:500])
            self.assertNotIn("plain-secret-value", json.dumps(response.json(), ensure_ascii=False))
        self.assertEqual(upsert.json()["data"]["setting"]["secret"]["masked_value"], "********")
        self.assertTrue(delete.json()["data"]["deleted"])


if __name__ == "__main__":
    unittest.main()
