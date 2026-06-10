import ipaddress
import os
import socket
from pathlib import Path
from urllib.parse import quote
from urllib import request as urlrequest


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
DEFAULT_NODE_EXPORTER_IMAGE = "quay.io/prometheus/node-exporter:v1.8.2"
DEFAULT_NODE_METRIC_COLLECTION_INTERVAL_SECONDS = "600"
DEFAULT_NODE_METRIC_SAMPLE_INTERVAL_SECONDS = "1"
DEFAULT_DDNS_PUBLIC_IP_URLS = [
    "https://api.ipify.org",
    "https://checkip.amazonaws.com",
    "https://ifconfig.me/ip",
]
DEFAULT_DDNS_STATE_FILE = "/var/lib/docker-infra/ddns/last-sent.json"
DEFAULT_DDNS_DISPATCHER_SCRIPT_PATH = "/usr/local/bin/docker-infra-ddns-update"
DEFAULT_DDNS_DISPATCHER_PATH = "/etc/NetworkManager/dispatcher.d/90-docker-infra-ddns"
CONFIG_ENV_NAME = "config.env"
LOCAL_EXECUTOR_ALLOWLIST_ENV = "DOCKER_INFRA_LOCAL_EXECUTOR_ALLOWLIST"
DEFAULT_LOCAL_EXECUTOR_ALLOWLIST = [
    "swarm.init",
    "swarm.node.remove",
    "swarm.network.ensure",
    "docker.container.start",
    "docker.container.stop",
    "docker.container.restart",
    "docker.container.delete",
    "docker.container.file.list",
    "docker.container.file.read",
    "docker.container.file.download",
    "docker.container.file.write",
    "docker.container.file.mkdir",
    "docker.container.file.rename",
    "docker.container.file.delete",
    "docker.container.file.move",
    "docker.image.load",
    "docker.image.remove",
    "docker.image.prune",
    "service.stack.deploy",
    "service.stack.remove",
    "service.stack.volumes.remove",
    "proxy.nginx.reload",
    "certbot.nginx.issue",
    "certbot.renew",
    "certbot.renewal.ensure",
    "openssl.self_signed_cert.issue",
    "backup.harbor.install",
    "backup.harbor.up",
    "backup.harbor.down",
    "backup.harbor.restart",
    "docker.daemon.insecure_registries.ensure",
    "monitoring.node_exporter.ensure",
    "monitoring.node_exporter.remove",
    "monitoring.node_exporter.status",
    "monitoring.metrics_collector.ensure",
    "monitoring.metrics_collector.remove",
    "monitoring.metrics_collector.status",
    "ddns.dispatcher.ensure",
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


def _configured_value(values, keys):
    for key in keys:
        value = str(values.get(key) or "").strip()
        if value:
            return value
    return ""


def _strip_host(value):
    host = str(value or "").strip()
    if "://" in host:
        host = host.split("://", 1)[1].split("/", 1)[0]
    if "/" in host:
        host = host.split("/", 1)[0]
    if host.count(":") == 1:
        host = host.rsplit(":", 1)[0]
    return host.strip("[]")


def _parse_public_ip(value, record_type="A"):
    for token in str(value or "").replace(",", " ").split():
        try:
            address = ipaddress.ip_address(token.strip())
        except Exception:
            continue
        if record_type == "A" and address.version != 4:
            continue
        if record_type == "AAAA" and address.version != 6:
            continue
        if address.is_global:
            return str(address)
    return ""


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


def node_exporter_image(env=None):
    return runtime_env(env).get("DOCKER_INFRA_NODE_EXPORTER_IMAGE") or DEFAULT_NODE_EXPORTER_IMAGE


def node_metric_collection_interval_seconds(env=None):
    value = runtime_env(env).get("DOCKER_INFRA_NODE_METRIC_COLLECTION_INTERVAL_SECONDS") or DEFAULT_NODE_METRIC_COLLECTION_INTERVAL_SECONDS
    try:
        seconds = int(value)
    except (TypeError, ValueError):
        seconds = int(DEFAULT_NODE_METRIC_COLLECTION_INTERVAL_SECONDS)
    return max(600, min(seconds, 3600))


def node_metric_sample_interval_seconds(env=None):
    value = runtime_env(env).get("DOCKER_INFRA_NODE_METRIC_SAMPLE_INTERVAL_SECONDS") or DEFAULT_NODE_METRIC_SAMPLE_INTERVAL_SECONDS
    try:
        seconds = int(value)
    except (TypeError, ValueError):
        seconds = int(DEFAULT_NODE_METRIC_SAMPLE_INTERVAL_SECONDS)
    return max(1, min(seconds, 60))


def ddns_public_ip_urls(env=None):
    raw = runtime_env(env).get("DOCKER_INFRA_DDNS_PUBLIC_IP_URLS", "")
    urls = [item.strip() for item in raw.split(",") if item.strip()]
    return urls or list(DEFAULT_DDNS_PUBLIC_IP_URLS)


def public_ip_urls(env=None):
    values = runtime_env(env)
    raw = values.get("DOCKER_INFRA_PUBLIC_IP_URLS") or values.get("DOCKER_INFRA_DDNS_PUBLIC_IP_URLS") or ""
    urls = [item.strip() for item in raw.split(",") if item.strip()]
    return urls or list(DEFAULT_DDNS_PUBLIC_IP_URLS)


def public_ip(record_type="A", env=None, lookup=True):
    record_type = str(record_type or "A").upper()
    if record_type not in {"A", "AAAA"}:
        record_type = "A"
    values = runtime_env(env)
    keys = (
        ["DOCKER_INFRA_PUBLIC_IPV6", "DOCKER_INFRA_DDNS_PUBLIC_IPV6"]
        if record_type == "AAAA"
        else [
            "DOCKER_INFRA_PUBLIC_IPV4",
            "DOCKER_INFRA_PUBLIC_IP",
            "DOCKER_INFRA_DDNS_PUBLIC_IPV4",
            "DOCKER_INFRA_DDNS_PUBLIC_IP",
        ]
    )
    configured = _parse_public_ip(_configured_value(values, keys), record_type=record_type)
    if configured:
        return configured
    if lookup is False:
        return ""
    for url in public_ip_urls(env):
        try:
            req = urlrequest.Request(url, headers={"User-Agent": "docker-infra/1.0"})
            with urlrequest.urlopen(req, timeout=5) as response:
                value = _parse_public_ip(response.read().decode("utf-8", errors="replace"), record_type=record_type)
                if value:
                    return value
        except Exception:
            continue
    return ""


def public_dns_address(env=None, record_type="A"):
    return public_ip(record_type=record_type, env=env)


def ddns_state_file(env=None):
    return runtime_env(env).get("DOCKER_INFRA_DDNS_STATE_FILE") or DEFAULT_DDNS_STATE_FILE


def ddns_dispatcher_script_path(env=None):
    return runtime_env(env).get("DOCKER_INFRA_DDNS_DISPATCHER_SCRIPT_PATH") or DEFAULT_DDNS_DISPATCHER_SCRIPT_PATH


def ddns_dispatcher_path(env=None):
    return runtime_env(env).get("DOCKER_INFRA_DDNS_DISPATCHER_PATH") or DEFAULT_DDNS_DISPATCHER_PATH


def ddns_dispatcher_auto_install(env=None):
    return _bool_value(runtime_env(env).get("DOCKER_INFRA_DDNS_DISPATCHER_AUTO_INSTALL"), default=True)


def reporter_base_url(env=None):
    values = runtime_env(env)
    return (values.get("DOCKER_INFRA_REPORTER_BASE_URL") or values.get("DOCKER_INFRA_BASE_URL") or "").rstrip("/")


def reporter_internal_base_url(env=None):
    values = runtime_env(env)
    explicit = values.get("DOCKER_INFRA_REPORTER_INTERNAL_BASE_URL") or values.get("DOCKER_INFRA_INTERNAL_BASE_URL")
    if explicit:
        return str(explicit).rstrip("/")
    host = advertise_address(env)
    if host and host not in {"127.0.0.1", "0.0.0.0", "::1", "localhost"}:
        scheme = values.get("DOCKER_INFRA_REPORTER_SCHEME") or "http"
        port = values.get("DOCKER_INFRA_REPORTER_PORT") or "3001"
        if ":" in host and not host.startswith("[") and host.count(":") >= 2:
            host = f"[{host}]"
        return f"{scheme}://{host}:{port}".rstrip("/")
    return reporter_base_url(env)


def backup_harbor_installer_url(env=None):
    version = backup_harbor_version(env)
    return runtime_env(env).get("DOCKER_INFRA_BACKUP_HARBOR_INSTALLER_URL") or (
        f"https://github.com/goharbor/harbor/releases/download/{version}/harbor-online-installer-{version}.tgz"
    )


def system_assets_dir(env=None):
    return str(Path(data_dir(env)) / "system-assets")


def advertise_address(env=None):
    values = runtime_env(env)
    configured = _configured_value(
        values,
        [
            "DOCKER_INFRA_MASTER_PRIVATE_IP",
            "DOCKER_INFRA_PRIVATE_IP",
            "DOCKER_INFRA_INTERNAL_ADDRESS",
            "DOCKER_INFRA_ADVERTISE_ADDRESS",
        ],
    )
    if configured:
        return _strip_host(configured)
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
