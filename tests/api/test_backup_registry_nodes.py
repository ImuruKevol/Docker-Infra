import unittest
from pathlib import Path

from tests.api.test_backup_system_runtime import load_struct_module


ROOT = Path(__file__).resolve().parents[2]


class FakeScripts:
    SYSTEM_METRICS_SCRIPT = "true"
    NODE_METRICS_AGENT_SCRIPT = "print('ok')"
    DOCKER_IMAGE_USAGE_SCRIPT = "true"
    DOCKER_IMAGE_STORAGE_SCRIPT = "print('{}')"
    DOCKER_IMAGE_DELETE_ESTIMATE_SCRIPT = "print('{}')"
    DOCKER_PRUNE_ESTIMATE_SCRIPT = "print('{}')"


class BackupRegistryNodeStaticContractTest(unittest.TestCase):
    def test_insecure_registry_command_is_declared_and_allowlisted(self):
        catalog = load_struct_module("local_command_catalog", models={"struct/local_command_scripts": FakeScripts()})
        argv = catalog._docker_daemon_insecure_registries_command({"registries": ["10.0.0.1:5000", "10.0.0.1:5000"]})
        command_text = " ".join(argv)

        self.assertIn("docker.daemon.insecure_registries.ensure", catalog.COMMAND_SPECS)
        self.assertIn('"10.0.0.1:5000"', command_text)
        self.assertIn("insecure-registries", command_text)

        config = (ROOT / "config" / "docker_infra.py").read_text(encoding="utf-8")
        self.assertIn('"docker.daemon.insecure_registries.ensure"', config)

    def test_nodes_apply_backup_registry_after_swarm_join_and_from_system_api(self):
        nodes = (ROOT / "src" / "model" / "struct" / "nodes.py").read_text(encoding="utf-8")
        join = (ROOT / "src" / "model" / "struct" / "nodes_join.py").read_text(encoding="utf-8")
        registry = (ROOT / "src" / "model" / "struct" / "nodes_backup_registry.py").read_text(encoding="utf-8")
        shared = (ROOT / "src" / "model" / "struct" / "nodes_shared.py").read_text(encoding="utf-8")
        monitoring = (ROOT / "src" / "model" / "struct" / "nodes_monitoring.py").read_text(encoding="utf-8")
        snapshot = (ROOT / "src" / "model" / "struct" / "service_image_snapshot_runner.py").read_text(encoding="utf-8")
        deploy = (ROOT / "src" / "model" / "struct" / "services_deploy.py").read_text(encoding="utf-8")
        system_api = (ROOT / "src" / "app" / "page.system" / "api.py").read_text(encoding="utf-8")
        view = (ROOT / "src" / "app" / "page.system" / "view.pug").read_text(encoding="utf-8")
        view_ts = (ROOT / "src" / "app" / "page.system" / "view.ts").read_text(encoding="utf-8")
        config = (ROOT / "config" / "docker_infra.py").read_text(encoding="utf-8")

        self.assertIn('wiz.model("struct/nodes_backup_registry")', nodes)
        self.assertIn("Backup registry setup", join)
        self.assertIn("configure_backup_registry_for_node", join)
        self.assertIn("def ensure_backup_registry_all", registry)
        self.assertIn("def node_access_host", shared)
        self.assertIn("_node_access_host(masters[0])", registry)
        self.assertIn("DOCKER_INFRA_MASTER_PRIVATE_IP", config)
        self.assertIn("def reporter_internal_base_url", config)
        self.assertIn("config.reporter_internal_base_url", monitoring)
        self.assertIn('remote != config["local_registry"]', registry)
        self.assertIn("backup_registry_reference_for_node", snapshot)
        self.assertIn("def _ensure_manager_backup_registry_for_deploy", deploy)
        self.assertIn("_ensure_manager_backup_registry_for_deploy(operation_id", deploy)
        self.assertGreaterEqual(deploy.count("_ensure_backup_system_running_for_deploy(operation_id"), 2)
        self.assertIn("def apply_backup_registry_nodes():", system_api)
        self.assertIn("applyBackupRegistryNodes()", view)
        self.assertIn("apply_backup_registry_nodes", view_ts)


if __name__ == "__main__":
    unittest.main()
