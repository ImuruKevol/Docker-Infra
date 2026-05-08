import datetime
import secrets
import shutil
from pathlib import Path

from psycopg.types.json import Jsonb


postgres = wiz.model("db/postgres")
config = wiz.config("docker_infra")
resources = wiz.model("struct/backup_system_resources")
runtime_mixin = wiz.model("struct/backup_system_runtime")
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


def _compose_path(data_path):
    return str(resources.paths(data_path)["compose"])


def _row(row, env=None):
    if row is None:
        data_path = _absolute_data_path(env=env)
        storage = _storage(data_path)
        compose_path = _compose_path(data_path)
        return {
            "id": None,
            "enabled": False,
            "status": "disabled",
            "data_path": data_path,
            "harbor_url": None,
            "admin_username": "admin",
            "secret_configured": False,
            "installed": Path(compose_path).is_file(),
            "compose_path": compose_path,
            "required_ports": _ports(env),
            "storage": storage,
            "last_error": None,
            "last_checked_at": None,
            "metadata": {"source": "default"},
        }
    data_path = row["data_path"]
    storage = _storage(data_path)
    compose_path = _compose_path(data_path)
    return {
        "id": str(row["id"]),
        "enabled": bool(row["enabled"]),
        "status": row["status"],
        "data_path": data_path,
        "harbor_url": row["harbor_url"],
        "admin_username": row["admin_username"] or "admin",
        "secret_configured": bool(row["admin_password_enc"]),
        "installed": Path(compose_path).is_file(),
        "compose_path": compose_path,
        "required_ports": _ports(env),
        "storage": storage,
        "last_error": row["last_error"],
        "last_checked_at": row["last_checked_at"],
        "metadata": row["metadata"],
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
    }


class BackupSystem(runtime_mixin):
    BackupSystemError = BackupSystemError
    connect = staticmethod(connect)
    _row = staticmethod(_row)
    _storage = staticmethod(_storage)

    def default_config(self, env=None):
        return _row(None, env=env)

    def status(self, env=None):
        with connect(env=env) as connection:
            with connection.cursor() as cursor:
                cursor.execute("SELECT * FROM backup_system_settings WHERE singleton_key = 'default'")
                return _row(cursor.fetchone(), env=env)

    def _fetch(self, cursor, decrypt=False, env=None):
        secret_expr = "NULL AS admin_password"
        if decrypt:
            secret_expr = "pgp_sym_decrypt(decode(admin_password_enc, 'base64'), %s) AS admin_password"
        cursor.execute(
            f"SELECT *, {secret_expr} FROM backup_system_settings WHERE singleton_key = 'default'",
            (config.secret_key(env),) if decrypt else (),
        )
        return cursor.fetchone()

    def _generated_password(self):
        return secrets.token_urlsafe(24)

    def _upsert(self, cursor, enabled, data_path, test_run_id=None, metadata=None, env=None):
        status = "pending_install" if enabled else "disabled"
        storage = _storage(data_path)
        admin_username = "admin"
        admin_password = self._generated_password() if enabled else None
        password_sql = "NULL"
        params = [
            enabled,
            status,
            data_path,
            resources.harbor_url(env),
            admin_username,
        ]
        if admin_password:
            password_sql = "encode(pgp_sym_encrypt(%s, %s), 'base64')"
            params.extend([admin_password, config.secret_key(env)])
        params.extend([
            storage["used_bytes"],
            storage["available_bytes"],
            storage["total_bytes"],
            _utcnow(),
            test_run_id,
            Jsonb(metadata or {}),
        ])
        cursor.execute(
            f"""
            INSERT INTO backup_system_settings(
                singleton_key, enabled, status, data_path, harbor_url, admin_username,
                admin_password_enc, used_bytes, available_bytes, total_bytes,
                last_error, last_checked_at, test_run_id, metadata
            )
            VALUES ('default', %s, %s, %s, %s, %s, {password_sql}, %s, %s, %s, NULL, %s, %s, %s)
            ON CONFLICT (singleton_key) DO UPDATE SET
                enabled = EXCLUDED.enabled,
                status = EXCLUDED.status,
                data_path = EXCLUDED.data_path,
                harbor_url = EXCLUDED.harbor_url,
                admin_username = EXCLUDED.admin_username,
                admin_password_enc = COALESCE(EXCLUDED.admin_password_enc, backup_system_settings.admin_password_enc),
                used_bytes = EXCLUDED.used_bytes,
                available_bytes = EXCLUDED.available_bytes,
                total_bytes = EXCLUDED.total_bytes,
                last_error = NULL,
                last_checked_at = EXCLUDED.last_checked_at,
                test_run_id = EXCLUDED.test_run_id,
                metadata = EXCLUDED.metadata
            RETURNING *
            """,
            params,
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
            "install_mode": "local_harbor",
            "required_ports": _ports(env),
        }
        with connection.cursor() as cursor:
            return self._upsert(cursor, enabled, data_path, test_run_id=test_run_id, metadata=metadata, env=env)

    def connection_config(self, env=None):
        with connect(env=env) as connection:
            with connection.cursor() as cursor:
                row = self._fetch(cursor, decrypt=True, env=env)
        status = _row(row, env=env)
        password = row.get("admin_password") if row else ""
        return {
            **status,
            "username": status.get("admin_username") or "admin",
            "password": password or "",
            "configured": bool(status.get("enabled") and status.get("harbor_url") and password),
        }

    def delete_by_test_run_id(self, test_run_id, env=None):
        with connect(env=env) as connection:
            with connection.cursor() as cursor:
                cursor.execute("DELETE FROM backup_system_settings WHERE test_run_id = %s", (test_run_id,))
                return cursor.rowcount


Model = BackupSystem()
