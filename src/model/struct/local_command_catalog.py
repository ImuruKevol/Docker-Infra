import base64
import json
import re
import shlex
import sys


scripts = wiz.model("struct/local_command_scripts")
DEFAULT_TIMEOUT_SECONDS = 10
MAX_TIMEOUT_SECONDS = 1800
MAX_CAPTURE_CHARS = 20000
NETWORK_NAME_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,127}$")
DOMAIN_RE = re.compile(r"^(?=.{1,253}$)([A-Za-z0-9-]{1,63}\.)+[A-Za-z]{2,63}$")
REGISTRY_RE = re.compile(r"^[A-Za-z0-9_.:-]{1,255}$")
SWARM_NODE_RE = re.compile(r"^[A-Za-z0-9_.:-]{1,128}$")
METRICS_COLLECTOR_AGENT_VERSION = "2026-05-13-container-labels-v1"


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


def _docker_network_ensure_command(params):
    network_name = (params or {}).get("network_name") or "docker_infra_bridge"
    driver = str((params or {}).get("driver") or "bridge").strip().lower()
    if NETWORK_NAME_RE.match(network_name) is None:
        raise LocalCommandError(400, "network_name 형식이 올바르지 않습니다.", "INVALID_NETWORK_NAME")
    if driver not in {"bridge", "overlay"}:
        raise LocalCommandError(400, "지원하지 않는 Docker network driver입니다.", "INVALID_NETWORK_DRIVER")
    command = ["docker", "network", "create", "--driver", driver]
    if driver == "overlay":
        command.append("--attachable")
    command.append(network_name)
    return command


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


def _swarm_node_remove_command(params):
    node_id = str((params or {}).get("node_id") or "").strip()
    if SWARM_NODE_RE.match(node_id) is None:
        raise LocalCommandError(400, "swarm node_id 형식이 올바르지 않습니다.", "INVALID_SWARM_NODE_ID")
    return ["docker", "node", "rm", "-f", node_id]


def _container_ids(params):
    ids = (params or {}).get("ids") or []
    if isinstance(ids, list) is False or len(ids) == 0:
        raise LocalCommandError(400, "container ids가 필요합니다.", "CONTAINER_IDS_REQUIRED")
    return [str(item).strip() for item in ids if str(item).strip()]


def _docker_container_start_command(params): return ["docker", "start", *_container_ids(params)]
def _docker_container_stop_command(params): return ["docker", "stop", *_container_ids(params)]
def _docker_container_restart_command(params): return ["docker", "restart", *_container_ids(params)]
def _docker_container_delete_command(params): return ["docker", "rm", "-f", *_container_ids(params)]


def _docker_service_containers_command(params):
    namespace = str((params or {}).get("namespace") or (params or {}).get("stack_name") or "").strip()
    if NETWORK_NAME_RE.match(namespace) is None:
        raise LocalCommandError(400, "service namespace 형식이 올바르지 않습니다.", "INVALID_SERVICE_NAMESPACE")
    return ["docker", "ps", "-a", "--no-trunc", "--filter", f"name={namespace}", "--format", "{{json .}}"]


CONTAINER_FILE_LIST_SCRIPT = r"""
set -eu
base="${1:-/}"
show_hidden="${2:-0}"
limit="${3:-5000}"
[ -d "$base" ] || exit 44
scan_base="${base%/}"
[ -n "$scan_base" ] || scan_base=""
count=0
emit_entry() {
  entry="$1"
  [ -e "$entry" ] || [ -L "$entry" ] || return 0
  name="${entry##*/}"
  if [ "$show_hidden" != "1" ]; then
    case "$name" in .*) return 0 ;; esac
  fi
  count=$((count + 1))
  if [ "$count" -gt "$limit" ]; then
    return 0
  fi
  if [ -d "$entry" ]; then
    kind="folder"
    size="0"
  else
    kind="file"
    size="$(wc -c < "$entry" 2>/dev/null | tr -d ' ' || printf '0')"
  fi
  printf '%s\t%s\t%s\t%s\n' "$name" "$entry" "$kind" "$size"
}
for entry in "$scan_base"/* "$scan_base"/.[!.]* "$scan_base"/..?*; do
  emit_entry "$entry"
done
printf '__DOCKER_INFRA_TOTAL__\t%s\n' "$count"
""".strip()


def _container_id_param(params):
    value = str((params or {}).get("container_id") or "").strip()
    if not value or re.match(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,127}$", value) is None:
        raise LocalCommandError(400, "container_id 형식이 올바르지 않습니다.", "INVALID_CONTAINER_ID")
    return value


def _container_path_param(params, key="path", default="/"):
    value = str((params or {}).get(key) or default).strip() or default
    if "\x00" in value:
        raise LocalCommandError(400, "path 형식이 올바르지 않습니다.", "INVALID_CONTAINER_FILE_PATH")
    return value if value.startswith("/") else f"/{value}"


def _docker_container_file_list_command(params):
    show_hidden = "1" if str((params or {}).get("show_hidden") or "").strip().lower() in {"1", "true", "yes", "on"} else "0"
    try:
        limit = max(100, min(int((params or {}).get("limit") or 5000), 20000))
    except Exception:
        limit = 5000
    return [
        "docker",
        "exec",
        _container_id_param(params),
        "sh",
        "-lc",
        CONTAINER_FILE_LIST_SCRIPT,
        "sh",
        _container_path_param(params),
        show_hidden,
        str(limit),
    ]


def _docker_container_file_read_command(params):
    return [
        "docker",
        "exec",
        _container_id_param(params),
        "sh",
        "-lc",
        'test -f "$1" || exit 44; cat -- "$1"',
        "sh",
        _container_path_param(params),
    ]


def _docker_container_file_download_command(params):
    return [
        "docker",
        "exec",
        _container_id_param(params),
        "sh",
        "-lc",
        'test -f "$1" || exit 44; base64 "$1" | tr -d "\\n"',
        "sh",
        _container_path_param(params),
    ]


def _docker_container_directory_download_command(params):
    script = r"""
set -eu
container_id="$1"
target="$2"
docker exec "$container_id" sh -lc 'test -d "$1"' sh "$target" || exit 44
tmp="$(mktemp "${TMPDIR:-/tmp}/docker-infra-container-dir.XXXXXX.tar")"
trap 'rm -f "$tmp"' EXIT
docker cp "$container_id:$target" - > "$tmp"
gzip -c "$tmp" | base64 | tr -d "\n"
""".strip()
    return [
        "sh",
        "-lc",
        script,
        "sh",
        _container_id_param(params),
        _container_path_param(params),
    ]


def _docker_container_file_write_command(params):
    raw_content = (params or {}).get("content", b"") or b""
    if isinstance(raw_content, str):
        raw_content = raw_content.encode("utf-8")
    payload = base64.b64encode(raw_content).decode("ascii")
    script = (
        'target="$1"\n'
        'parent="${target%/*}"\n'
        '[ "$parent" = "$target" ] && parent="/"\n'
        'mkdir -p "$parent"\n'
        f"cat <<'__DOCKER_INFRA_FILE__' | base64 -d > \"$target\"\n"
        f"{payload}\n"
        "__DOCKER_INFRA_FILE__\n"
    )
    return ["docker", "exec", _container_id_param(params), "sh", "-lc", script, "sh", _container_path_param(params)]


def _docker_container_file_mkdir_command(params):
    return ["docker", "exec", _container_id_param(params), "mkdir", "-p", _container_path_param(params)]


def _docker_container_file_rename_command(params):
    return [
        "docker",
        "exec",
        _container_id_param(params),
        "mv",
        _container_path_param(params),
        _container_path_param(params, "target_path"),
    ]


def _docker_container_file_delete_command(params):
    return ["docker", "exec", _container_id_param(params), "rm", "-rf", _container_path_param(params)]


def _docker_container_file_move_command(params):
    script = 'mkdir -p "$2"; mv "$1" "$3"'
    return [
        "docker",
        "exec",
        _container_id_param(params),
        "sh",
        "-lc",
        script,
        "sh",
        _container_path_param(params),
        _container_path_param(params, "destination"),
        _container_path_param(params, "target_path"),
    ]


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
        f"$SUDO systemctl enable {shlex.quote(service_name)}\n"
        f"$SUDO systemctl start {shlex.quote(service_name)}\n"
        f"$SUDO systemctl is-active --quiet {shlex.quote(service_name)}\n"
        "printf 'Running\n'\n"
        f"$SUDO systemctl --no-pager --full status {shlex.quote(service_name)} | sed -n '1,12p'\n"
    )
    return ["sh", "-lc", script]


def _node_exporter_status_command(params):
    service_name = str((params or {}).get("service_name") or "docker-infra-node-exporter.service").strip()
    unit_name = service_name[:-8] if service_name.endswith(".service") else service_name
    if NETWORK_NAME_RE.match(unit_name) is None:
        raise LocalCommandError(400, "node_exporter service 이름이 올바르지 않습니다.", "INVALID_NODE_EXPORTER_SERVICE")
    script = (
        "set -eu\n"
        "SUDO=''\n"
        "if [ \"$(id -u)\" != '0' ]; then SUDO='sudo -n'; fi\n"
        f"$SUDO systemctl is-active --quiet {shlex.quote(service_name)}\n"
        "printf 'Running\n'\n"
        f"$SUDO systemctl --no-pager --full status {shlex.quote(service_name)} | sed -n '1,12p'\n"
    )
    return ["sh", "-lc", script]


def _node_exporter_remove_command(params):
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
        f"SERVICE_NAME={shlex.quote(service_name)}\n"
        f"CONTAINER_NAME={shlex.quote(container_name)}\n"
        "$SUDO systemctl stop \"$SERVICE_NAME\" >/dev/null 2>&1 || true\n"
        "$SUDO systemctl disable \"$SERVICE_NAME\" >/dev/null 2>&1 || true\n"
        "$SUDO rm -f \"/etc/systemd/system/$SERVICE_NAME\"\n"
        "if command -v docker >/dev/null 2>&1; then $SUDO docker rm -f \"$CONTAINER_NAME\" >/dev/null 2>&1 || true; fi\n"
        "$SUDO systemctl daemon-reload >/dev/null 2>&1 || true\n"
        "printf 'Node exporter removed\\n'\n"
    )
    return ["sh", "-lc", script]


def _collector_param(params, key, error_code):
    value = str((params or {}).get(key) or "").strip()
    if not value:
        raise LocalCommandError(400, f"{key}가 필요합니다.", error_code)
    return value


def _metrics_collector_paths(params):
    service_name = str((params or {}).get("service_name") or "docker-infra-node-metrics.service").strip()
    timer_name = str((params or {}).get("timer_name") or "docker-infra-node-metrics.timer").strip()
    service_unit = service_name[:-8] if service_name.endswith(".service") else service_name
    timer_unit = timer_name[:-6] if timer_name.endswith(".timer") else timer_name
    if NETWORK_NAME_RE.match(service_unit) is None:
        raise LocalCommandError(400, "metrics collector service 이름이 올바르지 않습니다.", "INVALID_METRICS_COLLECTOR_SERVICE")
    if NETWORK_NAME_RE.match(timer_unit) is None:
        raise LocalCommandError(400, "metrics collector timer 이름이 올바르지 않습니다.", "INVALID_METRICS_COLLECTOR_TIMER")
    return {
        "service_name": service_name,
        "timer_name": timer_name,
        "script_path": str((params or {}).get("script_path") or "/usr/local/bin/docker-infra-node-metrics-agent"),
        "env_path": str((params or {}).get("env_path") or "/etc/docker-infra/node-metrics.env"),
        "state_file": str((params or {}).get("state_file") or "/var/lib/docker-infra/node-metrics.prev"),
    }


def _metrics_collector_ensure_command(params):
    node_id = _collector_param(params, "node_id", "METRICS_COLLECTOR_NODE_ID_REQUIRED")
    reporter_token = _collector_param(params, "reporter_token", "METRICS_COLLECTOR_TOKEN_REQUIRED")
    reporter_base_url = _collector_param(params, "reporter_base_url", "METRICS_COLLECTOR_BASE_URL_REQUIRED").rstrip("/")
    if not (reporter_base_url.startswith("http://") or reporter_base_url.startswith("https://")):
        raise LocalCommandError(400, "reporter_base_url은 http(s) URL이어야 합니다.", "INVALID_METRICS_COLLECTOR_BASE_URL")
    interval_seconds = str((params or {}).get("interval_seconds") or 600).strip()
    sample_interval_seconds = str((params or {}).get("sample_interval_seconds") or 1).strip()
    try:
        interval = max(600, min(int(interval_seconds), 3600))
    except Exception:
        raise LocalCommandError(400, "interval_seconds는 정수여야 합니다.", "INVALID_METRICS_COLLECTOR_INTERVAL")
    try:
        sample_interval = max(1, min(int(sample_interval_seconds), 60))
    except Exception:
        raise LocalCommandError(400, "sample_interval_seconds는 정수여야 합니다.", "INVALID_METRICS_COLLECTOR_SAMPLE_INTERVAL")
    timeout = interval + 120
    timer_schedule = f"OnUnitInactiveSec={sample_interval}s\n"
    paths = _metrics_collector_paths(params)
    script = (
        "set -eu\n"
        "SUDO=''\n"
        "if [ \"$(id -u)\" != '0' ]; then SUDO='sudo -n'; fi\n"
        f"SCRIPT_PATH={shlex.quote(paths['script_path'])}\n"
        f"ENV_PATH={shlex.quote(paths['env_path'])}\n"
        f"STATE_FILE={shlex.quote(paths['state_file'])}\n"
        f"SERVICE_NAME={shlex.quote(paths['service_name'])}\n"
        f"TIMER_NAME={shlex.quote(paths['timer_name'])}\n"
        "TMP_SCRIPT=$(mktemp)\n"
        "TMP_ENV=$(mktemp)\n"
        "TMP_SERVICE=$(mktemp)\n"
        "TMP_TIMER=$(mktemp)\n"
        "cleanup() { rm -f \"$TMP_SCRIPT\" \"$TMP_ENV\" \"$TMP_SERVICE\" \"$TMP_TIMER\"; }\n"
        "trap cleanup EXIT\n"
        "cat > \"$TMP_SCRIPT\" <<'PY'\n"
        f"{NODE_METRICS_AGENT_SCRIPT}\n"
        "PY\n"
        "cat > \"$TMP_ENV\" <<EOF\n"
        f"DOCKER_INFRA_NODE_ID={shlex.quote(node_id)}\n"
        f"DOCKER_INFRA_REPORTER_TOKEN={shlex.quote(reporter_token)}\n"
        f"DOCKER_INFRA_REPORTER_BASE_URL={shlex.quote(reporter_base_url)}\n"
        f"DOCKER_INFRA_METRICS_STATE_FILE={shlex.quote(paths['state_file'])}\n"
        f"DOCKER_INFRA_METRICS_INTERVAL_SECONDS={interval}\n"
        f"DOCKER_INFRA_METRICS_WINDOW_SECONDS={interval}\n"
        f"DOCKER_INFRA_METRICS_SAMPLE_SECONDS={sample_interval}\n"
        f"DOCKER_INFRA_METRICS_AGENT_VERSION={shlex.quote(METRICS_COLLECTOR_AGENT_VERSION)}\n"
        "EOF\n"
        "cat > \"$TMP_SERVICE\" <<EOF\n"
        "[Unit]\n"
        "Description=Docker Infra node metrics collector\n"
        "After=network-online.target docker.service\n"
        "Wants=network-online.target\n\n"
        "[Service]\n"
        "Type=oneshot\n"
        f"EnvironmentFile={paths['env_path']}\n"
        f"ExecStart={paths['script_path']}\n"
        f"TimeoutStartSec={timeout}s\n"
        "EOF\n"
        "cat > \"$TMP_TIMER\" <<EOF\n"
        "[Unit]\n"
        f"Description=Run Docker Infra node metrics collector {sample_interval}s samples / {interval}s rollups\n\n"
        "[Timer]\n"
        "OnBootSec=1min\n"
        f"{timer_schedule}"
        "AccuracySec=10s\n"
        "Persistent=true\n"
        f"Unit={paths['service_name']}\n\n"
        "[Install]\n"
        "WantedBy=timers.target\n"
        "EOF\n"
        "$SUDO install -d -m 700 \"$(dirname \"$ENV_PATH\")\"\n"
        "$SUDO install -d -m 700 \"$(dirname \"$STATE_FILE\")\"\n"
        "$SUDO install -m 0755 \"$TMP_SCRIPT\" \"$SCRIPT_PATH\"\n"
        "$SUDO install -m 0600 \"$TMP_ENV\" \"$ENV_PATH\"\n"
        "$SUDO install -m 0644 \"$TMP_SERVICE\" \"/etc/systemd/system/$SERVICE_NAME\"\n"
        "$SUDO install -m 0644 \"$TMP_TIMER\" \"/etc/systemd/system/$TIMER_NAME\"\n"
        "$SUDO systemctl daemon-reload\n"
        "$SUDO systemctl stop \"$TIMER_NAME\" >/dev/null 2>&1 || true\n"
        "$SUDO systemctl enable \"$TIMER_NAME\"\n"
        "$SUDO systemctl start \"$TIMER_NAME\"\n"
        "$SUDO systemctl start --no-block \"$SERVICE_NAME\"\n"
        "$SUDO systemctl is-active --quiet \"$TIMER_NAME\"\n"
        "printf 'Metrics collector timer running\\n'\n"
        "$SUDO systemctl --no-pager --full status \"$TIMER_NAME\" | sed -n '1,12p'\n"
    )
    return ["sh", "-lc", script]


def _metrics_collector_status_command(params):
    paths = _metrics_collector_paths(params)
    expected_interval = str((params or {}).get("interval_seconds") or "").strip()
    expected_sample_interval = str((params or {}).get("sample_interval_seconds") or "").strip()
    expected_agent_version = str((params or {}).get("agent_version") or METRICS_COLLECTOR_AGENT_VERSION).strip()
    script = (
        "set -eu\n"
        "SUDO=''\n"
        "if [ \"$(id -u)\" != '0' ]; then SUDO='sudo -n'; fi\n"
        f"TIMER_NAME={shlex.quote(paths['timer_name'])}\n"
        f"SERVICE_NAME={shlex.quote(paths['service_name'])}\n"
        f"ENV_PATH={shlex.quote(paths['env_path'])}\n"
        f"EXPECTED_INTERVAL={shlex.quote(expected_interval)}\n"
        f"EXPECTED_SAMPLE_INTERVAL={shlex.quote(expected_sample_interval)}\n"
        f"EXPECTED_AGENT_VERSION={shlex.quote(expected_agent_version)}\n"
        "$SUDO systemctl is-active --quiet \"$TIMER_NAME\"\n"
        "if $SUDO systemctl is-failed --quiet \"$SERVICE_NAME\"; then\n"
        "  $SUDO systemctl --no-pager --full status \"$SERVICE_NAME\" | sed -n '1,12p' || true\n"
        "  exit 1\n"
        "fi\n"
        "if [ -n \"$EXPECTED_INTERVAL\" ]; then\n"
        "  CURRENT_INTERVAL=$($SUDO awk -F= '$1==\"DOCKER_INFRA_METRICS_INTERVAL_SECONDS\" { gsub(/[\\\"'\\'' ]/, \"\", $2); print $2 }' \"$ENV_PATH\" 2>/dev/null | tail -n 1)\n"
        "  if [ \"$CURRENT_INTERVAL\" != \"$EXPECTED_INTERVAL\" ]; then\n"
        "    printf 'Metrics collector configuration drift: interval\\n'\n"
        "    exit 1\n"
        "  fi\n"
        "fi\n"
        "if [ -n \"$EXPECTED_SAMPLE_INTERVAL\" ]; then\n"
        "  CURRENT_SAMPLE_INTERVAL=$($SUDO awk -F= '$1==\"DOCKER_INFRA_METRICS_SAMPLE_SECONDS\" { gsub(/[\\\"'\\'' ]/, \"\", $2); print $2 }' \"$ENV_PATH\" 2>/dev/null | tail -n 1)\n"
        "  if [ \"$CURRENT_SAMPLE_INTERVAL\" != \"$EXPECTED_SAMPLE_INTERVAL\" ]; then\n"
        "    printf 'Metrics collector configuration drift: sample interval\\n'\n"
        "    exit 1\n"
        "  fi\n"
        "fi\n"
        "CURRENT_AGENT_VERSION=$($SUDO awk -F= '$1==\"DOCKER_INFRA_METRICS_AGENT_VERSION\" { gsub(/[\\\"'\\'' ]/, \"\", $2); print $2 }' \"$ENV_PATH\" 2>/dev/null | tail -n 1)\n"
        "if [ \"$CURRENT_AGENT_VERSION\" != \"$EXPECTED_AGENT_VERSION\" ]; then\n"
        "  printf 'Metrics collector configuration drift: agent version\\n'\n"
        "  exit 1\n"
        "fi\n"
        "printf 'Metrics collector timer running\\n'\n"
        "$SUDO systemctl --no-pager --full status \"$TIMER_NAME\" | sed -n '1,12p'\n"
        "$SUDO systemctl --no-pager --full status \"$SERVICE_NAME\" | sed -n '1,8p' || true\n"
    )
    return ["sh", "-lc", script]


def _metrics_collector_remove_command(params):
    paths = _metrics_collector_paths(params)
    script = (
        "set -eu\n"
        "SUDO=''\n"
        "if [ \"$(id -u)\" != '0' ]; then SUDO='sudo -n'; fi\n"
        f"SERVICE_NAME={shlex.quote(paths['service_name'])}\n"
        f"TIMER_NAME={shlex.quote(paths['timer_name'])}\n"
        f"SCRIPT_PATH={shlex.quote(paths['script_path'])}\n"
        f"ENV_PATH={shlex.quote(paths['env_path'])}\n"
        f"STATE_FILE={shlex.quote(paths['state_file'])}\n"
        "$SUDO systemctl stop \"$TIMER_NAME\" >/dev/null 2>&1 || true\n"
        "$SUDO systemctl disable \"$TIMER_NAME\" >/dev/null 2>&1 || true\n"
        "$SUDO systemctl stop \"$SERVICE_NAME\" >/dev/null 2>&1 || true\n"
        "$SUDO systemctl disable \"$SERVICE_NAME\" >/dev/null 2>&1 || true\n"
        "$SUDO rm -f \"/etc/systemd/system/$SERVICE_NAME\" \"/etc/systemd/system/$TIMER_NAME\" \"$SCRIPT_PATH\" \"$ENV_PATH\" \"$STATE_FILE\"\n"
        "$SUDO rmdir \"$(dirname \"$ENV_PATH\")\" >/dev/null 2>&1 || true\n"
        "$SUDO rmdir \"$(dirname \"$STATE_FILE\")\" >/dev/null 2>&1 || true\n"
        "$SUDO systemctl daemon-reload >/dev/null 2>&1 || true\n"
        "printf 'Metrics collector removed\\n'\n"
    )
    return ["sh", "-lc", script]


def _docker_image_ref_param(params):
    image_ref = str((params or {}).get("image_ref") or "").strip()
    if not image_ref:
        raise LocalCommandError(400, "image_ref가 필요합니다.", "IMAGE_REF_REQUIRED")
    if any(ch.isspace() for ch in image_ref):
        raise LocalCommandError(400, "image_ref에는 공백을 사용할 수 없습니다.", "INVALID_IMAGE_REF")
    return image_ref


def _docker_image_manifest_inspect_command(params):
    return ["docker", "manifest", "inspect", _docker_image_ref_param(params)]


def _docker_image_remove_command(params):
    image_ref = _docker_image_ref_param(params)
    return ["docker", "image", "rm", "-f", image_ref]


def _docker_image_refs(params):
    refs = (params or {}).get("image_refs") or []
    if isinstance(refs, list) is False or len(refs) == 0:
        raise LocalCommandError(400, "image_refs가 필요합니다.", "IMAGE_REFS_REQUIRED")
    image_refs = [str(item).strip() for item in refs if str(item).strip()]
    if not image_refs:
        raise LocalCommandError(400, "image_refs가 필요합니다.", "IMAGE_REFS_REQUIRED")
    return image_refs


def _docker_image_delete_estimate_command(params):
    return ["python3", "-c", DOCKER_IMAGE_DELETE_ESTIMATE_SCRIPT, json.dumps(_docker_image_refs(params))]


def _docker_prune_action(params):
    action = str((params or {}).get("action") or "image").strip()
    if action != "image":
        raise LocalCommandError(400, "지원하지 않는 이미지 정리 작업입니다.", "INVALID_PRUNE_ACTION")
    return action


def _docker_prune_estimate_command(params):
    return ["python3", "-c", DOCKER_PRUNE_ESTIMATE_SCRIPT, _docker_prune_action(params)]


def _docker_image_prune_command(params):
    return ["docker", "image", "prune", "-a", "-f"]


def _docker_image_load_command(params):
    image_path = str((params or {}).get("path") or "").strip()
    if not image_path:
        raise LocalCommandError(400, "path가 필요합니다.", "IMAGE_LOAD_PATH_REQUIRED")
    return ["docker", "load", "-i", image_path]


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
        return [*command, "ps", "-a", "--format", "json"]
    raise LocalCommandError(400, "지원하지 않는 Harbor command입니다.", "INVALID_BACKUP_HARBOR_COMMAND")


def _backup_harbor_up_command(params):
    return _backup_harbor_compose_command(params, "up")


def _backup_harbor_down_command(params):
    return _backup_harbor_compose_command(params, "down")


def _backup_harbor_restart_command(params):
    return _backup_harbor_compose_command(params, "restart")


def _backup_harbor_ps_command(params):
    return _backup_harbor_compose_command(params, "ps")


def _registry_params(params):
    raw = (params or {}).get("registries")
    if raw is None:
        raw = [(params or {}).get("registry")]
    if isinstance(raw, str):
        raw = [raw]
    if isinstance(raw, list) is False:
        raise LocalCommandError(400, "registries는 list여야 합니다.", "INVALID_REGISTRIES")
    registries = []
    for item in raw:
        registry = str(item or "").strip()
        if not registry:
            continue
        if "://" in registry or "/" in registry or REGISTRY_RE.match(registry) is None:
            raise LocalCommandError(400, "registry 형식이 올바르지 않습니다.", "INVALID_REGISTRY")
        if registry not in registries:
            registries.append(registry)
    if not registries:
        raise LocalCommandError(400, "registry가 필요합니다.", "REGISTRY_REQUIRED")
    return registries


def _docker_daemon_insecure_registries_command(params):
    registries = _registry_params(params)
    script = (
        "set -eu\n"
        f"REGISTRIES_JSON={shlex.quote(json.dumps(registries))}\n"
        "TARGET=/etc/docker/daemon.json\n"
        "SUDO=''\n"
        "if [ \"$(id -u)\" != '0' ]; then\n"
        "  if command -v sudo >/dev/null 2>&1 && sudo -n true >/dev/null 2>&1; then\n"
        "    SUDO='sudo -n'\n"
        "  else\n"
        "    echo 'root or passwordless sudo is required to update Docker daemon settings' >&2\n"
        "    exit 42\n"
        "  fi\n"
        "fi\n"
        "if ! command -v python3 >/dev/null 2>&1; then\n"
        "  echo 'python3 is required to update Docker daemon settings' >&2\n"
        "  exit 43\n"
        "fi\n"
        "TMP_CURRENT=$(mktemp)\n"
        "TMP_NEXT=$(mktemp)\n"
        "cleanup() { rm -f \"$TMP_CURRENT\" \"$TMP_NEXT\"; }\n"
        "trap cleanup EXIT\n"
        "$SUDO mkdir -p /etc/docker\n"
        "if $SUDO test -f \"$TARGET\"; then\n"
        "  $SUDO cat \"$TARGET\" > \"$TMP_CURRENT\"\n"
        "else\n"
        "  printf '{}\\n' > \"$TMP_CURRENT\"\n"
        "fi\n"
        "python3 - \"$TMP_CURRENT\" \"$TMP_NEXT\" \"$REGISTRIES_JSON\" <<'PY'\n"
        "import json\n"
        "import sys\n"
        "current_path, next_path, registries_json = sys.argv[1:4]\n"
        "registries = json.loads(registries_json)\n"
        "try:\n"
        "    with open(current_path, 'r', encoding='utf-8') as handle:\n"
        "        text = handle.read().strip()\n"
        "    data = json.loads(text or '{}')\n"
        "    if not isinstance(data, dict):\n"
        "        data = {}\n"
        "except Exception:\n"
        "    data = {}\n"
        "existing = data.get('insecure-registries')\n"
        "if not isinstance(existing, list):\n"
        "    existing = []\n"
        "merged = []\n"
        "for item in existing + registries:\n"
        "    value = str(item or '').strip()\n"
        "    if value and value not in merged:\n"
        "        merged.append(value)\n"
        "data['insecure-registries'] = merged\n"
        "with open(next_path, 'w', encoding='utf-8') as handle:\n"
        "    json.dump(data, handle, indent=2, sort_keys=True)\n"
        "    handle.write('\\n')\n"
        "print('configured insecure registries: ' + ', '.join(registries))\n"
        "PY\n"
        "if $SUDO test -f \"$TARGET\" && $SUDO cmp -s \"$TMP_NEXT\" \"$TARGET\"; then\n"
        "  echo 'Docker daemon insecure registries already configured'\n"
        "  CHANGED=0\n"
        "else\n"
        "  if $SUDO test -f \"$TARGET\"; then\n"
        "    $SUDO cp \"$TARGET\" \"$TARGET.bak.$(date +%Y%m%d%H%M%S)\"\n"
        "  fi\n"
        "  $SUDO install -m 0644 \"$TMP_NEXT\" \"$TARGET\"\n"
        "  echo 'Docker daemon configuration updated'\n"
        "  CHANGED=1\n"
        "fi\n"
        "if [ \"$CHANGED\" = '1' ]; then\n"
        "  if command -v systemctl >/dev/null 2>&1; then\n"
        "    $SUDO systemctl \"restart\" docker\n"
        "  else\n"
        "    $SUDO service docker restart\n"
        "  fi\n"
        "fi\n"
        "attempt=1\n"
        "while [ \"$attempt\" -le 30 ]; do\n"
        "  if docker info >/dev/null 2>&1; then\n"
        "    echo 'Docker daemon is ready'\n"
        "    exit 0\n"
        "  fi\n"
        "  sleep 2\n"
        "  attempt=$((attempt + 1))\n"
        "done\n"
        "echo 'Docker daemon did not become ready after registry configuration' >&2\n"
        "exit 44\n"
    )
    return ["sh", "-lc", script]


def _ddns_dispatcher_ensure_command(params):
    config_path = str((params or {}).get("config_path") or "/var/lib/docker-infra/data/ddns/dispatcher.json").strip()
    script_path = str((params or {}).get("script_path") or "/usr/local/bin/docker-infra-ddns-update").strip()
    dispatcher_path = str((params or {}).get("dispatcher_path") or "/etc/NetworkManager/dispatcher.d/90-docker-infra-ddns").strip()
    state_file = str((params or {}).get("state_file") or "/var/lib/docker-infra/ddns/last-sent.json").strip()
    script = (
        "set -eu\n"
        "SUDO=''\n"
        "if [ \"$(id -u)\" != '0' ]; then SUDO='sudo -n'; fi\n"
        "command -v python3 >/dev/null 2>&1 || { echo 'python3 is required for docker-infra ddns dispatcher' >&2; exit 43; }\n"
        f"CONFIG_PATH={shlex.quote(config_path)}\n"
        f"SCRIPT_PATH={shlex.quote(script_path)}\n"
        f"DISPATCHER_PATH={shlex.quote(dispatcher_path)}\n"
        f"STATE_FILE={shlex.quote(state_file)}\n"
        "TMP_AGENT=$(mktemp)\n"
        "TMP_DISPATCHER=$(mktemp)\n"
        "cleanup() { rm -f \"$TMP_AGENT\" \"$TMP_DISPATCHER\"; }\n"
        "trap cleanup EXIT\n"
        "cat > \"$TMP_AGENT\" <<'PY'\n"
        f"{DDNS_DISPATCHER_AGENT_SCRIPT}\n"
        "PY\n"
        "cat > \"$TMP_DISPATCHER\" <<EOF\n"
        "#!/bin/sh\n"
        "case \"\\$2\" in\n"
        "  up|dhcp4-change|dhcp6-change|connectivity-change|vpn-up) ;;\n"
        "  *) exit 0 ;;\n"
        "esac\n"
        "DOCKER_INFRA_DDNS_CONFIG=\"$CONFIG_PATH\" \"$SCRIPT_PATH\" --source \"networkmanager:\\$1:\\$2\" >/dev/null 2>&1 &\n"
        "exit 0\n"
        "EOF\n"
        "$SUDO install -d -m 0755 \"$(dirname \"$SCRIPT_PATH\")\"\n"
        "$SUDO install -d -m 0755 \"$(dirname \"$DISPATCHER_PATH\")\"\n"
        "$SUDO install -d -m 0700 \"$(dirname \"$STATE_FILE\")\"\n"
        "$SUDO install -m 0755 \"$TMP_AGENT\" \"$SCRIPT_PATH\"\n"
        "$SUDO install -m 0755 \"$TMP_DISPATCHER\" \"$DISPATCHER_PATH\"\n"
        "if [ ! -r \"$CONFIG_PATH\" ]; then\n"
        "  echo 'DDNS dispatcher config file is not readable yet; Docker Infra will write it after DDNS registrations exist.'\n"
        "fi\n"
        "if command -v systemctl >/dev/null 2>&1 && systemctl list-unit-files NetworkManager.service >/dev/null 2>&1; then\n"
        "  $SUDO systemctl reload NetworkManager.service >/dev/null 2>&1 || true\n"
        "fi\n"
        "echo 'DDNS NetworkManager dispatcher installed'\n"
    )
    return ["sh", "-lc", script]


def _service_stack_deploy_command(params):
    compose_path = _path_param(params, "compose_path")
    stack_name = _stack_name_param(params)
    return ["docker", "stack", "deploy", "--with-registry-auth", "--prune", "-c", compose_path, stack_name]


def _service_stack_update_image_command(params):
    stack_name = _stack_name_param(params)
    service_name = _compose_service_param(params)
    image_ref = _docker_image_ref_param(params)
    swarm_service_name = str((params or {}).get("swarm_service_name") or f"{stack_name}_{service_name}").strip()
    if NETWORK_NAME_RE.match(swarm_service_name) is None:
        raise LocalCommandError(400, "swarm service name 형식이 올바르지 않습니다.", "INVALID_SWARM_SERVICE_NAME")
    force = str((params or {}).get("force") or (params or {}).get("force_pull") or "").strip().lower() in {"1", "true", "yes", "on"}
    command = ["docker", "service", "update", "--with-registry-auth", "--image", image_ref]
    if force:
        command.append("--force")
    command.append(swarm_service_name)
    return command


def _service_compose_up_command(params):
    compose_path = _path_param(params, "compose_path")
    stack_name = _stack_name_param(params)
    return ["docker", "compose", "-p", stack_name, "-f", compose_path, "up", "-d", "--remove-orphans"]


def _compose_service_param(params):
    service_name = str((params or {}).get("service_name") or (params or {}).get("compose_service") or "").strip()
    if not service_name:
        raise LocalCommandError(400, "compose service name은 필수입니다.", "COMPOSE_SERVICE_NAME_REQUIRED")
    return service_name


def _service_compose_up_service_command(params):
    compose_path = _path_param(params, "compose_path")
    stack_name = _stack_name_param(params)
    service_name = _compose_service_param(params)
    force_pull = str((params or {}).get("force_pull") or "").strip().lower() in {"1", "true", "yes", "on"}
    script = (
        "set -eu\n"
        f"STACK={shlex.quote(stack_name)}\n"
        f"FILE={shlex.quote(compose_path)}\n"
        f"SERVICE={shlex.quote(service_name)}\n"
    )
    if force_pull:
        script += 'docker compose -p "$STACK" -f "$FILE" pull "$SERVICE"\n'
        script += 'docker compose -p "$STACK" -f "$FILE" up -d --no-deps --force-recreate "$SERVICE"\n'
    else:
        script += 'docker compose -p "$STACK" -f "$FILE" up -d --no-deps "$SERVICE"\n'
    return ["sh", "-lc", script]


def _service_compose_down_command(params):
    compose_path = _path_param(params, "compose_path")
    stack_name = _stack_name_param(params)
    command = ["docker", "compose", "-p", stack_name, "-f", compose_path, "down"]
    if (params or {}).get("remove_volumes") is True:
        command.append("--volumes")
    return command


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
    return ["docker", "stack", "ps", stack_name, "--filter", "desired-state=running", "--format", "{{json .}}"]


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


def _certbot_renew_command(params):
    cert_name = str((params or {}).get("cert_name") or (params or {}).get("domain") or "").strip().lower()
    if DOMAIN_RE.match(cert_name) is None or "*" in cert_name:
        raise LocalCommandError(400, "cert_name 형식이 올바르지 않습니다.", "INVALID_CERTBOT_CERT_NAME")
    command = ["certbot", "renew", "--cert-name", cert_name, "--non-interactive"]
    if (params or {}).get("force") is not False:
        command.append("--force-renewal")
    if (params or {}).get("dry_run"):
        command.append("--dry-run")
    return command


def _certbot_renewal_status_command(params):
    script = r"""
import glob
import json
import shutil
import subprocess
from pathlib import Path


def run(argv):
    try:
        completed = subprocess.run(argv, capture_output=True, text=True, timeout=5, check=False)
        return {"status": "ok" if completed.returncode == 0 else "error", "exit_code": completed.returncode, "stdout": completed.stdout or "", "stderr": completed.stderr or ""}
    except Exception as exc:
        return {"status": "error", "exit_code": None, "stdout": "", "stderr": str(exc)}


def unit_status(unit):
    return {
        "active": run(["systemctl", "is-active", unit])["stdout"].strip(),
        "enabled": run(["systemctl", "is-enabled", unit])["stdout"].strip(),
    }


certbot_path = shutil.which("certbot") or ""
systemd_available = shutil.which("systemctl") is not None
timer_lines = []
units = {}
if systemd_available:
    timers = run(["systemctl", "list-timers", "--all", "--no-pager", "--plain"])
    for line in (timers.get("stdout") or "").splitlines():
        lowered = line.lower()
        if "certbot" in lowered or "letsencrypt" in lowered or "docker-infra-certbot-renew" in lowered:
            timer_lines.append(" ".join(line.split()))
    for unit in ["certbot.timer", "snap.certbot.renew.timer", "docker-infra-certbot-renew.timer"]:
        units[unit] = unit_status(unit)

cron_entries = []
for path in [Path("/etc/crontab"), *[Path(item) for item in glob.glob("/etc/cron.d/*")]]:
    try:
        text = path.read_text(encoding="utf-8", errors="ignore")
    except Exception:
        continue
    for line in text.splitlines():
        clean = line.strip()
        if clean and not clean.startswith("#") and "certbot" in clean and "renew" in clean:
            cron_entries.append({"path": str(path), "line": clean})

configured = bool(cron_entries or timer_lines or any(
    item.get("active") == "active" or item.get("enabled") == "enabled"
    for item in units.values()
))
print(json.dumps({
    "installed": bool(certbot_path),
    "certbot_path": certbot_path,
    "configured": configured,
    "method": "systemd" if timer_lines or any(item.get("active") == "active" or item.get("enabled") == "enabled" for item in units.values()) else ("cron" if cron_entries else "none"),
    "schedule": "systemd timer 또는 cron이 certbot renew를 주기적으로 실행합니다." if configured else "자동 갱신 작업이 감지되지 않았습니다.",
    "systemd_available": systemd_available,
    "timers": timer_lines[:20],
    "units": units,
    "cron": cron_entries[:20],
}, ensure_ascii=False))
""".strip()
    return [sys.executable, "-c", script]


def _certbot_renewal_ensure_command(params):
    service_name = "docker-infra-certbot-renew.service"
    timer_name = "docker-infra-certbot-renew.timer"
    script = (
        "set -eu\n"
        "SUDO=''\n"
        "if [ \"$(id -u)\" != '0' ]; then SUDO='sudo -n'; fi\n"
        "CERTBOT_BIN=$(command -v certbot || true)\n"
        "if [ -z \"$CERTBOT_BIN\" ]; then echo 'certbot command not found' >&2; exit 44; fi\n"
        "NGINX_BIN=$(command -v nginx || true)\n"
        "HOOK=''\n"
        "if [ -n \"$NGINX_BIN\" ]; then HOOK=\" --deploy-hook \\\"$NGINX_BIN -s reload\\\"\"; fi\n"
        "if command -v systemctl >/dev/null 2>&1 && systemctl list-timers --all --no-pager >/dev/null 2>&1; then\n"
        "  if systemctl list-timers --all --no-pager 2>/dev/null | grep -Ei 'certbot|letsencrypt' >/dev/null 2>&1; then\n"
        "    echo 'certbot renewal timer already configured'\n"
        "    systemctl list-timers --all --no-pager 2>/dev/null | grep -Ei 'certbot|letsencrypt' || true\n"
        "    exit 0\n"
        "  fi\n"
        f"  SERVICE_TMP=/tmp/{shlex.quote(service_name)}\n"
        f"  TIMER_TMP=/tmp/{shlex.quote(timer_name)}\n"
        "  cat > \"$SERVICE_TMP\" <<EOF\n"
        "[Unit]\n"
        "Description=Docker Infra Certbot renewal\n"
        "After=network-online.target nginx.service\n"
        "Wants=network-online.target\n"
        "\n"
        "[Service]\n"
        "Type=oneshot\n"
        "ExecStart=/bin/sh -lc '$CERTBOT_BIN renew -q$HOOK'\n"
        "EOF\n"
        "  cat > \"$TIMER_TMP\" <<EOF\n"
        "[Unit]\n"
        "Description=Run Docker Infra Certbot renewal twice daily\n"
        "\n"
        "[Timer]\n"
        "OnCalendar=*-*-* 00,12:00:00\n"
        "RandomizedDelaySec=1h\n"
        "Persistent=true\n"
        "\n"
        "[Install]\n"
        "WantedBy=timers.target\n"
        "EOF\n"
        f"  $SUDO mv \"$SERVICE_TMP\" /etc/systemd/system/{shlex.quote(service_name)}\n"
        f"  $SUDO mv \"$TIMER_TMP\" /etc/systemd/system/{shlex.quote(timer_name)}\n"
        "  $SUDO systemctl daemon-reload\n"
        f"  $SUDO systemctl enable {shlex.quote(timer_name)}\n"
        f"  $SUDO systemctl start {shlex.quote(timer_name)}\n"
        f"  systemctl list-timers --all --no-pager | grep {shlex.quote(timer_name)} || true\n"
        "  exit 0\n"
        "fi\n"
        "CRON_TMP=/tmp/docker-infra-certbot-renew\n"
        "if [ -n \"$NGINX_BIN\" ]; then\n"
        "  printf \"7 0,12 * * * root %s renew -q --deploy-hook '%s -s reload'\\n\" \"$CERTBOT_BIN\" \"$NGINX_BIN\" > \"$CRON_TMP\"\n"
        "else\n"
        "  printf \"7 0,12 * * * root %s renew -q\\n\" \"$CERTBOT_BIN\" > \"$CRON_TMP\"\n"
        "fi\n"
        "if [ -f /etc/cron.d/docker-infra-certbot-renew ] && grep -q 'certbot.*renew' /etc/cron.d/docker-infra-certbot-renew; then\n"
        "  echo 'certbot renewal cron already configured'\n"
        "  cat /etc/cron.d/docker-infra-certbot-renew\n"
        "  exit 0\n"
        "fi\n"
        "$SUDO mv \"$CRON_TMP\" /etc/cron.d/docker-infra-certbot-renew\n"
        "$SUDO chmod 0644 /etc/cron.d/docker-infra-certbot-renew\n"
        "cat /etc/cron.d/docker-infra-certbot-renew\n"
    )
    return ["sh", "-lc", script]


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
NODE_METRICS_AGENT_SCRIPT = scripts.NODE_METRICS_AGENT_SCRIPT
DOCKER_IMAGE_USAGE_SCRIPT = scripts.DOCKER_IMAGE_USAGE_SCRIPT
DOCKER_IMAGE_STORAGE_SCRIPT = scripts.DOCKER_IMAGE_STORAGE_SCRIPT
DOCKER_IMAGE_DELETE_ESTIMATE_SCRIPT = scripts.DOCKER_IMAGE_DELETE_ESTIMATE_SCRIPT
DOCKER_PRUNE_ESTIMATE_SCRIPT = scripts.DOCKER_PRUNE_ESTIMATE_SCRIPT
DDNS_DISPATCHER_AGENT_SCRIPT = getattr(scripts, "DDNS_DISPATCHER_AGENT_SCRIPT", "")


COMMAND_SPECS = {
    "docker.version": {"category": "docker", "argv": ["docker", "version", "--format", "{{json .}}"]},
    "docker.info": {"category": "docker", "argv": ["docker", "info", "--format", "{{json .}}"]},
    "docker.containers": {"category": "docker", "argv": ["docker", "ps", "-a", "--no-trunc", "--format", "{{json .}}"]},
    "docker.containers.service": {"category": "docker", "factory": _docker_service_containers_command},
    "docker.images": {"category": "docker", "argv": ["docker", "image", "ls", "--digests", "--no-trunc", "--format", "{{json .}}"]},
    "docker.images.usage": {"category": "docker", "argv": ["sh", "-lc", DOCKER_IMAGE_USAGE_SCRIPT]},
    "docker.images.storage": {"category": "docker", "argv": ["python3", "-c", DOCKER_IMAGE_STORAGE_SCRIPT]},
    "docker.images.delete_estimate": {"category": "docker", "factory": _docker_image_delete_estimate_command, "default_timeout_seconds": 45},
    "docker.image.manifest.inspect": {"category": "docker", "factory": _docker_image_manifest_inspect_command, "default_timeout_seconds": 45},
    "docker.prune.estimate": {"category": "docker", "factory": _docker_prune_estimate_command, "default_timeout_seconds": 20},
    "docker.network.inspect": {"category": "docker", "factory": _inspect_network_command},
    "docker.network.ensure": {"category": "docker", "factory": _docker_network_ensure_command, "destructive": True},
    "docker.image.prune": {"category": "docker", "factory": _docker_image_prune_command, "destructive": True, "default_timeout_seconds": 300},
    "docker.image.load": {"category": "docker", "factory": _docker_image_load_command, "destructive": True, "default_timeout_seconds": 1800},
    "docker.container.start": {"category": "docker", "factory": _docker_container_start_command, "destructive": True},
    "docker.container.stop": {"category": "docker", "factory": _docker_container_stop_command, "destructive": True},
    "docker.container.restart": {"category": "docker", "factory": _docker_container_restart_command, "destructive": True},
    "docker.container.delete": {"category": "docker", "factory": _docker_container_delete_command, "destructive": True},
    "docker.container.file.list": {"category": "docker", "factory": _docker_container_file_list_command, "default_timeout_seconds": 20},
    "docker.container.file.read": {"category": "docker", "factory": _docker_container_file_read_command, "default_timeout_seconds": 20},
    "docker.container.file.download": {"category": "docker", "factory": _docker_container_file_download_command, "default_timeout_seconds": 30},
    "docker.container.directory.download": {"category": "docker", "factory": _docker_container_directory_download_command, "default_timeout_seconds": 120},
    "docker.container.file.write": {"category": "docker", "factory": _docker_container_file_write_command, "destructive": True, "default_timeout_seconds": 60},
    "docker.container.file.mkdir": {"category": "docker", "factory": _docker_container_file_mkdir_command, "destructive": True, "default_timeout_seconds": 20},
    "docker.container.file.rename": {"category": "docker", "factory": _docker_container_file_rename_command, "destructive": True, "default_timeout_seconds": 20},
    "docker.container.file.delete": {"category": "docker", "factory": _docker_container_file_delete_command, "destructive": True, "default_timeout_seconds": 30},
    "docker.container.file.move": {"category": "docker", "factory": _docker_container_file_move_command, "destructive": True, "default_timeout_seconds": 30},
    "docker.image.remove": {"category": "docker", "factory": _docker_image_remove_command, "destructive": True},
    "service.stack.deploy": {"category": "service", "factory": _service_stack_deploy_command, "destructive": True, "default_timeout_seconds": 300},
    "service.stack.update.image": {"category": "service", "factory": _service_stack_update_image_command, "destructive": True, "default_timeout_seconds": 300},
    "service.compose.up": {"category": "service", "factory": _service_compose_up_command, "destructive": True, "default_timeout_seconds": 300},
    "service.compose.up.service": {"category": "service", "factory": _service_compose_up_service_command, "destructive": True, "default_timeout_seconds": 300},
    "service.compose.down": {"category": "service", "factory": _service_compose_down_command, "destructive": True, "default_timeout_seconds": 120},
    "service.stack.remove": {"category": "service", "factory": _service_stack_remove_command, "destructive": True, "default_timeout_seconds": 120},
    "service.stack.volumes.remove": {"category": "service", "factory": _service_stack_volumes_remove_command, "destructive": True, "default_timeout_seconds": 90},
    "service.stack.services": {"category": "service", "factory": _service_stack_services_command, "default_timeout_seconds": 20},
    "service.stack.ps": {"category": "service", "factory": _service_stack_ps_command, "default_timeout_seconds": 20},
    "certbot.nginx.issue": {"category": "certbot", "factory": _certbot_nginx_issue_command, "destructive": True, "default_timeout_seconds": 300},
    "certbot.renew": {"category": "certbot", "factory": _certbot_renew_command, "destructive": True, "default_timeout_seconds": 300},
    "certbot.renewal.status": {"category": "certbot", "factory": _certbot_renewal_status_command, "default_timeout_seconds": 20},
    "certbot.renewal.ensure": {"category": "certbot", "factory": _certbot_renewal_ensure_command, "destructive": True, "default_timeout_seconds": 120},
    "openssl.self_signed_cert.issue": {"category": "openssl", "factory": _openssl_self_signed_cert_command, "destructive": True, "default_timeout_seconds": 30},
    "backup.harbor.install": {"category": "backup", "factory": _backup_harbor_install_command, "destructive": True, "default_timeout_seconds": 1800},
    "backup.harbor.up": {"category": "backup", "factory": _backup_harbor_up_command, "destructive": True, "default_timeout_seconds": 300},
    "backup.harbor.down": {"category": "backup", "factory": _backup_harbor_down_command, "destructive": True, "default_timeout_seconds": 300},
    "backup.harbor.restart": {"category": "backup", "factory": _backup_harbor_restart_command, "destructive": True, "default_timeout_seconds": 300},
    "backup.harbor.ps": {"category": "backup", "factory": _backup_harbor_ps_command},
    "docker.daemon.insecure_registries.ensure": {"category": "docker", "factory": _docker_daemon_insecure_registries_command, "destructive": True, "default_timeout_seconds": 180},
    "monitoring.node_exporter.ensure": {"category": "monitoring", "factory": _node_exporter_ensure_command, "destructive": True, "default_timeout_seconds": 120},
    "monitoring.node_exporter.remove": {"category": "monitoring", "factory": _node_exporter_remove_command, "destructive": True, "default_timeout_seconds": 60},
    "monitoring.node_exporter.status": {"category": "monitoring", "factory": _node_exporter_status_command, "default_timeout_seconds": 20},
    "monitoring.metrics_collector.ensure": {"category": "monitoring", "factory": _metrics_collector_ensure_command, "destructive": True, "default_timeout_seconds": 120},
    "monitoring.metrics_collector.remove": {"category": "monitoring", "factory": _metrics_collector_remove_command, "destructive": True, "default_timeout_seconds": 60},
    "monitoring.metrics_collector.status": {"category": "monitoring", "factory": _metrics_collector_status_command, "default_timeout_seconds": 20},
    "ddns.dispatcher.ensure": {"category": "ddns", "factory": _ddns_dispatcher_ensure_command, "destructive": True, "default_timeout_seconds": 60},
    "system.metrics": {"category": "system", "argv": ["sh", "-lc", SYSTEM_METRICS_SCRIPT]},
    "filesystem.list": {"category": "filesystem", "factory": _filesystem_list_command},
    "filesystem.read": {"category": "filesystem", "factory": _filesystem_read_command},
    "swarm.info": {"category": "swarm", "argv": ["docker", "info", "--format", "{{json .Swarm}}"]},
    "swarm.nodes": {"category": "swarm", "argv": ["docker", "node", "ls", "--format", "{{json .}}"]},
    "swarm.nodes.inspect": {"category": "swarm", "argv": ["sh", "-lc", "docker node inspect $(docker node ls -q)"]},
    "swarm.init": {"category": "swarm", "factory": _swarm_init_command, "destructive": True},
    "swarm.node.remove": {"category": "swarm", "factory": _swarm_node_remove_command, "destructive": True},
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
    NODE_METRICS_AGENT_SCRIPT = NODE_METRICS_AGENT_SCRIPT
    DDNS_DISPATCHER_AGENT_SCRIPT = DDNS_DISPATCHER_AGENT_SCRIPT
    DOCKER_IMAGE_USAGE_SCRIPT = DOCKER_IMAGE_USAGE_SCRIPT
    DOCKER_IMAGE_STORAGE_SCRIPT = DOCKER_IMAGE_STORAGE_SCRIPT
    DOCKER_IMAGE_DELETE_ESTIMATE_SCRIPT = DOCKER_IMAGE_DELETE_ESTIMATE_SCRIPT
    DOCKER_PRUNE_ESTIMATE_SCRIPT = DOCKER_PRUNE_ESTIMATE_SCRIPT
    METRICS_COLLECTOR_AGENT_VERSION = METRICS_COLLECTOR_AGENT_VERSION
    LocalCommandError = LocalCommandError
    COMMAND_SPECS = COMMAND_SPECS
    docker_daemon_insecure_registries_command = staticmethod(_docker_daemon_insecure_registries_command)


Model = LocalCommandCatalog()
