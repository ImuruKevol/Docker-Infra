import datetime
from pathlib import Path

from psycopg.types.json import Jsonb

auth = wiz.model("struct/auth")
backup_system = wiz.model("struct/backup_system")
postgres = wiz.model("db/postgres")
environment = wiz.model("struct/setup_environment")
connect = postgres.connect
has_database_config = postgres.has_database_config
AuthError = auth.AuthError
detect_advertise_address = environment.detect_advertise_address
detect_docker = environment.detect_docker
detect_proxy = environment.detect_proxy
detect_local_environment = environment.detect_local_environment


SETUP_COMPLETED_KEY = "setup.completed"
SETUP_COMPLETED_AT_KEY = "setup.completed_at"
SETUP_DEFAULT_PROXY_KEY = "setup.default_proxy"
SETUP_TEMPLATE_ROOT_KEY = "setup.template_root"
SETUP_ADVERTISE_ADDRESS_KEY = "setup.advertise_address"
ALLOWED_PROXY_TYPES = {"nginx"}


class SetupError(Exception):
    def __init__(self, status_code, message, error_code, **extra):
        super().__init__(message)
        self.status_code = status_code
        self.message = message
        self.error_code = error_code
        self.extra = extra


def utcnow():
    return datetime.datetime.now(datetime.timezone.utc)


def _setting_value(row):
    if row is None:
        return None
    return row["value_json"]


def _node_to_dict(row):
    if row is None:
        return None
    return {
        "id": str(row["id"]),
        "name": row["name"],
        "role": row["role"],
        "host": row["host"],
        "ssh_port": row["ssh_port"],
        "auth_type": row["auth_type"],
        "status": row["status"],
        "swarm_node_id": row["swarm_node_id"],
        "is_local_master": row["is_local_master"],
        "labels": row["labels"],
        "test_run_id": row["test_run_id"],
        "metadata": row["metadata"],
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
    }


class SetupService:
    SetupError = SetupError
    detect_advertise_address = staticmethod(detect_advertise_address)
    detect_docker = staticmethod(detect_docker)
    detect_proxy = staticmethod(detect_proxy)
    detect_local_environment = staticmethod(detect_local_environment)

    def database_configured(self):
        return has_database_config()

    def _settings(self, connection):
        keys = [
            SETUP_COMPLETED_KEY,
            SETUP_COMPLETED_AT_KEY,
            SETUP_DEFAULT_PROXY_KEY,
            SETUP_TEMPLATE_ROOT_KEY,
            SETUP_ADVERTISE_ADDRESS_KEY,
        ]
        with connection.cursor() as cursor:
            cursor.execute("SELECT key, value_json FROM system_settings WHERE key = ANY(%s)", (keys,))
            return {row["key"]: row for row in cursor.fetchall()}

    def _local_master(self, connection):
        with connection.cursor() as cursor:
            cursor.execute("SELECT * FROM nodes WHERE is_local_master = true LIMIT 1")
            return _node_to_dict(cursor.fetchone())

    def status(self, include_checks=True, env=None):
        if not has_database_config(env):
            return {
                "configured": False,
                "database_configured": False,
                "requires_setup": True,
                "settings": {
                    "completed": False,
                    "completed_at": None,
                    "default_proxy": None,
                    "template_root": None,
                    "advertise_address": None,
                },
                "local_master": None,
                "backup_system": backup_system.default_config(env=env),
                "checks": detect_local_environment(env=env) if include_checks else None,
            }

        with connect(env=env) as connection:
            settings = self._settings(connection)
            has_password = auth.get_password_hash(connection) is not None
            completed = bool(_setting_value(settings.get(SETUP_COMPLETED_KEY)))
            local_master = self._local_master(connection)
            return {
                "configured": completed and has_password and local_master is not None,
                "database_configured": True,
                "requires_setup": not (completed and has_password and local_master is not None),
                "settings": {
                    "completed": completed,
                    "completed_at": _setting_value(settings.get(SETUP_COMPLETED_AT_KEY)),
                    "default_proxy": _setting_value(settings.get(SETUP_DEFAULT_PROXY_KEY)),
                    "template_root": _setting_value(settings.get(SETUP_TEMPLATE_ROOT_KEY)),
                    "advertise_address": _setting_value(settings.get(SETUP_ADVERTISE_ADDRESS_KEY)),
                },
                "local_master": local_master,
                "backup_system": backup_system.status(env=env),
                "checks": detect_local_environment(env=env) if include_checks else None,
            }

    def _choose_proxy(self, requested, checks):
        return "nginx"

    def _upsert_setting(self, cursor, key, value, value_type, test_run_id, metadata=None):
        cursor.execute(
            """
            INSERT INTO system_settings(key, value_json, secret_enc, value_type, is_secret, test_run_id, metadata)
            VALUES (%s, %s, NULL, %s, false, %s, %s)
            ON CONFLICT (key) DO UPDATE SET
                value_json = EXCLUDED.value_json,
                value_type = EXCLUDED.value_type,
                is_secret = false,
                secret_enc = NULL,
                test_run_id = EXCLUDED.test_run_id,
                metadata = EXCLUDED.metadata
            """,
            (key, Jsonb(value), value_type, test_run_id, Jsonb(metadata or {})),
        )

    def _upsert_local_master(self, cursor, advertise_address, test_run_id, checks):
        metadata = {
            "source": "setup_wizard",
            "docker": checks["docker"],
            "proxy": checks["proxy"],
        }
        swarm = checks["docker"].get("swarm") or {}
        cursor.execute(
            """
            UPDATE nodes
            SET
                name = %s,
                role = 'local_master',
                host = %s,
                ssh_port = NULL,
                auth_type = NULL,
                status = %s,
                swarm_node_id = %s,
                is_local_master = true,
                labels = %s,
                test_run_id = %s,
                metadata = %s
            WHERE is_local_master = true
            RETURNING *
            """,
            (
                "local-master",
                advertise_address,
                "active",
                swarm.get("node_id"),
                Jsonb({"scope": "local"}),
                test_run_id,
                Jsonb(metadata),
            ),
        )
        row = cursor.fetchone()
        if row is not None:
            return _node_to_dict(row)

        cursor.execute(
            """
            INSERT INTO nodes(
                name, role, host, ssh_port, auth_type, status, swarm_node_id,
                is_local_master, labels, test_run_id, metadata
            )
            VALUES (%s, 'local_master', %s, NULL, NULL, %s, %s, true, %s, %s, %s)
            RETURNING *
            """,
            (
                "local-master",
                advertise_address,
                "active",
                swarm.get("node_id"),
                Jsonb({"scope": "local"}),
                test_run_id,
                Jsonb(metadata),
            ),
        )
        return _node_to_dict(cursor.fetchone())

    def complete(self, payload, env=None):
        if not has_database_config(env):
            raise RuntimeError("Docker Infra database config is not configured")

        payload = payload or {}
        password = payload.get("password")
        confirm_password = payload.get("confirm_password")
        if confirm_password is not None and password != confirm_password:
            raise SetupError(400, "비밀번호 확인이 일치하지 않습니다.", "PASSWORD_CONFIRM_MISMATCH")

        current = self.status(include_checks=False, env=env)
        if current["configured"]:
            raise SetupError(409, "이미 설치가 완료되었습니다.", "SETUP_ALREADY_COMPLETED")

        checks = detect_local_environment(env=env)
        advertise_address = payload.get("advertise_address") or checks["advertise_address"]
        template_root = payload.get("template_root") or ".runtime/dev/templates"
        proxy_type = self._choose_proxy(payload.get("proxy_type"), checks)
        test_run_id = payload.get("test_run_id")
        completed_at = utcnow().isoformat().replace("+00:00", "Z")

        try:
            Path(template_root).expanduser().mkdir(parents=True, exist_ok=True)
        except Exception as exc:
            raise SetupError(400, f"Template root를 생성할 수 없습니다: {exc}", "TEMPLATE_ROOT_UNAVAILABLE")

        backup_requested = bool((payload.get("backup_system") or {}).get("enabled"))
        backup_error = None
        with connect(env=env) as connection:
            auth.set_password(
                password,
                test_run_id=test_run_id,
                metadata={"source": "setup_wizard"},
                connection=connection,
            )
            with connection.cursor() as cursor:
                self._upsert_setting(cursor, SETUP_COMPLETED_KEY, True, "boolean", test_run_id)
                self._upsert_setting(cursor, SETUP_COMPLETED_AT_KEY, completed_at, "datetime", test_run_id)
                self._upsert_setting(cursor, SETUP_DEFAULT_PROXY_KEY, proxy_type, "string", test_run_id)
                self._upsert_setting(cursor, SETUP_TEMPLATE_ROOT_KEY, template_root, "path", test_run_id)
                self._upsert_setting(cursor, SETUP_ADVERTISE_ADDRESS_KEY, advertise_address, "string", test_run_id)
                local_master = self._upsert_local_master(cursor, advertise_address, test_run_id, checks)
                try:
                    backup = backup_system.configure_with_connection(
                        payload.get("backup_system"), test_run_id=test_run_id, connection=connection, env=env
                    )
                except backup_system.BackupSystemError as exc:
                    raise SetupError(exc.status_code, exc.message, exc.error_code, **exc.extra)

        if backup_requested:
            try:
                backup = backup_system.enable(env=env)["backup_system"]
            except backup_system.BackupSystemError as exc:
                backup = backup_system.status(env=env)
                backup_error = {"message": exc.message, "error_code": exc.error_code, **exc.extra}

        return {
            "setup": self.status(include_checks=True, env=env),
            "local_master": local_master,
            "backup_system": backup,
            "backup_error": backup_error,
        }

    def delete_by_test_run_id(self, test_run_id, env=None):
        with connect(env=env) as connection:
            with connection.cursor() as cursor:
                cursor.execute("DELETE FROM auth_sessions WHERE test_run_id = %s", (test_run_id,))
                sessions = cursor.rowcount
                cursor.execute("DELETE FROM auth_login_attempts WHERE test_run_id = %s", (test_run_id,))
                attempts = cursor.rowcount
                cursor.execute("DELETE FROM operator_auth WHERE test_run_id = %s", (test_run_id,))
                passwords = cursor.rowcount
                cursor.execute("DELETE FROM nodes WHERE test_run_id = %s", (test_run_id,))
                nodes = cursor.rowcount
                cursor.execute("DELETE FROM system_settings WHERE test_run_id = %s", (test_run_id,))
                settings = cursor.rowcount
                return {
                    "sessions": sessions,
                    "login_attempts": attempts,
                    "passwords": passwords,
                    "nodes": nodes,
                    "settings": settings,
                }


Model = SetupService()
