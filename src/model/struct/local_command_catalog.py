import re
import shlex
import sys


scripts = wiz.model("struct/local_command_scripts")
DEFAULT_TIMEOUT_SECONDS = 10
MAX_TIMEOUT_SECONDS = 1800
MAX_CAPTURE_CHARS = 20000
NETWORK_NAME_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,127}$")
DOMAIN_RE = re.compile(r"^(?=.{1,253}$)([A-Za-z0-9-]{1,63}\.)+[A-Za-z]{2,63}$")


class LocalCommandError(Exception):
    def __init__(self, status_code, message, error_code, **extra):
        super().__init__(message)
        self.status_code = status_code
        self.message = message
        self.error_code = error_code
        self.extra = extra


def _diagnostic_success_command(params):
    return [sys.executable, "-c", "print('docker-infra local executor ok')"]


def _diagnostic_failure_command(params):
    return [
        sys.executable,
        "-c",
        "import sys; print('diagnostic stderr', file=sys.stderr); sys.exit(42)",
    ]


def _diagnostic_timeout_command(params): return [sys.executable, "-c", "import time; time.sleep(2)"]


def _overlay_network_command(params):
    network_name = (params or {}).get("network_name") or "docker_infra_overlay"
    if NETWORK_NAME_RE.match(network_name) is None:
        raise LocalCommandError(400, "network_name 형식이 올바르지 않습니다.", "INVALID_NETWORK_NAME")
    return ["docker", "network", "create", "--driver", "overlay", "--attachable", network_name]


def _inspect_network_command(params):
    network_name = (params or {}).get("network_name") or "docker_infra_overlay"
    if NETWORK_NAME_RE.match(network_name) is None:
        raise LocalCommandError(400, "network_name 형식이 올바르지 않습니다.", "INVALID_NETWORK_NAME")
    return ["docker", "network", "inspect", network_name, "--format", "{{json .}}"]


def _swarm_init_command(params):
    command = ["docker", "swarm", "init"]
    advertise_addr = (params or {}).get("advertise_addr")
    if advertise_addr:
        command.extend(["--advertise-addr", str(advertise_addr)])
    return command


def _container_ids(params):
    ids = (params or {}).get("ids") or []
    if isinstance(ids, list) is False or len(ids) == 0:
        raise LocalCommandError(400, "container ids가 필요합니다.", "CONTAINER_IDS_REQUIRED")
    return [str(item).strip() for item in ids if str(item).strip()]


def _docker_container_start_command(params): return ["docker", "start", *_container_ids(params)]
def _docker_container_stop_command(params): return ["docker", "stop", *_container_ids(params)]
def _docker_container_restart_command(params): return ["docker", "restart", *_container_ids(params)]
def _docker_container_delete_command(params): return ["docker", "rm", "-f", *_container_ids(params)]


def _node_exporter_ensure_command(params):
    image = str((params or {}).get("image") or "quay.io/prometheus/node-exporter:v1.8.2").strip()
    if not image or any(char.isspace() for char in image):
        raise LocalCommandError(400, "node_exporter image가 필요합니다.", "NODE_EXPORTER_IMAGE_REQUIRED")
    container_name = str((params or {}).get("container_name") or "docker-infra-node-exporter").strip()
    if NETWORK_NAME_RE.match(container_name) is None:
        raise LocalCommandError(400, "node_exporter container 이름이 올바르지 않습니다.", "INVALID_NODE_EXPORTER_CONTAINER")
    service_name = str((params or {}).get("service_name") or "docker-infra-node-exporter.service").strip()
    unit_name = service_name[:-8] if service_name.endswith(".service") else service_name
    if NETWORK_NAME_RE.match(unit_name) is None:
        raise LocalCommandError(400, "node_exporter service 이름이 올바르지 않습니다.", "INVALID_NODE_EXPORTER_SERVICE")
    script = (
        "set -eu\n"
        "SUDO=''\n"
        "if [ \"$(id -u)\" != '0' ]; then SUDO='sudo -n'; fi\n"
        "DOCKER_BIN=$(command -v docker)\n"
        f"UNIT=/etc/systemd/system/{shlex.quote(service_name)}\n"
        f"cat > /tmp/{shlex.quote(service_name)} <<EOF\n"
        "[Unit]\n"
        "Description=Docker Infra node exporter\n"
        "After=docker.service network-online.target\n"
        "Wants=docker.service network-online.target\n\n"
        "[Service]\n"
        "Restart=always\n"
        "RestartSec=5\n"
        f"ExecStartPre=-${{DOCKER_BIN}} rm -f {container_name}\n"
        f"ExecStart=${{DOCKER_BIN}} run --rm --name {container_name} --pid=host --net=host -v /:/host:ro,rslave {image} --path.rootfs=/host\n"
        f"ExecStop=-${{DOCKER_BIN}} rm -f {container_name}\n\n"
        "[Install]\n"
        "WantedBy=multi-user.target\n"
        "EOF\n"
        f"$SUDO mv /tmp/{shlex.quote(service_name)} \"$UNIT\"\n"
        "$SUDO systemctl daemon-reload\n"
        f"$SUDO systemctl enable --now {shlex.quote(service_name)}\n"
        f"$SUDO systemctl restart {shlex.quote(service_name)}\n"
        f"$SUDO systemctl is-active --quiet {shlex.quote(service_name)}\n"
        f"$SUDO systemctl --no-pager --full status {shlex.quote(service_name)} | sed -n '1,12p'\n"
    )
    return ["sh", "-lc", script]


def _docker_image_remove_command(params):
    image_ref = str((params or {}).get("image_ref") or "").strip()
    if not image_ref:
        raise LocalCommandError(400, "image_ref가 필요합니다.", "IMAGE_REF_REQUIRED")
    return ["docker", "image", "rm", "-f", image_ref]


def _stack_name_param(params):
    stack_name = str((params or {}).get("stack_name") or "").strip()
    if NETWORK_NAME_RE.match(stack_name) is None:
        raise LocalCommandError(400, "stack_name 형식이 올바르지 않습니다.", "INVALID_STACK_NAME")
    return stack_name


def _path_param(params, name):
    value = str((params or {}).get(name) or "").strip()
    if not value:
        raise LocalCommandError(400, f"{name}이 필요합니다.", "PATH_PARAM_REQUIRED")
    return value


def _backup_harbor_install_command(params):
    installer_dir = _path_param(params, "installer_dir")
    return ["sh", "-lc", f"cd {shlex.quote(installer_dir)} && ./install.sh"]


def _backup_harbor_compose_command(params, action):
    compose_path = _path_param(params, "compose_path")
    command = ["docker", "compose", "-f", compose_path]
    if action == "up":
        return [*command, "up", "-d"]
    if action == "down":
        return [*command, "down"]
    if action == "restart":
        return [*command, "restart"]
    if action == "ps":
        return [*command, "ps", "--format", "json"]
    raise LocalCommandError(400, "지원하지 않는 Harbor command입니다.", "INVALID_BACKUP_HARBOR_COMMAND")


def _backup_harbor_up_command(params):
    return _backup_harbor_compose_command(params, "up")


def _backup_harbor_down_command(params):
    return _backup_harbor_compose_command(params, "down")


def _backup_harbor_restart_command(params):
    return _backup_harbor_compose_command(params, "restart")


def _backup_harbor_ps_command(params):
    return _backup_harbor_compose_command(params, "ps")


def _service_stack_deploy_command(params):
    compose_path = _path_param(params, "compose_path")
    stack_name = _stack_name_param(params)
    return ["docker", "stack", "deploy", "--with-registry-auth", "-c", compose_path, stack_name]


def _service_stack_remove_command(params):
    stack_name = _stack_name_param(params)
    return ["docker", "stack", "rm", stack_name]


def _service_stack_volumes_remove_command(params):
    stack_name = _stack_name_param(params)
    script = (
        "set -eu\n"
        f"STACK={shlex.quote(stack_name)}\n"
        "tmp=$(mktemp)\n"
        "trap 'rm -f \"$tmp\" \"${tmp}.uniq\"' EXIT\n"
        "docker volume ls -q --filter \"label=com.docker.stack.namespace=${STACK}\" 2>/dev/null >> \"$tmp\" || true\n"
        "docker volume ls -q 2>/dev/null | awk -v prefix=\"${STACK}_\" 'index($0, prefix) == 1 {print $0}' >> \"$tmp\" || true\n"
        "sort -u \"$tmp\" | awk 'NF' > \"${tmp}.uniq\"\n"
        "mv \"${tmp}.uniq\" \"$tmp\"\n"
        "if [ ! -s \"$tmp\" ]; then echo 'no stack volumes found'; exit 0; fi\n"
        "echo 'stack volumes:'\n"
        "cat \"$tmp\"\n"
        "attempt=1\n"
        "while [ \"$attempt\" -le 30 ]; do\n"
        "  failed=0\n"
        "  while IFS= read -r volume; do\n"
        "    [ -n \"$volume\" ] || continue\n"
        "    docker volume inspect \"$volume\" >/dev/null 2>&1 || continue\n"
        "    docker volume rm -f \"$volume\" || failed=1\n"
        "  done < \"$tmp\"\n"
        "  if [ \"$failed\" -eq 0 ]; then exit 0; fi\n"
        "  if [ \"$attempt\" -eq 30 ]; then exit 1; fi\n"
        "  sleep 2\n"
        "  attempt=$((attempt + 1))\n"
        "done\n"
    )
    return ["sh", "-lc", script]


def _service_stack_services_command(params):
    stack_name = _stack_name_param(params)
    return ["docker", "stack", "services", stack_name, "--format", "{{json .}}"]


def _service_stack_ps_command(params):
    stack_name = _stack_name_param(params)
    return ["docker", "stack", "ps", stack_name, "--no-trunc", "--format", "{{json .}}"]


def _certbot_nginx_issue_command(params):
    domain = str((params or {}).get("domain") or "").strip().lower()
    email = str((params or {}).get("email") or "").strip()
    if DOMAIN_RE.match(domain) is None or "*" in domain:
        raise LocalCommandError(400, "domain 형식이 올바르지 않습니다.", "INVALID_CERTBOT_DOMAIN")
    command = [
        "certbot",
        "certonly",
        "--nginx",
        "-d",
        domain,
        "--non-interactive",
        "--agree-tos",
        "--keep-until-expiring",
    ]
    if email:
        command.extend(["--email", email])
    else:
        command.append("--register-unsafely-without-email")
    if (params or {}).get("staging"):
        command.append("--staging")
    return command


def _openssl_self_signed_cert_command(params):
    domain = str((params or {}).get("domain") or "").strip().lower()
    cert_path = _path_param(params, "cert_path")
    key_path = _path_param(params, "key_path")
    try:
        days = int((params or {}).get("days") or 7)
    except (TypeError, ValueError):
        days = 7
    days = max(1, min(days, 365))
    if DOMAIN_RE.match(domain) is None or "*" in domain:
        raise LocalCommandError(400, "domain 형식이 올바르지 않습니다.", "INVALID_SELF_SIGNED_DOMAIN")
    return [
        "openssl",
        "req",
        "-x509",
        "-nodes",
        "-newkey",
        "rsa:2048",
        "-days",
        str(days),
        "-keyout",
        key_path,
        "-out",
        cert_path,
        "-subj",
        f"/CN={domain}",
        "-addext",
        f"subjectAltName=DNS:{domain}",
    ]


def _filesystem_target(params, required_type=None):
    target = str((params or {}).get("path") or "/").strip() or "/"
    script = (
        "from pathlib import Path; import sys; "
        "path = Path(sys.argv[1]).expanduser(); "
        "ok = path.is_dir() if sys.argv[2] == 'dir' else (path.is_file() if sys.argv[2] == 'file' else path.exists()); "
        "sys.exit(0 if ok else 44)"
    )
    return [sys.executable, "-c", script, target, required_type or "any"], target


def _filesystem_list_command(params):
    argv, target = _filesystem_target(params, "dir")
    show_hidden = "1" if str((params or {}).get("show_hidden") or "").strip().lower() in {"1", "true", "yes", "on"} else "0"
    try:
        limit = max(100, min(int((params or {}).get("limit") or 5000), 20000))
    except Exception:
        limit = 5000
    script = """
import json
import os
import sys
import time

root = os.path.abspath(os.path.expanduser(sys.argv[1]))
show_hidden = sys.argv[2] == "1"
limit = int(sys.argv[3] or "5000")
started = time.monotonic()
items = []
total_count = 0
with os.scandir(root) as iterator:
    for child in iterator:
        if not show_hidden and child.name.startswith("."):
            continue
        total_count += 1
        try:
            is_dir = child.is_dir(follow_symlinks=False)
            size = 0 if is_dir else child.stat(follow_symlinks=False).st_size
        except OSError:
            is_dir = False
            size = 0
        items.append({
            "name": child.name,
            "path": os.path.join(root, child.name) if root != "/" else "/" + child.name,
            "type": "folder" if is_dir else "file",
            "size": size,
        })
items.sort(key=lambda item: (item["type"] != "folder", item["name"].lower()))
truncated = len(items) > limit
if truncated:
    items = items[:limit]
print(json.dumps({"path": root, "items": items, "total_count": total_count, "truncated": truncated, "limit": limit, "duration_ms": int((time.monotonic() - started) * 1000)}, ensure_ascii=False))
""".strip()
    return [sys.executable, "-c", script, target, show_hidden, str(limit)]


def _filesystem_read_command(params):
    argv, target = _filesystem_target(params, "file")
    script = (
        "from pathlib import Path; import sys; "
        "path = Path(sys.argv[1]).expanduser().resolve(); "
        "print(path.read_text(encoding='utf-8'))"
    )
    return [sys.executable, "-c", script, target]


SYSTEM_METRICS_SCRIPT = scripts.SYSTEM_METRICS_SCRIPT
DOCKER_IMAGE_USAGE_SCRIPT = scripts.DOCKER_IMAGE_USAGE_SCRIPT


COMMAND_SPECS = {
    "docker.version": {"category": "docker", "argv": ["docker", "version", "--format", "{{json .}}"]},
    "docker.info": {"category": "docker", "argv": ["docker", "info", "--format", "{{json .}}"]},
    "docker.containers": {"category": "docker", "argv": ["docker", "ps", "-a", "--no-trunc", "--format", "{{json .}}"]},
    "docker.images": {"category": "docker", "argv": ["docker", "image", "ls", "--digests", "--no-trunc", "--format", "{{json .}}"]},
    "docker.images.usage": {"category": "docker", "argv": ["sh", "-lc", DOCKER_IMAGE_USAGE_SCRIPT]},
    "docker.container.start": {"category": "docker", "factory": _docker_container_start_command, "destructive": True},
    "docker.container.stop": {"category": "docker", "factory": _docker_container_stop_command, "destructive": True},
    "docker.container.restart": {"category": "docker", "factory": _docker_container_restart_command, "destructive": True},
    "docker.container.delete": {"category": "docker", "factory": _docker_container_delete_command, "destructive": True},
    "docker.image.remove": {"category": "docker", "factory": _docker_image_remove_command, "destructive": True},
    "service.stack.deploy": {"category": "service", "factory": _service_stack_deploy_command, "destructive": True, "default_timeout_seconds": 300},
    "service.stack.remove": {"category": "service", "factory": _service_stack_remove_command, "destructive": True, "default_timeout_seconds": 120},
    "service.stack.volumes.remove": {"category": "service", "factory": _service_stack_volumes_remove_command, "destructive": True, "default_timeout_seconds": 90},
    "service.stack.services": {"category": "service", "factory": _service_stack_services_command, "default_timeout_seconds": 20},
    "service.stack.ps": {"category": "service", "factory": _service_stack_ps_command, "default_timeout_seconds": 20},
    "certbot.nginx.issue": {"category": "certbot", "factory": _certbot_nginx_issue_command, "destructive": True, "default_timeout_seconds": 300},
    "openssl.self_signed_cert.issue": {"category": "openssl", "factory": _openssl_self_signed_cert_command, "destructive": True, "default_timeout_seconds": 30},
    "backup.harbor.install": {"category": "backup", "factory": _backup_harbor_install_command, "destructive": True, "default_timeout_seconds": 1800},
    "backup.harbor.up": {"category": "backup", "factory": _backup_harbor_up_command, "destructive": True, "default_timeout_seconds": 300},
    "backup.harbor.down": {"category": "backup", "factory": _backup_harbor_down_command, "destructive": True, "default_timeout_seconds": 300},
    "backup.harbor.restart": {"category": "backup", "factory": _backup_harbor_restart_command, "destructive": True, "default_timeout_seconds": 300},
    "backup.harbor.ps": {"category": "backup", "factory": _backup_harbor_ps_command},
    "monitoring.node_exporter.ensure": {"category": "monitoring", "factory": _node_exporter_ensure_command, "destructive": True, "default_timeout_seconds": 120},
    "system.metrics": {"category": "system", "argv": ["sh", "-lc", SYSTEM_METRICS_SCRIPT]},
    "filesystem.list": {"category": "filesystem", "factory": _filesystem_list_command},
    "filesystem.read": {"category": "filesystem", "factory": _filesystem_read_command},
    "swarm.info": {"category": "swarm", "argv": ["docker", "info", "--format", "{{json .Swarm}}"]},
    "swarm.nodes": {"category": "swarm", "argv": ["docker", "node", "ls", "--format", "{{json .}}"]},
    "swarm.nodes.inspect": {"category": "swarm", "argv": ["sh", "-lc", "docker node inspect $(docker node ls -q)"]},
    "swarm.init": {"category": "swarm", "factory": _swarm_init_command, "destructive": True},
    "swarm.join-token.worker": {"category": "swarm", "argv": ["docker", "swarm", "join-token", "-q", "worker"]},
    "swarm.join-token.manager": {"category": "swarm", "argv": ["docker", "swarm", "join-token", "-q", "manager"]},
    "swarm.network.inspect": {"category": "swarm", "factory": _inspect_network_command},
    "swarm.network.ensure": {"category": "swarm", "factory": _overlay_network_command, "destructive": True},
    "proxy.nginx.version": {"category": "proxy", "argv": ["nginx", "-v"]},
    "proxy.nginx.configtest": {"category": "proxy", "argv": ["nginx", "-t"]},
    "proxy.nginx.reload": {"category": "proxy", "argv": ["nginx", "-s", "reload"], "destructive": True},
    "diagnostic.success": {"category": "diagnostic", "factory": _diagnostic_success_command},
    "diagnostic.failure": {"category": "diagnostic", "factory": _diagnostic_failure_command},
    "diagnostic.timeout": {"category": "diagnostic", "factory": _diagnostic_timeout_command, "default_timeout_seconds": 1},
}


class LocalCommandCatalog:
    DEFAULT_TIMEOUT_SECONDS = DEFAULT_TIMEOUT_SECONDS
    MAX_TIMEOUT_SECONDS = MAX_TIMEOUT_SECONDS
    MAX_CAPTURE_CHARS = MAX_CAPTURE_CHARS
    SYSTEM_METRICS_SCRIPT = SYSTEM_METRICS_SCRIPT
    LocalCommandError = LocalCommandError
    COMMAND_SPECS = COMMAND_SPECS


Model = LocalCommandCatalog()
