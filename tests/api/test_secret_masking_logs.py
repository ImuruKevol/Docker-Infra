import json
import unittest
from pathlib import Path

from tests.fixtures.api_client import DockerInfraApiClient, password_only_login


ROOT = Path(__file__).resolve().parents[2]
JOBS_PATH_ROUTE = ROOT / "src" / "route" / "api-jobs-path" / "controller.py"


class SecretMaskingLogsStaticContractTest(unittest.TestCase):
    def test_log_routes_expose_search_and_download_actions(self):
        controller = JOBS_PATH_ROUTE.read_text(encoding="utf-8")

        self.assertIn('action == "logs"', controller)
        self.assertIn('action == "logs/search"', controller)
        self.assertIn('action == "logs/download"', controller)
        self.assertIn("secret_values", controller)


class SecretMaskingLogsLiveFlowTest(unittest.TestCase):
    def setUp(self):
        self.client = DockerInfraApiClient.from_env(self)
        password_only_login(self.client, testcase=self)

    def test_runtime_secret_is_masked_before_search_and_download(self):
        create = self.client.post(
            "/api/jobs",
            json={"type": "masking-flow", "steps": ["capture"], "test_run_id": self.client.test_run_id},
            validate=False,
        )
        self.assertEqual(create.status_code, 200, create.text[:500])
        job_id = create.json()["data"]["job"]["id"]

        append = self.client.post(
            f"/api/jobs/{job_id}/logs",
            json={
                "stream": "stderr",
                "message": "deploy token=plain-token-value failed",
                "secret_values": ["plain-token-value"],
            },
            validate=False,
        )
        search = self.client.post(f"/api/jobs/{job_id}/logs/search", json={"query": "plain-token-value"}, validate=False)
        download = self.client.get(f"/api/jobs/{job_id}/logs/download", validate=False)

        for response in [append, search, download]:
            self.assertEqual(response.status_code, 200, response.text[:500])
            self.assertNotIn("plain-token-value", json.dumps(response.json(), ensure_ascii=False))
        self.assertIn("********", json.dumps(download.json(), ensure_ascii=False))


if __name__ == "__main__":
    unittest.main()
