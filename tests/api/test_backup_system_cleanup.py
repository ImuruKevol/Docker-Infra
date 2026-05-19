import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
HARBOR_MODEL = ROOT / "src" / "model" / "struct" / "images_harbor.py"
CLEANUP_MODEL = ROOT / "src" / "model" / "struct" / "service_image_backup_cleanup.py"
BACKUP_RUNNER_MODEL = ROOT / "src" / "model" / "struct" / "service_image_backup_runner.py"
SNAPSHOT_RUNNER_MODEL = ROOT / "src" / "model" / "struct" / "service_image_snapshot_runner.py"


class BackupSystemCleanupContractTest(unittest.TestCase):
    def test_retention_cleanup_deletes_backup_tags_without_removing_shared_artifact(self):
        harbor = HARBOR_MODEL.read_text(encoding="utf-8")
        cleanup = CLEANUP_MODEL.read_text(encoding="utf-8")

        self.assertIn("def delete_tag(", harbor)
        self.assertIn("/tags/{urlparse.quote(tag", harbor)
        self.assertIn("harbor.delete_tag(", cleanup)
        self.assertNotIn("harbor.delete_artifact(parts", cleanup)

    def test_backup_push_removes_local_backup_images_after_registry_push(self):
        backup_runner = BACKUP_RUNNER_MODEL.read_text(encoding="utf-8")
        snapshot_runner = SNAPSHOT_RUNNER_MODEL.read_text(encoding="utf-8")

        self.assertIn('["docker", "image", "rm", ref]', backup_runner)
        self.assertIn('"local_cleanup": local_cleanup', backup_runner)
        self.assertIn('["docker", "image", "rm", backup_ref]', snapshot_runner)
        self.assertIn('"local_cleanup": {"ref": backup_ref', snapshot_runner)


if __name__ == "__main__":
    unittest.main()
