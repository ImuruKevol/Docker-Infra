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
            "struct/operations": object(),
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
            }
        )

        self.assertEqual(policy["mode"], "scheduled")
        self.assertEqual(policy["schedule_type"], "monthly")
        self.assertEqual(policy["schedule_weekday"], 6)
        self.assertEqual(policy["schedule_month_day"], 31)
        self.assertEqual(policy["schedule_time"], "02:00")

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


if __name__ == "__main__":
    unittest.main()
