import json
import re
import shutil
import subprocess
import urllib.request
from pathlib import Path


connect = wiz.model("db/postgres").connect
validator = wiz.model("struct/compose_validator")
service_ports = wiz.model("struct/services_ports")
webserver = wiz.model("struct/webserver")
ddns_model = wiz.model("struct/domains_ddns")
nodes_model = wiz.model("struct").nodes
ssh_executor = wiz.model("struct/ssh_executor")
placement_selector = wiz.model("struct/services_placement")

DOMAIN_RE = re.compile(r"^(?=.{1,253}$)([a-zA-Z0-9_*-]{1,63}\.)*[a-zA-Z0-9-]{1,63}\.[a-zA-Z]{2,63}$")
VOLUME_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,127}$")
SERVICE_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,62}$")


def _item(key, title, status, message, details=None):
    return {
        "key": key,
        "title": title,
        "status": status,
        "message": message,
        "details": details or [],
    }


def _split_image(ref):
    clean = str(ref or "").strip()
    digest = clean.find("@")
    if digest > 0:
        return clean[:digest], clean[digest + 1:]
    slash = clean.rfind("/")
    colon = clean.rfind(":")
    if colon > slash:
        return clean[:colon], clean[colon + 1:] or "latest"
    return clean, "latest"


def _image_exists(ref):
    if not ref:
        return {"exists": False, "source": "none", "message": "이미지 이름이 비어 있습니다."}
    try:
        result = subprocess.run(["docker", "image", "inspect", ref], capture_output=True, text=True, timeout=4, check=False)
        if result.returncode == 0:
            return {"exists": True, "source": "local", "message": "로컬 이미지 저장소에서 확인했습니다."}
    except Exception:
        pass
    name, tag = _split_image(ref)
    first = name.split("/", 1)[0]
    if "/" in name and ("." in first or ":" in first or first == "localhost"):
        return {"exists": None, "source": "registry", "message": "외부 registry 이미지는 배포 중 pull 결과로 확인합니다."}
    repository = f"library/{name}" if "/" not in name else name
    try:
        token_url = f"https://auth.docker.io/token?service=registry.docker.io&scope=repository:{repository}:pull"
        token = json.loads(urllib.request.urlopen(token_url, timeout=4).read().decode("utf-8"))["token"]
        request = urllib.request.Request(
            f"https://registry-1.docker.io/v2/{repository}/manifests/{tag}",
            headers={"Authorization": f"Bearer {token}", "Accept": "application/vnd.docker.distribution.manifest.v2+json"},
            method="HEAD",
        )
        urllib.request.urlopen(request, timeout=4).close()
        return {"exists": True, "source": "docker_hub", "message": "Docker Hub에서 이미지를 확인했습니다."}
    except Exception:
        return {"exists": False, "source": "docker_hub", "message": "로컬 저장소와 Docker Hub에서 이미지를 찾지 못했습니다."}


def _registry_pull_status(ref):
    name, tag = _split_image(ref)
    first = name.split("/", 1)[0]
    if "/" in name and ("." in first or ":" in first or first == "localhost"):
        return {"exists": None, "source": "registry", "message": "외부 registry 이미지는 서버에서 pull 가능한지 배포 중 다시 확인합니다."}
    repository = f"library/{name}" if "/" not in name else name
    try:
        token_url = f"https://auth.docker.io/token?service=registry.docker.io&scope=repository:{repository}:pull"
        token = json.loads(urllib.request.urlopen(token_url, timeout=4).read().decode("utf-8"))["token"]
        request = urllib.request.Request(
            f"https://registry-1.docker.io/v2/{repository}/manifests/{tag}",
            headers={"Authorization": f"Bearer {token}", "Accept": "application/vnd.docker.distribution.manifest.v2+json"},
            method="HEAD",
        )
        urllib.request.urlopen(request, timeout=4).close()
        return {"exists": True, "source": "docker_hub", "message": "Docker Hub에서 pull 가능한 이미지입니다."}
    except Exception:
        return {"exists": False, "source": "docker_hub", "message": "Docker Hub에서 pull 가능한 이미지를 찾지 못했습니다."}


def _parse_ports(service):
    ports = []
    for item in service.get("ports") or []:
        if isinstance(item, dict):
            target = int(item.get("target") or item.get("published") or 0)
            published = int(item.get("published") or target)
            ports.append({"target": target, "published": published, "protocol": item.get("protocol") or "tcp"})
            continue
        raw = str(item).strip().strip('"')
        base, _, protocol = raw.partition("/")
        chunks = base.split(":")
        target = int(chunks[-1])
        published = int(chunks[-2]) if len(chunks) >= 2 and chunks[-2].isdigit() else target
        ports.append({"target": target, "published": published, "protocol": protocol or "tcp"})
    return ports


def _service_volumes(service):
    rows = []
    for raw in service.get("volumes") or []:
        if isinstance(raw, dict):
            rows.append({"source": str(raw.get("source") or ""), "target": str(raw.get("target") or ""), "external": bool(raw.get("external"))})
            continue
        source, _, target = str(raw).partition(":")
        if source or target:
            rows.append({"source": source, "target": target, "external": False})
    return rows


class ServicesPreflight:
    def _candidate_nodes(self, payload, env=None):
        payload = payload or {}
        selected_node_id = str(payload.get("node_id") or payload.get("target_node_id") or "").strip()
        try:
            rows = nodes_model.list(env=env)
        except Exception:
            return []
        if selected_node_id:
            rows = [row for row in rows if str(row.get("id")) == selected_node_id]
        else:
            rows = sorted(rows, key=lambda item: (not bool(item.get("is_local_master")), str(item.get("name") or item.get("host") or "")))[:10]
        detailed = []
        for row in rows:
            try:
                detailed.append(nodes_model.detail(row["id"], env=env))
            except Exception as exc:
                detailed.append({**row, "_detail_error": str(exc)})
        return detailed

    def _node_label(self, node):
        return str(node.get("name") or node.get("host") or node.get("id") or "서버")

    def _check_placement(self, nodes, recommendation=None):
        if not nodes:
            return [_item("placement", "실행 서버", "warning", "등록된 실행 서버 정보를 확인하지 못했습니다. 저장 후 배포 단계에서 다시 확인합니다.")]
        selected = (recommendation or {}).get("selected") or {}
        selected_node = selected.get("node") or {}
        scores = {
            ((item.get("node") or {}).get("id")): item
            for item in (recommendation or {}).get("candidates") or []
        }
        details = [
            {
                "node_id": node.get("id"),
                "name": self._node_label(node),
                "host": node.get("host"),
                "local_master": bool(node.get("is_local_master")),
                "credential_ready": bool((node.get("credential") or {}).get("key_file")) or bool(node.get("is_local_master")),
                "score": (scores.get(node.get("id")) or {}).get("score"),
                "cpu_percent": (scores.get(node.get("id")) or {}).get("cpu_percent"),
                "memory_used_percent": (scores.get(node.get("id")) or {}).get("memory_used_percent"),
                "storage_used_percent": (scores.get(node.get("id")) or {}).get("storage_used_percent"),
                "containers": (scores.get(node.get("id")) or {}).get("containers"),
            }
            for node in nodes
        ]
        if selected_node.get("id"):
            label = selected_node.get("name") or selected_node.get("host") or selected_node.get("id")
            return [_item("placement", "실행 서버", "ok", f"자원 사용량을 기준으로 {label} 서버를 자동 선택합니다.", details)]
        return [_item("placement", "실행 서버", "ok", f"배포 후보 서버 {len(nodes)}대를 확인했습니다.", details)]

    def _domain_entries(self, payload):
        payload = payload or {}
        rows = []
        for item in payload.get("domains") or []:
            if not isinstance(item, dict):
                continue
            domain = str(item.get("domain") or "").strip().lower()
            if domain:
                rows.append({**item, "domain": domain})
        if not rows:
            domain = str(payload.get("domain") or "").strip().lower()
            if domain:
                rows.append({"domain": domain, "port": payload.get("port") or payload.get("domain_target_port")})
        deduped = []
        seen = set()
        for item in rows:
            if item["domain"] in seen:
                continue
            seen.add(item["domain"])
            deduped.append(item)
        return deduped

    def _check_database(self, namespace, domains, service_id=None, env=None):
        domains = domains if isinstance(domains, list) else ([{"domain": domains}] if domains else [])
        issues = []
        with connect(env=env) as connection:
            with connection.cursor() as cursor:
                if service_id:
                    cursor.execute("SELECT id FROM services WHERE namespace = %s AND id <> %s LIMIT 1", (namespace, service_id))
                else:
                    cursor.execute("SELECT id FROM services WHERE namespace = %s LIMIT 1", (namespace,))
                if cursor.fetchone() is not None:
                    issues.append(_item("namespace", "서비스 이름", "error", "같은 이름으로 생성된 서비스가 이미 있습니다. 이름을 조금 바꿔 다시 저장해주세요."))
                for item in domains:
                    domain = str((item or {}).get("domain") or "").strip().lower()
                    if not domain:
                        continue
                    if service_id:
                        cursor.execute("SELECT service_id FROM service_domains WHERE lower(domain) = lower(%s) AND service_id <> %s LIMIT 1", (domain, service_id))
                    else:
                        cursor.execute("SELECT service_id FROM service_domains WHERE lower(domain) = lower(%s) LIMIT 1", (domain,))
                    if cursor.fetchone() is not None:
                        issues.append(_item("domain.duplicate", "도메인 중복", "error", f"{domain} 도메인은 이미 다른 서비스에서 사용 중입니다."))
        return issues

    def _check_compose(self, validation, namespace):
        compose = validation.get("normalized") or {}
        services = compose.get("services") or {}
        issues = []
        generated = []
        for service_name, service in services.items():
            if SERVICE_RE.match(str(service_name)) is None:
                issues.append(_item("compose.service_name", "컨테이너 이름", "error", f"{service_name} 이름은 Docker 서비스 이름으로 사용하기 어렵습니다."))
            generated.append(f"{namespace}_{service_name}")
            if "container_name" in service:
                issues.append(_item("compose.container_name", "컨테이너 이름", "error", "컨테이너 이름은 Docker Infra가 자동 생성해야 합니다."))
        if issues:
            return issues
        return [_item("compose.names", "실행 이름", "ok", "실행에 필요한 내부 이름은 Docker Infra가 자동으로 준비합니다.", generated)]

    def _node_image_status(self, node, ref, registry_status, env=None):
        node_label = self._node_label(node)
        if node.get("_detail_error"):
            return {"node": node_label, "status": "warning", "exists": None, "message": "서버 상세 정보를 확인하지 못했습니다.", "error": node.get("_detail_error")}
        if node.get("is_local_master"):
            status = _image_exists(ref)
            return {"node": node_label, "status": "ok" if status["exists"] else "missing", **status}
        try:
            result = nodes_model._run_ssh_command(
                node,
                ["docker", "image", "inspect", ref, "--format", "{{json .}}"],
                timeout_seconds=8,
                env=env,
            )
        except Exception as exc:
            return {"node": node_label, "status": "warning", "exists": None, "message": str(exc)}
        if result.get("status") == "ok":
            return {"node": node_label, "status": "ok", "exists": True, "source": "node", "message": "서버 로컬 이미지 저장소에서 확인했습니다."}
        failure = ssh_executor.failure_reason(result)
        output = f"{result.get('stderr', '')}\n{result.get('stdout', '')}".lower()
        if "no such image" in output or "no such object" in output:
            if registry_status.get("exists") is True:
                return {"node": node_label, "status": "ok", "exists": False, "pull_possible": True, "source": registry_status.get("source"), "message": "서버에는 없지만 배포 중 자동으로 받을 수 있는 이미지입니다."}
            if registry_status.get("exists") is None:
                return {"node": node_label, "status": "warning", "exists": False, "pull_possible": None, "source": registry_status.get("source"), "message": "서버에는 없고 외부 저장소 접근 여부는 배포 중 확인됩니다."}
            return {"node": node_label, "status": "warning", "exists": False, "pull_possible": False, "source": registry_status.get("source"), "message": "서버와 공개 저장소에서 이미지를 확인하지 못했습니다."}
        return {"node": node_label, "status": "warning", "exists": None, "message": failure}

    def _check_images(self, validation, nodes=None, env=None):
        issues = []
        for service_name, service in ((validation.get("normalized") or {}).get("services") or {}).items():
            ref = str(service.get("image") or "").strip()
            status = _image_exists(ref)
            registry_status = _registry_pull_status(ref)
            node_checks = [self._node_image_status(node, ref, registry_status, env=env) for node in nodes or []]
            any_confirmed = status.get("exists") is True or any(item.get("exists") is True or item.get("pull_possible") is True for item in node_checks)
            uncertain = any(item.get("status") == "warning" for item in node_checks) or status.get("exists") is None
            level = "ok" if any_confirmed and not uncertain else ("warning" if any_confirmed or status.get("exists") is None else "error")
            message = f"{service_name}: {status['message']}"
            if node_checks:
                if level == "ok":
                    message = f"{service_name}: 이미지가 배포 서버에서 사용 가능한지 확인했습니다."
                elif level == "warning":
                    message = f"{service_name}: 일부 서버에서는 배포 중 이미지 pull 확인이 필요합니다."
                else:
                    message = f"{service_name}: 사용할 이미지를 찾지 못했습니다. 이미지 이름과 버전을 확인해주세요."
            issues.append(_item(f"image.{service_name}", "이미지 확인", level, message, [{"image": ref, **status, "registry": registry_status, "nodes": node_checks}]))
        return issues

    def _check_volumes(self, validation, namespace):
        compose = validation.get("normalized") or {}
        issues = []
        details = []
        for service_name, service in (compose.get("services") or {}).items():
            targets = set()
            for volume in _service_volumes(service):
                source = volume["source"]
                target = volume["target"]
                if target and not target.startswith("/"):
                    issues.append(_item("volume.target", "데이터 보관", "error", f"{service_name}의 저장 경로는 /로 시작해야 합니다."))
                if target in targets:
                    issues.append(_item("volume.duplicate_target", "데이터 보관", "error", f"{service_name} 안에서 같은 저장 경로가 두 번 연결됩니다."))
                targets.add(target)
                if source and not source.startswith("/") and VOLUME_RE.match(source) is None:
                    issues.append(_item("volume.name", "데이터 보관", "error", f"{source} 볼륨 이름은 사용할 수 없습니다."))
                if source and not source.startswith("/"):
                    details.append({"service": service_name, "volume": source, "docker_name": f"{namespace}_{source}"})
        if issues:
            return issues
        return [_item("volumes", "데이터 보관", "ok", "볼륨 이름과 컨테이너 저장 경로를 확인했습니다.", details)]

    def _remote_port_usage(self, node, ports, env=None):
        if node.get("is_local_master") or not ports:
            return {"node": self._node_label(node), "used": [], "status": "skipped" if node.get("is_local_master") else "ok"}
        script = (
            "import json,socket,sys\n"
            "used=[]\n"
            "for raw in sys.argv[1:]:\n"
            "    p=int(raw)\n"
            "    s=socket.socket(socket.AF_INET,socket.SOCK_STREAM)\n"
            "    s.setsockopt(socket.SOL_SOCKET,socket.SO_REUSEADDR,1)\n"
            "    try:\n"
            "        s.bind(('0.0.0.0',p))\n"
            "    except OSError:\n"
            "        used.append(p)\n"
            "    finally:\n"
            "        s.close()\n"
            "print(json.dumps(used))\n"
        )
        try:
            result = nodes_model._run_ssh_command(node, ["python3", "-c", script, *[str(port) for port in ports]], timeout_seconds=8, env=env)
        except Exception as exc:
            return {"node": self._node_label(node), "status": "warning", "message": str(exc), "used": []}
        if result.get("status") != "ok":
            return {"node": self._node_label(node), "status": "warning", "message": ssh_executor.failure_reason(result), "used": []}
        try:
            used = json.loads(result.get("stdout") or "[]")
        except Exception:
            used = []
        return {"node": self._node_label(node), "status": "ok", "used": used}

    def _check_ports(self, content, nodes=None, env=None):
        try:
            plan = service_ports.preview_content(content)
        except Exception as exc:
            return [_item("ports", "포트 자동 조정", "error", f"포트 사용 여부를 확인할 수 없습니다. {exc}")]
        items = []
        changed = [item for item in plan.get("allocations") or [] if item.get("previous") != item.get("published")]
        if changed:
            items.append(_item("ports", "포트 자동 조정", "adjusted", "이미 사용 중인 포트가 있어 저장/배포 시 다음 사용 가능한 포트로 조정합니다.", changed))
        else:
            items.append(_item("ports", "포트 자동 조정", "ok", "현재 공개 포트는 바로 사용할 수 있습니다.", plan.get("allocations") or []))
        published_ports = sorted({int(item.get("published") or 0) for item in plan.get("allocations") or [] if int(item.get("published") or 0) > 0})
        remote_checks = [self._remote_port_usage(node, published_ports, env=env) for node in nodes or [] if not node.get("is_local_master")]
        remote_used = [item for item in remote_checks if item.get("used")]
        remote_unknown = [item for item in remote_checks if item.get("status") == "warning"]
        if remote_used:
            items.append(_item("ports.remote", "다른 서버 포트", "warning", "다른 서버에서 이미 사용 중인 공개 포트가 있습니다. 배포 시 실행 서버 기준으로 조정이 필요할 수 있습니다.", remote_used))
        elif remote_unknown:
            items.append(_item("ports.remote", "다른 서버 포트", "warning", "일부 서버의 포트 상태를 확인하지 못했습니다. 배포 단계에서 다시 확인합니다.", remote_unknown))
        elif remote_checks:
            items.append(_item("ports.remote", "다른 서버 포트", "ok", "등록된 다른 서버에서도 공개 포트를 사용할 수 있습니다.", remote_checks))
        return items

    def _check_domain(self, payload, validation, domains, env=None):
        domains = domains if isinstance(domains, list) else ([{"domain": domains}] if domains else [])
        if not domains:
            return [_item("domain", "도메인 연결", "ok", "도메인을 사용하지 않는 서비스로 저장합니다.")]
        issues = []
        details = []
        nginx = webserver.nginx_defaults()
        for item in domains:
            item = item or {}
            domain = str((item or {}).get("domain") or "").strip().lower()
            if not domain:
                continue
            if DOMAIN_RE.match(domain) is None:
                issues.append(_item("domain.format", "도메인 연결", "error", f"{domain} 도메인 형식이 올바르지 않습니다."))
                continue
            metadata = dict(item.get("metadata") or {})
            zone_id = item.get("zone_id") or payload.get("zone_id") or metadata.get("zone_id")
            ddns_endpoint_id = metadata.get("ddns_endpoint_id") or (zone_id if not metadata.get("zone_id") else None)
            ddns_endpoint = None
            if metadata.get("routing_provider") == "ddns" or metadata.get("dns_provider") == "ddns" or ddns_endpoint_id:
                ddns_endpoint = ddns_model.match_domain(domain, endpoint_id=ddns_endpoint_id, env=env)
            elif not zone_id:
                ddns_endpoint = ddns_model.match_domain(domain, env=env)
            ddns_requested = metadata.get("routing_provider") == "ddns" or metadata.get("dns_provider") == "ddns" or bool(metadata.get("ddns_endpoint_id"))
            if ddns_requested and not ddns_endpoint:
                issues.append(_item("domain.ddns.endpoint", "DDNS 도메인", "error", f"{domain} 도메인을 처리할 DDNS 관리 서버를 찾을 수 없습니다."))
                continue
            dns_provider = ""
            external_proxy = ""
            ssl_mode = ""
            if ddns_endpoint:
                dns_provider = "ddns"
                external_proxy = "ddns_management"
            certs = webserver.certificates_for_domain(domain, zone_id=None if ddns_endpoint else ((item or {}).get("zone_id") or payload.get("zone_id")), env=env)
            ssl_mode = "existing" if int((certs.get("summary") or {}).get("valid") or 0) > 0 else "certbot"
            if ssl_mode == "certbot" and shutil.which("certbot") is None:
                issues.append(_item("domain.certbot", "SSL 인증서", "warning", f"{domain} 인증서가 없어 무료 인증서 발급 대상입니다. certbot 설치 여부는 배포 단계에서 다시 확인합니다."))
            if nginx.get("installed") is not True:
                issues.append(_item("nginx.installed", "nginx 설정", "warning", "nginx가 아직 설치되어 있지 않습니다. 배포 전에 설치가 필요합니다."))
            safe_domain = re.sub(r"[^A-Za-z0-9_.-]+", "-", domain).strip(".-")
            config_path = Path(nginx.get("available_site_path") or "/etc/nginx/sites-available") / f"docker-infra-{safe_domain}.conf"
            if config_path.exists():
                issues.append(_item("nginx.config", "nginx 설정", "warning", f"{domain} nginx 설정 파일이 이미 있습니다. 배포 시 Docker Infra 관리 설정인지 확인합니다.", [{"path": str(config_path)}]))
            detail = {"domain": domain, "routing_provider": "nginx", "ssl_mode": ssl_mode, "config_path": str(config_path)}
            if ddns_endpoint:
                detail.update({
                    "dns_provider": dns_provider,
                    "ddns_mode": external_proxy,
                    "endpoint_id": str(ddns_endpoint["id"]),
                    "endpoint": ddns_endpoint.get("domain_suffix"),
                    "api_base_url": ddns_endpoint.get("api_base_url"),
                })
            details.append(detail)
        if issues:
            return issues
        if details and all(item.get("dns_provider") == "ddns" for item in details):
            return [_item("domain", "DDNS 도메인", "ok", "DDNS 관리 서버 등록과 로컬 nginx 연결 대상 도메인을 확인했습니다.", details)]
        return [_item("domain", "도메인 연결", "ok", "도메인 중복과 연결 방식을 확인했습니다.", details)]

    def check(self, payload, content, namespace, validation=None, env=None):
        payload = payload or {}
        domains = self._domain_entries(payload)
        service_id = payload.get("service_id")
        validation = validation or validator.validate({"namespace": namespace, "filename": "docker-compose.yaml", "content": content})
        candidate_nodes = self._candidate_nodes(payload, env=env)
        try:
            placement_recommendation = placement_selector.recommend(payload, env=env)
        except Exception:
            placement_recommendation = None
        items = []
        items.extend(self._check_database(namespace, domains, service_id=service_id, env=env))
        items.extend(self._check_compose(validation, namespace))
        items.extend(self._check_placement(candidate_nodes, recommendation=placement_recommendation))
        items.extend(self._check_images(validation, nodes=candidate_nodes, env=env))
        items.extend(self._check_volumes(validation, namespace))
        items.extend(self._check_ports(content, nodes=candidate_nodes, env=env))
        items.extend(self._check_domain(payload, validation, domains, env=env))
        blocking = [item for item in items if item["status"] == "error"]
        warnings = [item for item in items if item["status"] in {"warning", "adjusted"}]
        return {
            "ok": len(blocking) == 0,
            "items": items,
            "blocking": blocking,
            "warnings": warnings,
            "summary": {
                "total": len(items),
                "blocking": len(blocking),
                "warnings": len(warnings),
                "passed": len([item for item in items if item["status"] == "ok"]),
            },
        }


Model = ServicesPreflight()
