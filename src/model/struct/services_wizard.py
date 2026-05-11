import json
import re
import subprocess
import urllib.request
import uuid
import hashlib
from pathlib import PurePosixPath

import yaml


connect = wiz.model("db/postgres").connect
services = wiz.model("struct/services")
webserver = wiz.model("struct/webserver")
validator = wiz.model("struct/compose_validator")
preflight_model = wiz.model("struct/services_preflight")


def _normalize(value):
    return re.sub(r"_+", "_", re.sub(r"[^a-z0-9_]+", "_", str(value or "").strip().lower())).strip("_")


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
            "warning_codes": ["FORBIDDEN_CONTAINER_NAME", "HEALTHCHECK_REQUIRED"],
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
            "warning_codes": ["FORBIDDEN_CONTAINER_NAME", "HEALTHCHECK_REQUIRED"],
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
        if self._is_import_source(body):
            return {
                "allow_warnings": True,
                "warning_codes": ["FORBIDDEN_CONTAINER_NAME", "HEALTHCHECK_REQUIRED"],
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
        return {
            "namespace": namespace,
            "content": content,
            "validation": validation,
            "preflight": preflight_model.check(body, content, namespace, validation=validation, env=env),
        }

    def create(self, payload, env=None):
        body = payload or {}
        self._require_base_content_source(body)
        self._require_base_content(body)
        name = str(body.get("name") or "").strip()
        if not name:
            raise services.ServiceError(400, "서비스 이름을 입력해주세요.", "SERVICE_NAME_REQUIRED")
        namespace = self._unique_namespace(name, env=env)
        content = self.render(body, namespace=namespace)
        domain = str(body.get("domain") or "").strip()
        domain_selection = self._domain_port_selection(body)
        port = int(domain_selection.get("target_port") or body.get("domain_target_port") or 80)
        ssl_mode = "none"
        if domain:
            ssl_info = webserver.certificates_for_domain(domain, zone_id=body.get("zone_id"), env=env)
            ssl_mode = "existing" if int((ssl_info.get("summary") or {}).get("valid") or 0) > 0 else "certbot"
            domain_selection["zone_id"] = body.get("zone_id")
        validation_options = self._validation_options(body)
        validation = validator.validate({
            "namespace": namespace,
            "filename": body.get("filename") or "docker-compose.yaml",
            "content": content,
            **validation_options,
        })
        preflight = preflight_model.check(body, content, namespace, validation=validation, env=env)
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
            "import_source": body.get("import_source"),
        }
        source = body.get("source") or ("server_compose_import" if self._is_import_source(body) else "manual_compose")
        draft_metadata = body.get("draft_metadata") if isinstance(body.get("draft_metadata"), dict) else {}
        if draft_metadata:
            draft_metadata = {
                **draft_metadata,
                "source": draft_metadata.get("source") or body.get("source") or source,
            }
        if generated_secret_keys:
            wizard_metadata["generated_secret_keys"] = generated_secret_keys
            wizard_metadata["secret_strategy"] = "runtime_generated"
        if draft_metadata and not draft_metadata.get("source"):
            draft_metadata["source"] = source
        source_ref = body.get("source_ref") or body.get("import_source") or {"source": source, "wizard": "services.create"}
        if generated_secret_keys and isinstance(source_ref, dict):
            source_ref = {**source_ref, "generated_secret_keys": generated_secret_keys}
        return services.create({
            "namespace": namespace,
            "name": name,
            "description": body.get("description"),
            "filename": "docker-compose.yaml",
            "content": content,
            "domain": domain,
            "port": port,
            "ssl_mode": ssl_mode,
            "test_run_id": body.get("test_run_id"),
            "source": source,
            "source_ref": source_ref,
            "draft_metadata": draft_metadata,
            "domain_metadata": domain_selection,
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


Model = ServicesWizard()
