import json
import unittest
from pathlib import Path

from tests.fixtures.api_client import DockerInfraApiClient, password_only_login


ROOT = Path(__file__).resolve().parents[2]
ROUTE_ROOT = ROOT / "src" / "route" / "api-system-local-command-check"
OPENAPI_JSON = ROOT / "docs" / "api" / "openapi.json"


class LocalExecutorStaticContractTest(unittest.TestCase):
    def test_local_command_check_route_and_openapi_contract_are_registered(self):
        app_config = json.loads((ROUTE_ROOT / "app.json").read_text(encoding="utf-8"))
        controller = (ROUTE_ROOT / "controller.py").read_text(encoding="utf-8")
        document = OPENAPI_JSON.read_text(encoding="utf-8")

        self.assertEqual(app_config["route"], "/api/system/local-command/check")
        self.assertEqual(app_config["controller"], "user")
        self.assertIn("executor.check", controller)
        for token in ["LocalCommandCheckRequest", "LocalCommandCheckResponse", "LocalCommandResult"]:
            self.assertIn(token, document)


class LocalExecutorLiveFlowTest(unittest.TestCase):
    def setUp(self):
        self.client = DockerInfraApiClient.from_env(self)
        password_only_login(self.client, testcase=self)

    def test_diagnostic_success_and_failure_return_http_results(self):
        success = self.client.post(
            "/api/system/local-command/check",
            json={"target": "diagnostic.success"},
            validate=False,
        )
        failure = self.client.post(
            "/api/system/local-command/check",
            json={"target": "diagnostic.failure"},
            validate=False,
        )

        self.assertEqual(success.status_code, 200, success.text[:500])
        self.assertEqual(success.json()["data"]["result"]["status"], "ok")
        self.assertEqual(failure.status_code, 200, failure.text[:500])
        self.assertEqual(failure.json()["data"]["result"]["status"], "error")
        self.assertEqual(failure.json()["data"]["result"]["exit_code"], 42)

    def test_unknown_command_is_rejected_by_api(self):
        response = self.client.post(
            "/api/system/local-command/check",
            json={"target": "unknown.command"},
            validate=False,
        )

        self.assertEqual(response.status_code, 404, response.text[:500])
        self.assertEqual(response.json()["data"]["error_code"], "LOCAL_COMMAND_NOT_FOUND")


if __name__ == "__main__":
    unittest.main()
