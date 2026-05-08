import unittest
from time import sleep
from uuid import uuid4
from pathlib import Path

from tests.fixtures.api_client import DockerInfraApiClient, password_only_login


class ServerMacrosStaticContractTest(unittest.TestCase):
    def test_servers_and_global_macros_pages_declare_editor_terminal_and_api_contracts(self):
        servers_view = Path("/root/docker-infra/project/main/src/app/page.servers/view.pug").read_text(encoding="utf-8")
        servers_api = Path("/root/docker-infra/project/main/src/app/page.servers/api.py").read_text(encoding="utf-8")
        servers_socket = Path("/root/docker-infra/project/main/src/app/page.servers/socket.py").read_text(encoding="utf-8")
        macros_view = Path("/root/docker-infra/project/main/src/app/page.macros/view.pug").read_text(encoding="utf-8")
        macros_api = Path("/root/docker-infra/project/main/src/app/page.macros/api.py").read_text(encoding="utf-8")
        search_select_view = Path("/root/docker-infra/project/main/src/app/component.search.select/view.html").read_text(encoding="utf-8")

        for token in ["매크로", "웹 터미널", "nu-monaco-editor", "servers-terminal-host", "wiz-component-search-select"]:
            self.assertIn(token, servers_view)
        for token in ["전역 매크로", "nu-monaco-editor"]:
            self.assertIn(token, macros_view)
        for token in ["data-search-select-input", "valueChange.emit", "filteredItems()"]:
            self.assertIn(token, search_select_view if token == "data-search-select-input" else Path("/root/docker-infra/project/main/src/app/component.search.select/view.ts").read_text(encoding="utf-8"))
        for token in ["def list_macros()", "def save_macro()", "def delete_macro()", "def run_macro()"]:
            self.assertIn(token, servers_api)
        for token in ["def load()", "def save_macro()", "def delete_macro()"]:
            self.assertIn(token, macros_api)
        for token in ["def create(self, wiz, data, io):", "def ptyinput(self, wiz, data):", "def resize(self, wiz, data):", "def close(self, wiz, data, io):"]:
            self.assertIn(token, servers_socket)
        macros_store = Path("/root/docker-infra/project/main/src/model/struct/macros_store.py").read_text(encoding="utf-8")
        for token in ["scope_type", "available_for_node", "node_id"]:
            self.assertIn(token, macros_store)


class ServerMacrosLiveFlowTest(unittest.TestCase):
    def setUp(self):
        self.client = DockerInfraApiClient.from_env(self)
        password_only_login(self.client, testcase=self)

    def wait_operation(self, operation_id, timeout_seconds=20):
        deadline = timeout_seconds * 10
        for _ in range(deadline):
            response = self.client.post(
                "/wiz/api/page.servers/operation_status",
                json={"operation_id": operation_id},
                validate=False,
            )
            self.assertEqual(response.status_code, 200, response.text[:500])
            operation = response.json()["data"]["operation"]
            if operation["status"] in {"succeeded", "failed", "canceled"}:
                return operation
            sleep(0.1)
        self.fail(f"operation {operation_id} did not finish within {timeout_seconds}s")

    def test_global_and_node_macros_can_be_saved_listed_run_and_deleted(self):
        global_name = f"macro-global-{uuid4().hex[:8]}"
        node_name = f"macro-node-{uuid4().hex[:8]}"
        created_global_id = None
        created_node_id = None
        try:
            load = self.client.post("/wiz/api/page.servers/load", json={}, validate=False)
            self.assertEqual(load.status_code, 200, load.text[:500])
            nodes = load.json()["data"]["nodes"]
            local = next(node for node in nodes if node.get("is_local_master"))

            create_global = self.client.post(
                "/wiz/api/page.macros/save_macro",
                json={
                    "name": global_name,
                    "description": "global test macro",
                    "script": "#!/usr/bin/env bash\necho global:$1\n",
                    "enabled": True,
                    "test_run_id": self.client.test_run_id,
                },
                validate=False,
            )
            self.assertEqual(create_global.status_code, 200, create_global.text[:500])
            created_global = create_global.json()["data"]["macro"]
            created_global_id = created_global["id"]
            self.assertEqual(created_global["scope_type"], "global")

            create_node = self.client.post(
                "/wiz/api/page.servers/save_macro",
                json={
                    "node_id": local["id"],
                    "name": node_name,
                    "description": "node test macro",
                    "script": "#!/usr/bin/env bash\necho node:$1\n",
                    "enabled": True,
                    "test_run_id": self.client.test_run_id,
                },
                validate=False,
            )
            self.assertEqual(create_node.status_code, 200, create_node.text[:500])
            created_node = create_node.json()["data"]["macro"]
            created_node_id = created_node["id"]
            self.assertEqual(created_node["scope_type"], "node")
            self.assertEqual(created_node["node_id"], local["id"])

            listed_global = self.client.post("/wiz/api/page.macros/load", json={}, validate=False)
            self.assertEqual(listed_global.status_code, 200, listed_global.text[:500])
            self.assertTrue(any(item["id"] == created_global_id for item in listed_global.json()["data"]["macros"]))

            listed_server = self.client.post(
                "/wiz/api/page.servers/list_macros",
                json={"node_id": local["id"]},
                validate=False,
            )
            self.assertEqual(listed_server.status_code, 200, listed_server.text[:500])
            server_payload = listed_server.json()["data"]
            self.assertTrue(any(item["id"] == created_global_id for item in server_payload["global_macros"]))
            self.assertTrue(any(item["id"] == created_node_id for item in server_payload["node_macros"]))
            self.assertTrue(any(item["id"] == created_global_id for item in server_payload["available_macros"]))
            self.assertTrue(any(item["id"] == created_node_id for item in server_payload["available_macros"]))

            run_global = self.client.post(
                "/wiz/api/page.servers/run_macro",
                json={"macro_id": created_global_id, "node_id": local["id"], "args": "hello"},
                validate=False,
                timeout=20,
            )
            self.assertEqual(run_global.status_code, 200, run_global.text[:500])
            global_operation = self.wait_operation(run_global.json()["data"]["operation"]["id"])
            self.assertEqual(global_operation["status"], "succeeded")
            self.assertTrue(any("global:hello" in (entry.get("message") or "") for entry in global_operation["output"]))

            run_node = self.client.post(
                "/wiz/api/page.servers/run_macro",
                json={"macro_id": created_node_id, "node_id": local["id"], "args": "world"},
                validate=False,
                timeout=20,
            )
            self.assertEqual(run_node.status_code, 200, run_node.text[:500])
            node_operation = self.wait_operation(run_node.json()["data"]["operation"]["id"])
            self.assertEqual(node_operation["status"], "succeeded")
            self.assertTrue(any("node:world" in (entry.get("message") or "") for entry in node_operation["output"]))
        finally:
            if created_node_id:
                self.client.post("/wiz/api/page.servers/delete_macro", json={"macro_id": created_node_id}, validate=False)
            if created_global_id:
                self.client.post("/wiz/api/page.macros/delete_macro", json={"macro_id": created_global_id}, validate=False)


if __name__ == "__main__":
    unittest.main()
