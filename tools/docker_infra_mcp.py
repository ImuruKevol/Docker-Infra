#!/usr/bin/env python3
import json
import os
import re
import shlex
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path


MAX_CAPTURE_CHARS = 20000
DEFAULT_TIMEOUT_SECONDS = int(os.environ.get("DOCKER_INFRA_MCP_TIMEOUT_SECONDS") or "30")
MCP_CONTRACT_URI = "docker-infra://mcp/contract"
PERMISSION_MODE = "agent_full_control_except_critical_destruction"
CRITICAL_SYSTEM_RE = re.compile(
    r"(\bshutdown\b|\breboot\b|\bpoweroff\b|\bhalt\b|\bmkfs(?:\.[\w-]+)?\b|\bwipefs\b|\bfdisk\b|\bparted\b|\bdd\b[^\n;|&]*\bof=)",
    re.I,
)
RM_RECURSIVE_RE = re.compile(r"\brm\s+(?P<flags>-[^\n;|&\s]*r[^\n;|&\s]*)\s+(?P<targets>[^\n;|&]+)", re.I)
SELF_RESOURCE_RE = re.compile(r"(docker[-_]?infra|/root/docker-infra|/etc/docker-infra|/var/lib/docker-infra)", re.I)
DOCKER_SELF_RE = re.compile(
    r"\bdocker\b[^\n;|&]*(?:\b(stop|restart|kill|rm|down)\b|\bservice\s+rm\b|\bstack\s+rm\b)[^\n;|&]*(docker[-_]?infra|season[-_]?wiz|\bwiz\b)",
    re.I,
)
DOCKER_COMPOSE_VOLUME_DOWN_RE = re.compile(
    r"\b(?:docker\s+compose|docker-compose)\b(?=[^\n;|&]*\bdown\b)(?=[^\n;|&]*(?:--volumes?\b|-v\b))",
    re.I,
)
DOCKER_COMPOSE_VOLUME_RM_RE = re.compile(
    r"\b(?:docker\s+compose|docker-compose)\b(?=[^\n;|&]*\brm\b)(?=[^\n;|&]*(?:--volumes?\b|-v\b))",
    re.I,
)
DOCKER_VOLUME_DELETE_RE = re.compile(r"\bdocker\s+volume\s+(?:rm|remove|prune)\b", re.I)
DOCKER_SYSTEM_PRUNE_VOLUMES_RE = re.compile(
    r"\bdocker\s+system\s+prune\b(?=[^\n;|&]*(?:--volumes?\b))",
    re.I,
)
SYSTEMCTL_SELF_RE = re.compile(r"\bsystemctl\s+(stop|disable|mask)\s+(docker[-_]?infra|wiz|season-wiz)\b", re.I)
OS_CRITICAL_RM_PATHS = {
    "/",
    "/bin",
    "/boot",
    "/dev",
    "/etc",
    "/lib",
    "/lib64",
    "/proc",
    "/sbin",
    "/sys",
    "/usr",
    "/var/lib/docker",
}
CONTAINER_ID_RE = re.compile(r"^[A-Za-z0-9_.:-]{3,128}$")


def trim(value, limit=MAX_CAPTURE_CHARS):
    text = "" if value is None else str(value)
    if len(text) <= limit:
        return text
    return text[:limit] + "\n[truncated]"


def load_context():
    path = os.environ.get("DOCKER_INFRA_MCP_CONTEXT_FILE")
    if path and Path(path).exists():
        return json.loads(Path(path).read_text(encoding="utf-8"))
    raw = os.environ.get("DOCKER_INFRA_MCP_CONTEXT_JSON") or "{}"
    return json.loads(raw)


CONTEXT = load_context()
MESSAGE_FRAMING = "header"


def public_node(node):
    swarm_connected = bool(str(node.get("swarm_node_id") or "").strip())
    deployment_mode = "swarm" if swarm_connected else "compose"
    return {
        "id": node.get("id"),
        "name": node.get("name"),
        "host": node.get("host"),
        "role": node.get("role"),
        "status": node.get("status"),
        "swarm_node_id": node.get("swarm_node_id"),
        "swarm_connected": swarm_connected,
        "deployment_mode": deployment_mode,
        "network": node.get("network") or ("docker_infra_overlay" if swarm_connected else "docker_infra_bridge"),
        "is_local_master": node.get("is_local_master"),
        "ssh_port": node.get("ssh_port"),
        "ssh_configured": bool((node.get("ssh") or {}).get("username") and (node.get("ssh") or {}).get("key_file")),
    }


def public_context():
    return {
        "workspace_root": CONTEXT.get("workspace_root"),
        "project_root": CONTEXT.get("project_root"),
        "runtime_values": CONTEXT.get("runtime_values") or {},
        "mcp_contract": mcp_contract(),
        "placement": CONTEXT.get("placement"),
        "domain_zones": CONTEXT.get("domain_zones") or [],
        "ddns_endpoints": CONTEXT.get("ddns_endpoints") or [],
        "ai_permission_scope": CONTEXT.get("ai_permission_scope") or {},
        "ai_request_summary": CONTEXT.get("ai_request_summary") or {},
        "request_context_keys": CONTEXT.get("request_context_keys") or [],
        "mcp_enabled_tools": CONTEXT.get("mcp_enabled_tools") or [],
        "allowed_probe_hosts": CONTEXT.get("allowed_probe_hosts") or [],
        "servers": [public_node(node) for node in CONTEXT.get("nodes") or []],
    }


def _normalized_absolute_path(value):
    text = str(value or "").strip().strip("'\"")
    if not text or text.startswith("-"):
        return ""
    try:
        return str(Path(text).expanduser().resolve(strict=False))
    except Exception:
        return text


def protected_docker_infra_exact_paths():
    roots = [
        CONTEXT.get("workspace_root"),
        CONTEXT.get("project_root"),
        "/root/docker-infra",
        "/root/docker-infra/project/main",
    ]
    return sorted({_normalized_absolute_path(item) for item in roots if _normalized_absolute_path(item)})


def protected_docker_infra_paths():
    roots = [*protected_docker_infra_exact_paths(), "/etc/docker-infra", "/var/lib/docker-infra"]
    core_children = []
    for root in roots:
        normalized = _normalized_absolute_path(root)
        if not normalized:
            continue
        core_children.append(normalized)
        if normalized.endswith("/project/main"):
            core_children.extend(
                [
                    f"{normalized}/src",
                    f"{normalized}/config",
                    f"{normalized}/tools",
                ]
            )
    return sorted({item for item in core_children if item})


def _is_path_or_child(path, root):
    if not path or not root:
        return False
    if path == root:
        return True
    return path.startswith(root.rstrip("/") + "/")


def critical_rm_target(target):
    path = _normalized_absolute_path(target)
    if not path:
        return ""
    if path in {"/", "/*"}:
        return "root filesystem"
    for root in OS_CRITICAL_RM_PATHS:
        if root == "/" and path != "/":
            continue
        if _is_path_or_child(path, root):
            return f"OS critical path {root}"
    for root in protected_docker_infra_exact_paths():
        if path == root:
            return f"Docker Infra protected path {root}"
    for root in protected_docker_infra_paths():
        if root in protected_docker_infra_exact_paths():
            continue
        if _is_path_or_child(path, root):
            return f"Docker Infra protected path {root}"
    if SELF_RESOURCE_RE.search(path):
        return "Docker Infra protected resource"
    return ""


def critical_command_violation(command):
    command = str(command or "")
    if CRITICAL_SYSTEM_RE.search(command):
        return "OS critical command"
    if SYSTEMCTL_SELF_RE.search(command):
        return "Docker Infra control service operation"
    if DOCKER_SELF_RE.search(command):
        return "Docker Infra control container or stack operation"
    for match in RM_RECURSIVE_RE.finditer(command):
        try:
            parts = shlex.split(match.group("targets"))
        except Exception:
            parts = match.group("targets").split()
        for target in parts:
            reason = critical_rm_target(target)
            if reason:
                return reason
    reason = persistent_volume_destruction_violation(command)
    if reason:
        return reason
    return ""


def persistent_volume_destruction_allowed():
    for key in ["ai_permission_scope", "mcp_guidance", "terminal_actions"]:
        value = CONTEXT.get(key)
        if not isinstance(value, dict):
            continue
        if (
            value.get("allow_volume_destruction") is True
            or value.get("allow_persistent_volume_delete") is True
            or value.get("allow_compose_volume_delete") is True
        ):
            return True
    return False


def persistent_volume_destruction_violation(command):
    if persistent_volume_destruction_allowed():
        return ""
    patterns = [
        ("docker compose down --volumes", DOCKER_COMPOSE_VOLUME_DOWN_RE),
        ("docker compose rm --volumes", DOCKER_COMPOSE_VOLUME_RM_RE),
        ("docker volume rm/prune", DOCKER_VOLUME_DELETE_RE),
        ("docker system prune --volumes", DOCKER_SYSTEM_PRUNE_VOLUMES_RE),
    ]
    for label, pattern in patterns:
        if pattern.search(str(command or "")):
            return "Persistent Docker volume deletion is blocked by Docker Infra MCP policy: %s" % label
    return ""


def node_by_id(node_id):
    for node in CONTEXT.get("nodes") or []:
        if str(node.get("id") or "") == str(node_id or ""):
            return node
    raise ValueError("registered server not found")


def shell_result(command, timeout_seconds=None):
    started = time.monotonic()
    try:
        completed = subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=int(timeout_seconds or DEFAULT_TIMEOUT_SECONDS),
            check=False,
        )
        return {
            "command": command,
            "command_display": shlex.join(command),
            "status": "ok" if completed.returncode == 0 else "error",
            "exit_code": completed.returncode,
            "stdout": trim(completed.stdout),
            "stderr": trim(completed.stderr),
            "duration_ms": int((time.monotonic() - started) * 1000),
        }
    except subprocess.TimeoutExpired as exc:
        return {
            "command": command,
            "command_display": shlex.join(command),
            "status": "timeout",
            "exit_code": None,
            "stdout": trim(exc.stdout),
            "stderr": trim(exc.stderr or "command timed out"),
            "duration_ms": int((time.monotonic() - started) * 1000),
        }
    except FileNotFoundError as exc:
        return {
            "command": command,
            "command_display": shlex.join(command),
            "status": "missing",
            "exit_code": None,
            "stdout": "",
            "stderr": str(exc),
            "duration_ms": int((time.monotonic() - started) * 1000),
        }


def assert_safe_command(command):
    reason = critical_command_violation(command)
    if reason:
        raise ValueError("critical command is blocked by Docker Infra MCP policy: %s" % reason)


def normalize_host(value):
    return str(value or "").strip().strip("[]").lower()


def allowed_probe_hosts():
    hosts = {normalize_host(item) for item in CONTEXT.get("allowed_probe_hosts") or [] if normalize_host(item)}
    for node in CONTEXT.get("nodes") or []:
        host = normalize_host(node.get("host"))
        if host:
            hosts.add(host)
    return hosts


def assert_allowed_probe_host(host):
    normalized = normalize_host(host)
    if not normalized:
        raise ValueError("host is required")
    allowed = allowed_probe_hosts()
    if not allowed:
        raise ValueError("no probe hosts are allowed for this AI request")
    if normalized not in allowed:
        raise ValueError("probe host is not allowed for this AI request")
    return normalized


def ssh_argv(node, command):
    ssh = node.get("ssh") or {}
    username = ssh.get("username")
    key_file = ssh.get("key_file")
    host = node.get("host")
    if not host:
        raise ValueError("server host is missing")
    if not username or not key_file:
        raise ValueError("server ssh credential is not configured")
    argv = [
        "ssh",
        "-o",
        "BatchMode=yes",
        "-o",
        "StrictHostKeyChecking=accept-new",
        "-o",
        "LogLevel=ERROR",
        "-i",
        str(key_file),
    ]
    if node.get("ssh_port"):
        argv.extend(["-p", str(node.get("ssh_port"))])
    argv.extend([f"{username}@{host}", "sh", "-lc", command])
    return argv


def run_on_node(node, command, timeout_seconds=None):
    if node.get("is_local_master") or node.get("role") == "local_master" or node.get("name") == "local-master":
        return shell_result(["sh", "-lc", command], timeout_seconds=timeout_seconds)
    return shell_result(ssh_argv(node, command), timeout_seconds=timeout_seconds)


def tool_docker_search(arguments):
    query = str((arguments or {}).get("query") or "").strip()
    if not query:
        raise ValueError("query is required")
    limit = max(1, min(int((arguments or {}).get("limit") or 10), 25))
    result = shell_result(["docker", "search", "--limit", str(limit), "--format", "json", query], timeout_seconds=20)
    rows = []
    if result["status"] == "ok":
        for line in result["stdout"].splitlines():
            try:
                rows.append(json.loads(line))
            except Exception:
                pass
    return {"query": query, "limit": limit, "items": rows, "raw": result}


def tool_infra_context(_arguments):
    return public_context()


def tool_docker_image_check(arguments):
    image_ref = str((arguments or {}).get("image_ref") or "").strip()
    if not image_ref:
        raise ValueError("image_ref is required")
    local = shell_result(["docker", "image", "inspect", image_ref], timeout_seconds=8)
    manifest = shell_result(["docker", "manifest", "inspect", image_ref], timeout_seconds=25)
    return {
        "image_ref": image_ref,
        "exists": local["status"] == "ok" or manifest["status"] == "ok",
        "local": {
            "status": local["status"],
            "exit_code": local["exit_code"],
            "stderr": local["stderr"],
        },
        "manifest": {
            "status": manifest["status"],
            "exit_code": manifest["exit_code"],
            "stderr": manifest["stderr"],
        },
    }


def tool_server_list(_arguments):
    return {"servers": [public_node(node) for node in CONTEXT.get("nodes") or []]}


def port_check_script(ports):
    return (
        "import json,socket,sys\n"
        "ports=json.loads(sys.argv[1])\n"
        "rows=[]\n"
        "for raw in ports:\n"
        "    p=int(raw)\n"
        "    s=socket.socket(socket.AF_INET,socket.SOCK_STREAM)\n"
        "    s.setsockopt(socket.SOL_SOCKET,socket.SO_REUSEADDR,1)\n"
        "    available=True\n"
        "    error=''\n"
        "    try:\n"
        "        s.bind(('0.0.0.0',p))\n"
        "    except OSError as exc:\n"
        "        available=False\n"
        "        error=str(exc)\n"
        "    finally:\n"
        "        s.close()\n"
        "    rows.append({'port':p,'available':available,'error':error})\n"
        "print(json.dumps(rows))\n"
    )


def tool_server_port_check(arguments):
    arguments = arguments or {}
    node = node_by_id(arguments.get("node_id"))
    raw_ports = arguments.get("ports") or []
    if not isinstance(raw_ports, list):
        raise ValueError("ports must be an array")
    ports = []
    for raw in raw_ports[:50]:
        try:
            port = int(raw)
        except Exception:
            continue
        if 1 <= port <= 65535:
            ports.append(port)
    if not ports:
        raise ValueError("at least one valid port is required")
    timeout = max(3, min(int(arguments.get("timeout_seconds") or DEFAULT_TIMEOUT_SECONDS), 120))
    command = "python3 -c %s %s" % (shlex.quote(port_check_script(ports)), shlex.quote(json.dumps(ports)))
    result = run_on_node(node, command, timeout_seconds=timeout)
    parsed = []
    if result.get("status") == "ok":
        try:
            parsed = json.loads(result.get("stdout") or "[]")
        except Exception:
            parsed = []
    return {"server": public_node(node), "ports": ports, "items": parsed, "raw": result}


def tool_container_logs(arguments):
    arguments = arguments or {}
    node = node_by_id(arguments.get("node_id"))
    container_id = str(arguments.get("container_id") or "").strip()
    if not container_id:
        raise ValueError("container_id is required")
    tail = max(20, min(int(arguments.get("tail") or 160), 1000))
    command = "docker logs --tail %s %s 2>&1" % (tail, shlex.quote(container_id))
    result = run_on_node(node, command, timeout_seconds=max(5, min(int(arguments.get("timeout_seconds") or 30), 120)))
    return {"server": public_node(node), "container_id": container_id, "tail": tail, "result": result}


def tool_container_action(arguments):
    if (CONTEXT.get("terminal_actions") or {}).get("allow_container_actions") is False:
        raise ValueError("container terminal actions are not allowed for this AI request")
    arguments = arguments or {}
    node = node_by_id(arguments.get("node_id"))
    container_id = str(arguments.get("container_id") or "").strip()
    action = str(arguments.get("action") or "").strip().lower()
    if action not in {"stop", "restart", "remove"}:
        raise ValueError("action must be one of stop, restart, remove")
    if not CONTAINER_ID_RE.match(container_id):
        raise ValueError("container_id is invalid")
    timeout = max(5, min(int(arguments.get("timeout_seconds") or 45), 180))
    quoted = shlex.quote(container_id)
    inspect = run_on_node(
        node,
        "docker inspect --format '{{.Name}} {{json .Config.Labels}} {{json .Mounts}}' %s 2>/dev/null || true" % quoted,
        timeout_seconds=10,
    )
    if SELF_RESOURCE_RE.search((inspect.get("stdout") or "") + "\n" + container_id):
        raise ValueError("Docker Infra control containers are protected by MCP policy")
    if action == "stop":
        command = f"docker stop {quoted}"
    elif action == "restart":
        command = f"docker restart {quoted}"
    else:
        command = f"docker stop {quoted} >/dev/null 2>&1 || true; docker rm {quoted}"
    result = run_on_node(node, command, timeout_seconds=timeout)
    return {"server": public_node(node), "container_id": container_id, "action": action, "result": result}


def tool_service_stack_status(arguments):
    stack_name = str((arguments or {}).get("stack_name") or "").strip()
    if not stack_name:
        raise ValueError("stack_name is required")
    services = shell_result(["docker", "stack", "services", stack_name, "--format", "{{json .}}"], timeout_seconds=20)
    tasks = shell_result(["docker", "stack", "ps", stack_name, "--no-trunc", "--format", "{{json .}}"], timeout_seconds=20)
    return {
        "stack_name": stack_name,
        "scope": "swarm_only",
        "note": "For non-Swarm Compose deployments, inspect containers on the selected server with server_collect, container_logs, or ssh_command.",
        "services": services,
        "tasks": tasks,
    }


def tool_dns_lookup(arguments):
    host = assert_allowed_probe_host((arguments or {}).get("host") or (arguments or {}).get("hostname"))
    records = []
    try:
        for family, socktype, proto, canonname, sockaddr in socket.getaddrinfo(host, None):
            address = sockaddr[0]
            item = {
                "family": "ipv6" if family == socket.AF_INET6 else "ipv4",
                "address": address,
            }
            if item not in records:
                records.append(item)
    except Exception as exc:
        return {"host": host, "status": "error", "message": str(exc), "records": []}
    return {"host": host, "status": "ok" if records else "empty", "records": records}


def tool_tcp_connect_check(arguments):
    arguments = arguments or {}
    host = assert_allowed_probe_host(arguments.get("host"))
    port = int(arguments.get("port") or 0)
    if port < 1 or port > 65535:
        raise ValueError("port must be between 1 and 65535")
    timeout = max(1, min(int(arguments.get("timeout_seconds") or 5), 30))
    started = time.monotonic()
    try:
        with socket.create_connection((host, port), timeout=timeout):
            pass
        return {
            "host": host,
            "port": port,
            "status": "ok",
            "duration_ms": int((time.monotonic() - started) * 1000),
        }
    except Exception as exc:
        return {
            "host": host,
            "port": port,
            "status": "error",
            "message": str(exc),
            "duration_ms": int((time.monotonic() - started) * 1000),
        }


def tool_http_probe(arguments):
    arguments = arguments or {}
    url = str(arguments.get("url") or "").strip()
    if not url:
        raise ValueError("url is required")
    parsed = urllib.parse.urlparse(url)
    if parsed.scheme not in {"http", "https"}:
        raise ValueError("url scheme must be http or https")
    host = assert_allowed_probe_host(parsed.hostname)
    method = str(arguments.get("method") or "GET").strip().upper()
    if method not in {"GET", "HEAD"}:
        raise ValueError("method must be GET or HEAD")
    timeout = max(1, min(int(arguments.get("timeout_seconds") or 10), 30))
    contains = str(arguments.get("contains") or "")
    request = urllib.request.Request(url, method=method, headers={"User-Agent": "DockerInfra-AI-Probe/1.0"})
    started = time.monotonic()
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            body = response.read(4096).decode("utf-8", "replace") if method == "GET" else ""
            return {
                "url": url,
                "host": host,
                "status": "ok",
                "status_code": response.getcode(),
                "final_url": response.geturl(),
                "contains": None if not contains else contains in body,
                "body_snippet": trim(body, limit=2000),
                "duration_ms": int((time.monotonic() - started) * 1000),
            }
    except urllib.error.HTTPError as exc:
        body = exc.read(4096).decode("utf-8", "replace") if method == "GET" else ""
        return {
            "url": url,
            "host": host,
            "status": "http_error",
            "status_code": exc.code,
            "final_url": exc.geturl(),
            "contains": None if not contains else contains in body,
            "body_snippet": trim(body, limit=2000),
            "duration_ms": int((time.monotonic() - started) * 1000),
        }
    except Exception as exc:
        return {
            "url": url,
            "host": host,
            "status": "error",
            "message": str(exc),
            "duration_ms": int((time.monotonic() - started) * 1000),
        }


def html_text_summary(body):
    title = ""
    title_match = re.search(r"<title[^>]*>(.*?)</title>", body or "", flags=re.I | re.S)
    if title_match:
        title = re.sub(r"\s+", " ", title_match.group(1)).strip()
    text = re.sub(r"<(script|style)[^>]*>.*?</\1>", " ", body or "", flags=re.I | re.S)
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return {"title": trim(title, 300), "text_snippet": trim(text, 3000)}


def tool_browser_probe(arguments):
    arguments = arguments or {}
    url = str(arguments.get("url") or "").strip()
    if not url:
        raise ValueError("url is required")
    parsed = urllib.parse.urlparse(url)
    if parsed.scheme not in {"http", "https"}:
        raise ValueError("url scheme must be http or https")
    host = assert_allowed_probe_host(parsed.hostname)
    timeout = max(1, min(int(arguments.get("timeout_seconds") or 15), 45))
    contains = str(arguments.get("contains") or "")
    request = urllib.request.Request(
        url,
        method="GET",
        headers={
            "User-Agent": "DockerInfra-AI-BrowserProbe/1.0",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        },
    )
    started = time.monotonic()
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            raw = response.read(200000)
            content_type = response.headers.get("content-type") or ""
            charset = "utf-8"
            match = re.search(r"charset=([^;\s]+)", content_type, flags=re.I)
            if match:
                charset = match.group(1).strip("\"'")
            body = raw.decode(charset, "replace")
            summary = html_text_summary(body)
            return {
                "url": url,
                "host": host,
                "status": "ok",
                "status_code": response.getcode(),
                "final_url": response.geturl(),
                "content_type": content_type,
                "title": summary["title"],
                "text_snippet": summary["text_snippet"],
                "contains": None if not contains else contains in body,
                "duration_ms": int((time.monotonic() - started) * 1000),
                "javascript": "not_executed",
            }
    except urllib.error.HTTPError as exc:
        body = exc.read(200000).decode("utf-8", "replace")
        summary = html_text_summary(body)
        return {
            "url": url,
            "host": host,
            "status": "http_error",
            "status_code": exc.code,
            "final_url": exc.geturl(),
            "title": summary["title"],
            "text_snippet": summary["text_snippet"],
            "contains": None if not contains else contains in body,
            "duration_ms": int((time.monotonic() - started) * 1000),
            "javascript": "not_executed",
        }
    except Exception as exc:
        return {
            "url": url,
            "host": host,
            "status": "error",
            "message": str(exc),
            "duration_ms": int((time.monotonic() - started) * 1000),
            "javascript": "not_executed",
        }


def collect_script(arguments):
    include = arguments.get("include") or ["system", "docker", "logs"]
    if not isinstance(include, list):
        include = ["system", "docker", "logs"]
    container = str(arguments.get("container") or "").strip()
    tail = max(10, min(int(arguments.get("tail") or 120), 1000))
    lines = ["set +e"]
    if "system" in include:
        lines.extend(
            [
                "printf '\\n## system\\n'",
                "uname -a",
                "uptime",
                "df -h",
                "free -m 2>/dev/null || true",
            ]
        )
    if "docker" in include:
        lines.extend(
            [
                "printf '\\n## docker\\n'",
                "docker version --format '{{json .}}' 2>/dev/null || docker version 2>&1",
                "docker ps --format '{{json .}}' 2>/dev/null | head -200",
                "docker service ls --format '{{json .}}' 2>/dev/null | head -200",
            ]
        )
    if "logs" in include:
        lines.append("printf '\\n## logs\\n'")
        if container:
            lines.append(f"docker logs --tail {tail} {shlex.quote(container)} 2>&1 || true")
        else:
            lines.append(f"journalctl -u docker --no-pager -n {tail} 2>&1 || true")
    return "\n".join(lines)


def tool_server_collect(arguments):
    arguments = arguments or {}
    node = node_by_id(arguments.get("node_id"))
    timeout = max(5, min(int(arguments.get("timeout_seconds") or 45), 180))
    result = run_on_node(node, collect_script(arguments), timeout_seconds=timeout)
    return {"server": public_node(node), "result": result}


def tool_ssh_command(arguments):
    arguments = arguments or {}
    node = node_by_id(arguments.get("node_id"))
    command = str(arguments.get("command") or "").strip()
    if not command:
        raise ValueError("command is required")
    assert_safe_command(command)
    timeout = max(1, min(int(arguments.get("timeout_seconds") or DEFAULT_TIMEOUT_SECONDS), 300))
    result = run_on_node(node, command, timeout_seconds=timeout)
    return {"server": public_node(node), "result": result}


TOOLS = {
    "infra_context": {
        "description": "Read Docker Infra registered servers, placement recommendation, DDNS endpoints, runtime values, and compact AI request summary for this Codex run.",
        "inputSchema": {"type": "object", "properties": {}},
        "handler": tool_infra_context,
    },
    "docker_search": {
        "description": "Search Docker Hub images with the local docker search command.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {"type": "string"},
                "limit": {"type": "integer", "minimum": 1, "maximum": 25},
            },
            "required": ["query"],
        },
        "handler": tool_docker_search,
    },
    "docker_image_check": {
        "description": "Check whether an image reference exists locally or through docker manifest inspect.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "image_ref": {"type": "string"},
            },
            "required": ["image_ref"],
        },
        "handler": tool_docker_image_check,
    },
    "server_list": {
        "description": "List Docker Infra registered servers available to this Codex run.",
        "inputSchema": {"type": "object", "properties": {}},
        "handler": tool_server_list,
    },
    "server_port_check": {
        "description": "Check whether published ports are currently bindable on a registered server.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "node_id": {"type": "string"},
                "ports": {"type": "array", "items": {"type": "integer", "minimum": 1, "maximum": 65535}},
                "timeout_seconds": {"type": "integer", "minimum": 3, "maximum": 120},
            },
            "required": ["node_id", "ports"],
        },
        "handler": tool_server_port_check,
    },
    "container_logs": {
        "description": "Collect recent docker logs for a container on a registered server.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "node_id": {"type": "string"},
                "container_id": {"type": "string"},
                "tail": {"type": "integer", "minimum": 20, "maximum": 1000},
                "timeout_seconds": {"type": "integer", "minimum": 5, "maximum": 120},
            },
            "required": ["node_id", "container_id"],
        },
        "handler": tool_container_logs,
    },
    "container_action": {
        "description": "Stop, restart, or remove a problem container on a registered server when the current AI request explicitly allows terminal container actions.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "node_id": {"type": "string"},
                "container_id": {"type": "string"},
                "action": {"type": "string", "enum": ["stop", "restart", "remove"]},
                "timeout_seconds": {"type": "integer", "minimum": 5, "maximum": 180},
            },
            "required": ["node_id", "container_id", "action"],
        },
        "handler": tool_container_action,
    },
    "service_stack_status": {
        "description": "Collect docker stack services and task status from the local swarm manager. Swarm-only; for non-Swarm Compose deployments inspect containers on the selected server.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "stack_name": {"type": "string"},
            },
            "required": ["stack_name"],
        },
        "handler": tool_service_stack_status,
    },
    "dns_lookup": {
        "description": "Resolve an allowed service domain or node host for post-deploy verification.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "host": {"type": "string"},
            },
            "required": ["host"],
        },
        "handler": tool_dns_lookup,
    },
    "tcp_connect_check": {
        "description": "Check TCP connectivity to an allowed service domain, IP, or registered node host.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "host": {"type": "string"},
                "port": {"type": "integer", "minimum": 1, "maximum": 65535},
                "timeout_seconds": {"type": "integer", "minimum": 1, "maximum": 30},
            },
            "required": ["host", "port"],
        },
        "handler": tool_tcp_connect_check,
    },
    "http_probe": {
        "description": "Perform a GET or HEAD request against an allowed service URL and return status, final URL, and a short body snippet.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "url": {"type": "string"},
                "method": {"type": "string", "enum": ["GET", "HEAD"]},
                "contains": {"type": "string"},
                "timeout_seconds": {"type": "integer", "minimum": 1, "maximum": 30},
            },
            "required": ["url"],
        },
        "handler": tool_http_probe,
    },
    "browser_probe": {
        "description": "Load an allowed service URL with browser-like request headers and return page title, status, final URL, and visible text snippet for user-facing service checks.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "url": {"type": "string"},
                "contains": {"type": "string"},
                "timeout_seconds": {"type": "integer", "minimum": 1, "maximum": 45},
            },
            "required": ["url"],
        },
        "handler": tool_browser_probe,
    },
    "server_collect": {
        "description": "Collect system, Docker status, and recent error logs from a registered server.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "node_id": {"type": "string"},
                "include": {"type": "array", "items": {"type": "string", "enum": ["system", "docker", "logs"]}},
                "container": {"type": "string"},
                "tail": {"type": "integer", "minimum": 10, "maximum": 1000},
                "timeout_seconds": {"type": "integer", "minimum": 5, "maximum": 180},
            },
            "required": ["node_id"],
        },
        "handler": tool_server_collect,
    },
    "ssh_command": {
        "description": "Run an operator-level SSH command on a registered server using the stored Docker Infra SSH key. Docker Infra self-destruction, OS-critical commands, and persistent Docker volume deletion are blocked by policy.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "node_id": {"type": "string"},
                "command": {"type": "string"},
                "timeout_seconds": {"type": "integer", "minimum": 1, "maximum": 300},
            },
            "required": ["node_id", "command"],
        },
        "handler": tool_ssh_command,
    },
}


TOOL_POLICIES = {
    "infra_context": {
        "category": "context",
        "capability": "Docker Infra topology, runtime values, placement, DDNS endpoints, request summary, and MCP policy.",
        "side_effects": "none",
        "permission": "always allowed",
        "critical_guards": [],
        "annotations": {"readOnlyHint": True, "destructiveHint": False, "idempotentHint": True, "openWorldHint": False},
    },
    "docker_search": {
        "category": "image",
        "capability": "Search Docker Hub image candidates through the local Docker CLI.",
        "side_effects": "network read",
        "permission": "allowed; no mutation",
        "critical_guards": [],
        "annotations": {"readOnlyHint": True, "destructiveHint": False, "idempotentHint": True, "openWorldHint": True},
    },
    "docker_image_check": {
        "category": "image",
        "capability": "Inspect local images and remote manifests for exact image references.",
        "side_effects": "local/network read",
        "permission": "allowed; no mutation",
        "critical_guards": [],
        "annotations": {"readOnlyHint": True, "destructiveHint": False, "idempotentHint": True, "openWorldHint": True},
    },
    "server_list": {
        "category": "inventory",
        "capability": "List registered Docker Infra servers exposed to this Agent run.",
        "side_effects": "none",
        "permission": "always allowed",
        "critical_guards": [],
        "annotations": {"readOnlyHint": True, "destructiveHint": False, "idempotentHint": True, "openWorldHint": False},
    },
    "server_port_check": {
        "category": "server",
        "capability": "Check whether one or more ports can be bound on a registered server.",
        "side_effects": "short-lived bind test on target server",
        "permission": "allowed on registered servers",
        "critical_guards": [],
        "annotations": {"readOnlyHint": True, "destructiveHint": False, "idempotentHint": True, "openWorldHint": False},
    },
    "container_logs": {
        "category": "runtime",
        "capability": "Read recent Docker logs from a container on a registered server.",
        "side_effects": "none",
        "permission": "allowed on registered servers",
        "critical_guards": [],
        "annotations": {"readOnlyHint": True, "destructiveHint": False, "idempotentHint": True, "openWorldHint": False},
    },
    "container_action": {
        "category": "runtime",
        "capability": "Stop, restart, or remove a non-Docker-Infra container on a registered server.",
        "side_effects": "container runtime mutation",
        "permission": "allowed by default unless terminal_actions.allow_container_actions=false",
        "critical_guards": ["Docker Infra control containers are protected."],
        "annotations": {"readOnlyHint": False, "destructiveHint": True, "idempotentHint": False, "openWorldHint": False},
    },
    "service_stack_status": {
        "category": "runtime",
        "capability": "Read Docker stack services and task state from the local swarm manager. For non-Swarm Compose deployments, use container/server inspection tools instead.",
        "side_effects": "none",
        "permission": "allowed",
        "critical_guards": [],
        "annotations": {"readOnlyHint": True, "destructiveHint": False, "idempotentHint": True, "openWorldHint": False},
    },
    "dns_lookup": {
        "category": "network",
        "capability": "Resolve allowed service domains and registered node hosts.",
        "side_effects": "network read",
        "permission": "allowed only for allowed_probe_hosts and registered node hosts",
        "critical_guards": ["arbitrary host probing is blocked by allowed_probe_hosts."],
        "annotations": {"readOnlyHint": True, "destructiveHint": False, "idempotentHint": True, "openWorldHint": True},
    },
    "tcp_connect_check": {
        "category": "network",
        "capability": "Check TCP reachability for allowed service domains, IPs, and node hosts.",
        "side_effects": "network read",
        "permission": "allowed only for allowed_probe_hosts and registered node hosts",
        "critical_guards": ["arbitrary host probing is blocked by allowed_probe_hosts."],
        "annotations": {"readOnlyHint": True, "destructiveHint": False, "idempotentHint": True, "openWorldHint": True},
    },
    "http_probe": {
        "category": "network",
        "capability": "Fetch an allowed service URL and return status, redirect, and a short body snippet.",
        "side_effects": "network read",
        "permission": "allowed only for allowed_probe_hosts and registered node hosts",
        "critical_guards": ["arbitrary URL probing is blocked by allowed_probe_hosts."],
        "annotations": {"readOnlyHint": True, "destructiveHint": False, "idempotentHint": True, "openWorldHint": True},
    },
    "browser_probe": {
        "category": "network",
        "capability": "Fetch an allowed service URL with browser-like headers and summarize title/body text.",
        "side_effects": "network read without JavaScript execution",
        "permission": "allowed only for allowed_probe_hosts and registered node hosts",
        "critical_guards": ["arbitrary URL probing is blocked by allowed_probe_hosts."],
        "annotations": {"readOnlyHint": True, "destructiveHint": False, "idempotentHint": True, "openWorldHint": True},
    },
    "server_collect": {
        "category": "server",
        "capability": "Collect system, Docker, and recent logs from a registered server.",
        "side_effects": "diagnostic reads",
        "permission": "allowed on registered servers",
        "critical_guards": [],
        "annotations": {"readOnlyHint": True, "destructiveHint": False, "idempotentHint": True, "openWorldHint": False},
    },
    "ssh_command": {
        "category": "server",
        "capability": "Run an operator-level shell command on a registered server through stored Docker Infra SSH credentials.",
        "side_effects": "depends on command; mutations are allowed unless they cross the critical guard",
        "permission": "allowed by default; OS-critical commands, Docker Infra self-destruction, and persistent Docker volume deletion are blocked unless explicitly permitted by Docker Infra context",
        "critical_guards": [
            "OS shutdown/reboot/poweroff/halt and disk format/partition/wipe commands are blocked.",
            "Recursive deletion of OS critical paths is blocked.",
            "Recursive deletion of Docker Infra protected roots is blocked.",
            "Stopping/removing Docker Infra control services, containers, or stacks is blocked.",
            "Persistent Docker volume deletion is blocked: docker compose down --volumes, docker volume rm/prune, and docker system prune --volumes.",
        ],
        "annotations": {"readOnlyHint": False, "destructiveHint": True, "idempotentHint": False, "openWorldHint": False},
    },
}


def mcp_contract():
    return {
        "server": "docker_infra",
        "version": "2026-05-28.agent-full-control",
        "permission_mode": PERMISSION_MODE,
        "default_permission": "allow",
        "guardrail": "Agents may use Docker Infra MCP for broad server control. The MCP server blocks Docker Infra self-destruction, OS-critical operations, and persistent Docker volume deletion unless Docker Infra context explicitly permits volume destruction.",
        "blocked_action_families": [
            "OS shutdown/reboot/poweroff/halt",
            "disk format, partition, wipe, or dd write operations",
            "recursive deletion of OS critical paths",
            "recursive deletion of Docker Infra protected roots",
            "stop/remove/disable Docker Infra control services, containers, or stacks",
            "persistent Docker volume deletion: docker compose down --volumes, docker volume rm/prune, docker system prune --volumes",
        ],
        "volume_destruction_policy": {
            "default": "blocked",
            "allow_context_flags": ["allow_volume_destruction", "allow_persistent_volume_delete", "allow_compose_volume_delete"],
            "safe_compose_recreate": "Use docker compose down without --volumes or docker compose up -d --remove-orphans for repair, migration, and redeploy work.",
            "delete_flow": "Service deletion is handled by Docker Infra service delete APIs, not ad-hoc MCP shell cleanup.",
        },
        "protected_paths": protected_docker_infra_paths(),
        "probe_policy": "network probes are limited to registered node hosts and allowed_probe_hosts from the request context",
        "tool_count": len(TOOLS),
        "tools": [
            {
                "name": name,
                "description": TOOLS[name]["description"],
                "inputSchema": TOOLS[name]["inputSchema"],
                **{key: value for key, value in (TOOL_POLICIES.get(name) or {}).items() if key != "annotations"},
            }
            for name in TOOLS.keys()
        ],
    }


def enabled_tool_names():
    configured = CONTEXT.get("mcp_enabled_tools")
    if not isinstance(configured, list) or not configured:
        return list(TOOLS.keys())
    return [name for name in configured if name in TOOLS]


def resource_list():
    return {
        "resources": [
            {
                "uri": MCP_CONTRACT_URI,
                "name": "Docker Infra MCP Agent Contract",
                "description": "Detailed Docker Infra MCP tool, permission, and critical guard definition for Agent runtimes.",
                "mimeType": "application/json",
            }
        ]
    }


def resource_read(params):
    uri = (params or {}).get("uri")
    if uri != MCP_CONTRACT_URI:
        raise ValueError("unknown resource")
    return {
        "contents": [
            {
                "uri": MCP_CONTRACT_URI,
                "mimeType": "application/json",
                "text": json.dumps(mcp_contract(), ensure_ascii=False, indent=2),
            }
        ]
    }


def read_message():
    global MESSAGE_FRAMING
    first = sys.stdin.buffer.read(1)
    while first in {b"\r", b"\n"}:
        first = sys.stdin.buffer.read(1)
    if not first:
        return None

    if first == b"{":
        MESSAGE_FRAMING = "newline"
        body = first + sys.stdin.buffer.readline()
        return json.loads(body.decode("utf-8"))

    MESSAGE_FRAMING = "header"
    header = first
    while b"\r\n\r\n" not in header and b"\n\n" not in header:
        chunk = sys.stdin.buffer.read(1)
        if not chunk:
            return None
        header += chunk
    if b"\r\n\r\n" in header:
        headers, rest = header.split(b"\r\n\r\n", 1)
        header_lines = headers.decode("ascii", "replace").split("\r\n")
    else:
        headers, rest = header.split(b"\n\n", 1)
        header_lines = headers.decode("ascii", "replace").split("\n")
    content_length = 0
    for line in header_lines:
        if line.lower().startswith("content-length:"):
            content_length = int(line.split(":", 1)[1].strip())
            break
    body = rest + sys.stdin.buffer.read(max(0, content_length - len(rest)))
    return json.loads(body.decode("utf-8"))


def write_message(payload):
    data = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    if MESSAGE_FRAMING == "newline":
        sys.stdout.buffer.write(data + b"\n")
        sys.stdout.buffer.flush()
        return
    sys.stdout.buffer.write(f"Content-Length: {len(data)}\r\n\r\n".encode("ascii"))
    sys.stdout.buffer.write(data)
    sys.stdout.buffer.flush()


def tool_list():
    return {
        "tools": [
            {
                "name": name,
                "description": spec["description"],
                "inputSchema": spec["inputSchema"],
                "annotations": (TOOL_POLICIES.get(name) or {}).get("annotations", {}),
            }
            for name, spec in TOOLS.items()
            if name in enabled_tool_names()
        ]
    }


def tool_call(params):
    name = (params or {}).get("name")
    arguments = (params or {}).get("arguments") or {}
    spec = TOOLS.get(name)
    if spec is None or name not in enabled_tool_names():
        raise ValueError("unknown tool")
    result = spec["handler"](arguments)
    return {
        "content": [
            {
                "type": "text",
                "text": json.dumps(result, ensure_ascii=False, indent=2),
            }
        ],
        "isError": False,
    }


def handle(request):
    method = request.get("method")
    request_id = request.get("id")
    if method == "initialize":
        return {
            "jsonrpc": "2.0",
            "id": request_id,
            "result": {
                "protocolVersion": "2024-11-05",
                "capabilities": {"tools": {}},
                "serverInfo": {"name": "docker-infra", "version": "1.0.0"},
            },
        }
    if method == "tools/list":
        return {"jsonrpc": "2.0", "id": request_id, "result": tool_list()}
    if method == "tools/call":
        return {"jsonrpc": "2.0", "id": request_id, "result": tool_call(request.get("params") or {})}
    if method == "resources/list":
        return {"jsonrpc": "2.0", "id": request_id, "result": resource_list()}
    if method == "resources/read":
        return {"jsonrpc": "2.0", "id": request_id, "result": resource_read(request.get("params") or {})}
    if method == "resources/templates/list":
        return {"jsonrpc": "2.0", "id": request_id, "result": {"resourceTemplates": []}}
    if method == "prompts/list":
        return {"jsonrpc": "2.0", "id": request_id, "result": {"prompts": []}}
    if method == "ping":
        return {"jsonrpc": "2.0", "id": request_id, "result": {}}
    if method and method.startswith("notifications/"):
        return None
    return {
        "jsonrpc": "2.0",
        "id": request_id,
        "error": {"code": -32601, "message": f"method not found: {method}"},
    }


def main():
    while True:
        request = read_message()
        if request is None:
            return
        try:
            response = handle(request)
        except Exception as exc:
            response = {
                "jsonrpc": "2.0",
                "id": request.get("id"),
                "error": {"code": -32000, "message": str(exc)},
            }
        if response is not None and request.get("id") is not None:
            write_message(response)


if __name__ == "__main__":
    main()
