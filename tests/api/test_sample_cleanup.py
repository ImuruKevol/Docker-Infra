import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


class SampleCleanupTest(unittest.TestCase):
    def test_sample_source_paths_are_removed(self):
        removed_paths = [
            "src/app/page.posts",
            "src/app/page.posts.item",
            "src/app/page.members",
            "src/app/page.mypage",
            "src/portal/post",
            "src/model/db/user.py",
            "src/model/struct/user.py",
            "src/model/docker_infra",
            "src/controller/admin.py",
        ]
        for relative_path in removed_paths:
            self.assertFalse((ROOT / relative_path).exists(), relative_path)

    def test_docker_infra_models_follow_wiz_struct_layout(self):
        expected_paths = [
            "src/model/db/postgres.py",
            "src/model/db/migration.py",
            "src/model/struct/auth.py",
            "src/model/struct/settings.py",
            "src/model/struct/operations.py",
            "src/model/struct/nodes.py",
            "src/model/struct/nodes_shared.py",
            "src/model/struct/nodes_local_master.py",
            "src/model/struct/nodes_registry.py",
            "src/model/struct/nodes_join.py",
            "src/model/struct/nodes_reporter.py",
            "src/model/struct/setup.py",
            "src/model/struct/setup_environment.py",
            "src/model/struct/compose_validator.py",
            "src/model/struct/compose_rules.py",
            "src/model/struct/local_command_catalog.py",
        ]
        for relative_path in expected_paths:
            self.assertTrue((ROOT / relative_path).is_file(), relative_path)

    def test_user_controller_is_docker_infra_access_guard_not_sample_user_model(self):
        controller = (ROOT / "src" / "controller" / "user.py").read_text(encoding="utf-8")

        self.assertIn('wiz.controller("base")', controller)
        self.assertNotIn("src/model/db/user", controller)

    def test_docker_infra_page_skeletons_exist(self):
        expected_pages = [
            "page.dashboard",
            "page.servers",
            "page.services",
            "page.domains",
            "page.images",
            "page.system",
            "page.tools",
        ]
        for page in expected_pages:
            page_root = ROOT / "src" / "app" / page
            self.assertTrue((page_root / "app.json").is_file(), page)
            self.assertTrue((page_root / "view.pug").is_file(), page)
            self.assertTrue((page_root / "view.ts").is_file(), page)


if __name__ == "__main__":
    unittest.main()
