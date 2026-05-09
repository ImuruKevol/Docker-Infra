import socket
from pathlib import Path

import yaml


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


def _next_free(port, reserved=None):
    reserved = reserved or set()
    candidate = max(1, int(port or 1))
    while candidate <= 65535:
        if candidate not in reserved and _is_free(candidate):
            return candidate
        candidate += 1
    return int(port or 1)


def _string_port(item, reserved):
    raw = str(item).strip().strip('"')
    base, suffix = (raw.split("/", 1) + [""])[:2] if "/" in raw else (raw, "")
    chunks = base.split(":")
    target = int(chunks[-1])
    published = int(chunks[-2]) if len(chunks) >= 2 and chunks[-2].isdigit() else target
    allocated = _next_free(published, reserved=reserved)
    reserved.add(allocated)
    next_base = f"{allocated}:{target}" if allocated != published or len(chunks) >= 2 else raw
    return f"{next_base}/{suffix}" if suffix else next_base, {"target": target, "previous": published, "published": allocated}


def _allocate_compose(compose):
    allocations = []
    reserved = set()
    for service_name, service in (compose.get("services") or {}).items():
        next_ports = []
        for item in service.get("ports") or []:
            if isinstance(item, dict):
                target = int(item.get("target") or item.get("published") or 0)
                previous = int(item.get("published") or target)
                published = _next_free(previous, reserved=reserved)
                reserved.add(published)
                item["published"] = published
                next_ports.append(item)
                allocations.append({"service": service_name, "target": target, "previous": previous, "published": published})
                continue
            try:
                next_item, allocation = _string_port(item, reserved)
                allocation["service"] = service_name
                allocations.append(allocation)
                next_ports.append(next_item)
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

    def allocate_file(self, compose_path):
        path = Path(compose_path).expanduser()
        compose = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        result = _allocate_compose(compose)
        if result["changed"]:
            path.write_text(yaml.safe_dump(result["compose"], sort_keys=False, allow_unicode=False), encoding="utf-8")
        return {"changed": result["changed"], "allocations": result["allocations"]}


Model = ServicePorts()
