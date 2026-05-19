import json
import os
import unittest
from pathlib import Path

from tests.fixtures.api_client import DockerInfraApiClient, password_only_login


ROOT = Path(__file__).resolve().parents[2]
OPENAPI_JSON = ROOT / "docs" / "api" / "openapi.json"


class NodesSwarmStaticContractTest(unittest.TestCase):
    def test_node_routes_and_openapi_contract_are_declared(self):
        routes = {
            "api-system-local-master-ensure": "/api/system/local-master/ensure",
            "api-nodes": "/api/nodes",
            "api-nodes-path": "/api/nodes/<path:path>",
        }
        for folder, route in routes.items():
            config = json.loads((ROOT / "src" / "route" / folder / "app.json").read_text(encoding="utf-8"))
            self.assertEqual(config["route"], route)
            self.assertEqual(config["controller"], "user")

        document = OPENAPI_JSON.read_text(encoding="utf-8")
        node_path_controller = (ROOT / "src" / "route" / "api-nodes-path" / "controller.py").read_text(encoding="utf-8")
        servers_api = (ROOT / "src" / "app" / "page.servers" / "api.py").read_text(encoding="utf-8")
        servers_view = (ROOT / "src" / "app" / "page.servers" / "view.pug").read_text(encoding="utf-8")
        servers_view_ts = (ROOT / "src" / "app" / "page.servers" / "view.ts").read_text(encoding="utf-8")
        nodes_model = (ROOT / "src" / "model" / "struct" / "nodes.py").read_text(encoding="utf-8")
        nodes_delete = (ROOT / "src" / "model" / "struct" / "nodes_delete.py").read_text(encoding="utf-8")
        for token in [
            "/api/system/local-master/ensure",
            "/api/nodes",
            "/api/nodes/{node_id}/check",
            "/api/nodes/{node_id}/join",
            "NodeJoinResponse",
            "NodeUnregisterRequest",
            "NodeUnregisterResponse",
        ]:
            self.assertIn(token, document)
        self.assertIn("DELETE", node_path_controller)
        self.assertIn("unregister_slave", node_path_controller)
        self.assertIn("def unregister_server", servers_api)
        self.assertIn("openDeleteServer()", servers_view)
        self.assertIn("runningServiceGroups", servers_view_ts)
        self.assertIn("NodeDeleteMixin", nodes_model)
        self.assertIn("NODE_RUNNING_SERVICES_BLOCK_UNREGISTER", nodes_delete)
        self.assertIn("live_containers", nodes_delete)


class NodesSwarmLiveFlowTest(unittest.TestCase):
    def setUp(self):
        self.client = DockerInfraApiClient.from_env(self)
        password_only_login(self.client, testcase=self)

    def test_local_master_ensure_api_returns_overlay_network_result(self):
        response = self.client.post(
            "/api/system/local-master/ensure",
            json={"test_run_id": self.client.test_run_id},
            validate=False,
        )

        self.assertIn(response.status_code, {200, 403}, response.text[:500])
        if response.status_code == 403:
            self.assertEqual(response.json()["data"]["error_code"], "LOCAL_COMMAND_NOT_ALLOWLISTED")
            return
        data = response.json()["data"]
        self.assertIn("local_master", data)
        self.assertIn("overlay_network", data)

    def test_configured_test_slave_host_can_be_registered_and_checked(self):
        host = os.environ.get("DOCKER_INFRA_TEST_SSH_HOST")
        if not host:
            self.skipTest("DOCKER_INFRA_TEST_SSH_HOST is not set")
        password = os.environ.get("DOCKER_INFRA_TEST_SSH_PASSWORD")
        if not password:
            self.skipTest("DOCKER_INFRA_TEST_SSH_PASSWORD is not set")
        username = os.environ.get("DOCKER_INFRA_TEST_SSH_USER", "root")

        register = self.client.post(
            "/api/nodes",
            json={
                "name": host,
                "host": host,
                "username": username,
                "password": password,
                "ssh_port": int(os.environ.get("DOCKER_INFRA_TEST_SSH_PORT", "22")),
                "test_run_id": self.client.test_run_id,
            },
            validate=False,
        )
        self.assertEqual(register.status_code, 200, register.text[:500])
        node_id = register.json()["data"]["node"]["id"]
        check = self.client.post(f"/api/nodes/{node_id}/check", json={}, validate=False)
        self.assertEqual(check.status_code, 200, check.text[:500])
        self.assertIn("ssh", check.json()["data"])


if __name__ == "__main__":
    unittest.main()
