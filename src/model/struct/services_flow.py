import re

import yaml


def _text(value):
    return str(value or "").strip()


def _service_id(key):
    return f"service:{key}"


def _domain_id(domain):
    return f"domain:{domain.get('id') or domain.get('domain') or 'unknown'}"


def _split_image(ref):
    raw = _text(ref)
    if not raw:
        return {"name": "", "tag": "", "ref": ""}
    digest = raw.find("@")
    if digest > 0:
        return {"name": raw[:digest], "tag": raw[digest + 1:], "ref": raw}
    slash = raw.rfind("/")
    colon = raw.rfind(":")
    if colon > slash:
        return {"name": raw[:colon], "tag": raw[colon + 1:] or "latest", "ref": raw}
    return {"name": raw, "tag": "latest", "ref": raw}


def _parse_port(item):
    protocol = "tcp"
    published = None
    target = None
    mode = ""
    if isinstance(item, dict):
        protocol = _text(item.get("protocol") or "tcp") or "tcp"
        mode = _text(item.get("mode"))
        try:
            target = int(item.get("target") or 0)
        except Exception:
            target = 0
        try:
            published = int(item.get("published") or 0)
        except Exception:
            published = 0
    else:
        raw = _text(item).strip('"')
        base, _, proto = raw.partition("/")
        protocol = proto or protocol
        chunks = base.split(":")
        try:
            target = int(chunks[-1])
        except Exception:
            target = 0
        try:
            published = int(chunks[-2]) if len(chunks) >= 2 else 0
        except Exception:
            published = 0
    if not target:
        return None
    return {
        "target": target,
        "published": published or target,
        "protocol": protocol,
        "mode": mode,
        "internal_only": False,
        "label": f"{published or target} -> {target}/{protocol}",
    }


def _parse_expose(item):
    raw = _text(item).strip('"')
    base, _, proto = raw.partition("/")
    try:
        target = int(base)
    except Exception:
        return None
    protocol = proto or "tcp"
    return {
        "target": target,
        "published": None,
        "protocol": protocol,
        "mode": "internal",
        "internal_only": True,
        "label": f"내부 {target}/{protocol}",
    }


def _service_ports(service):
    result = []
    for item in service.get("ports") or []:
        parsed = _parse_port(item)
        if parsed:
            result.append(parsed)
    for item in service.get("expose") or []:
        parsed = _parse_expose(item)
        if parsed:
            result.append(parsed)
    return result


def _depends_on(service):
    value = service.get("depends_on") or []
    if isinstance(value, dict):
        return list(value.keys())
    if isinstance(value, list):
        return [_text(item) for item in value if _text(item)]
    return []


def _environment_values(service):
    env = service.get("environment") or {}
    if isinstance(env, dict):
        return [_text(value) for value in env.values()]
    if isinstance(env, list):
        return [_text(item).partition("=")[2] for item in env]
    return []


def _references_service(value, service_key, namespace):
    text = _text(value)
    if not text:
        return False
    candidates = [service_key]
    if namespace:
        candidates.append(f"{namespace}_{service_key}")
    for candidate in candidates:
        if re.search(rf"(^|[^a-zA-Z0-9_-]){re.escape(candidate)}([^a-zA-Z0-9_-]|$)", text):
            return True
    return False


def _extract_service_key(runtime_name, namespace):
    raw = _text(runtime_name)
    if namespace and raw.startswith(f"{namespace}_"):
        return raw[len(namespace) + 1:]
    return raw


def _runtime_by_service(runtime_status, namespace):
    result = {}
    containers = (((runtime_status or {}).get("containers") or {}).get("containers") or [])
    for container in containers:
        key = _extract_service_key(container.get("runtime_service_name") or container.get("name"), namespace)
        if not key:
            continue
        result.setdefault(key, []).append(container)
    return result


def _container_summary(containers):
    running = 0
    unhealthy = 0
    starting = 0
    stopped = 0
    for container in containers or []:
        state = _text(container.get("state")).lower()
        status = _text(container.get("status")).lower()
        if "unhealthy" in status:
            unhealthy += 1
        elif "health: starting" in status:
            starting += 1
        elif state == "running":
            running += 1
        elif state:
            stopped += 1
    if unhealthy:
        return {"status": "failed", "label": f"문제 {unhealthy}개", "running": running, "total": len(containers or [])}
    if starting:
        return {"status": "pending", "label": f"시작 중 {starting}개", "running": running, "total": len(containers or [])}
    if running:
        return {"status": "running", "label": f"실행 {running}개", "running": running, "total": len(containers or [])}
    if stopped:
        return {"status": "failed", "label": f"중지 {stopped}개", "running": running, "total": len(containers or [])}
    return {"status": "unknown", "label": "상태 확인 전", "running": 0, "total": 0}


def _node_label(key, component):
    label = _text(component.get("label"))
    if label and not label.startswith("구성 "):
        return label
    role = _text(component.get("role"))
    if role == "public":
        return "웹 서비스"
    if any(token in key.lower() for token in ["db", "postgres", "mysql", "mariadb", "redis"]):
        return "데이터 저장소"
    return key


def _domain_target(domain, service_nodes):
    metadata = dict(domain.get("metadata") or {})
    target = _text(metadata.get("compose_service"))
    if target in service_nodes:
        return target
    public_nodes = [key for key, node in service_nodes.items() if node.get("public")]
    if public_nodes:
        return public_nodes[0]
    return next(iter(service_nodes.keys()), "")


def _domain_ssl_label(domain):
    metadata = dict(domain.get("metadata") or {})
    mode = _text(metadata.get("nginx_ssl_mode") or domain.get("ssl_mode"))
    labels = {
        "existing": "업로드 인증서",
        "certbot": "자동 인증서",
        "self_signed": "자체 인증서",
        "none": "HTTP",
    }
    return labels.get(mode, "SSL 준비")


def _proxy_label(domain):
    metadata = dict(domain.get("metadata") or {})
    host = _text(metadata.get("proxy_host") or "127.0.0.1")
    published = metadata.get("published_port") or domain.get("port")
    target = metadata.get("target_port") or domain.get("port")
    node = _text(metadata.get("proxy_node_name"))
    base = f"{host}:{published} -> {target}"
    return f"{base} · {node}" if node else base


def _reachable(start_key, edges):
    seen = []
    stack = [start_key]
    while stack:
        current = stack.pop(0)
        for edge in edges:
            if edge["from"] != current:
                continue
            target = edge["to"]
            if target == start_key or target in seen:
                continue
            seen.append(target)
            stack.append(target)
    return seen


class ServicesFlow:
    def build(self, detail, components=None):
        detail = detail or {}
        service = detail.get("service") or {}
        namespace = _text(service.get("namespace"))
        domains = detail.get("domains") or []
        runtime_status = detail.get("runtime_status") or {}
        components_by_key = {
            _text(item.get("key")): dict(item)
            for item in components or []
            if _text(item.get("key"))
        }
        try:
            compose = yaml.safe_load(detail.get("compose_content") or "{}") or {}
        except Exception:
            compose = {}
        services = compose.get("services") or {}
        runtime_map = _runtime_by_service(runtime_status, namespace)
        service_nodes = {}
        for key, raw_service in services.items():
            key = _text(key)
            raw_service = raw_service if isinstance(raw_service, dict) else {}
            component = components_by_key.get(key) or {}
            image = _split_image(raw_service.get("image") or component.get("image") or "")
            ports = _service_ports(raw_service)
            containers = runtime_map.get(key) or []
            public = any(port.get("published") and not port.get("internal_only") for port in ports)
            if any(port.get("public_endpoint") for port in component.get("ports") or []):
                public = True
            service_nodes[key] = {
                "id": _service_id(key),
                "key": key,
                "type": "service",
                "role": component.get("role") or ("public" if public else "internal"),
                "label": _node_label(key, component),
                "subtitle": key,
                "image": image["ref"],
                "image_name": image["name"],
                "image_tag": image["tag"],
                "ports": ports,
                "public": public,
                "containers": _container_summary(containers),
            }

        internal_edges = []
        for key, raw_service in services.items():
            key = _text(key)
            raw_service = raw_service if isinstance(raw_service, dict) else {}
            targets = set()
            for target in _depends_on(raw_service):
                if target in service_nodes and target != key:
                    targets.add(target)
            for target in service_nodes:
                if target == key:
                    continue
                if any(_references_service(value, target, namespace) for value in _environment_values(raw_service)):
                    targets.add(target)
            for target in sorted(targets):
                internal_edges.append({
                    "from": key,
                    "to": target,
                    "label": "내부 연결",
                    "kind": "internal",
                })

        public_paths = []
        for domain in domains:
            target = _domain_target(domain, service_nodes)
            if not target:
                continue
            reachable = _reachable(target, internal_edges)
            public_paths.append({
                "id": _domain_id(domain),
                "entry": {
                    "id": _domain_id(domain),
                    "type": "domain",
                    "label": domain.get("domain") or "도메인",
                    "subtitle": _domain_ssl_label(domain),
                    "url": f"https://{domain.get('domain')}" if domain.get("ssl_mode") != "none" else f"http://{domain.get('domain')}",
                },
                "proxy": {
                    "id": "proxy:nginx",
                    "type": "proxy",
                    "label": "Docker Infra 연결",
                    "subtitle": "nginx",
                    "route": _proxy_label(domain),
                },
                "target": service_nodes[target],
                "internal_targets": [service_nodes[item] for item in reachable if item in service_nodes],
                "edges": [
                    {"from": "사용자", "to": domain.get("domain"), "label": "접속"},
                    {"from": domain.get("domain"), "to": "nginx", "label": "도메인/SSL"},
                    {"from": "nginx", "to": service_nodes[target]["label"], "label": _proxy_label(domain)},
                ],
            })

        if not public_paths:
            for key, node in service_nodes.items():
                public_ports = [port for port in node.get("ports") or [] if port.get("published") and not port.get("internal_only")]
                if not public_ports:
                    continue
                reachable = _reachable(key, internal_edges)
                public_paths.append({
                    "id": f"port:{key}",
                    "entry": {
                        "id": f"port:{key}",
                        "type": "port",
                        "label": "공개 포트",
                        "subtitle": ", ".join([str(port.get("published")) for port in public_ports]),
                        "url": "",
                    },
                    "proxy": None,
                    "target": node,
                    "internal_targets": [service_nodes[item] for item in reachable if item in service_nodes],
                    "edges": [
                        {"from": "사용자", "to": node["label"], "label": "공개 포트"},
                    ],
                })

        connected = set()
        for path in public_paths:
            connected.add(path["target"]["key"])
            for item in path.get("internal_targets") or []:
                connected.add(item["key"])
        unexposed = [node for key, node in service_nodes.items() if key not in connected]
        warnings = []
        if not public_paths and service_nodes:
            warnings.append("외부 접속 경로가 없습니다. 서비스 내부 구성만 표시합니다.")
        if not service_nodes:
            warnings.append("Compose에서 서비스 구성요소를 찾지 못했습니다.")
        return {
            "summary": {
                "service_count": len(service_nodes),
                "public_path_count": len(public_paths),
                "internal_edge_count": len(internal_edges),
                "unexposed_count": len(unexposed),
            },
            "actor": {"id": "actor:user", "type": "actor", "label": "사용자", "subtitle": "브라우저 접속"},
            "public_paths": public_paths,
            "internal_edges": internal_edges,
            "unexposed_nodes": unexposed,
            "warnings": warnings,
        }


Model = ServicesFlow()
