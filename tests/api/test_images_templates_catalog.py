import importlib.util
import unittest
from pathlib import Path
import time

from tests.fixtures.api_client import DockerInfraApiClient, password_only_login


ROOT = Path(__file__).resolve().parents[2]
IMAGES_API = ROOT / "src" / "app" / "page.images" / "api.py"
IMAGES_MODEL = ROOT / "src" / "model" / "struct" / "images.py"
IMAGES_LOCAL_MODEL = ROOT / "src" / "model" / "struct" / "images_local.py"
IMAGES_SHARED_MODEL = ROOT / "src" / "model" / "struct" / "images_shared.py"
IMAGES_TS = ROOT / "src" / "app" / "page.images" / "view.ts"
SERVICES_API = ROOT / "src" / "app" / "page.services" / "api.py"
FILE_TREE_MODEL = ROOT / "src" / "model" / "struct" / "file_tree.py"
NODES_RUNTIME_FILES = ROOT / "src" / "model" / "struct" / "nodes_runtime_files.py"
SSH_EXECUTOR = ROOT / "src" / "model" / "struct" / "ssh_executor.py"
LOCAL_COMMANDS = ROOT / "src" / "model" / "struct" / "local_command_catalog.py"
FILE_TREE_COMPONENT = ROOT / "src" / "app" / "component.file.tree" / "view.ts"
FILE_TREE_COMPONENT_TEMPLATE = ROOT / "src" / "app" / "component.file.tree" / "view.html"
FILE_TREE_ROUTE = ROOT / "src" / "route" / "api-file-tree" / "controller.py"
FILE_TREE_UPLOAD_ROUTE = ROOT / "src" / "route" / "api-file-tree-upload" / "controller.py"
SERVICES_TEMPLATE = ROOT / "src" / "app" / "page.services" / "view.pug"
SERVERS_TEMPLATE = ROOT / "src" / "app" / "page.servers" / "view.pug"
IMAGES_TEMPLATE = ROOT / "src" / "app" / "page.images" / "view.pug"


class ImagesStaticContractTest(unittest.TestCase):
    def test_images_and_file_tree_routes_are_declared(self):
        images_api = IMAGES_API.read_text(encoding="utf-8")
        images_model = IMAGES_MODEL.read_text(encoding="utf-8")
        images_local_model = IMAGES_LOCAL_MODEL.read_text(encoding="utf-8")
        images_shared_model = IMAGES_SHARED_MODEL.read_text(encoding="utf-8")
        images_view = IMAGES_TEMPLATE.read_text(encoding="utf-8")
        images_ts = IMAGES_TS.read_text(encoding="utf-8")
        services_api = SERVICES_API.read_text(encoding="utf-8")
        file_tree_model = FILE_TREE_MODEL.read_text(encoding="utf-8")
        nodes_runtime_files = NODES_RUNTIME_FILES.read_text(encoding="utf-8")
        ssh_executor = SSH_EXECUTOR.read_text(encoding="utf-8")
        local_commands = LOCAL_COMMANDS.read_text(encoding="utf-8")
        file_tree_component = FILE_TREE_COMPONENT.read_text(encoding="utf-8")
        file_tree_component_template = FILE_TREE_COMPONENT_TEMPLATE.read_text(encoding="utf-8")
        file_tree_route = FILE_TREE_ROUTE.read_text(encoding="utf-8")
        file_tree_upload_route = FILE_TREE_UPLOAD_ROUTE.read_text(encoding="utf-8")
        file_tree_usages = "\n".join(path.read_text(encoding="utf-8") for path in [SERVICES_TEMPLATE, SERVERS_TEMPLATE, IMAGES_TEMPLATE])

        self.assertIn("def harbor_detail():", images_api)
        self.assertIn("def harbor_tags():", images_api)
        self.assertIn("def harbor_overview():", images_api)
        self.assertIn("def create_harbor_project():", images_api)
        self.assertIn("def local_detail():", images_api)
        self.assertIn("def delete_harbor():", images_api)
        self.assertIn("def delete_harbor_project():", images_api)
        self.assertIn("def delete_harbor_repository():", images_api)
        self.assertIn("def delete_local():", images_api)
        self.assertNotIn("def template_detail():", services_api)
        self.assertIn("harbor_project_detail", images_model)
        self.assertIn("harbor_repository_tags", images_model)
        self.assertIn("harbor_overview", images_model)
        self.assertIn("create_harbor_project", images_model)
        self.assertIn("delete_harbor_repository", images_model)
        self.assertIn("harbor.delete_artifact(project_name, repository_name, digest", images_model)
        self.assertIn("harbor.delete_repository(project_name, repository_name", images_model)
        self.assertIn("delete_local_image", images_local_model)
        self.assertIn("_remove_image_with_fallbacks", images_local_model)
        self.assertIn('f"{repository}:{tag}@{digest_value}"', images_shared_model)
        self.assertIn("def parse_int", images_shared_model)
        self.assertIn("class FileTree", file_tree_model)
        self.assertIn("def upload", file_tree_model)
        self.assertIn("def mutate", file_tree_model)
        self.assertIn("os.scandir", file_tree_model)
        self.assertIn("duration_ms", file_tree_model)
        self.assertIn("_list_local_dir", nodes_runtime_files)
        self.assertIn("os.scandir", nodes_runtime_files)
        self.assertIn("show_hidden", nodes_runtime_files)
        self.assertIn("total_count", nodes_runtime_files)
        self.assertIn("truncated", nodes_runtime_files)
        self.assertIn("ssh_duration_ms", nodes_runtime_files)
        self.assertIn("known_hosts_for_run", ssh_executor)
        self.assertIn("known_fingerprint", ssh_executor)
        self.assertIn("filesystem.list", local_commands)
        self.assertIn("show_hidden", local_commands)
        self.assertIn("/api/file-tree/upload", file_tree_component)
        self.assertIn("@wiz/libs/portal/season/service", file_tree_component)
        self.assertIn("await this.service.render()", file_tree_component)
        self.assertIn("webkitdirectory", file_tree_component_template)
        self.assertIn("dropOn", file_tree_component)
        self.assertIn("file_tree.list", file_tree_route)
        self.assertIn("file_tree.upload", file_tree_upload_route)
        self.assertIn("wiz-component-file-tree", file_tree_usages)
        self.assertIn("백업 저장소", images_view)
        self.assertIn("백업 저장소", images_ts)
        self.assertNotIn("span Harbor", images_view)
        self.assertNotIn("Harbor 프로젝트", images_view)

    def test_docker_image_parser_accepts_na_container_count(self):
        spec = importlib.util.spec_from_file_location("images_shared_under_test", IMAGES_SHARED_MODEL)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)

        rows = module.parse_docker_image_lines(
            '{"Repository":"nginx","Tag":"latest","Digest":"<none>","ID":"sha256:123","Containers":"N/A","Size":"10MB"}\n'
        )

        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["containers_count"], 0)


class ImagesLiveFlowTest(unittest.TestCase):
    def setUp(self):
        self.client = DockerInfraApiClient.from_env(self)
        password_only_login(self.client, testcase=self)

    def test_images_load_and_local_detail_flow(self):
        load = self.client.post("/wiz/api/page.images/load", json={}, validate=False)
        self.assertEqual(load.status_code, 200, load.text[:500])
        data = load.json()["data"]
        self.assertIn("harbor", data)
        self.assertIn("nodes", data)

        selected_node_id = data.get("selected_node_id")
        if not selected_node_id:
            self.skipTest("등록된 서버가 없습니다.")

        detail = self.client.post(
            "/wiz/api/page.images/local_detail",
            json={"node_id": selected_node_id},
            validate=False,
            timeout=20,
        )
        self.assertEqual(detail.status_code, 200, detail.text[:500])
        detail_data = detail.json()["data"]
        self.assertEqual(detail_data["node"]["id"], selected_node_id)
        self.assertIn("docker_available", detail_data)
        self.assertIn("summary", detail_data)
        self.assertIn("used_count", detail_data["summary"])

    def test_harbor_project_create_and_tags_flow(self):
        load = self.client.post("/wiz/api/page.images/load", json={}, validate=False)
        self.assertEqual(load.status_code, 200, load.text[:500])
        harbor_meta = load.json()["data"].get("harbor") or {}
        if not harbor_meta.get("enabled") or not harbor_meta.get("configured"):
            self.skipTest("서비스 백업 시스템이 설정되어 있지 않습니다.")

        overview = self.client.post("/wiz/api/page.images/harbor_overview", json={}, validate=False)
        self.assertEqual(overview.status_code, 200, overview.text[:500])
        overview_data = overview.json()["data"]
        project_name = f"codex-images-{int(time.time())}"

        created = self.client.post(
            "/wiz/api/page.images/create_harbor_project",
            json={"project_name": project_name, "public": False},
            validate=False,
        )
        self.assertEqual(created.status_code, 200, created.text[:500])
        try:
            detail = self.client.post(
                "/wiz/api/page.images/harbor_detail",
                json={"project_name": project_name},
                validate=False,
            )
            self.assertEqual(detail.status_code, 200, detail.text[:500])
            detail_data = detail.json()["data"]
            self.assertEqual(detail_data["project_name"], project_name)

            projects = overview_data.get("projects") or []
            if projects:
                first_project = projects[0]["name"]
                first_detail = self.client.post(
                    "/wiz/api/page.images/harbor_detail",
                    json={"project_name": first_project},
                    validate=False,
                )
                self.assertEqual(first_detail.status_code, 200, first_detail.text[:500])
                repositories = first_detail.json()["data"].get("repositories") or []
                if repositories:
                    tags = self.client.post(
                        "/wiz/api/page.images/harbor_tags",
                        json={"project_name": first_project, "repository_name": repositories[0]["name"]},
                        validate=False,
                    )
                    self.assertEqual(tags.status_code, 200, tags.text[:500])
                    self.assertIn("tags", tags.json()["data"])
        finally:
            self.client.post(
                "/wiz/api/page.images/delete_harbor_project",
                json={"project_name": project_name},
                validate=False,
            )

if __name__ == "__main__":
    unittest.main()
