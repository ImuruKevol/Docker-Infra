import json
import os
import unittest
from pathlib import Path

from tests.fixtures.api_client import DockerInfraApiClient, password_only_login


ROOT = Path(__file__).resolve().parents[2]
NODES_PATH_ROUTE = ROOT / "src" / "route" / "api-nodes-path" / "controller.py"
REPORTER_ROUTE = ROOT / "src" / "route" / "api-reporter-metrics" / "controller.py"
SERVERS_VIEW = ROOT / "src" / "app" / "page.servers" / "view.pug"
SERVERS_API = ROOT / "src" / "app" / "page.servers" / "api.py"


class NodeReporterStaticContractTest(unittest.TestCase):
    def test_reporter_routes_and_servers_page_contract_are_declared(self):
        nodes_controller = NODES_PATH_ROUTE.read_text(encoding="utf-8")
        reporter_controller = REPORTER_ROUTE.read_text(encoding="utf-8")
        servers_view = SERVERS_VIEW.read_text(encoding="utf-8")
        servers_api = SERVERS_API.read_text(encoding="utf-8")

        for token in ['action == "reporter-token"', 'action == "metrics"', 'action == "containers"']:
            self.assertIn(token, nodes_controller)
        self.assertIn("ingest_metric", reporter_controller)
        self.assertIn("overview()", servers_api)
        for token in [
            'data-testid="servers-node-list"',
            'data-testid="servers-detail"',
            'data-testid="servers-cpu"',
            'data-testid="servers-memory"',
            'data-testid="servers-storage"',
            'data-testid="servers-containers-table"',
        ]:
            self.assertIn(token, servers_view)


class NodeReporterLiveFlowTest(unittest.TestCase):
    def setUp(self):
        self.client = DockerInfraApiClient.from_env(self)
        password_only_login(self.client, testcase=self)

    def test_configured_node_reporter_token_metric_and_container_flow(self):
        node_id = os.environ.get("DOCKER_INFRA_TEST_NODE_ID")
        if not node_id:
            self.skipTest("DOCKER_INFRA_TEST_NODE_ID is not set")

        token_response = self.client.post(f"/api/nodes/{node_id}/reporter-token", json={}, validate=False)
        self.assertEqual(token_response.status_code, 200, token_response.text[:500])
        token = token_response.json()["data"]["token"]

        metric = self.client.post(
            "/api/reporter/metrics",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "node_id": node_id,
                "cpu_percent": 12.5,
                "memory": {"used_percent": 25.0},
                "storage": {"used_percent": 40.0},
                "containers": {"items": [{"id": "test-container", "name": "web", "state": "running"}]},
                "metadata": {"test_run_id": self.client.test_run_id},
            },
            validate=False,
        )
        metrics = self.client.get(f"/api/nodes/{node_id}/metrics?limit=1", validate=False)
        containers = self.client.get(f"/api/nodes/{node_id}/containers", validate=False)

        for response in [metric, metrics, containers]:
            self.assertEqual(response.status_code, 200, response.text[:500])
        self.assertEqual(containers.json()["data"]["containers"][0]["id"], "test-container")
        self.assertNotIn(token, json.dumps(metrics.json(), ensure_ascii=False))


if __name__ == "__main__":
    unittest.main()
