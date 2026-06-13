import unittest
from pathlib import Path
from time import sleep
from uuid import uuid4

from tests.fixtures.api_client import DockerInfraApiClient, password_only_login


class ServerMacrosStaticContractTest(unittest.TestCase):
    def test_macro_page_declares_unified_run_and_attachment_contracts(self):
        servers_view = Path("/root/docker-infra/project/main/src/app/page.servers/view.pug").read_text(encoding="utf-8")
        servers_api = Path("/root/docker-infra/project/main/src/app/page.servers/api.py").read_text(encoding="utf-8")
        servers_socket = Path("/root/docker-infra/project/main/src/app/page.servers/socket.py").read_text(encoding="utf-8")
        macros_view = Path("/root/docker-infra/project/main/src/app/page.macros/view.pug").read_text(encoding="utf-8")
        macros_ts = Path("/root/docker-infra/project/main/src/app/page.macros/view.ts").read_text(encoding="utf-8")
        macros_api = Path("/root/docker-infra/project/main/src/app/page.macros/api.py").read_text(encoding="utf-8")
        search_select_view = Path("/root/docker-infra/project/main/src/app/component.search.select/view.html").read_text(encoding="utf-8")

        self.assertNotIn("setDetailTab('macros')", servers_view)
        for token in ["웹 터미널", "servers-terminal-host"]:
            self.assertIn(token, servers_view)
        for token in [
            "매크로 목록",
            "nu-monaco-editor",
            "첨부 파일",
            "selectMacroFiles($event)",
            "downloadMacroFile(file, $event)",
            "runTargetType() === 'service'",
            "serviceTargetServiceItems()",
            "serviceContainerTargetItems()",
            "macroArgsEnabled()",
            "macroArgsInput()",
            "실행 인자 사용",
            "페이지당 10개",
        ]:
            self.assertIn(token, macros_view)
        self.assertNotIn("페이지당 20개", macros_view)
        for token in ["public pageSize = 10", "selectedServiceId", "container_display_name", "macroArgsEnabled", "macroArgsInput"]:
            self.assertIn(token, macros_ts)
        for token in ["data-search-select-input", "valueChange.emit", "filteredItems()"]:
            self.assertIn(token, search_select_view if token == "data-search-select-input" else Path("/root/docker-infra/project/main/src/app/component.search.select/view.ts").read_text(encoding="utf-8"))
        for token in ["def list_macros()", "def run_macro()"]:
            self.assertIn(token, servers_api)
        for token in ["def load()", "def save_macro()", "def delete_macro()", "def run_macro()", "def operation_status()", "def download_macro_file()", "container_display_name", "_friendly_container_name"]:
            self.assertIn(token, macros_api)
        for token in ["def create(self, wiz, data, io):", "def ptyinput(self, wiz, data):", "def resize(self, wiz, data):", "def close(self, wiz, data, io):"]:
            self.assertIn(token, servers_socket)
        macros_store = Path("/root/docker-infra/project/main/src/model/struct/macros_store.py").read_text(encoding="utf-8")
        for token in ["scope_type", "available_for_node", "node_id", "shell_macro_files", "keep_file_ids", "download_file"]:
            self.assertIn(token, macros_store)
        macros_runner = Path("/root/docker-infra/project/main/src/model/struct/macros_runner.py").read_text(encoding="utf-8")
        for token in ["DOCKER_INFRA_MACRO_DIR", "write_file_bytes", "_fetch_files", "normalize_script_text", "target_context"]:
            self.assertIn(token, macros_runner)
        macros_shared = Path("/root/docker-infra/project/main/src/model/struct/macros_shared.py").read_text(encoding="utf-8")
        self.assertIn('replace("\\r\\n", "\\n").replace("\\r", "\\n")', macros_shared)


class ServerMacrosLiveFlowTest(unittest.TestCase):
    def setUp(self):
        self.client = DockerInfraApiClient.from_env(self)
        password_only_login(self.client, testcase=self)

    def wait_operation(self, operation_id, timeout_seconds=20):
        deadline = timeout_seconds * 10
        for _ in range(deadline):
            response = self.client.post(
                "/wiz/api/page.macros/operation_status",
                json={"operation_id": operation_id},
                validate=False,
            )
            self.assertEqual(response.status_code, 200, response.text[:500])
            operation = response.json()["data"]["operation"]
            if operation["status"] in {"succeeded", "failed", "canceled"}:
                return operation
            sleep(0.1)
        self.fail(f"operation {operation_id} did not finish within {timeout_seconds}s")

    def test_global_macros_can_be_saved_listed_run_downloaded_and_deleted(self):
        global_name = f"macro-global-{uuid4().hex[:8]}"
        created_global_id = None
        try:
            load = self.client.post("/wiz/api/page.servers/load", json={}, validate=False)
            self.assertEqual(load.status_code, 200, load.text[:500])
            nodes = load.json()["data"]["nodes"]
            local = next(node for node in nodes if node.get("is_local_master"))

            create_global = self.client.post(
                "/wiz/api/page.macros/save_macro",
                data={
                    "name": global_name,
                    "description": "global test macro",
                    "script": "#!/usr/bin/env bash\ncat global-payload.txt\necho global:$1\n",
                    "enabled": True,
                    "test_run_id": self.client.test_run_id,
                },
                files=[("files", ("global-payload.txt", b"global-file\n", "text/plain"))],
                validate=False,
            )
            self.assertEqual(create_global.status_code, 200, create_global.text[:500])
            created_global = create_global.json()["data"]["macro"]
            created_global_id = created_global["id"]
            self.assertEqual(created_global["scope_type"], "global")
            self.assertEqual(created_global["file_count"], 1)

            listed_global = self.client.post("/wiz/api/page.macros/load", json={}, validate=False)
            self.assertEqual(listed_global.status_code, 200, listed_global.text[:500])
            listed_payload = listed_global.json()["data"]
            self.assertTrue(any(item["id"] == created_global_id for item in listed_payload["macros"]))
            self.assertTrue(any(item["id"] == local["id"] for item in listed_payload["nodes"]))
            self.assertIn("service_targets", listed_payload)

            download = self.client.post(
                "/wiz/api/page.macros/download_macro_file",
                json={"macro_id": created_global_id, "file_id": created_global["files"][0]["id"]},
                validate=False,
            )
            self.assertEqual(download.status_code, 200, download.text[:500])
            self.assertEqual(download.json()["data"]["content_base64"], "Z2xvYmFsLWZpbGUK")

            run_global = self.client.post(
                "/wiz/api/page.macros/run_macro",
                json={"macro_id": created_global_id, "node_id": local["id"], "args": "hello"},
                validate=False,
                timeout=20,
            )
            self.assertEqual(run_global.status_code, 200, run_global.text[:500])
            global_operation = self.wait_operation(run_global.json()["data"]["operation"]["id"])
            self.assertEqual(global_operation["status"], "succeeded")
            self.assertTrue(any("global-file" in (entry.get("message") or "") for entry in global_operation["output"]))
            self.assertTrue(any("global:hello" in (entry.get("message") or "") for entry in global_operation["output"]))
        finally:
            if created_global_id:
                self.client.post("/wiz/api/page.macros/delete_macro", json={"macro_id": created_global_id}, validate=False)


if __name__ == "__main__":
    unittest.main()
