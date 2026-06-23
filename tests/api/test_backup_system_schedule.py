import datetime
import unittest
from types import SimpleNamespace

from tests.api.test_backup_system_runtime import FakeConfig, load_struct_module


def load_scheduler_module():
    return load_struct_module(
        "service_image_backup_scheduler",
        config=FakeConfig(),
        models={
            "db/postgres": SimpleNamespace(connect=lambda env=None: None),
            "struct/backup_system": object(),
            "struct/service_image_backups": object(),
            "struct/service_volume_backups": object(),
            "struct/service_image_backup_cleanup": object(),
            "struct/operations": object(),
            "struct/services_shared": SimpleNamespace(ServiceError=Exception, row=lambda row: row),
        },
    )


def load_backups_module(nodes):
    class FakeActions:
        pass

    return load_struct_module(
        "service_image_backups",
        config=FakeConfig(),
        models={
            "db/postgres": SimpleNamespace(connect=lambda env=None: None),
            "struct/service_image_backup_actions": FakeActions,
            "struct/nodes": nodes,
            "struct/services_shared": SimpleNamespace(ServiceError=Exception, row=lambda row: row),
        },
    )


class BackupSystemSchedulePolicyTest(unittest.TestCase):
    def test_policy_defaults_normalize_weekly_monthly_schedule_fields(self):
        defaults = load_struct_module("backup_system_policy_defaults", config=FakeConfig())

        policy = defaults.normalize(
            {
                "enabled": True,
                "schedule_type": "monthly",
                "schedule_weekday": 9,
                "schedule_month_day": 45,
                "schedule_time": "25:99",
                "snapshot_enabled": False,
            }
        )

        self.assertEqual(policy["mode"], "scheduled")
        self.assertEqual(policy["schedule_type"], "monthly")
        self.assertEqual(policy["schedule_weekday"], 6)
        self.assertEqual(policy["schedule_month_day"], 31)
        self.assertEqual(policy["schedule_time"], "02:00")
        self.assertEqual(policy["method"], "service_state_snapshot")
        self.assertEqual(policy["backup_mode"], "full_state")
        self.assertTrue(policy["snapshot_enabled"])

    def test_weekly_schedule_runs_only_after_selected_day_and_time(self):
        scheduler = load_scheduler_module()
        policy = {
            "enabled": True,
            "schedule_type": "weekly",
            "schedule_weekday": 0,
            "schedule_time": "02:00",
            "interval_days": 365,
        }

        with self._frozen_now(scheduler, datetime.datetime(2026, 5, 11, 1, 59, tzinfo=datetime.timezone.utc)):
            self.assertIn("예약 시간이", scheduler.Model._skip_reason(policy))
        with self._frozen_now(scheduler, datetime.datetime(2026, 5, 11, 2, 0, tzinfo=datetime.timezone.utc)):
            self.assertIsNone(scheduler.Model._skip_reason(policy))
        with self._frozen_now(scheduler, datetime.datetime(2026, 5, 12, 2, 0, tzinfo=datetime.timezone.utc)):
            self.assertIn("실행일", scheduler.Model._skip_reason(policy))

    def test_schedule_skips_when_current_occurrence_already_ran(self):
        scheduler = load_scheduler_module()
        policy = {
            "enabled": True,
            "schedule_type": "weekly",
            "schedule_weekday": 0,
            "schedule_time": "02:00",
            "last_run_at": "2026-05-11T02:01:00+00:00",
        }

        with self._frozen_now(scheduler, datetime.datetime(2026, 5, 11, 3, 0, tzinfo=datetime.timezone.utc)):
            self.assertIn("이미 실행", scheduler.Model._skip_reason(policy))

    def test_monthly_schedule_clamps_to_last_day_of_short_month(self):
        scheduler = load_scheduler_module()
        policy = {
            "enabled": True,
            "schedule_type": "monthly",
            "schedule_month_day": 31,
            "schedule_time": "02:00",
        }

        with self._frozen_now(scheduler, datetime.datetime(2026, 4, 30, 2, 1, tzinfo=datetime.timezone.utc)):
            self.assertIsNone(scheduler.Model._skip_reason(policy))

    def test_force_manual_run_includes_snapshots_even_when_policy_option_is_off(self):
        scheduler = load_scheduler_module()

        class FakeBackupSystem:
            def status(self, env=None):
                return {"status": "running", "backup_policy": {"max_items_per_run": 1, "snapshot_enabled": False, "snapshot_pause": True}}

            def mark_policy_run(self, result, env=None):
                return {"status": "running", "backup_policy": {"last_result": result}}

        class FakeImageBackups:
            def __init__(self):
                self.snapshot_ids = []
                self.limits = []

            def snapshot_to_harbor(self, service_id, backup_id, pause=True, env=None):
                self.snapshot_ids.append(backup_id)

            def record_runtime_snapshot_targets(self, limit=None, source="backup_policy_snapshot", env=None):
                self.limits.append(limit)
                return [{"service_id": "svc-1", "id": "snapshot-1", "compose_service": "web", "metadata": {"service_name": "demo-service"}}]

        class FakeVolumeBackups:
            def __init__(self):
                self.volume_ids = []

            def volume_to_harbor(self, service_id, backup_id, env=None):
                self.volume_ids.append(backup_id)

            def record_runtime_volume_targets(self, source="backup_policy_snapshot", env=None):
                return [{"service_id": "svc-1", "id": "volume-1", "compose_service": "db", "docker_volume": "demo_db_data", "metadata": {"service_name": "demo-service"}}]

        class FakeCleanup:
            def __init__(self):
                self.payloads = []

            def cleanup(self, payload=None, env=None):
                self.payloads.append(payload or {})
                return {"summary": {"deleted_count": 2, "failed_count": 0, "keep": payload.get("retention_keep_per_service")}}

        class FakeOperations:
            def __init__(self):
                self.requested_payload = None
                self.output_messages = []

            def create(self, operation_type, **kwargs):
                self.requested_payload = kwargs.get("requested_payload")
                return {"id": "op-1"}

            def append_output(self, operation_id, message, stream="system", metadata=None, env=None):
                self.output_messages.append({"operation_id": operation_id, "message": message, "stream": stream, "metadata": metadata or {}})

            def transition(self, operation_id, status, message=None, result_payload=None, env=None):
                return {"id": operation_id, "status": status, "result_payload": result_payload or {}}

        image_backups = FakeImageBackups()
        volume_backups = FakeVolumeBackups()
        cleanup = FakeCleanup()
        operations = FakeOperations()
        scheduler.backup_system = FakeBackupSystem()
        scheduler.image_backups = image_backups
        scheduler.volume_backups = volume_backups
        scheduler.cleanup = cleanup
        scheduler.operations = operations

        result = scheduler.Model.run({"force": True, "include_snapshots": False, "snapshot_enabled": False})

        self.assertEqual(image_backups.snapshot_ids, ["snapshot-1"])
        self.assertEqual(image_backups.limits, [None])
        self.assertEqual(volume_backups.volume_ids, ["volume-1"])
        self.assertEqual(result["snapshots"], 1)
        self.assertEqual(result["volumes"], 1)
        self.assertEqual(result["cleanup"]["deleted_count"], 2)
        self.assertEqual(cleanup.payloads[0]["retention_keep_per_service"], 10)
        self.assertTrue(operations.requested_payload["snapshot_enabled"])
        self.assertTrue(operations.requested_payload["volume_enabled"])
        self.assertNotIn("limit", operations.requested_payload)
        self.assertTrue(any("등록 서비스" in item["message"] for item in operations.output_messages))
        self.assertTrue(any("demo-service / web 스냅샷" in item["message"] for item in operations.output_messages))
        self.assertTrue(any("demo-service / db / demo_db_data named volume" in item["message"] for item in operations.output_messages))
        self.assertTrue(any("보존 정책 정리 완료" in item["message"] for item in operations.output_messages))

    def _frozen_now(self, module, now):
        real_datetime = module.datetime.datetime

        class FrozenDateTime(real_datetime):
            @classmethod
            def now(cls, tz=None):
                return now.astimezone(tz) if tz else now.replace(tzinfo=None)

            @classmethod
            def fromisoformat(cls, value):
                return real_datetime.fromisoformat(value)

        class FrozenContext:
            def __enter__(self_inner):
                module.datetime.datetime = FrozenDateTime

            def __exit__(self_inner, exc_type, exc, tb):
                module.datetime.datetime = real_datetime

        return FrozenContext()


class BackupSystemRuntimeSnapshotTargetTest(unittest.TestCase):
    def test_snapshot_targets_are_discovered_from_registered_running_service_containers(self):
        class FakeNodes:
            def list(self, env=None):
                return [{"id": "node-1", "name": "app-node"}]

            def live_containers(self, node_id, persist=False, env=None):
                return {
                    "groups": {
                        "service_groups": [
                            {
                                "service": {"id": "svc-1", "namespace": "demo"},
                                "containers": [
                                    {
                                        "id": "abcdef1234567890",
                                        "name": "demo_web_1",
                                        "image": "nginx:alpine",
                                        "state": "running",
                                        "service_namespace": "demo",
                                        "runtime_service_name": "demo-web",
                                    }
                                ],
                            }
                        ]
                    }
                }

        backups = load_backups_module(FakeNodes())
        backups.Model.ensure_schema = lambda env=None: None
        backups.Model._runtime_snapshot_services = lambda env=None: [
            {
                "id": "svc-1",
                "namespace": "demo",
                "stack_name": "demo",
                "compose_path": "/missing/docker-compose.yaml",
                "latest_compose_version_id": "version-1",
            }
        ]
        inserted = []

        def fake_insert(service, image, node, container, source, env=None):
            row = {
                "id": "target-1",
                "service_id": service["id"],
                "compose_service": image["compose_service"],
                "image_ref": image["image_ref"],
                "source": source,
                "metadata": {
                    "snapshot_target_node_id": node["id"],
                    "snapshot_target_container_id": container["id"],
                },
            }
            inserted.append(row)
            return row

        backups.Model._insert_runtime_snapshot_target = fake_insert

        rows = backups.Model.record_runtime_snapshot_targets(10)

        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["compose_service"], "web")
        self.assertEqual(rows[0]["image_ref"], "nginx:alpine")
        self.assertEqual(rows[0]["source"], "backup_policy_snapshot")
        self.assertEqual(rows[0]["metadata"]["snapshot_target_node_id"], "node-1")
        self.assertEqual(rows[0]["metadata"]["snapshot_target_container_id"], "abcdef1234567890")
        self.assertEqual(inserted, rows)

    def test_snapshot_runner_uses_recorded_target_node_and_container(self):
        class FakeNodes:
            def __init__(self):
                self.live_node_ids = []

            def live_containers(self, node_id, persist=False, env=None):
                self.live_node_ids.append(node_id)
                return {
                    "groups": {
                        "service_groups": [
                            {
                                "service": {"id": "svc-1", "namespace": "demo"},
                                "containers": [
                                    {
                                        "id": "abcdef1234567890",
                                        "state": "running",
                                        "service_namespace": "demo",
                                        "runtime_service_name": "demo_web",
                                    }
                                ],
                            }
                        ]
                    }
                }

            def detail(self, node_id, env=None):
                return {"id": node_id, "name": "app-node"}

            def list(self, env=None):
                return [{"id": "fallback-node"}]

        fake_nodes = FakeNodes()
        runner = load_struct_module(
            "service_image_snapshot_runner",
            config=FakeConfig(),
            models={
                "struct/backup_system": object(),
                "struct/images_harbor": object(),
                "struct/nodes": fake_nodes,
                "struct/operations": object(),
                "struct/services_shared": SimpleNamespace(ServiceError=Exception),
            },
        )

        target = runner.Model._target_container(
            {"id": "svc-1", "namespace": "demo"},
            {
                "compose_service": "web",
                "metadata": {
                    "snapshot_target_node_id": "node-1",
                    "snapshot_target_container_id": "abcdef1234567890",
                },
            },
        )

        self.assertEqual(target["node"]["id"], "node-1")
        self.assertEqual(target["container"]["id"], "abcdef1234567890")
        self.assertEqual(fake_nodes.live_node_ids, ["node-1"])


class BackupSystemCronTest(unittest.TestCase):
    def load_cron_module(self):
        return load_struct_module(
            "backup_system_cron",
            config=FakeConfig(),
            models={"db/postgres": SimpleNamespace(connect=lambda env=None: None)},
        )

    def test_enabled_policy_installs_single_managed_crontab_entry(self):
        cron = self.load_cron_module()
        cron.shutil.which = lambda name: "/usr/bin/curl" if name == "curl" else "/usr/bin/crontab"
        writes = []
        cron._read_crontab = lambda: "\n".join(
            [
                "MAILTO=root",
                "5 1 * * * echo keep-me",
                "0 0 * * * echo old # docker-infra-service-backup",
            ]
        )
        cron._write_crontab = lambda content: writes.append(content)
        policy = {
            "enabled": True,
            "schedule_type": "weekly",
            "schedule_weekday": 0,
            "schedule_time": "02:30",
        }

        plan = cron.Model.prepare(policy)
        result = cron.Model.sync(policy, plan)

        self.assertTrue(result["installed"])
        self.assertEqual(plan["metadata"]["schedule"], "30 2 * * 1")
        self.assertIn("token_hash", plan["metadata"])
        self.assertNotIn(plan["token"], str(plan["metadata"]))
        self.assertEqual(len(writes), 1)
        self.assertIn("MAILTO=root", writes[0])
        self.assertIn("echo keep-me", writes[0])
        self.assertNotIn("echo old", writes[0])
        self.assertIn("30 2 * * 1", writes[0])
        self.assertIn("/api/system/backup/tick", writes[0])
        self.assertIn("X-Docker-Infra-Cron-Token", writes[0])
        self.assertIn("# docker-infra-service-backup", writes[0])

    def test_disabled_policy_removes_managed_crontab_entry(self):
        cron = self.load_cron_module()
        writes = []
        cron._read_crontab = lambda: "\n".join(
            [
                "MAILTO=root",
                "0 0 * * * echo old # docker-infra-service-backup",
            ]
        )
        cron._write_crontab = lambda content: writes.append(content)

        plan = cron.Model.prepare({"enabled": False}, current={"token_hash": "old"})
        result = cron.Model.sync({"enabled": False}, plan)

        self.assertFalse(result["installed"])
        self.assertEqual(len(writes), 1)
        self.assertIn("MAILTO=root", writes[0])
        self.assertNotIn("docker-infra-service-backup", writes[0])


if __name__ == "__main__":
    unittest.main()
