import json
import os
import tarfile
import urllib.request
from pathlib import Path


config = wiz.config("docker_infra")


def paths(data_path):
    root = Path(data_path).expanduser()
    return {
        "root": root,
        "data": root / "data",
        "logs": root / "logs",
        "installer_root": root / "installer",
        "archive": root / "installer" / "harbor-online-installer.tgz",
        "compose": root / "installer" / "harbor" / "docker-compose.yml",
        "harbor_yml": root / "installer" / "harbor" / "harbor.yml",
    }


def harbor_url(env=None):
    ports = config.backup_harbor_ports(env)
    return f"http://127.0.0.1:{ports['http']}"


def _yaml_string(value):
    return json.dumps(str(value), ensure_ascii=False)


def _harbor_version(env=None):
    return str(config.backup_harbor_version(env) or "").strip().lstrip("v") or "2.15.0"


def _harbor_hostname(env=None):
    configured = ""
    try:
        configured = config.runtime_env(env).get("DOCKER_INFRA_BACKUP_HARBOR_HOSTNAME") or ""
    except Exception:
        configured = ""
    hostname = str(configured or config.advertise_address(env) or "").strip()
    if "://" in hostname:
        hostname = hostname.split("://", 1)[1].split("/", 1)[0]
    if hostname.count(":") == 1:
        hostname = hostname.split(":", 1)[0]
    if hostname in {"", "127.0.0.1", "0.0.0.0", "::1"}:
        return "localhost"
    return hostname


def write_harbor_yml(data_path, admin_password, database_password, env=None):
    ports = config.backup_harbor_ports(env)
    version = _harbor_version(env)
    resolved = paths(data_path)
    for key in ["data", "logs", "installer_root"]:
        resolved[key].mkdir(parents=True, exist_ok=True)
    resolved["harbor_yml"].parent.mkdir(parents=True, exist_ok=True)
    content = f"""
hostname: {_yaml_string(_harbor_hostname(env))}
external_url: {_yaml_string(harbor_url(env))}

http:
  port: {ports['http']}

harbor_admin_password: {_yaml_string(admin_password)}

database:
  password: {_yaml_string(database_password)}
  max_idle_conns: 100
  max_open_conns: 900
  conn_max_lifetime: 5m
  conn_max_idle_time: 0

data_volume: {resolved['data']}

trivy:
  ignore_unfixed: false
  skip_update: false
  skip_java_db_update: false
  db_repository: ghcr.io/aquasecurity/trivy-db
  java_db_repository: ghcr.io/aquasecurity/trivy-java-db
  offline_scan: false
  security_check: vuln
  insecure: false
  timeout: 5m0s

jobservice:
  max_job_workers: 10
  max_job_duration_hours: 24
  job_loggers:
    - STD_OUTPUT
    - FILE
  logger_sweeper_duration: 1

notification:
  webhook_job_max_retry: 3
  webhook_job_http_client_timeout: 3

chart:
  absolute_url: disabled

log:
  level: info
  local:
    rotate_count: 50
    rotate_size: 200M
    location: {resolved['logs']}

_version: {version}

proxy:
  http_proxy:
  https_proxy:
  no_proxy: 127.0.0.1,localhost,.local,.internal
  components:
    - core
    - jobservice
    - trivy

upload_purging:
  enabled: true
  age: 168h
  interval: 24h
  dryrun: false

cache:
  enabled: false
  expire_hours: 24
"""
    resolved["harbor_yml"].write_text(content.strip() + "\n", encoding="utf-8")
    os.chmod(resolved["harbor_yml"], 0o600)
    return str(resolved["harbor_yml"])


def ensure_installer(data_path, env=None):
    resolved = paths(data_path)
    installer_dir = resolved["compose"].parent
    if (installer_dir / "install.sh").is_file():
        return str(installer_dir)

    resolved["installer_root"].mkdir(parents=True, exist_ok=True)
    if not resolved["archive"].is_file():
        urllib.request.urlretrieve(config.backup_harbor_installer_url(env), resolved["archive"])
    with tarfile.open(resolved["archive"], "r:gz") as archive:
        archive.extractall(resolved["installer_root"], filter="data")
    return str(installer_dir)


class BackupSystemResources:
    paths = staticmethod(paths)
    harbor_url = staticmethod(harbor_url)
    write_harbor_yml = staticmethod(write_harbor_yml)
    ensure_installer = staticmethod(ensure_installer)


Model = BackupSystemResources()
