import json
import unittest
from pathlib import Path

from tests.fixtures.api_client import DockerInfraApiClient, password_only_login


ROOT = Path(__file__).resolve().parents[2]
JOBS_ROUTE = ROOT / "src" / "route" / "api-jobs" / "controller.py"
JOBS_PATH_ROUTE = ROOT / "src" / "route" / "api-jobs-path" / "controller.py"


class JobsApiStaticContractTest(unittest.TestCase):
    def test_jobs_routes_are_registered(self):
        routes = {
            "api-jobs": "/api/jobs",
            "api-jobs-path": "/api/jobs/<path:path>",
        }
        for folder, route in routes.items():
            app_json = ROOT / "src" / "route" / folder / "app.json"
            config = json.loads(app_json.read_text(encoding="utf-8"))
            self.assertEqual(config["route"], route)
            self.assertEqual(config["controller"], "user")

        self.assertIn("jobs.create", JOBS_ROUTE.read_text(encoding="utf-8"))
        self.assertIn("transition_job", JOBS_PATH_ROUTE.read_text(encoding="utf-8"))


class JobsApiLiveFlowTest(unittest.TestCase):
    def setUp(self):
        self.client = DockerInfraApiClient.from_env(self)
        password_only_login(self.client, testcase=self)

    def test_create_transition_log_search_download_and_retry_flow(self):
        create = self.client.post(
            "/api/jobs",
            json={
                "type": "api-flow-test",
                "steps": [{"name": "prepare"}, {"name": "run"}],
                "requested_payload": {"source": "live-http"},
                "test_run_id": self.client.test_run_id,
            },
            validate=False,
        )
        self.assertEqual(create.status_code, 200, create.text[:500])
        job = create.json()["data"]["job"]

        status = self.client.post(f"/api/jobs/{job['id']}/status", json={"status": "running"}, validate=False)
        log = self.client.post(
            f"/api/jobs/{job['id']}/logs",
            json={"stream": "stdout", "message": "password=secret-from-test", "secret_values": ["secret-from-test"]},
            validate=False,
        )
        search = self.client.post(f"/api/jobs/{job['id']}/logs/search", json={"query": "********"}, validate=False)
        download = self.client.get(f"/api/jobs/{job['id']}/logs/download", validate=False)
        failed = self.client.post(f"/api/jobs/{job['id']}/status", json={"status": "failed"}, validate=False)
        retry = self.client.post(f"/api/jobs/{job['id']}/retry", json={}, validate=False)

        for response in [status, log, search, download, failed, retry]:
            self.assertEqual(response.status_code, 200, response.text[:500])
        self.assertNotIn("secret-from-test", json.dumps(log.json(), ensure_ascii=False))
        self.assertNotIn("secret-from-test", json.dumps(search.json(), ensure_ascii=False))
        self.assertNotIn("secret-from-test", json.dumps(download.json(), ensure_ascii=False))
        self.assertEqual(retry.json()["data"]["job"]["metadata"]["retry_of"], job["id"])


if __name__ == "__main__":
    unittest.main()
