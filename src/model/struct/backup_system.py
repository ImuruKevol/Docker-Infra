import datetime
import shutil
from pathlib import Path

from psycopg.types.json import Jsonb


postgres = wiz.model("db/postgres")
config = wiz.config("docker_infra")
connect = postgres.connect


STATUSES = {"disabled", "pending_install", "running", "stopped", "failed"}


class BackupSystemError(Exception):
    def __init__(self, status_code, message, error_code, **extra):
        super().__init__(message)
        self.status_code = status_code
        self.message = message
        self.error_code = error_code
        self.extra = extra


def _utcnow():
    return datetime.datetime.now(datetime.timezone.utc)


def _absolute_data_path(value=None, env=None):
    if not value:
        return config.backup_harbor_data_dir(env)
    path = Path(str(value)).expanduser()
    if path.is_absolute():
        return str(path)
    return str((Path(config.data_dir(env)).parent / path).resolve())


def _probe_path(data_path):
    path = Path(data_path).expanduser()
    probe = path if path.exists() else path.parent
    while not probe.exists() and probe.parent != probe:
        probe = probe.parent
    return probe


def _storage(data_path):
    usage = shutil.disk_usage(_probe_path(data_path))
    return {
        "total_bytes": int(usage.total),
        "used_bytes": int(usage.used),
        "available_bytes": int(usage.free),
    }


def _ports(env=None):
    configured = config.backup_harbor_ports(env)
    return [
        {"label": "Harbor HTTP", "port": configured["http"], "protocol": "tcp"},
        {"label": "Harbor HTTPS", "port": configured["https"], "protocol": "tcp"},
    ]


def _row(row, env=None):
    if row is None:
        data_path = _absolute_data_path(env=env)
        storage = _storage(data_path)
        return {
            "id": None,
            "enabled": False,
            "status": "disabled",
            "data_path": data_path,
            "harbor_url": None,
            "required_ports": _ports(env),
            "storage": storage,
            "last_error": None,
            "last_checked_at": None,
            "metadata": {"source": "default"},
        }
    data_path = row["data_path"]
    storage = _storage(data_path)
    return {
        "id": str(row["id"]),
        "enabled": bool(row["enabled"]),
        "status": row["status"],
        "data_path": data_path,
        "harbor_url": row["harbor_url"],
        "required_ports": _ports(env),
        "storage": storage,
        "last_error": row["last_error"],
        "last_checked_at": row["last_checked_at"],
        "metadata": row["metadata"],
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
    }


class BackupSystem:
    BackupSystemError = BackupSystemError

    def default_config(self, env=None):
        return _row(None, env=env)

    def status(self, env=None):
        with connect(env=env) as connection:
            with connection.cursor() as cursor:
                cursor.execute("SELECT * FROM backup_system_settings WHERE singleton_key = 'default'")
                return _row(cursor.fetchone(), env=env)

    def _upsert(self, cursor, enabled, data_path, test_run_id=None, metadata=None, env=None):
        status = "pending_install" if enabled else "disabled"
        storage = _storage(data_path)
        cursor.execute(
            """
            INSERT INTO backup_system_settings(
                singleton_key, enabled, status, data_path, used_bytes, available_bytes,
                total_bytes, last_error, last_checked_at, test_run_id, metadata
            )
            VALUES ('default', %s, %s, %s, %s, %s, %s, NULL, %s, %s, %s)
            ON CONFLICT (singleton_key) DO UPDATE SET
                enabled = EXCLUDED.enabled,
                status = EXCLUDED.status,
                data_path = EXCLUDED.data_path,
                used_bytes = EXCLUDED.used_bytes,
                available_bytes = EXCLUDED.available_bytes,
                total_bytes = EXCLUDED.total_bytes,
                last_error = NULL,
                last_checked_at = EXCLUDED.last_checked_at,
                test_run_id = EXCLUDED.test_run_id,
                metadata = EXCLUDED.metadata
            RETURNING *
            """,
            (
                enabled,
                status,
                data_path,
                storage["used_bytes"],
                storage["available_bytes"],
                storage["total_bytes"],
                _utcnow(),
                test_run_id,
                Jsonb(metadata or {}),
            ),
        )
        return _row(cursor.fetchone(), env=env)

    def configure(self, payload=None, test_run_id=None, env=None):
        with connect(env=env) as connection:
            return self.configure_with_connection(payload, test_run_id=test_run_id, connection=connection, env=env)

    def configure_with_connection(self, payload=None, test_run_id=None, connection=None, env=None):
        payload = payload or {}
        enabled = bool(payload.get("enabled"))
        data_path = _absolute_data_path(payload.get("data_path"), env=env)
        if enabled:
            try:
                Path(data_path).mkdir(parents=True, exist_ok=True)
            except OSError as exc:
                raise BackupSystemError(400, f"백업 저장 경로를 생성할 수 없습니다: {exc}", "BACKUP_DATA_PATH_UNAVAILABLE")
        metadata = {
            "source": "setup_wizard",
            "install_mode": "deferred_compose",
            "required_ports": _ports(env),
        }
        with connection.cursor() as cursor:
            return self._upsert(cursor, enabled, data_path, test_run_id=test_run_id, metadata=metadata, env=env)

    def delete_by_test_run_id(self, test_run_id, env=None):
        with connect(env=env) as connection:
            with connection.cursor() as cursor:
                cursor.execute("DELETE FROM backup_system_settings WHERE test_run_id = %s", (test_run_id,))
                return cursor.rowcount


Model = BackupSystem()
