import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SYSTEM_API = ROOT / "src" / "app" / "page.system" / "api.py"
SYSTEM_VIEW = ROOT / "src" / "app" / "page.system" / "view.pug"
SYSTEM_TS = ROOT / "src" / "app" / "page.system" / "view.ts"
SERVICES_VIEW = ROOT / "src" / "app" / "page.services" / "view.pug"
SERVICES_TS = ROOT / "src" / "app" / "page.services" / "view.ts"
LOCAL_EXECUTOR = ROOT / "src" / "model" / "struct" / "local_executor.py"
BACKUP_RUNTIME = ROOT / "src" / "model" / "struct" / "backup_system_runtime.py"
BACKUP_SCHEDULER = ROOT / "src" / "model" / "struct" / "service_image_backup_scheduler.py"
BACKUP_RECORDS = ROOT / "src" / "model" / "struct" / "service_image_backups.py"
BACKUP_VOLUME_RECORDS = ROOT / "src" / "model" / "struct" / "service_volume_backups.py"
BACKUP_SNAPSHOT_RUNNER = ROOT / "src" / "model" / "struct" / "service_image_snapshot_runner.py"
SERVICES_ROLLBACK = ROOT / "src" / "model" / "struct" / "services_rollback.py"
BACKUP_POLICY = ROOT / "src" / "model" / "struct" / "backup_system_policy.py"
BACKUP_CRON = ROOT / "src" / "model" / "struct" / "backup_system_cron.py"
BACKUP_TICK_ROUTE = ROOT / "src" / "route" / "api-system-backup-tick" / "controller.py"


class BackupSystemUiStaticContractTest(unittest.TestCase):
    def test_backup_system_ui_hides_internal_harbor_details_and_streams_backup_progress(self):
        view = SYSTEM_VIEW.read_text(encoding="utf-8")
        view_ts = SYSTEM_TS.read_text(encoding="utf-8")
        services_view = SERVICES_VIEW.read_text(encoding="utf-8")
        services_view_ts = SERVICES_TS.read_text(encoding="utf-8")
        system_api = SYSTEM_API.read_text(encoding="utf-8")
        local_executor = LOCAL_EXECUTOR.read_text(encoding="utf-8")
        runtime = BACKUP_RUNTIME.read_text(encoding="utf-8")
        scheduler = BACKUP_SCHEDULER.read_text(encoding="utf-8")
        backup_records = BACKUP_RECORDS.read_text(encoding="utf-8")
        volume_records = BACKUP_VOLUME_RECORDS.read_text(encoding="utf-8")
        snapshot_runner = BACKUP_SNAPSHOT_RUNNER.read_text(encoding="utf-8")
        rollback = SERVICES_ROLLBACK.read_text(encoding="utf-8")
        policy = BACKUP_POLICY.read_text(encoding="utf-8")
        cron = BACKUP_CRON.read_text(encoding="utf-8")
        tick_route = BACKUP_TICK_ROUTE.read_text(encoding="utf-8")

        self.assertNotIn("Harbor URL", view)
        self.assertNotIn("관리자 계정", view)
        self.assertNotIn("저장 경로", view)
        self.assertNotIn("로컬 Harbor", view)
        self.assertIn("백업 시스템 설치", view)
        self.assertIn("backupInstallOutput()", view)
        self.assertIn("수동 백업 진행", view)
        self.assertIn("backupPolicyProgressVisible()", view)
        self.assertIn("backupPolicyProgressOutput()", view)
        self.assertIn("서비스 상태 자동 백업", view)
        self.assertNotIn("서비스 이미지 자동 백업", view)
        self.assertNotIn("노드 설정 적용", view)
        self.assertIn('[disabled]="!backupPolicy.enabled"', view)
        self.assertIn("opacity-50 grayscale", view)
        self.assertNotIn('div(*ngIf="backupPolicy.enabled"', view)
        self.assertNotIn('[(ngModel)]="backupPolicy.snapshot_enabled"', view)
        self.assertNotIn("자동 백업을 켜기 전에는 추가 설정을 표시하지 않습니다.", view)
        self.assertIn("backupScheduleTypes()", view)
        self.assertIn("weekdayOptions()", view)
        self.assertIn("schedule_time", view)
        self.assertIn("schedule_type", view_ts)
        self.assertIn("schedule_weekday", view_ts)
        self.assertIn("schedule_month_day", view_ts)
        self.assertIn("실행 중인 컨테이너 상태 스냅샷", view_ts)
        self.assertIn("named volume", view_ts)
        self.assertIn("잠깐 일시 정지", view_ts)
        self.assertNotIn("include_snapshots", view_ts)
        self.assertIn("snapshot_enabled: true", view_ts)
        self.assertIn("backup_mode: 'full_state'", view_ts)
        self.assertNotIn("max_items_per_run", view_ts)
        self.assertNotIn("일마다", view)
        self.assertIn("def backup_operation_status():", system_api)
        self.assertIn("backup_system.enable_async()", system_api)
        self.assertIn("start_backup_system', { background: true }", view_ts)
        self.assertIn("backup_operation_status", view_ts)
        self.assertIn("pollBackupPolicyOperation", view_ts)
        self.assertIn("fetchBackupPolicyOperation", view_ts)
        self.assertIn("run_backup_policy_now', { snapshot_pause: true }", view_ts)
        self.assertIn("code === 200 || code === 202", view_ts)
        self.assertIn('"include_snapshots": True', system_api)
        self.assertIn('"include_named_volumes": True', system_api)
        self.assertIn("code = 202", system_api)
        self.assertIn("scheduler.run_async(run_payload)", system_api)
        self.assertNotIn('{"result": scheduler.run(run_payload)}', system_api)
        self.assertIn("record_runtime_snapshot_targets", scheduler)
        self.assertIn("record_runtime_volume_targets", scheduler)
        self.assertNotIn("DEFAULT_SNAPSHOT_LIMIT", scheduler)
        self.assertIn("volume_to_harbor", scheduler)
        self.assertNotIn("backup_to_harbor(item", scheduler)
        self.assertIn("nodes.live_containers", backup_records)
        self.assertIn("nodes.live_containers", volume_records)
        self.assertIn("service_volume_backups", volume_records)
        self.assertIn("oras push", volume_records)
        self.assertIn("oras pull", volume_records)
        self.assertIn("def version_restore_context", volume_records)
        self.assertIn("def restore_version", volume_records)
        self.assertIn("service.volume.restore", volume_records)
        self.assertIn("volume_backups.version_restore_context", rollback)
        self.assertIn("volume_backups.restore_version", rollback)
        self.assertIn("volume_restore_count", rollback)
        self.assertIn("named volume 복원", services_view)
        self.assertIn("rollbackVolumeRestoreText()", services_view)
        self.assertIn("rollbackVolumeRestoreValue()", services_view_ts)
        self.assertIn("snapshot_target_node_id", backup_records)
        self.assertIn("snapshot_target_container_id", backup_records)
        self.assertIn("_ensure_backup_compose_version", backup_records)
        self.assertIn('"backup_checkpoint": True', backup_records)
        self.assertIn("_ensure_backup_compose_version", volume_records)
        self.assertIn('"backup_checkpoint": True', volume_records)
        self.assertIn("snapshot_target_node_id", snapshot_runner)
        self.assertIn("_find_container_on_node", snapshot_runner)
        self.assertIn('wiz.model("struct/backup_system_cron")', policy)
        self.assertIn("cron.sync(policy, cron_plan", policy)
        self.assertIn('"volumes": int(result.get("volumes")', policy)
        self.assertIn("CRON_MARKER", cron)
        self.assertIn("crontab", cron)
        self.assertIn("X-Docker-Infra-Cron-Token", tick_route)
        self.assertIn("backup_tick.tick()", tick_route)
        self.assertIn("def run_stream(", local_executor)
        self.assertIn("threading.Thread(target=worker, daemon=True).start()", runtime)
        self.assertIn("def run_async", scheduler)
        self.assertIn("append_output", scheduler)


if __name__ == "__main__":
    unittest.main()
