import unittest
from pathlib import Path

import yaml

from tests.cleanup.reset_test_environment import cleanup_test_roots


ROOT = Path(__file__).resolve().parents[2]
DEV_COMPOSE = ROOT / "docker" / "compose" / "development.yaml"
TEST_COMPOSE = ROOT / "docker" / "compose" / "test.yaml"


class EnvironmentComposeTest(unittest.TestCase):
    def load_yaml(self, path):
        with path.open("r", encoding="utf-8") as handle:
            return yaml.safe_load(handle)

    def test_development_and_test_compose_are_separate_postgres_16_configs(self):
        dev = self.load_yaml(DEV_COMPOSE)
        test = self.load_yaml(TEST_COMPOSE)

        self.assertEqual(dev["services"]["postgres"]["image"], "postgres:16")
        self.assertEqual(test["services"]["postgres"]["image"], "postgres:16")
        self.assertNotEqual(dev["name"], test["name"])
        self.assertNotEqual(
            dev["services"]["postgres"]["environment"]["POSTGRES_DB"],
            test["services"]["postgres"]["environment"]["POSTGRES_DB"],
        )
        self.assertIn("docker_infra_dev_pgdata", dev.get("volumes", {}))
        self.assertIn("/var/lib/postgresql/data", test["services"]["postgres"].get("tmpfs", []))

    def test_test_compose_uses_isolated_runtime_roots_and_profiles(self):
        test = self.load_yaml(TEST_COMPOSE)
        runtime = test["x-docker-infra-runtime"]

        self.assertEqual(runtime["profile"], "test")
        self.assertEqual(runtime["database"]["reset"], "recreate-compose-service")
        for path in runtime["roots"].values():
            self.assertIn(".runtime/test", path)
            self.assertNotIn("/opt/templates", path)
            self.assertNotIn("/var/log", path)

        self.assertEqual(test["services"]["postgres"]["profiles"], ["api"])
        self.assertEqual(test["services"]["docker-cli"]["profiles"], ["swarm"])
        self.assertEqual(test["services"]["proxy-sandbox"]["profiles"], ["proxy"])
        self.assertIn("/var/run/docker.sock:/var/run/docker.sock", test["services"]["docker-cli"]["volumes"])

    def test_proxy_sandbox_directories_and_test_db_init_script_exist(self):
        self.assertTrue((ROOT / "docker" / "sandbox" / "nginx" / "conf.d").is_dir())
        self.assertTrue((ROOT / "docker" / "sandbox" / "apache2" / "sites-enabled").is_dir())
        self.assertTrue((ROOT / "docker" / "postgres" / "init-test.sql").is_file())

        test = self.load_yaml(TEST_COMPOSE)
        self.assertIn(
            "../postgres/init-test.sql:/docker-entrypoint-initdb.d/001-init-test.sql:ro",
            test["services"]["postgres"]["volumes"],
        )

    def test_cleanup_helper_only_removes_project_local_test_runtime_roots(self):
        probe = ROOT / ".runtime" / "test" / "services" / "cleanup-probe"
        probe.mkdir(parents=True, exist_ok=True)
        (probe / "probe.txt").write_text("temporary test artifact", encoding="utf-8")

        result = cleanup_test_roots(paths=[probe, ROOT / "README.md"])
        self.assertIn(str(probe), result["removed"])
        self.assertIn(str(ROOT / "README.md"), result["skipped"])
        self.assertFalse(probe.exists())
        self.assertTrue((ROOT / "README.md").is_file())


if __name__ == "__main__":
    unittest.main()
