import datetime
import json


DEFAULT_OVERLAY_NETWORK = "docker_infra_overlay"
NODE_ROLES = {"worker"}
REPORTER_TOKEN_TYPE = "reporter_token"


class NodeError(Exception):
    def __init__(self, status_code, message, error_code, **extra):
        super().__init__(message)
        self.status_code = status_code
        self.message = message
        self.error_code = error_code
        self.extra = extra


def node_to_dict(row):
    if row is None:
        return None
    return {
        "id": str(row["id"]),
        "name": row["name"],
        "role": row["role"],
        "host": row["host"],
        "ssh_port": row["ssh_port"],
        "auth_type": row["auth_type"],
        "status": row["status"],
        "swarm_node_id": row["swarm_node_id"],
        "is_local_master": row["is_local_master"],
        "labels": row["labels"],
        "test_run_id": row["test_run_id"],
        "metadata": row["metadata"],
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
    }


def credential_to_public(row):
    if row is None:
        return None
    metadata = dict(row["metadata"] or {})
    metadata.pop("token_hash", None)
    return {
        "id": str(row["id"]),
        "node_id": str(row["node_id"]),
        "username": row["username"],
        "has_password": row["password_enc"] is not None,
        "has_private_key": row["private_key_enc"] is not None,
        "has_key_file": bool(row.get("key_file")),
        "key_file": row.get("key_file"),
        "has_passphrase": row["passphrase_enc"] is not None,
        "ssh_fingerprint": row["ssh_fingerprint"],
        "test_run_id": row["test_run_id"],
        "metadata": metadata,
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
    }


def reporter_to_public(row):
    if row is None:
        return {"configured": False, "issued_at": None, "last_used_at": None}
    metadata = row["metadata"] or {}
    return {
        "configured": True,
        "issued_at": metadata.get("issued_at"),
        "last_used_at": metadata.get("last_used_at"),
        "credential_id": str(row["id"]),
    }


def metric_to_dict(row):
    if row is None:
        return None
    cpu_percent = row["cpu_percent"]
    return {
        "id": str(row["id"]),
        "node_id": str(row["node_id"]),
        "cpu_percent": None if cpu_percent is None else float(cpu_percent),
        "memory": row["memory"],
        "storage": row["storage"],
        "containers": row["containers"],
        "reported_at": row["reported_at"],
        "test_run_id": row["test_run_id"],
        "metadata": row["metadata"],
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
    }


def parse_reported_at(value):
    if value in (None, ""):
        return datetime.datetime.now(datetime.timezone.utc)
    if isinstance(value, datetime.datetime):
        return value
    if isinstance(value, str):
        try:
            return datetime.datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            raise NodeError(400, "reported_at 형식이 올바르지 않습니다.", "INVALID_REPORTED_AT")
    raise NodeError(400, "reported_at 형식이 올바르지 않습니다.", "INVALID_REPORTED_AT")


def container_items(containers):
    if isinstance(containers, list):
        return containers
    if isinstance(containers, dict):
        items = containers.get("items")
        if isinstance(items, list):
            return items
        running = containers.get("running")
        stopped = containers.get("stopped")
        if isinstance(running, list) or isinstance(stopped, list):
            return (running or []) + (stopped or [])
    return []


def parse_label_map(value):
    labels = {}
    for raw in str(value or "").split(","):
        raw = raw.strip()
        if not raw or "=" not in raw:
            continue
        key, item = raw.split("=", 1)
        labels[key.strip()] = item.strip()
    return labels


def infer_service_namespace(labels):
    if not isinstance(labels, dict):
        return None
    if labels.get("com.docker.stack.namespace"):
        return labels["com.docker.stack.namespace"]
    if labels.get("com.docker.compose.project"):
        return labels["com.docker.compose.project"]
    swarm_name = labels.get("com.docker.swarm.service.name")
    if swarm_name and "_" in swarm_name:
        return swarm_name.split("_", 1)[0]
    return None


def infer_runtime_kind(labels):
    if not isinstance(labels, dict):
        return "container"
    if labels.get("com.docker.stack.namespace") or labels.get("com.docker.swarm.service.name"):
        return "swarm"
    if labels.get("com.docker.compose.project"):
        return "compose"
    return "container"


def parse_port_bindings(value):
    bindings = []
    seen = set()
    for raw in str(value or "").split(","):
        raw = raw.strip()
        if not raw:
            continue
        target_raw = raw
        published = None
        host = None
        if "->" in raw:
            published_raw, target_raw = [part.strip() for part in raw.split("->", 1)]
            if ":" in published_raw:
                host, published = published_raw.rsplit(":", 1)
                host = host.strip("[]")
            else:
                published = published_raw
        if host and (host == "::" or host.count(":") >= 2):
            continue
        target = target_raw
        protocol = None
        if "/" in target_raw:
            target, protocol = target_raw.rsplit("/", 1)
        key = (host or "", published or "", target or "", protocol or "", "->" in raw)
        if key in seen:
            continue
        seen.add(key)
        bindings.append({
            "raw": raw,
            "host": host,
            "published": published,
            "target": target,
            "protocol": protocol,
            "mapped": "->" in raw,
            "internal_only": "->" not in raw,
        })
    return bindings


def parse_docker_ps_lines(stdout):
    items = []
    for line in (stdout or "").splitlines():
        data = load_json(line)
        if not data:
            continue
        ports = data.get("Ports") or data.get("ports")
        labels = parse_label_map(data.get("Labels") or data.get("labels"))
        item = {
            "id": data.get("ID") or data.get("Id") or data.get("id"),
            "name": data.get("Names") or data.get("Name") or data.get("name"),
            "image": data.get("Image") or data.get("image"),
            "state": data.get("State") or data.get("state"),
            "status": data.get("Status") or data.get("status"),
            "ports": ports,
            "port_bindings": parse_port_bindings(ports),
            "labels": labels,
            "runtime_kind": infer_runtime_kind(labels),
            "service_namespace": infer_service_namespace(labels),
            "runtime_service_name": labels.get("com.docker.swarm.service.name") or labels.get("com.docker.compose.service"),
        }
        item["raw"] = data
        items.append(item)
    return items


def container_summary(items):
    summary = {"total": len(items), "running": 0, "stopped": 0}
    for item in items:
        state = (item.get("state") or "").lower()
        if state == "running":
            summary["running"] += 1
        else:
            summary["stopped"] += 1
    return summary


def load_json(stdout):
    try:
        return json.loads(stdout or "{}")
    except Exception:
        return {}


def swarm_from_docker_info(stdout):
    info = load_json(stdout)
    return info, info.get("Swarm") or {}


def node_status_from_swarm(swarm):
    if swarm.get("LocalNodeState") == "active":
        return "active"
    if swarm.get("LocalNodeState"):
        return swarm.get("LocalNodeState")
    return "reachable"


class NodesShared:
    DEFAULT_OVERLAY_NETWORK = DEFAULT_OVERLAY_NETWORK
    NODE_ROLES = NODE_ROLES
    REPORTER_TOKEN_TYPE = REPORTER_TOKEN_TYPE
    NodeError = NodeError
    node_to_dict = staticmethod(node_to_dict)
    credential_to_public = staticmethod(credential_to_public)
    reporter_to_public = staticmethod(reporter_to_public)
    metric_to_dict = staticmethod(metric_to_dict)
    parse_reported_at = staticmethod(parse_reported_at)
    container_items = staticmethod(container_items)
    parse_label_map = staticmethod(parse_label_map)
    infer_service_namespace = staticmethod(infer_service_namespace)
    infer_runtime_kind = staticmethod(infer_runtime_kind)
    parse_port_bindings = staticmethod(parse_port_bindings)
    parse_docker_ps_lines = staticmethod(parse_docker_ps_lines)
    container_summary = staticmethod(container_summary)
    load_json = staticmethod(load_json)
    swarm_from_docker_info = staticmethod(swarm_from_docker_info)
    node_status_from_swarm = staticmethod(node_status_from_swarm)


Model = NodesShared()
