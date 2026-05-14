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
DESTRUCTIVE_RE = re.compile(
    r"(\brm\s+-[^\n;|&]*r|\bshutdown\b|\breboot\b|\bpoweroff\b|\bhalt\b|\bmkfs\b|\bdd\s+if=|\bdocker\s+(stop|restart|kill|pause|unpause|rm)\b|\bdocker\s+service\s+rm\b|\bdocker\s+stack\s+rm\b|\bdocker\s+volume\s+rm\b|\bdocker\s+system\s+prune\b)",
    re.I,
)
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


def public_node(node):
    return {
        "id": node.get("id"),
        "name": node.get("name"),
        "host": node.get("host"),
        "role": node.get("role"),
        "status": node.get("status"),
        "is_local_master": node.get("is_local_master"),
        "ssh_port": node.get("ssh_port"),
        "ssh_configured": bool((node.get("ssh") or {}).get("username") and (node.get("ssh") or {}).get("key_file")),
    }


def public_context():
    return {
        "workspace_root": CONTEXT.get("workspace_root"),
        "project_root": CONTEXT.get("project_root"),
        "runtime_values": CONTEXT.get("runtime_values") or {},
        "placement": CONTEXT.get("placement"),
        "ai_permission_scope": CONTEXT.get("ai_permission_scope") or {},
        "mcp_enabled_tools": CONTEXT.get("mcp_enabled_tools") or [],
        "allowed_probe_hosts": CONTEXT.get("allowed_probe_hosts") or [],
        "servers": [public_node(node) for node in CONTEXT.get("nodes") or []],
    }


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
    if os.environ.get("DOCKER_INFRA_MCP_ALLOW_DESTRUCTIVE") == "1":
        return
    if DESTRUCTIVE_RE.search(command or ""):
        raise ValueError("destructive ssh command is blocked by Docker Infra MCP policy")


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
    if not bool((CONTEXT.get("terminal_actions") or {}).get("allow_container_actions")):
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
    return {"stack_name": stack_name, "services": services, "tasks": tasks}


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
        "description": "Read Docker Infra registered servers, placement recommendation, and runtime values for this Codex run.",
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
        "description": "Collect docker stack services and task status from the local swarm manager.",
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
        "description": "Run a non-destructive SSH command on a registered server using the stored Docker Infra SSH key.",
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


def enabled_tool_names():
    configured = CONTEXT.get("mcp_enabled_tools")
    if not isinstance(configured, list) or not configured:
        return list(TOOLS.keys())
    return [name for name in configured if name in TOOLS]


def read_message():
    header = b""
    while b"\r\n\r\n" not in header:
        chunk = sys.stdin.buffer.read(1)
        if not chunk:
            return None
        header += chunk
    headers, rest = header.split(b"\r\n\r\n", 1)
    content_length = 0
    for line in headers.decode("ascii", "replace").split("\r\n"):
        if line.lower().startswith("content-length:"):
            content_length = int(line.split(":", 1)[1].strip())
            break
    body = rest + sys.stdin.buffer.read(max(0, content_length - len(rest)))
    return json.loads(body.decode("utf-8"))


def write_message(payload):
    data = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
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
