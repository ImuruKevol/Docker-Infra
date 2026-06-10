import socket
from pathlib import Path

import yaml


nodes_model = wiz.model("struct").nodes


class PortCheckError(RuntimeError):
    def __init__(self, message, details=None):
        super().__init__(message)
        self.details = details or {}


REMOTE_PORT_FREE_SCRIPT = """
import socket
import sys

port = int(sys.argv[1])
sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
try:
    sock.bind(("0.0.0.0", port))
    print("free")
except OSError:
    print("used")
finally:
    sock.close()
""".strip()


def _is_free(port):
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    try:
        sock.bind(("0.0.0.0", int(port)))
        return True
    except OSError:
        return False
    finally:
        sock.close()


def _node_detail(node, env=None):
    node = node or {}
    if not node or node.get("is_local_master"):
        return node
    node_id = str(node.get("id") or "").strip()
    if not node_id:
        raise PortCheckError("원격 배포 서버 ID가 없어 공개 포트를 확인할 수 없습니다.", {"code": "REMOTE_NODE_ID_REQUIRED", "node": node})
    try:
        return nodes_model.detail(node_id, env=env)
    except Exception as exc:
        raise PortCheckError(
            "원격 배포 서버 정보를 불러올 수 없어 공개 포트를 확인할 수 없습니다.",
            {"code": "REMOTE_NODE_DETAIL_FAILED", "node_id": node_id, "error": str(exc)},
        )


def _is_free_on_node(port, node=None, env=None):
    node = _node_detail(node, env=env)
    if not node or node.get("is_local_master"):
        return _is_free(port)
    try:
        result = nodes_model._run_ssh_command(
            node,
            ["python3", "-c", REMOTE_PORT_FREE_SCRIPT, str(int(port))],
            timeout_seconds=6,
            env=env,
        )
        if result.get("status") != "ok":
            raise PortCheckError(
                "원격 배포 서버의 공개 포트 점검 SSH 명령이 실패했습니다.",
                {"code": "REMOTE_PORT_CHECK_FAILED", "node_id": node.get("id"), "port": int(port), "result": result},
            )
        output = str(result.get("stdout") or "").strip().lower()
        if output == "free":
            return True
        if output == "used":
            return False
        raise PortCheckError(
            "원격 배포 서버의 공개 포트 점검 결과를 해석할 수 없습니다.",
            {"code": "REMOTE_PORT_CHECK_INVALID_OUTPUT", "node_id": node.get("id"), "port": int(port), "stdout": result.get("stdout")},
        )
    except PortCheckError:
        raise
    except Exception as exc:
        raise PortCheckError(
            "원격 배포 서버의 공개 포트를 확인할 수 없습니다.",
            {"code": "REMOTE_PORT_CHECK_ERROR", "node_id": node.get("id"), "port": int(port), "error": str(exc)},
        )


def _next_free(port, reserved=None, node=None, env=None):
    reserved = reserved or set()
    candidate = max(1, int(port or 1))
    while candidate <= 65535:
        if candidate not in reserved and _is_free_on_node(candidate, node=node, env=env):
            return candidate
        candidate += 1
    raise PortCheckError("사용 가능한 공개 포트를 찾을 수 없습니다.", {"code": "NO_FREE_PUBLISHED_PORT", "start_port": int(port or 1)})


def _string_port(item, reserved, node=None, env=None):
    raw = str(item).strip().strip('"')
    base, suffix = (raw.split("/", 1) + [""])[:2] if "/" in raw else (raw, "")
    chunks = base.split(":")
    target = int(chunks[-1])
    published = int(chunks[-2]) if len(chunks) >= 2 and chunks[-2].isdigit() else target
    allocated = _next_free(published, reserved=reserved, node=node, env=env)
    reserved.add(allocated)
    next_base = f"{allocated}:{target}" if allocated != published or len(chunks) >= 2 else raw
    return f"{next_base}/{suffix}" if suffix else next_base, {"target": target, "previous": published, "published": allocated}


def _allocate_compose(compose, node=None, env=None):
    allocations = []
    reserved = set()
    for service_name, service in (compose.get("services") or {}).items():
        next_ports = []
        for item in service.get("ports") or []:
            if isinstance(item, dict):
                target = int(item.get("target") or item.get("published") or 0)
                previous = int(item.get("published") or target)
                published = _next_free(previous, reserved=reserved, node=node, env=env)
                reserved.add(published)
                item["published"] = published
                next_ports.append(item)
                allocations.append({"service": service_name, "target": target, "previous": previous, "published": published})
                continue
            try:
                next_item, allocation = _string_port(item, reserved, node=node, env=env)
                allocation["service"] = service_name
                allocations.append(allocation)
                next_ports.append(next_item)
            except PortCheckError:
                raise
            except Exception:
                next_ports.append(item)
        if next_ports:
            service["ports"] = next_ports
    changed = any(item["previous"] != item["published"] for item in allocations)
    return {"changed": changed, "allocations": allocations, "compose": compose}


class ServicePorts:
    def preview_content(self, content):
        compose = yaml.safe_load(content or "{}") or {}
        return _allocate_compose(compose)

    def allocate_file(self, compose_path, node=None, env=None):
        path = Path(compose_path).expanduser()
        compose = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        result = _allocate_compose(compose, node=node, env=env)
        if result["changed"]:
            path.write_text(yaml.safe_dump(result["compose"], sort_keys=False, allow_unicode=False), encoding="utf-8")
        return {"changed": result["changed"], "allocations": result["allocations"]}


Model = ServicePorts()
