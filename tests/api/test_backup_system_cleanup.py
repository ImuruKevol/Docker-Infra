import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
HARBOR_MODEL = ROOT / "src" / "model" / "struct" / "images_harbor.py"
CLEANUP_MODEL = ROOT / "src" / "model" / "struct" / "service_image_backup_cleanup.py"
SCHEDULER_MODEL = ROOT / "src" / "model" / "struct" / "service_image_backup_scheduler.py"
POLICY_MODEL = ROOT / "src" / "model" / "struct" / "backup_system_policy.py"
BACKUP_RUNNER_MODEL = ROOT / "src" / "model" / "struct" / "service_image_backup_runner.py"
SNAPSHOT_RUNNER_MODEL = ROOT / "src" / "model" / "struct" / "service_image_snapshot_runner.py"
VOLUME_BACKUPS_MODEL = ROOT / "src" / "model" / "struct" / "service_volume_backups.py"
NODES_REGISTRY_MODEL = ROOT / "src" / "model" / "struct" / "nodes_registry.py"
AI_ASSISTANT_MODEL = ROOT / "src" / "model" / "struct" / "ai_assistant.py"
VOLUME_DESIGN = ROOT / "docs" / "backup-named-volume-snapshot-design.md"


class BackupSystemCleanupContractTest(unittest.TestCase):
    def test_retention_cleanup_deletes_backup_tags_without_removing_shared_artifact(self):
        harbor = HARBOR_MODEL.read_text(encoding="utf-8")
        cleanup = CLEANUP_MODEL.read_text(encoding="utf-8")

        self.assertIn("def delete_tag(", harbor)
        self.assertIn("/tags/{urlparse.quote(tag", harbor)
        self.assertIn("harbor.delete_tag(", cleanup)
        self.assertNotIn("harbor.delete_artifact(parts", cleanup)

        scheduler = SCHEDULER_MODEL.read_text(encoding="utf-8")
        self.assertIn('wiz.model("struct/service_image_backup_cleanup")', scheduler)
        self.assertIn('wiz.model("struct/service_volume_backups")', scheduler)
        self.assertIn("_run_retention_cleanup", scheduler)
        self.assertIn("retention_keep_per_service", scheduler)
        self.assertIn("record_runtime_volume_targets", scheduler)
        self.assertIn("volume_to_harbor", scheduler)

        policy = POLICY_MODEL.read_text(encoding="utf-8")
        self.assertIn('"cleanup": result.get("cleanup")', policy)
        self.assertIn("service_volume_backups", cleanup)
        self.assertIn("artifact_ref", cleanup)
        self.assertIn("artifact_status = 'deleted'", cleanup)

    def test_backup_push_removes_local_backup_images_after_registry_push(self):
        backup_runner = BACKUP_RUNNER_MODEL.read_text(encoding="utf-8")
        snapshot_runner = SNAPSHOT_RUNNER_MODEL.read_text(encoding="utf-8")

        self.assertIn('["docker", "image", "rm", ref]', backup_runner)
        self.assertIn('"local_cleanup": local_cleanup', backup_runner)
        self.assertIn('["docker", "image", "rm", backup_ref]', snapshot_runner)
        self.assertIn('"local_cleanup": {"ref": backup_ref', snapshot_runner)

    def test_named_volume_snapshot_design_exists(self):
        design = VOLUME_DESIGN.read_text(encoding="utf-8")

        self.assertIn("named_volume_snapshot", design)
        self.assertIn("volume_only", design)
        self.assertIn("full_state", design)
        self.assertIn("Agent 연동", design)
        self.assertIn("container_snapshot: false", design)
        self.assertIn("oras push", design)
        self.assertIn("snap install oras --classic", design)
        self.assertIn("fallback push 경로는 두지 않는다", design)
        self.assertIn("SERVICE_VOLUME_BACKUP_ORAS_REQUIRED", design)
        self.assertIn("DB", design)

    def test_oras_is_required_for_volume_backups_and_installed_on_server_add(self):
        volume_backups = VOLUME_BACKUPS_MODEL.read_text(encoding="utf-8")
        nodes_registry = NODES_REGISTRY_MODEL.read_text(encoding="utf-8")

        self.assertIn("CREATE TABLE IF NOT EXISTS service_volume_backups", volume_backups)
        self.assertIn("record_runtime_volume_targets", volume_backups)
        self.assertIn("command -v oras", volume_backups)
        self.assertIn("SERVICE_VOLUME_BACKUP_ORAS_REQUIRED", volume_backups)
        self.assertIn("_failure_tail", volume_backups)
        self.assertIn("oras push", volume_backups)
        self.assertIn("archive_name + ':' + VOLUME_MEDIA_TYPE", volume_backups)
        self.assertIn("snap install oras --classic", nodes_registry)
        self.assertIn("NODE_ORAS_INSTALL_FAILED", nodes_registry)

    def test_agent_template_contract_includes_backup_policy(self):
        assistant = AI_ASSISTANT_MODEL.read_text(encoding="utf-8")

        self.assertIn("metadata.backup_policy", assistant)
        self.assertIn("mode=full_state", assistant)
        self.assertIn("_template_backup_policy", assistant)
        self.assertIn("container_snapshot=false", assistant)


if __name__ == "__main__":
    unittest.main()
