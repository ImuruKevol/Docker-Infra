import unittest
from pathlib import Path
import time

from tests.fixtures.api_client import DockerInfraApiClient, password_only_login


ROOT = Path(__file__).resolve().parents[2]
IMAGES_API = ROOT / "src" / "app" / "page.images" / "api.py"
TEMPLATES_API = ROOT / "src" / "app" / "page.templates" / "api.py"
IMAGES_MODEL = ROOT / "src" / "model" / "struct" / "images.py"
IMAGES_LOCAL_MODEL = ROOT / "src" / "model" / "struct" / "images_local.py"
IMAGES_SHARED_MODEL = ROOT / "src" / "model" / "struct" / "images_shared.py"
TEMPLATES_MODEL = ROOT / "src" / "model" / "struct" / "templates.py"
TEMPLATES_STORE = ROOT / "src" / "model" / "struct" / "templates_store.py"
TEMPLATES_SEED = ROOT / "src" / "model" / "struct" / "templates_seed.py"
TEMPLATES_SEED_FILES = sorted((ROOT / "src" / "model" / "struct").glob("templates_seed*.py"))
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
TEMPLATES_TEMPLATE = ROOT / "src" / "app" / "page.templates" / "view.pug"
IMAGES_TEMPLATE = ROOT / "src" / "app" / "page.images" / "view.pug"


class ImagesTemplatesStaticContractTest(unittest.TestCase):
    def test_images_and_templates_routes_are_declared(self):
        images_api = IMAGES_API.read_text(encoding="utf-8")
        templates_api = TEMPLATES_API.read_text(encoding="utf-8")
        images_model = IMAGES_MODEL.read_text(encoding="utf-8")
        images_local_model = IMAGES_LOCAL_MODEL.read_text(encoding="utf-8")
        images_shared_model = IMAGES_SHARED_MODEL.read_text(encoding="utf-8")
        templates_model = TEMPLATES_MODEL.read_text(encoding="utf-8")
        templates_store = TEMPLATES_STORE.read_text(encoding="utf-8")
        templates_seed = TEMPLATES_SEED.read_text(encoding="utf-8")
        templates_seed_all = "\n".join(path.read_text(encoding="utf-8") for path in TEMPLATES_SEED_FILES)
        services_api = SERVICES_API.read_text(encoding="utf-8")
        file_tree_model = FILE_TREE_MODEL.read_text(encoding="utf-8")
        nodes_runtime_files = NODES_RUNTIME_FILES.read_text(encoding="utf-8")
        ssh_executor = SSH_EXECUTOR.read_text(encoding="utf-8")
        local_commands = LOCAL_COMMANDS.read_text(encoding="utf-8")
        file_tree_component = FILE_TREE_COMPONENT.read_text(encoding="utf-8")
        file_tree_component_template = FILE_TREE_COMPONENT_TEMPLATE.read_text(encoding="utf-8")
        file_tree_route = FILE_TREE_ROUTE.read_text(encoding="utf-8")
        file_tree_upload_route = FILE_TREE_UPLOAD_ROUTE.read_text(encoding="utf-8")
        file_tree_usages = "\n".join(path.read_text(encoding="utf-8") for path in [SERVICES_TEMPLATE, SERVERS_TEMPLATE, TEMPLATES_TEMPLATE, IMAGES_TEMPLATE])

        self.assertIn("def harbor_detail():", images_api)
        self.assertIn("def harbor_tags():", images_api)
        self.assertIn("def harbor_overview():", images_api)
        self.assertIn("def create_harbor_project():", images_api)
        self.assertIn("def local_detail():", images_api)
        self.assertIn("def delete_harbor():", images_api)
        self.assertIn("def delete_harbor_project():", images_api)
        self.assertIn("def delete_harbor_repository():", images_api)
        self.assertIn("def delete_local():", images_api)
        self.assertIn("def preview_template():", templates_api)
        self.assertIn("def release_template():", templates_api)
        self.assertIn("def version_detail():", templates_api)
        self.assertIn("def template_detail():", services_api)
        self.assertIn("harbor_project_detail", images_model)
        self.assertIn("harbor_repository_tags", images_model)
        self.assertIn("harbor_overview", images_model)
        self.assertIn("create_harbor_project", images_model)
        self.assertIn("delete_harbor_repository", images_model)
        self.assertIn("delete_local_image", images_local_model)
        self.assertIn("_remove_image_with_fallbacks", images_local_model)
        self.assertIn('f"{repository}:{tag}@{digest_value}"', images_shared_model)
        self.assertIn("ensure_defaults", templates_model)
        self.assertIn("def preview(self, payload, env=None):", templates_store)
        self.assertIn("def release(self, payload, env=None):", templates_store)
        self.assertIn("def version_detail(self, version_id, env=None):", templates_store)
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
        self.assertIn("webkitdirectory", file_tree_component_template)
        self.assertIn("dropOn", file_tree_component)
        self.assertIn("file_tree.list", file_tree_route)
        self.assertIn("file_tree.upload", file_tree_upload_route)
        self.assertIn("wiz-component-file-tree", file_tree_usages)
        for token in [
            "wordpress_site",
            "nextcloud_stack",
            "odoo_suite",
            "wikijs_site",
            "domain_ready",
        ]:
            self.assertIn(token, templates_seed_all)
        self.assertIn("managed_namespaces", templates_seed)


class ImagesTemplatesLiveFlowTest(unittest.TestCase):
    def setUp(self):
        self.client = DockerInfraApiClient.from_env(self)
        password_only_login(self.client, testcase=self)

    def test_templates_seed_and_preview_flow(self):
        load = self.client.post("/wiz/api/page.templates/load", json={}, validate=False)
        self.assertEqual(load.status_code, 200, load.text[:500])
        data = load.json()["data"]
        self.assertIn("template_root", data)
        self.assertTrue(str(data["template_root"]).endswith("/data/templates"))
        namespaces = {item["namespace"] for item in data.get("templates", [])}
        self.assertGreaterEqual(len(data.get("templates", [])), 4)
        for namespace in ["wordpress_site", "nextcloud_stack", "odoo_suite", "wikijs_site"]:
            self.assertIn(namespace, namespaces)
        for namespace in ["gitlab_ce", "harbor_registry", "nginx_static", "postgres_db", "redis_cache"]:
            self.assertNotIn(namespace, namespaces)

        first = data["templates"][0]
        detail = self.client.post(
            "/wiz/api/page.templates/detail",
            json={"template_id": first["id"]},
            validate=False,
        )
        self.assertEqual(detail.status_code, 200, detail.text[:500])
        detail_data = detail.json()["data"]
        self.assertTrue(detail_data["preview"]["validation"]["valid"])
        self.assertIn("docker-compose.yaml", detail_data["files"])

        preview = self.client.post(
            "/wiz/api/page.templates/preview_template",
            json={
                "namespace": detail_data["template"]["namespace"],
                "compose": detail_data["files"]["docker-compose.yaml"],
                "values_default": detail_data["files"]["values.default.yaml"],
            },
            validate=False,
        )
        self.assertEqual(preview.status_code, 200, preview.text[:500])
        preview_data = preview.json()["data"]["preview"]
        self.assertTrue(preview_data["validation"]["valid"])
        self.assertIn("services:", preview_data["rendered_compose"])

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

    def test_template_release_and_version_detail_flow(self):
        suffix = str(int(time.time()))
        payload = {
            "name": f"Live Template {suffix}",
            "namespace": f"live_template_{suffix}",
            "description": "live release flow test",
            "enabled": True,
            "metadata": {"primary_image": "nginx:alpine"},
            "compose": "services:\n  web:\n    image: {{ image }}\n    ports:\n      - \"{{ service_port }}:80\"\n    healthcheck:\n      test: [\"CMD-SHELL\", \"wget -qO- http://127.0.0.1/ || exit 1\"]\n      interval: 30s\n      timeout: 5s\n      retries: 3\n",
            "values_default": f"namespace: live_template_{suffix}\nservice_name: web\nimage: nginx:alpine\nservice_port: 8080\n",
            "values_schema": "{\"type\":\"object\"}\n",
            "readme": "# live\n",
        }
        saved = self.client.post("/wiz/api/page.templates/save_template", json=payload, validate=False)
        self.assertEqual(saved.status_code, 200, saved.text[:500])
        template_id = saved.json()["data"]["template"]["id"]
        try:
            release = self.client.post("/wiz/api/page.templates/release_template", json={**payload, "id": template_id}, validate=False)
            self.assertEqual(release.status_code, 200, release.text[:500])
            release_data = release.json()["data"]
            self.assertIn("version", release_data)

            version_detail = self.client.post(
                "/wiz/api/page.templates/version_detail",
                json={"version_id": release_data["version"]["id"]},
                validate=False,
            )
            self.assertEqual(version_detail.status_code, 200, version_detail.text[:500])
            version_data = version_detail.json()["data"]
            self.assertIn("docker-compose.yaml", version_data["files"])
        finally:
            self.client.post("/wiz/api/page.templates/delete_template", json={"template_id": template_id}, validate=False)


if __name__ == "__main__":
    unittest.main()
