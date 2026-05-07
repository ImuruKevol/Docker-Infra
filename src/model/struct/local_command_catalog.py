import re
import sys


DEFAULT_TIMEOUT_SECONDS = 10
MAX_TIMEOUT_SECONDS = 60
MAX_CAPTURE_CHARS = 20000
NETWORK_NAME_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,127}$")


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


def _diagnostic_timeout_command(params):
    return [sys.executable, "-c", "import time; time.sleep(2)"]


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


def _docker_container_start_command(params):
    return ["docker", "start", *_container_ids(params)]


def _docker_container_stop_command(params):
    return ["docker", "stop", *_container_ids(params)]


def _docker_container_restart_command(params):
    return ["docker", "restart", *_container_ids(params)]


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
    script = (
        "import json, os, sys; "
        "from pathlib import Path; "
        "root = Path(sys.argv[1]).expanduser().resolve(); "
        "items = []; "
        "children = sorted(root.iterdir(), key=lambda item: (item.is_file(), item.name.lower())); "
        "items = [{"
        "'name': child.name, "
        "'path': str(child), "
        "'type': 'folder' if child.is_dir() else 'file', "
        "'size': 0 if child.is_dir() else child.stat().st_size"
        "} for child in children]; "
        "print(json.dumps({'path': str(root), 'items': items}, ensure_ascii=False))"
    )
    return [sys.executable, "-c", script, target]


def _filesystem_read_command(params):
    argv, target = _filesystem_target(params, "file")
    script = (
        "from pathlib import Path; import sys; "
        "path = Path(sys.argv[1]).expanduser().resolve(); "
        "print(path.read_text(encoding='utf-8'))"
    )
    return [sys.executable, "-c", script, target]


SYSTEM_METRICS_SCRIPT = r"""
read cpu user nice system idle iowait irq softirq steal rest < /proc/stat
total1=$((user + nice + system + idle + iowait + irq + softirq + steal))
idle1=$((idle + iowait))
sleep 1
read cpu user nice system idle iowait irq softirq steal rest < /proc/stat
total2=$((user + nice + system + idle + iowait + irq + softirq + steal))
idle2=$((idle + iowait))
total_delta=$((total2 - total1))
idle_delta=$((idle2 - idle1))
cpu_percent=$(awk -v total="$total_delta" -v idle="$idle_delta" 'BEGIN { if (total <= 0) print "0.0"; else printf "%.2f", ((total - idle) * 100 / total) }')
mem_total=$(awk '/MemTotal:/ {printf "%.0f", $2 * 1024}' /proc/meminfo)
mem_available=$(awk '/MemAvailable:/ {printf "%.0f", $2 * 1024}' /proc/meminfo)
mem_used=$((mem_total - mem_available))
mem_percent=$(awk -v used="$mem_used" -v total="$mem_total" 'BEGIN { if (total <= 0) print "0.0"; else printf "%.2f", (used * 100 / total) }')
storage_json=$(df -Pk / | awk 'NR==2 { gsub("%", "", $5); printf "\"total\":%d,\"used\":%d,\"available\":%d,\"used_percent\":%.2f", $2 * 1024, $3 * 1024, $4 * 1024, $5 }')
printf '{"cpu_percent":%s,"memory":{"total":%s,"used":%s,"available":%s,"used_percent":%s},"storage":{%s}}\n' "$cpu_percent" "$mem_total" "$mem_used" "$mem_available" "$mem_percent" "$storage_json"
"""


COMMAND_SPECS = {
    "docker.version": {"category": "docker", "argv": ["docker", "version", "--format", "{{json .}}"]},
    "docker.info": {"category": "docker", "argv": ["docker", "info", "--format", "{{json .}}"]},
    "docker.containers": {"category": "docker", "argv": ["docker", "ps", "-a", "--format", "{{json .}}"]},
    "docker.container.start": {"category": "docker", "factory": _docker_container_start_command, "destructive": True},
    "docker.container.stop": {"category": "docker", "factory": _docker_container_stop_command, "destructive": True},
    "docker.container.restart": {"category": "docker", "factory": _docker_container_restart_command, "destructive": True},
    "system.metrics": {"category": "system", "argv": ["sh", "-lc", SYSTEM_METRICS_SCRIPT]},
    "filesystem.list": {"category": "filesystem", "factory": _filesystem_list_command},
    "filesystem.read": {"category": "filesystem", "factory": _filesystem_read_command},
    "swarm.info": {"category": "swarm", "argv": ["docker", "info", "--format", "{{json .Swarm}}"]},
    "swarm.nodes": {"category": "swarm", "argv": ["docker", "node", "ls", "--format", "{{json .}}"]},
    "swarm.init": {"category": "swarm", "factory": _swarm_init_command, "destructive": True},
    "swarm.join-token.worker": {"category": "swarm", "argv": ["docker", "swarm", "join-token", "-q", "worker"]},
    "swarm.join-token.manager": {"category": "swarm", "argv": ["docker", "swarm", "join-token", "-q", "manager"]},
    "swarm.network.inspect": {"category": "swarm", "factory": _inspect_network_command},
    "swarm.network.ensure": {"category": "swarm", "factory": _overlay_network_command, "destructive": True},
    "proxy.nginx.version": {"category": "proxy", "argv": ["nginx", "-v"]},
    "proxy.nginx.configtest": {"category": "proxy", "argv": ["nginx", "-t"]},
    "proxy.nginx.reload": {"category": "proxy", "argv": ["nginx", "-s", "reload"], "destructive": True},
    "proxy.apache2.version": {"category": "proxy", "argv": ["apache2", "-v"]},
    "proxy.apachectl.version": {"category": "proxy", "argv": ["apachectl", "-v"]},
    "proxy.apachectl.configtest": {"category": "proxy", "argv": ["apachectl", "configtest"]},
    "proxy.apachectl.reload": {"category": "proxy", "argv": ["apachectl", "graceful"], "destructive": True},
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
