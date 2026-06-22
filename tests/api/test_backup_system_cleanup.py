import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
HARBOR_MODEL = ROOT / "src" / "model" / "struct" / "images_harbor.py"
CLEANUP_MODEL = ROOT / "src" / "model" / "struct" / "service_image_backup_cleanup.py"
SCHEDULER_MODEL = ROOT / "src" / "model" / "struct" / "service_image_backup_scheduler.py"
POLICY_MODEL = ROOT / "src" / "model" / "struct" / "backup_system_policy.py"
BACKUP_RUNNER_MODEL = ROOT / "src" / "model" / "struct" / "service_image_backup_runner.py"
SNAPSHOT_RUNNER_MODEL = ROOT / "src" / "model" / "struct" / "service_image_snapshot_runner.py"
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
        self.assertIn("_run_retention_cleanup", scheduler)
        self.assertIn("retention_keep_per_service", scheduler)

        policy = POLICY_MODEL.read_text(encoding="utf-8")
        self.assertIn('"cleanup": result.get("cleanup")', policy)

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
        self.assertIn("backup-tools", design)
        self.assertIn("BACKUP_VOLUME_PUSH_TOOL_UNAVAILABLE", design)
        self.assertIn("DB", design)


if __name__ == "__main__":
    unittest.main()
