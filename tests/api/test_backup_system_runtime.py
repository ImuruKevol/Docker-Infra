import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace


ROOT = Path(__file__).resolve().parents[2]


class FakeConfig:
    LOCAL_EXECUTOR_ALLOWLIST_ENV = "DOCKER_INFRA_LOCAL_EXECUTOR_ALLOWLIST"

    def backup_harbor_ports(self, env=None):
        return {"http": 5000, "https": 5443}

    def backup_harbor_version(self, env=None):
        return "v2.15.0"

    def runtime_env(self, env=None):
        return dict(env or {})

    def advertise_address(self, env=None):
        return "127.0.0.1"

    def data_dir(self, env=None):
        return "/tmp/docker-infra-data"


def load_struct_module(name, config=None, models=None):
    path = ROOT / "src" / "model" / "struct" / f"{name}.py"
    module_name = f"_test_{name}_{id(models)}"
    spec = importlib.util.spec_from_file_location(module_name, path)
    module = importlib.util.module_from_spec(spec)
    module.wiz = SimpleNamespace(
        config=lambda _: config or FakeConfig(),
        model=lambda key: (models or {})[key],
    )
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


class BackupSystemResourceTest(unittest.TestCase):
    def test_generated_harbor_yml_contains_harbor_2_15_required_fields(self):
        resources = load_struct_module("backup_system_resources", config=FakeConfig())

        with tempfile.TemporaryDirectory() as tmp:
            path = resources.write_harbor_yml(tmp, "admin-secret", "db-secret")
            content = Path(path).read_text(encoding="utf-8")

        self.assertIn('hostname: "localhost"', content)
        self.assertIn('external_url: "http://127.0.0.1:5000"', content)
        self.assertIn('harbor_admin_password: "admin-secret"', content)
        self.assertIn('password: "db-secret"', content)
        self.assertIn("db_repository: ghcr.io/aquasecurity/trivy-db", content)
        self.assertIn("java_db_repository: ghcr.io/aquasecurity/trivy-java-db", content)
        self.assertIn("max_job_duration_hours: 24", content)
        self.assertIn("logger_sweeper_duration: 1", content)
        self.assertIn("webhook_job_http_client_timeout: 3", content)
        self.assertIn("expire_hours: 24", content)
        self.assertIn("_version: 2.15.0", content)
        self.assertNotIn("\nhttps:\n", content)


class FakeOperations:
    def __init__(self):
        self.outputs = []
        self.transitions = []

    def create(self, operation_type, **kwargs):
        return {"id": "op-1", "type": operation_type, "status": "running"}

    def append_output(self, operation_id, message, stream="system", **kwargs):
        self.outputs.append({"operation_id": operation_id, "message": message, "stream": stream})

    def transition(self, operation_id, status, message=None, result_payload=None, **kwargs):
        operation = {"id": operation_id, "status": status, "message": message, "result_payload": result_payload or {}}
        self.transitions.append(operation)
        return operation


class FakeLocalExecutor:
    class LocalCommandError(Exception):
        def __init__(self, status_code, message, error_code, **extra):
            super().__init__(message)
            self.status_code = status_code
            self.message = message
            self.error_code = error_code
            self.extra = extra

    def __init__(self, result):
        self.result = result

    def run(self, command_id, params=None, env=None):
        return self.result


class BackupSystemError(Exception):
    def __init__(self, status_code, message, error_code, **extra):
        super().__init__(message)
        self.status_code = status_code
        self.message = message
        self.error_code = error_code
        self.extra = extra


class BackupSystemRuntimeTest(unittest.TestCase):
    def test_run_operation_records_stdout_and_stderr_for_failed_commands(self):
        operations = FakeOperations()
        local_executor = FakeLocalExecutor(
            {
                "status": "error",
                "exit_code": 1,
                "stdout": "normal output with admin-secret",
                "stderr": "Traceback\nKeyError: 'logger_sweeper_duration'\n",
            }
        )
        runtime = load_struct_module(
            "backup_system_runtime",
            config=FakeConfig(),
            models={
                "struct/local_executor": local_executor,
                "struct/operations": operations,
                "struct/backup_system_resources": object(),
            },
        )

        class Backup(runtime.BackupSystemRuntimeMixin):
            BackupSystemError = BackupSystemError

        with self.assertRaises(BackupSystemError) as raised:
            Backup()._run_operation("backup.harbor.enable", "backup.harbor.install", {}, secret_values=["admin-secret"])

        self.assertEqual([item["stream"] for item in operations.outputs], ["stdout", "stderr"])
        self.assertIn("KeyError: 'logger_sweeper_duration'", raised.exception.message)
        self.assertIn("KeyError: 'logger_sweeper_duration'", operations.transitions[-1]["message"])
        self.assertNotIn("admin-secret", raised.exception.extra["check"]["stdout"])

    def test_refresh_preserves_failed_install_state_when_compose_is_missing(self):
        runtime = load_struct_module(
            "backup_system_runtime",
            config=FakeConfig(),
            models={
                "struct/local_executor": FakeLocalExecutor({"status": "ok", "stdout": ""}),
                "struct/operations": FakeOperations(),
                "struct/backup_system_resources": object(),
            },
        )

        class Backup(runtime.BackupSystemRuntimeMixin):
            def __init__(self):
                self.calls = []

            def status(self, env=None):
                return {
                    "id": "backup-1",
                    "enabled": True,
                    "installed": False,
                    "status": "failed",
                    "last_error": "prepare failed",
                    "data_path": "/tmp/backup-harbor",
                }

            def _set_state(self, status, message=None, env=None):
                self.calls.append((status, message))
                return {"status": status, "last_error": message}

        backup = Backup()
        result = backup.refresh()

        self.assertEqual(result["status"], "failed")
        self.assertEqual(result["last_error"], "prepare failed")
        self.assertEqual(backup.calls, [("failed", "prepare failed")])


if __name__ == "__main__":
    unittest.main()
