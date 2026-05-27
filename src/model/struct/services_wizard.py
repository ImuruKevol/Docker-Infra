import json
import re
import subprocess
import urllib.parse
import urllib.request
import uuid
import hashlib
from pathlib import PurePosixPath

import yaml


connect = wiz.model("db/postgres").connect
services = wiz.model("struct/services")
webserver = wiz.model("struct/webserver")
ddns_model = wiz.model("struct/domains_ddns")
validator = wiz.model("struct/compose_validator")
preflight_model = wiz.model("struct/services_preflight")

DOCKER_SEARCH_TIMEOUT_SECONDS = 8
DOCKER_HUB_TIMEOUT_SECONDS = 8
DOCKER_SEARCH_LIMIT = 5
IMAGE_TAG_FALLBACKS = ["latest", "stable", "alpine", "slim", "bookworm", "bullseye", "lts"]


def _normalize(value):
    return re.sub(r"_+", "_", re.sub(r"[^a-z0-9_]+", "_", str(value or "").strip().lower())).strip("_")


def _safe_int(value, fallback=0):
    try:
        return int(value)
    except Exception:
        return fallback


def _split_image(ref):
    clean = str(ref or "nginx:alpine").strip()
    digest = clean.find("@")
    if digest > 0:
        return clean[:digest], clean[digest + 1:]
    slash = clean.rfind("/")
    colon = clean.rfind(":")
    if colon > slash:
        return clean[:colon], clean[colon + 1:] or "latest"
    return clean, "latest"


def _image_ref(component):
    name = str(component.get("image_name") or component.get("image") or "nginx").strip()
    tag = str(component.get("image_tag") or "latest").strip()
    return f"{name}@{tag}" if tag.startswith("sha256:") else f"{name}:{tag}"


def _docker_hub_repository(name):
    name = str(name or "").strip()
    if not name:
        return None
    first = name.split("/", 1)[0]
    if "/" in name and ("." in first or ":" in first or first == "localhost"):
        return None
    return f"library/{name}" if "/" not in name else name


def _image_ref_from_name_tag(name, tag):
    tag = str(tag or "latest").strip() or "latest"
    return f"{name}@{tag}" if tag.startswith("sha256:") else f"{name}:{tag}"


def _parse_ports(ports):
    result = []
    for item in ports or []:
        protocol = "tcp"
        published = ""
        target = ""
        if isinstance(item, dict):
            target = str(item.get("target") or "").strip()
            published = str(item.get("published") or "").strip()
            protocol = str(item.get("protocol") or "tcp").strip()
        else:
            raw = str(item).strip().strip('"')
            base, _, protocol = raw.partition("/")
            chunks = base.split(":")
            target = chunks[-1] if chunks else ""
            published = chunks[-2] if len(chunks) >= 2 else target
        if target:
            result.append({"target": int(target), "published": int(published or target), "protocol": protocol or "tcp"})
    return result


def _environment(service):
    env = service.get("environment") or {}
    if isinstance(env, dict):
        return [{"key": str(key), "value": str(value)} for key, value in env.items()]
    result = []
    for item in env if isinstance(env, list) else []:
        key, _, value = str(item).partition("=")
        if key:
            result.append({"key": key, "value": value})
    return result


def _volumes(service):
    result = []
    for item in service.get("volumes") or []:
        raw = str(item)
        source, _, target = raw.partition(":")
        if source and target:
            result.append({"source": source, "target": target})
    return result


def _rewrite_internal_service_ref(value, namespace, service_names):
    text = str(value if value is not None else "")
    namespace = str(namespace or "").strip()
    if not namespace:
        return text
    if "{{ namespace }}" in text:
        text = text.replace("{{ namespace }}", namespace)
    for service_name in sorted([str(item) for item in service_names if str(item)], key=len, reverse=True):
        pattern = re.compile(rf"^[a-z0-9_]+_{re.escape(service_name)}(?=(:|$))")
        if pattern.search(text):
            return pattern.sub(f"{namespace}_{service_name}", text, count=1)
    return text


def _suggest_import_name(payload):
    payload = payload or {}
    for key in ["suggested_name", "name", "service_name", "suggested_namespace"]:
        value = str(payload.get(key) or "").strip()
        if value:
            return value
    source_path = str(payload.get("source_path") or payload.get("path") or "").strip()
    if source_path:
        path = PurePosixPath(source_path)
        if path.parent.name:
            return path.parent.name
        stem = path.stem.replace("docker-compose", "").strip("-_.")
        if stem:
            return stem
    return "가져온 서비스"


class ServicesWizard:
    ServiceError = services.ServiceError
    ComposeValidationError = validator.ComposeValidationError

    def _is_import_source(self, body):
        return bool(body.get("import_source")) or body.get("source") in {"server_compose_import", "server_compose_import_wizard"}

    def _is_template_source(self, body):
        source_ref = body.get("source_ref") if isinstance(body.get("source_ref"), dict) else {}
        draft_metadata = body.get("draft_metadata") if isinstance(body.get("draft_metadata"), dict) else {}
        return body.get("source") == "compose_template" or source_ref.get("source") == "compose_template" or draft_metadata.get("source") == "compose_template"

    def _require_base_content_source(self, body):
        if str(body.get("base_content") or "").strip():
            return
        raise services.ServiceError(
            400,
            "서비스 초안을 먼저 작성해주세요.",
            "SERVICE_DRAFT_REQUIRED",
        )

    def _require_base_content(self, body):
        if str(body.get("base_content") or "").strip():
            return
        raise services.ServiceError(
            400,
            "서비스 초안을 먼저 작성해주세요.",
            "SERVICE_DRAFT_CONTENT_REQUIRED",
        )

    def prepare_manual(self, payload, env=None):
        body = payload or {}
        content = str(body.get("content") or body.get("base_content") or "")
        if not content.strip():
            raise services.ServiceError(400, "Compose 내용을 입력해주세요.", "COMPOSE_CONTENT_REQUIRED")
        filename = str(body.get("filename") or "docker-compose.yaml").split("/")[-1] or "docker-compose.yaml"
        suggested_name = str(body.get("suggested_name") or body.get("name") or "직접 작성 서비스").strip()
        namespace = _normalize(suggested_name) or "manual_service"
        validation = validator.validate({
            "namespace": namespace,
            "filename": filename,
            "content": content,
            "allow_warnings": True,
            "warning_codes": ["FORBIDDEN_CONTAINER_NAME"],
        })
        components = self.components_from_content(content)
        checksum = hashlib.sha256(content.encode("utf-8")).hexdigest()
        return {
            "filename": filename,
            "content": content,
            "components": components,
            "suggested_name": suggested_name,
            "source": "manual_compose",
            "source_ref": {
                "source": "manual_compose",
                "filename": filename,
                "checksum": checksum,
            },
            "warnings": validation.get("warnings") or [],
            "summary": {
                "services": len(components),
                "ports": sum(len(item.get("ports") or []) for item in components),
            },
        }

    def _unique_namespace(self, name, env=None):
        base = _normalize(name) or "service"
        with connect(env=env) as connection:
            with connection.cursor() as cursor:
                for _ in range(20):
                    candidate = f"{base}_{uuid.uuid4().hex[:6]}"
                    cursor.execute("SELECT 1 FROM services WHERE namespace = %s LIMIT 1", (candidate,))
                    if cursor.fetchone() is None:
                        return candidate
        return f"{base}_{uuid.uuid4().hex[:10]}"

    def _create_session_id(self, body):
        body = body or {}
        candidates = [body.get("create_session_id")]
        for key in ["source_ref", "draft_metadata"]:
            value = body.get(key)
            if isinstance(value, dict):
                candidates.append(value.get("create_session_id"))
        for value in candidates:
            clean = str(value or "").strip()
            if clean:
                return clean[:120]
        return ""

    def _existing_create_session(self, create_session_id, env=None):
        if not create_session_id:
            return None
        with connect(env=env) as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT id
                    FROM services
                    WHERE metadata->'source_ref'->>'create_session_id' = %s
                       OR metadata->'draft'->>'create_session_id' = %s
                       OR metadata->'wizard'->>'create_session_id' = %s
                    ORDER BY created_at DESC
                    LIMIT 1
                    """,
                    (create_session_id, create_session_id, create_session_id),
                )
                row = cursor.fetchone()
        if row is None:
            return None
        try:
            return (services.detail(row["id"], env=env) or {}).get("service")
        except Exception:
            return None

    def default_content(self):
        service_key = f"svc_{uuid.uuid4().hex[:8]}"
        compose = {
            "services": {
                service_key: {
                    "image": "nginx:alpine",
                    "ports": ["80:80"],
                    "healthcheck": {
                        "test": ["CMD", "wget", "-qO-", "http://127.0.0.1:80"],
                        "interval": "30s",
                        "timeout": "5s",
                        "retries": 3,
                    },
                }
            }
        }
        return yaml.safe_dump(compose, sort_keys=False, allow_unicode=False)

    def components_from_content(self, content, metadata=None):
        metadata = metadata or {}
        labels = metadata.get("component_labels") or {}
        public_endpoint = metadata.get("public_endpoint") or {}
        public_service = str(public_endpoint.get("service") or "").strip()
        try:
            public_port = int(public_endpoint.get("port") or 0)
        except Exception:
            public_port = 0
        compose = yaml.safe_load(content or "{}") or {}
        result = []
        for index, (key, service) in enumerate((compose.get("services") or {}).items(), start=1):
            service = service if isinstance(service, dict) else {}
            image_name, image_tag = _split_image(service.get("image"))
            ports = _parse_ports(service.get("ports") or [])
            is_public = public_service == str(key)
            for port in ports:
                port["public_endpoint"] = bool(is_public and (public_port <= 0 or int(port.get("target") or 0) == public_port))
            result.append({
                "key": key,
                "label": labels.get(key) or (public_endpoint.get("label") if is_public else "") or f"구성 {index}",
                "role": "public" if is_public else "internal",
                "image_name": image_name,
                "image_tag": image_tag,
                "ports": ports,
                "env_vars": _environment(service),
                "volumes": _volumes(service),
            })
        return result

    def prepare_import(self, payload, env=None):
        body = payload or {}
        content = str(body.get("content") or "")
        if not content.strip():
            raise services.ServiceError(400, "Compose 파일 내용이 필요합니다.", "COMPOSE_CONTENT_REQUIRED")
        filename = str(body.get("filename") or "docker-compose.yaml").split("/")[-1] or "docker-compose.yaml"
        source_path = str(body.get("source_path") or body.get("path") or "").strip()
        suggested_name = _suggest_import_name(body)
        namespace = _normalize(suggested_name) or "imported_service"
        validation = validator.validate({
            "namespace": namespace,
            "filename": filename,
            "content": content,
            "allow_warnings": True,
            "warning_codes": ["FORBIDDEN_CONTAINER_NAME"],
        })
        components = self.components_from_content(content)
        return {
            "filename": filename,
            "content": content,
            "components": components,
            "suggested_name": suggested_name,
            "source": "server_compose_import",
            "source_ref": {
                "source": "server_compose_import",
                "node_id": body.get("node_id"),
                "path": source_path,
                "filename": filename,
            },
            "warnings": validation.get("warnings") or [],
            "summary": {
                "services": len(components),
                "ports": sum(len(item.get("ports") or []) for item in components),
            },
        }

    def _domain_port_selection(self, payload):
        payload = payload or {}
        selected_key = str(payload.get("domain_target_key") or "").strip()
        selected_port = int(payload.get("domain_target_port") or 0)
        fallback = None
        for component in payload.get("components") or []:
            service_key = str(component.get("key") or "").strip()
            for port in component.get("ports") or []:
                target = int(port.get("target") or 0)
                if target <= 0:
                    continue
                published = int(port.get("published") or target)
                candidate = {
                    "compose_service": service_key,
                    "target_port": target,
                    "published_port": published,
                    "protocol": str(port.get("protocol") or "tcp"),
                }
                if fallback is None:
                    fallback = candidate
                if selected_key == f"{service_key}:{target}" or selected_port == target:
                    return candidate
        return fallback or {
            "compose_service": "",
            "target_port": selected_port or 80,
            "published_port": selected_port or 80,
            "protocol": "tcp",
        }

    def _domain_entries(self, body, env=None):
        body = body or {}
        raw_domains = body.get("domains") if isinstance(body.get("domains"), list) else []
        entries = []
        for item in raw_domains:
            if not isinstance(item, dict):
                continue
            domain = str(item.get("domain") or "").strip().lower()
            if not domain:
                continue
            target_key = str(item.get("domain_target_key") or item.get("target_key") or body.get("domain_target_key") or "").strip()
            target_port = _safe_int(item.get("domain_target_port") or item.get("target_port") or item.get("port") or body.get("domain_target_port"), 80)
            metadata = dict(item.get("metadata") or {})
            metadata.update({
                "source": metadata.get("source") or "service_wizard",
                "compose_service": item.get("compose_service") or item.get("service_key") or target_key.split(":", 1)[0],
                "target_port": target_port,
                "published_port": _safe_int(item.get("published_port") or target_port, target_port),
            })
            zone_id = item.get("zone_id") or body.get("zone_id") or metadata.get("zone_id")
            normalized = ddns_model.normalize_service_domain(
                domain,
                endpoint_id=zone_id,
                prefix=item.get("domain_prefix") or item.get("prefix") or body.get("domain_prefix") or metadata.get("domain_prefix"),
                fallback_prefix=body.get("name") or body.get("namespace") or metadata.get("compose_service"),
                env=env,
            )
            domain = normalized.get("domain") or domain
            ddns_endpoint = normalized.get("endpoint") or (ddns_model.match_domain(domain, endpoint_id=zone_id, env=env) if zone_id else ddns_model.match_domain(domain, env=env))
            if ddns_endpoint:
                metadata.pop("zone_id", None)
                metadata.update({
                    "dns_provider": "ddns",
                    "routing_provider": "nginx",
                    "ddns_endpoint_id": str(ddns_endpoint["id"]),
                    "ddns_domain_suffix": ddns_endpoint.get("domain_suffix"),
                    "domain_prefix": normalized.get("prefix"),
                    "ddns_mode": "ddns_management",
                })
            elif zone_id:
                metadata["zone_id"] = zone_id
            ssl_mode = str(item.get("ssl_mode") or "").strip()
            if not ssl_mode:
                ssl_info = webserver.certificates_for_domain(domain, zone_id=None if ddns_endpoint else zone_id, env=env)
                ssl_mode = "existing" if int((ssl_info.get("summary") or {}).get("valid") or 0) > 0 else "certbot"
            entries.append({"domain": domain, "port": target_port, "ssl_mode": ssl_mode, "metadata": metadata})
        if not entries and str(body.get("domain") or "").strip():
            domain = str(body.get("domain") or "").strip().lower()
            selection = self._domain_port_selection(body)
            port = int(selection.get("target_port") or body.get("domain_target_port") or 80)
            metadata = dict(body.get("domain_metadata") or {})
            metadata.update(selection)
            metadata["source"] = metadata.get("source") or "service_wizard"
            zone_id = body.get("zone_id") or metadata.get("zone_id")
            normalized = ddns_model.normalize_service_domain(
                domain,
                endpoint_id=zone_id,
                prefix=body.get("domain_prefix") or metadata.get("domain_prefix"),
                fallback_prefix=body.get("name") or body.get("namespace") or metadata.get("compose_service"),
                env=env,
            )
            domain = normalized.get("domain") or domain
            ddns_endpoint = normalized.get("endpoint") or (ddns_model.match_domain(domain, endpoint_id=zone_id, env=env) if zone_id else ddns_model.match_domain(domain, env=env))
            if ddns_endpoint:
                metadata.pop("zone_id", None)
                metadata.update({
                    "dns_provider": "ddns",
                    "routing_provider": "nginx",
                    "ddns_endpoint_id": str(ddns_endpoint["id"]),
                    "ddns_domain_suffix": ddns_endpoint.get("domain_suffix"),
                    "domain_prefix": normalized.get("prefix"),
                    "ddns_mode": "ddns_management",
                })
            elif zone_id:
                metadata["zone_id"] = zone_id
            ssl_info = webserver.certificates_for_domain(domain, zone_id=None if ddns_endpoint else zone_id, env=env)
            ssl_mode = "existing" if int((ssl_info.get("summary") or {}).get("valid") or 0) > 0 else "certbot"
            entries.append({"domain": domain, "port": port, "ssl_mode": ssl_mode, "metadata": metadata})
        deduped = []
        seen = set()
        for item in entries:
            key = item["domain"].lower()
            if key in seen:
                continue
            seen.add(key)
            deduped.append(item)
        return deduped

    def render(self, payload, namespace=None):
        body = payload or {}
        compose = yaml.safe_load(body.get("base_content") or self.default_content()) or {}
        services_map = compose.setdefault("services", {})
        service_names = set(services_map.keys())
        for index, component in enumerate(body.get("components") or [], start=1):
            key = str(component.get("key") or f"svc_{index}").strip()
            service = services_map.setdefault(key, {})
            service_names.add(key)
            service.pop("container_name", None)
            service.pop("hostname", None)
            service["image"] = _image_ref(component)
            ports = []
            for port in component.get("ports") or []:
                target = int(port.get("target") or 0)
                if target > 0:
                    published = int(port.get("published") or target)
                    protocol = str(port.get("protocol") or "tcp")
                    ports.append({
                        "target": target,
                        "published": published,
                        "protocol": protocol,
                        "mode": "host",
                    })
            if ports:
                service["ports"] = ports
            else:
                service.pop("ports", None)
            env_vars = {
                str(item.get("key")).strip(): _rewrite_internal_service_ref(item.get("value"), namespace, service_names)
                for item in component.get("env_vars") or []
                if str(item.get("key") or "").strip()
            }
            if env_vars:
                service["environment"] = env_vars
            else:
                service.pop("environment", None)
            volumes = [f"{item.get('source')}:{item.get('target')}" for item in component.get("volumes") or [] if item.get("source") and item.get("target")]
            if volumes:
                service["volumes"] = volumes
            else:
                service.pop("volumes", None)
        content = yaml.safe_dump(compose, sort_keys=False, allow_unicode=False)
        return _rewrite_internal_service_ref(content, namespace, service_names)

    def _validation_options(self, body):
        if self._is_import_source(body) or self._is_template_source(body):
            return {
                "allow_warnings": True,
                "warning_codes": ["FORBIDDEN_CONTAINER_NAME"],
            }
        return {}

    def preflight(self, payload, env=None):
        body = payload or {}
        self._require_base_content_source(body)
        self._require_base_content(body)
        name = str(body.get("name") or "").strip()
        if not name:
            raise services.ServiceError(400, "서비스 이름을 입력해주세요.", "SERVICE_NAME_REQUIRED")
        namespace = str(body.get("namespace") or "").strip() or self._unique_namespace(name, env=env)
        content = self.render(body, namespace=namespace)
        validation_options = self._validation_options(body)
        validation = validator.validate({
            "namespace": namespace,
            "filename": body.get("filename") or "docker-compose.yaml",
            "content": content,
            **validation_options,
        })
        domain_entries = self._domain_entries(body, env=env)
        return {
            "namespace": namespace,
            "content": content,
            "validation": validation,
            "preflight": preflight_model.check({**body, "domains": domain_entries or body.get("domains") or []}, content, namespace, validation=validation, env=env),
        }

    def create(self, payload, env=None):
        body = payload or {}
        self._require_base_content_source(body)
        self._require_base_content(body)
        name = str(body.get("name") or "").strip()
        if not name:
            raise services.ServiceError(400, "서비스 이름을 입력해주세요.", "SERVICE_NAME_REQUIRED")
        create_session_id = self._create_session_id(body)
        existing = self._existing_create_session(create_session_id, env=env)
        if existing:
            return {"service": existing, "idempotent_reuse": True}
        namespace = self._unique_namespace(name, env=env)
        content = self.render(body, namespace=namespace)
        domain_entries = self._domain_entries(body, env=env)
        primary_domain = domain_entries[0] if domain_entries else {}
        domain = primary_domain.get("domain") or ""
        port = int(primary_domain.get("port") or body.get("domain_target_port") or 80)
        ssl_mode = primary_domain.get("ssl_mode") or "none"
        validation_options = self._validation_options(body)
        validation = validator.validate({
            "namespace": namespace,
            "filename": body.get("filename") or "docker-compose.yaml",
            "content": content,
            **validation_options,
        })
        preflight = preflight_model.check({**body, "domains": domain_entries or body.get("domains") or []}, content, namespace, validation=validation, env=env)
        if preflight.get("ok") is not True:
            raise services.ServiceError(
                409,
                "서비스를 만들기 전에 해결해야 할 항목이 있습니다.",
                "SERVICE_PREFLIGHT_BLOCKED",
                preflight=preflight,
            )
        generated_secret_keys = [str(key) for key in body.get("generated_secret_keys") or [] if str(key)]
        wizard_metadata = {
            "components": body.get("components") or [],
            "domain_mode": body.get("domain_mode"),
            "domains": domain_entries,
            "import_source": body.get("import_source"),
        }
        if create_session_id:
            wizard_metadata["create_session_id"] = create_session_id
        source = body.get("source") or ("server_compose_import" if self._is_import_source(body) else "manual_compose")
        draft_metadata = body.get("draft_metadata") if isinstance(body.get("draft_metadata"), dict) else {}
        if draft_metadata:
            draft_metadata = {
                **draft_metadata,
                "source": draft_metadata.get("source") or body.get("source") or source,
            }
        if create_session_id:
            draft_metadata = {**draft_metadata, "create_session_id": create_session_id}
        if generated_secret_keys:
            wizard_metadata["generated_secret_keys"] = generated_secret_keys
            wizard_metadata["secret_strategy"] = "runtime_generated"
        if draft_metadata and not draft_metadata.get("source"):
            draft_metadata["source"] = source
        source_ref = body.get("source_ref") or body.get("import_source") or {"source": source, "wizard": "services.create"}
        if create_session_id and isinstance(source_ref, dict):
            source_ref = {**source_ref, "create_session_id": create_session_id}
        if generated_secret_keys and isinstance(source_ref, dict):
            source_ref = {**source_ref, "generated_secret_keys": generated_secret_keys}
        return services.create({
            "namespace": namespace,
            "name": name,
            "description": body.get("description"),
            "filename": "docker-compose.yaml",
            "content": content,
            "domain": domain,
            "domains": domain_entries,
            "port": port,
            "ssl_mode": ssl_mode,
            "test_run_id": body.get("test_run_id"),
            "source": source,
            "source_ref": source_ref,
            "draft_metadata": draft_metadata,
            "domain_metadata": primary_domain.get("metadata") or {},
            "wizard": wizard_metadata,
        }, env=env, validation=validation)

    def check_image(self, image_ref):
        ref = str(image_ref or "").strip()
        if not ref:
            return {"exists": False, "source": "none", "message": "이미지 이름이 비어 있습니다."}
        try:
            local = subprocess.run(["docker", "image", "inspect", ref], capture_output=True, text=True, timeout=8, check=False)
            if local.returncode == 0:
                return {"exists": True, "source": "local", "message": "로컬 이미지 저장소에서 확인했습니다."}
        except Exception:
            pass
        name, tag = _split_image(ref)
        if "/" not in name:
            repository = f"library/{name}"
        else:
            first = name.split("/", 1)[0]
            if "." in first or ":" in first or first == "localhost":
                return {"exists": None, "source": "registry", "message": "외부 registry 이미지는 배포 시 pull 결과로 확인합니다."}
            repository = name
        try:
            token_url = f"https://auth.docker.io/token?service=registry.docker.io&scope=repository:{repository}:pull"
            token = json.loads(urllib.request.urlopen(token_url, timeout=8).read().decode("utf-8"))["token"]
            request = urllib.request.Request(
                f"https://registry-1.docker.io/v2/{repository}/manifests/{tag}",
                headers={"Authorization": f"Bearer {token}", "Accept": "application/vnd.docker.distribution.manifest.v2+json"},
                method="HEAD",
            )
            urllib.request.urlopen(request, timeout=8).close()
            return {"exists": True, "source": "docker_hub", "message": "Docker Hub에서 이미지를 확인했습니다."}
        except Exception:
            return {"exists": False, "source": "docker_hub", "message": "로컬 저장소와 Docker Hub에서 이미지를 찾지 못했습니다."}

    def search_image_candidates(self, query, limit=DOCKER_SEARCH_LIMIT):
        query = str(query or "").strip()
        if not query:
            return []
        try:
            completed = subprocess.run(
                [
                    "docker",
                    "search",
                    "--no-trunc",
                    "--limit",
                    str(max(1, min(int(limit or DOCKER_SEARCH_LIMIT), 25))),
                    "--format",
                    "{{json .}}",
                    query,
                ],
                capture_output=True,
                text=True,
                timeout=DOCKER_SEARCH_TIMEOUT_SECONDS,
                check=False,
            )
        except Exception as exc:
            return [{"query": query, "error": str(exc), "source": "docker_search"}]
        if completed.returncode != 0:
            message = (completed.stderr or completed.stdout or "docker search failed").strip()
            return [{"query": query, "error": message[:500], "source": "docker_search"}]
        rows = []
        for line in (completed.stdout or "").splitlines():
            try:
                item = json.loads(line)
            except Exception:
                continue
            name = str(item.get("Name") or item.get("name") or "").strip()
            if not name:
                continue
            rows.append(
                {
                    "name": name,
                    "description": str(item.get("Description") or item.get("description") or "").strip(),
                    "stars": str(item.get("StarCount") or item.get("stars") or "").strip(),
                    "official": str(item.get("IsOfficial") or item.get("official") or "").strip(),
                    "automated": str(item.get("IsAutomated") or item.get("automated") or "").strip(),
                    "source": "docker_search",
                }
            )
        return rows

    def _docker_hub_tags(self, repository, limit=50):
        repository = str(repository or "").strip()
        if not repository:
            return []
        query = urllib.parse.urlencode({"page_size": max(1, min(int(limit or 50), 100)), "ordering": "last_updated"})
        url = "https://hub.docker.com/v2/repositories/%s/tags?%s" % (urllib.parse.quote(repository, safe="/"), query)
        try:
            payload = json.loads(urllib.request.urlopen(url, timeout=DOCKER_HUB_TIMEOUT_SECONDS).read().decode("utf-8"))
        except Exception:
            return []
        result = []
        for item in payload.get("results") or []:
            tag = str(item.get("name") or "").strip()
            if tag:
                result.append(tag)
        return result

    def _candidate_image_tags(self, repository, requested_tag):
        seen = set()
        result = []

        def add(tag):
            tag = str(tag or "").strip()
            if not tag or tag in seen:
                return
            seen.add(tag)
            result.append(tag)

        add(requested_tag)
        for tag in IMAGE_TAG_FALLBACKS:
            add(tag)
        for tag in self._docker_hub_tags(repository):
            add(tag)
        return result[:20]

    def resolve_image_ref(self, image_ref, search_query=None):
        ref = str(image_ref or "").strip()
        status = self.check_image(ref)
        if not ref:
            return {"resolved": False, "image_ref": ref, "image_name": "", "image_tag": "", "status": status, "candidates": []}
        if status.get("exists") is not False:
            name, tag = _split_image(ref)
            return {"resolved": False, "image_ref": ref, "image_name": name, "image_tag": tag, "status": status, "candidates": []}

        name, tag = _split_image(ref)
        if tag.startswith("sha256:"):
            return {"resolved": False, "image_ref": ref, "image_name": name, "image_tag": tag, "status": status, "candidates": []}

        query = str(search_query or name.rsplit("/", 1)[-1] or name).strip()
        search_rows = self.search_image_candidates(query)
        candidate_names = []
        for candidate in [name, *[item.get("name") for item in search_rows if isinstance(item, dict)]]:
            candidate = str(candidate or "").strip()
            if candidate and candidate not in candidate_names:
                candidate_names.append(candidate)

        candidates = []
        for candidate_name in candidate_names[:DOCKER_SEARCH_LIMIT + 1]:
            repository = _docker_hub_repository(candidate_name)
            if not repository:
                continue
            tags = self._candidate_image_tags(repository, tag)
            for candidate_tag in tags:
                candidate_ref = _image_ref_from_name_tag(candidate_name, candidate_tag)
                candidate_status = self.check_image(candidate_ref)
                row = {
                    "image_ref": candidate_ref,
                    "image_name": candidate_name,
                    "image_tag": candidate_tag,
                    "status": candidate_status,
                    "source": "docker_search",
                }
                candidates.append(row)
                if candidate_status.get("exists") is True:
                    return {
                        "resolved": True,
                        "original": ref,
                        "image_ref": candidate_ref,
                        "image_name": candidate_name,
                        "image_tag": candidate_tag,
                        "status": candidate_status,
                        "source": "docker_search",
                        "query": query,
                        "search": search_rows,
                        "candidates": candidates[:10],
                    }
        return {
            "resolved": False,
            "original": ref,
            "image_ref": ref,
            "image_name": name,
            "image_tag": tag,
            "status": status,
            "query": query,
            "search": search_rows,
            "candidates": candidates[:10],
        }


Model = ServicesWizard()
