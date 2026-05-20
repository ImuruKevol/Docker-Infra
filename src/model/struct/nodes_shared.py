import datetime
import json
import re


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
    metadata = row["metadata"] or {}
    private_host = metadata.get("node_access_host") or metadata.get("private_host") or metadata.get("internal_host") or row["host"]
    return {
        "id": str(row["id"]),
        "name": row["name"],
        "role": row["role"],
        "host": row["host"],
        "private_host": private_host,
        "public_ip": metadata.get("public_ip") or metadata.get("public_host") or "",
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


def node_access_host(node):
    node = node or {}
    metadata = node.get("metadata") or {}
    return (
        metadata.get("node_access_host")
        or metadata.get("private_host")
        or metadata.get("internal_host")
        or node.get("private_host")
        or node.get("host")
        or ""
    )


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
        parsed = value
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=datetime.timezone.utc)
        return parsed.astimezone(datetime.timezone.utc)
    if isinstance(value, str):
        try:
            parsed = datetime.datetime.fromisoformat(value.replace("Z", "+00:00"))
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=datetime.timezone.utc)
            return parsed.astimezone(datetime.timezone.utc)
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


def _container_name(value):
    raw = str(value or "").strip().lstrip("/")
    if "," in raw:
        raw = raw.split(",", 1)[0].strip().lstrip("/")
    return raw


def infer_runtime_service_name(labels, container_name=None):
    if not isinstance(labels, dict):
        labels = {}
    swarm_name = labels.get("com.docker.swarm.service.name")
    if swarm_name:
        return swarm_name
    compose_project = labels.get("com.docker.compose.project")
    compose_service = labels.get("com.docker.compose.service")
    if compose_project and compose_service:
        return f"{compose_project}_{compose_service}"
    if compose_service:
        return compose_service
    name = _container_name(container_name)
    if not name:
        return None
    swarm_match = re.match(r"^(.+)\.\d+\.[A-Za-z0-9_.-]+$", name)
    if swarm_match:
        return swarm_match.group(1)
    compose_match = re.match(r"^(.+)[_-]\d+$", name)
    if compose_match:
        return compose_match.group(1)
    return None


def infer_service_namespace(labels, runtime_service_name=None, container_name=None):
    if not isinstance(labels, dict):
        labels = {}
    if labels.get("com.docker.stack.namespace") or labels.get("com.docker.swarm.service.name"):
        if labels.get("com.docker.stack.namespace"):
            return labels["com.docker.stack.namespace"]
        swarm_name = labels.get("com.docker.swarm.service.name")
        if swarm_name and swarm_name.count("_") == 1:
            return swarm_name.split("_", 1)[0]
    if labels.get("com.docker.compose.project"):
        return labels["com.docker.compose.project"]
    runtime_name = runtime_service_name or infer_runtime_service_name(labels, container_name)
    if runtime_name and runtime_name.count("_") == 1:
        return runtime_name.split("_", 1)[0]
    return None


def infer_runtime_kind(labels, runtime_service_name=None, container_name=None):
    if not isinstance(labels, dict):
        labels = {}
    if labels.get("com.docker.stack.namespace") or labels.get("com.docker.swarm.service.name"):
        return "swarm"
    if labels.get("com.docker.compose.project"):
        return "compose"
    name = _container_name(container_name)
    runtime_name = runtime_service_name or infer_runtime_service_name(labels, name)
    if runtime_name and name.startswith(f"{runtime_name}."):
        return "swarm"
    if runtime_name:
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


def _labels_from_item(item):
    labels = (item or {}).get("labels")
    if isinstance(labels, dict):
        return labels
    raw = (item or {}).get("Labels")
    if raw is None:
        raw = labels
    if isinstance(raw, dict):
        return raw
    return parse_label_map(raw)


def normalize_container_item(item):
    data = dict(item or {})
    labels = _labels_from_item(data)
    name = data.get("name") or data.get("Names") or data.get("Name")
    ports = data.get("ports") or data.get("Ports")
    runtime_service_name = data.get("runtime_service_name") or infer_runtime_service_name(labels, name)
    service_namespace = data.get("service_namespace") or infer_service_namespace(labels, runtime_service_name, name)
    normalized = {
        **data,
        "id": data.get("id") or data.get("ID") or data.get("Id"),
        "name": name,
        "image": data.get("image") or data.get("Image"),
        "state": data.get("state") or data.get("State"),
        "status": data.get("status") or data.get("Status"),
        "ports": ports,
        "labels": labels,
        "runtime_kind": data.get("runtime_kind") or infer_runtime_kind(labels, runtime_service_name, name),
        "service_namespace": service_namespace,
        "runtime_service_name": runtime_service_name,
        "port_bindings": data.get("port_bindings") or parse_port_bindings(ports),
    }
    return normalized


def _identity_matches(value, identity):
    value = _container_name(value)
    identity = str(identity or "").strip()
    if not value or not identity:
        return False
    if value == identity:
        return True
    return any(value.startswith(f"{identity}{separator}") for separator in ("_", "-", "."))


def container_matches_service(item, service):
    item = normalize_container_item(item)
    service = service or {}
    identities = [service.get("namespace"), service.get("stack_name")]
    values = [item.get("service_namespace"), item.get("runtime_service_name"), item.get("name")]
    for identity in identities:
        if not identity:
            continue
        for value in values:
            if _identity_matches(value, identity):
                return True
    return False


def parse_docker_ps_lines(stdout):
    items = []
    for line in (stdout or "").splitlines():
        data = load_json(line)
        if not data:
            continue
        ports = data.get("Ports") or data.get("ports")
        labels = parse_label_map(data.get("Labels") or data.get("labels"))
        item = normalize_container_item({
            "id": data.get("ID") or data.get("Id") or data.get("id"),
            "name": data.get("Names") or data.get("Name") or data.get("name"),
            "image": data.get("Image") or data.get("image"),
            "state": data.get("State") or data.get("state"),
            "status": data.get("Status") or data.get("status"),
            "ports": ports,
            "labels": labels,
        })
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
    node_access_host = staticmethod(node_access_host)
    credential_to_public = staticmethod(credential_to_public)
    reporter_to_public = staticmethod(reporter_to_public)
    metric_to_dict = staticmethod(metric_to_dict)
    parse_reported_at = staticmethod(parse_reported_at)
    container_items = staticmethod(container_items)
    parse_label_map = staticmethod(parse_label_map)
    infer_runtime_service_name = staticmethod(infer_runtime_service_name)
    infer_service_namespace = staticmethod(infer_service_namespace)
    infer_runtime_kind = staticmethod(infer_runtime_kind)
    parse_port_bindings = staticmethod(parse_port_bindings)
    normalize_container_item = staticmethod(normalize_container_item)
    container_matches_service = staticmethod(container_matches_service)
    parse_docker_ps_lines = staticmethod(parse_docker_ps_lines)
    container_summary = staticmethod(container_summary)
    load_json = staticmethod(load_json)
    swarm_from_docker_info = staticmethod(swarm_from_docker_info)
    node_status_from_swarm = staticmethod(node_status_from_swarm)


Model = NodesShared()
