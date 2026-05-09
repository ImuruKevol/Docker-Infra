import os
import socket
from pathlib import Path
from urllib.parse import quote


DEFAULT_DB_PORT = "5432"
DEFAULT_DB_NAME = "docker_infra"
DEFAULT_DB_USER = "docker_infra"
DEFAULT_DB_SCHEMA = "public"
DEFAULT_SECRET_KEY = "docker-infra-development-secret"
DEFAULT_SSH_KEY_DIR = ".runtime/ssh"
DEFAULT_DATA_DIR = "data"
DEFAULT_BACKUP_HARBOR_DATA_DIR = "data/backup-harbor"
DEFAULT_BACKUP_HARBOR_HTTP_PORT = "5000"
DEFAULT_BACKUP_HARBOR_HTTPS_PORT = "5443"
DEFAULT_BACKUP_HARBOR_VERSION = "v2.15.0"
CONFIG_ENV_NAME = "config.env"
LOCAL_EXECUTOR_ALLOWLIST_ENV = "DOCKER_INFRA_LOCAL_EXECUTOR_ALLOWLIST"
DEFAULT_LOCAL_EXECUTOR_ALLOWLIST = [
    "swarm.init",
    "swarm.network.ensure",
    "docker.container.start",
    "docker.container.stop",
    "docker.container.restart",
    "docker.image.remove",
    "service.stack.deploy",
    "service.stack.remove",
    "proxy.nginx.reload",
    "certbot.nginx.issue",
    "openssl.self_signed_cert.issue",
    "backup.harbor.install",
    "backup.harbor.up",
    "backup.harbor.down",
    "backup.harbor.restart",
]


def _workspace_root():
    try:
        return Path(server.path.root)
    except Exception:
        return Path(__file__).resolve().parents[3]


def _env_file_path():
    return _workspace_root() / CONFIG_ENV_NAME


def _parse_env_line(line):
    line = line.strip()
    if not line or line.startswith("#") or "=" not in line:
        return None, None
    key, value = line.split("=", 1)
    key = key.strip()
    value = value.strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
        value = value[1:-1]
    return key, value


def _read_config_env():
    path = _env_file_path()
    if not path.is_file():
        return {}
    values = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        key, value = _parse_env_line(line)
        if key:
            values[key] = value
    return values


def runtime_env(env=None):
    values = _read_config_env()
    values.update(os.environ)
    if env:
        values.update(env)
    return values


def _bool_value(value, default=False):
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"1", "true", "yes", "on"}


def database(env=None):
    values = runtime_env(env)
    return {
        "url": values.get("DOCKER_INFRA_DATABASE_URL"),
        "host": values.get("DOCKER_INFRA_DB_HOST"),
        "port": values.get("DOCKER_INFRA_DB_PORT", DEFAULT_DB_PORT),
        "name": values.get("DOCKER_INFRA_DB_NAME", DEFAULT_DB_NAME),
        "user": values.get("DOCKER_INFRA_DB_USER", DEFAULT_DB_USER),
        "password": values.get("DOCKER_INFRA_DB_PASSWORD", ""),
        "schema": values.get("DOCKER_INFRA_DB_SCHEMA", DEFAULT_DB_SCHEMA) or DEFAULT_DB_SCHEMA,
    }


def database_url(env=None):
    config = database(env)
    if config["url"]:
        return config["url"]
    if not config["host"]:
        return None
    user = quote(str(config["user"]), safe="")
    password = quote(str(config["password"]), safe="")
    auth = user if password == "" else f"{user}:{password}"
    return f"postgresql://{auth}@{config['host']}:{config['port']}/{config['name']}"


def database_schema(env=None):
    return database(env)["schema"]


def has_database_config(env=None):
    return database_url(env) is not None


def secret_key(env=None):
    return runtime_env(env).get("DOCKER_INFRA_SECRET_KEY") or DEFAULT_SECRET_KEY


def local_executor_allowlist(env=None):
    raw = runtime_env(env).get(LOCAL_EXECUTOR_ALLOWLIST_ENV, "")
    configured = [item.strip() for item in raw.split(",") if item.strip()]
    return sorted({*DEFAULT_LOCAL_EXECUTOR_ALLOWLIST, *configured})


def ssh_key_dir(env=None):
    raw = runtime_env(env).get("DOCKER_INFRA_SSH_KEY_DIR") or DEFAULT_SSH_KEY_DIR
    path = Path(raw).expanduser()
    if path.is_absolute():
        return str(path)
    return str(_workspace_root() / path)


def data_dir(env=None):
    raw = runtime_env(env).get("DOCKER_INFRA_DATA_DIR") or DEFAULT_DATA_DIR
    path = Path(raw).expanduser()
    if path.is_absolute():
        return str(path)
    return str(_workspace_root() / path)


def backup_harbor_data_dir(env=None):
    raw = runtime_env(env).get("DOCKER_INFRA_BACKUP_HARBOR_DATA_DIR") or DEFAULT_BACKUP_HARBOR_DATA_DIR
    path = Path(raw).expanduser()
    if path.is_absolute():
        return str(path)
    return str(_workspace_root() / path)


def _port(value, fallback):
    try:
        number = int(value)
    except (TypeError, ValueError):
        return int(fallback)
    return number if 1 <= number <= 65535 else int(fallback)


def backup_harbor_ports(env=None):
    values = runtime_env(env)
    return {
        "http": _port(values.get("DOCKER_INFRA_BACKUP_HARBOR_HTTP_PORT"), DEFAULT_BACKUP_HARBOR_HTTP_PORT),
        "https": _port(values.get("DOCKER_INFRA_BACKUP_HARBOR_HTTPS_PORT"), DEFAULT_BACKUP_HARBOR_HTTPS_PORT),
    }


def backup_harbor_version(env=None):
    return runtime_env(env).get("DOCKER_INFRA_BACKUP_HARBOR_VERSION") or DEFAULT_BACKUP_HARBOR_VERSION


def backup_harbor_installer_url(env=None):
    version = backup_harbor_version(env)
    return runtime_env(env).get("DOCKER_INFRA_BACKUP_HARBOR_INSTALLER_URL") or (
        f"https://github.com/goharbor/harbor/releases/download/{version}/harbor-online-installer-{version}.tgz"
    )


def system_assets_dir(env=None):
    return str(Path(data_dir(env)) / "system-assets")


def advertise_address(env=None):
    configured = runtime_env(env).get("DOCKER_INFRA_ADVERTISE_ADDRESS")
    if configured:
        return configured
    try:
        return socket.gethostbyname(socket.gethostname())
    except Exception:
        return "127.0.0.1"


def session_cookie_secure(default=False, env=None):
    return _bool_value(runtime_env(env).get("DOCKER_INFRA_SESSION_COOKIE_SECURE"), default=default)


def certbot_email(env=None):
    return runtime_env(env).get("DOCKER_INFRA_CERTBOT_EMAIL", "").strip()


def certbot_staging(env=None):
    return _bool_value(runtime_env(env).get("DOCKER_INFRA_CERTBOT_STAGING"), default=False)


def self_signed_cert_test_enabled(env=None):
    return _bool_value(runtime_env(env).get("DOCKER_INFRA_SSL_SELF_SIGNED_TEST"), default=False)


def self_signed_cert_days(env=None):
    value = runtime_env(env).get("DOCKER_INFRA_SSL_SELF_SIGNED_DAYS", "7")
    try:
        days = int(value)
    except (TypeError, ValueError):
        days = 7
    return max(1, min(days, 365))
