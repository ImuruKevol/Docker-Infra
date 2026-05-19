import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SYSTEM_API = ROOT / "src" / "app" / "page.system" / "api.py"
SYSTEM_VIEW = ROOT / "src" / "app" / "page.system" / "view.pug"
SYSTEM_TS = ROOT / "src" / "app" / "page.system" / "view.ts"
LOCAL_EXECUTOR = ROOT / "src" / "model" / "struct" / "local_executor.py"
BACKUP_RUNTIME = ROOT / "src" / "model" / "struct" / "backup_system_runtime.py"
BACKUP_SCHEDULER = ROOT / "src" / "model" / "struct" / "service_image_backup_scheduler.py"


class BackupSystemUiStaticContractTest(unittest.TestCase):
    def test_backup_system_ui_hides_internal_harbor_details_and_streams_backup_progress(self):
        view = SYSTEM_VIEW.read_text(encoding="utf-8")
        view_ts = SYSTEM_TS.read_text(encoding="utf-8")
        system_api = SYSTEM_API.read_text(encoding="utf-8")
        local_executor = LOCAL_EXECUTOR.read_text(encoding="utf-8")
        runtime = BACKUP_RUNTIME.read_text(encoding="utf-8")
        scheduler = BACKUP_SCHEDULER.read_text(encoding="utf-8")

        self.assertNotIn("Harbor URL", view)
        self.assertNotIn("관리자 계정", view)
        self.assertNotIn("저장 경로", view)
        self.assertNotIn("로컬 Harbor", view)
        self.assertIn("백업 시스템 설치", view)
        self.assertIn("backupInstallOutput()", view)
        self.assertIn("수동 백업 진행", view)
        self.assertIn("backupPolicyProgressVisible()", view)
        self.assertIn("backupPolicyProgressOutput()", view)
        self.assertIn('*ngIf="backupPolicy.enabled"', view)
        self.assertIn("backupScheduleTypes()", view)
        self.assertIn("weekdayOptions()", view)
        self.assertIn("schedule_time", view)
        self.assertIn("schedule_type", view_ts)
        self.assertIn("schedule_weekday", view_ts)
        self.assertIn("schedule_month_day", view_ts)
        self.assertIn("실행 중인 컨테이너 스냅샷", view_ts)
        self.assertIn("잠깐 일시 정지", view_ts)
        self.assertIn("include_snapshots: true", view_ts)
        self.assertNotIn("일마다", view)
        self.assertIn("def backup_operation_status():", system_api)
        self.assertIn("backup_system.enable_async()", system_api)
        self.assertIn("start_backup_system', { background: true }", view_ts)
        self.assertIn("backup_operation_status", view_ts)
        self.assertIn("pollBackupPolicyOperation", view_ts)
        self.assertIn("fetchBackupPolicyOperation", view_ts)
        self.assertIn("run_backup_policy_now', { include_snapshots: true, snapshot_pause: true, background: true }", view_ts)
        self.assertIn("scheduler.run_async(run_payload)", system_api)
        self.assertIn("def run_stream(", local_executor)
        self.assertIn("threading.Thread(target=worker, daemon=True).start()", runtime)
        self.assertIn("def run_async", scheduler)
        self.assertIn("append_output", scheduler)


if __name__ == "__main__":
    unittest.main()
