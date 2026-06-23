import base64
import datetime
import json
import shlex
import shutil
from pathlib import Path

import yaml
from psycopg.types.json import Jsonb


connect = wiz.model("db/postgres").connect
validator = wiz.model("struct/compose_validator")
compose_rules = wiz.model("struct/compose_rules")
preflight_model = wiz.model("struct/services_preflight")
webserver = wiz.model("struct/webserver")
ddns_model = wiz.model("struct/domains_ddns")
shared = wiz.model("struct/services_shared")
nodes = wiz.model("struct/nodes")
local_executor = wiz.model("struct/local_executor")
operations = wiz.model("struct/operations")
ServiceError = shared.ServiceError
_row = shared.row


def _safe_int(value, fallback):
    try:
        return int(value)
    except Exception:
        return fallback


def _history_id():
    return datetime.datetime.utcnow().strftime("%Y%m%d_%H%M%S")


def _truthy(value):
    if isinstance(value, bool):
        return value
    return str(value or "").strip().lower() in {"1", "true", "yes", "on"}


def _container_id_matches(actual, requested):
    actual = str(actual or "").strip()
    requested = str(requested or "").strip()
    if not actual or not requested:
        return False
    return actual == requested or actual.startswith(requested) or requested.startswith(actual)


def _split_image_ref(image_ref):
    raw = str(image_ref or "").strip()
    if not raw:
        return {"repository": "", "version": "", "digest": ""}
    without_digest = raw
    digest = ""
    if "@" in raw:
        without_digest, digest = raw.split("@", 1)
    repository = without_digest
    version = ""
    last_slash = without_digest.rfind("/")
    last_colon = without_digest.rfind(":")
    if last_colon > last_slash:
        repository = without_digest[:last_colon]
        version = without_digest[last_colon + 1:]
    if digest:
        version = digest
    return {"repository": repository.strip(), "version": version.strip() or "latest", "digest": digest.strip()}


def _validate_image_version(version):
    value = str(version or "").strip()
    if value.startswith("@sha256:"):
        value = value[1:]
    if not value:
        raise ServiceError(400, "변경할 버전을 입력해주세요.", "SERVICE_IMAGE_VERSION_REQUIRED")
    if any(ch.isspace() for ch in value):
        raise ServiceError(400, "이미지 버전에는 공백을 사용할 수 없습니다.", "SERVICE_IMAGE_VERSION_INVALID")
    if "/" in value or "@" in value:
        raise ServiceError(400, "이미지 이름이 아닌 tag 또는 sha256 digest만 입력해주세요.", "SERVICE_IMAGE_VERSION_INVALID")
    if value.startswith("sha256:"):
        digest = value.split(":", 1)[1]
        if len(digest) != 64 or any(ch not in "0123456789abcdefABCDEF" for ch in digest):
            raise ServiceError(400, "sha256 digest 형식이 올바르지 않습니다.", "SERVICE_IMAGE_DIGEST_INVALID")
        return value
    if ":" in value:
        raise ServiceError(400, "tag에는 ':' 문자를 사용할 수 없습니다. digest는 sha256:... 형식으로 입력해주세요.", "SERVICE_IMAGE_VERSION_INVALID")
    if len(value) > 128:
        raise ServiceError(400, "이미지 tag는 128자 이하여야 합니다.", "SERVICE_IMAGE_VERSION_INVALID")
    return value


def _image_ref_with_version(image_ref, version):
    parsed = _split_image_ref(image_ref)
    repository = parsed["repository"]
    if not repository:
        raise ServiceError(400, "이미지 이름을 확인할 수 없습니다.", "SERVICE_IMAGE_REPOSITORY_MISSING")
    if version.startswith("sha256:"):
        return f"{repository}@{version}"
    return f"{repository}:{version}"


def _image_ref_matches_target(actual_image, target_image):
    actual = str(actual_image or "").strip()
    target = str(target_image or "").strip()
    if not actual or not target:
        return False
    if actual == target:
        return True
    if "@" in actual and "@" not in target:
        return actual.split("@", 1)[0] == target
    return False


def _container_image_ref(*containers):
    for container in containers:
        if not isinstance(container, dict):
            continue
        value = str(container.get("image") or container.get("Image") or "").strip()
        if value and value != "<none>":
            return value
    return ""


def _swarm_service_name(stack_name, compose_service, container=None):
    labels = (container or {}).get("labels") if isinstance(container, dict) else {}
    if isinstance(labels, dict):
        label_name = str(labels.get("com.docker.swarm.service.name") or "").strip()
        if label_name:
            return label_name
    runtime_name = str((container or {}).get("runtime_service_name") or "").strip()
    if runtime_name and runtime_name.startswith(f"{stack_name}_"):
        return runtime_name
    service_name = str(compose_service or "").strip()
    if service_name.startswith(f"{stack_name}_"):
        return service_name
    return f"{stack_name}_{service_name}"


def _compose_service_from_container(container, stack_name, namespace, service_names):
    labels = container.get("labels") or {}
    if isinstance(labels, dict):
        label_service = str(labels.get("com.docker.compose.service") or "").strip()
        if label_service in service_names:
            return label_service
    candidates = []

    def push(value):
        text = str(value or "").strip().lstrip("/")
        if text and text not in candidates:
            candidates.append(text)

    push(container.get("runtime_service_name"))
    push(container.get("name"))
    for value in list(candidates):
        for prefix in [stack_name, namespace]:
            prefix = str(prefix or "").strip()
            if not prefix:
                continue
            for separator in ["_", "-", "."]:
                marker = f"{prefix}{separator}"
                if value.startswith(marker):
                    push(value[len(marker):])
    for value in candidates:
        if value in service_names:
            return value
    for service_name in service_names:
        for value in candidates:
            if value == service_name:
                return service_name
            if any(value.startswith(f"{prefix}{separator}{service_name}{separator}") for prefix in [stack_name, namespace] for separator in ["_", "-", "."] if prefix):
                return service_name
            if any(value.startswith(f"{service_name}{separator}") for separator in ["_", "-", "."]):
                return service_name
    return ""


def _append_operation_result(operation_id, result, label, env=None):
    if not operation_id:
        return
    text = result.get("stdout") if result.get("status") == "ok" else (result.get("stderr") or result.get("stdout"))
    operations.append_output(
        operation_id,
        text or result.get("status") or "",
        stream="stdout" if result.get("status") == "ok" else "stderr",
        metadata={"step": label, "result": result},
        env=env,
    )


def _short_command_output(result, limit=1000):
    text = str((result or {}).get("stderr") or (result or {}).get("stdout") or "").strip()
    if len(text) <= limit:
        return text
    return text[:limit].rstrip() + "..."


def _manifest_summary(stdout):
    try:
        data = json.loads(stdout or "{}")
    except Exception:
        return {}
    manifests = data.get("manifests") if isinstance(data, dict) else None
    return {
        "schema_version": data.get("schemaVersion") if isinstance(data, dict) else None,
        "media_type": data.get("mediaType") if isinstance(data, dict) else None,
        "manifest_count": len(manifests) if isinstance(manifests, list) else 0,
    }


def _compose_network_names(compose):
    if not isinstance(compose, dict):
        return set()
    names = set()
    root_networks = compose.get("networks")
    if isinstance(root_networks, dict):
        names.update(str(name).strip() for name in root_networks.keys() if str(name).strip())
    elif isinstance(root_networks, list):
        names.update(str(name).strip() for name in root_networks if str(name).strip())

    services = compose.get("services") or {}
    if isinstance(services, dict):
        for service in services.values():
            if not isinstance(service, dict):
                continue
            service_networks = service.get("networks")
            network_names = compose_rules.network_names(service_networks)
            if network_names is None and isinstance(service_networks, str):
                network_names = [service_networks]
            if isinstance(network_names, list):
                names.update(str(name).strip() for name in network_names if str(name).strip())
    return names


def _deployment_context_for_compose(compose, deployment_context=None):
    context = dict(deployment_context or {})
    network_names = _compose_network_names(compose)
    if compose_rules.OVERLAY_NETWORK in network_names:
        network_name = compose_rules.OVERLAY_NETWORK
        deployment_mode = "swarm"
    elif compose_rules.BRIDGE_NETWORK in network_names:
        network_name = compose_rules.BRIDGE_NETWORK
        deployment_mode = "compose"
    else:
        network_name = str(context.get("network_name") or context.get("network") or "").strip()
        if network_name == compose_rules.BRIDGE_NETWORK:
            deployment_mode = "compose"
        elif network_name == compose_rules.OVERLAY_NETWORK:
            deployment_mode = "swarm"
        else:
            deployment_mode = compose_rules.normalize_deployment_mode(context.get("deployment_mode"))
            network_name = compose_rules.default_network_name(deployment_mode)
    return {
        **context,
        "deployment_mode": deployment_mode,
        "network": network_name,
        "network_name": network_name,
    }


class ServiceUpdateMixin:
    def _service_deployment_validation_context(self, service, env=None):
        policy = dict((service or {}).get("target_node_policy") or {})
        metadata = dict((service or {}).get("metadata") or {})
        placement = dict(metadata.get("placement") or {})
        mode = policy.get("mode") or placement.get("deployment_mode")
        network = policy.get("network") or placement.get("network")
        node_id = str(policy.get("node_id") or placement.get("node_id") or "").strip()
        if node_id:
            try:
                with connect(env=env) as connection:
                    with connection.cursor() as cursor:
                        cursor.execute("SELECT swarm_node_id FROM nodes WHERE id = %s LIMIT 1", (node_id,))
                        row = cursor.fetchone()
                        if row is not None:
                            mode = "swarm" if str(row.get("swarm_node_id") or "").strip() else "compose"
                            network = compose_rules.default_network_name(mode)
            except Exception:
                pass
        if not mode and network == compose_rules.BRIDGE_NETWORK:
            mode = "compose"
        deployment_mode = compose_rules.normalize_deployment_mode(mode)
        network_name = network or compose_rules.default_network_name(deployment_mode)
        return {"deployment_mode": deployment_mode, "network_name": network_name}

    def _domain_payload(self, payload, domain, port, env=None):
        metadata = dict(payload.get("domain_metadata") or {})
        metadata["source"] = "service_update"
        zone_id = payload.get("zone_id") or metadata.get("zone_id")
        normalized = ddns_model.normalize_service_domain(
            domain,
            endpoint_id=zone_id,
            prefix=payload.get("domain_prefix") or metadata.get("domain_prefix"),
            fallback_prefix=payload.get("name") or payload.get("namespace") or metadata.get("compose_service"),
            env=env,
        )
        domain = normalized.get("domain") or domain
        ddns_endpoint = normalized.get("endpoint") or (ddns_model.match_domain(domain, endpoint_id=zone_id, env=env) if zone_id else ddns_model.match_domain(domain, env=env))
        if not ddns_endpoint:
            raise ServiceError(400, "서비스 도메인은 DDNS 관리 서버에 등록된 suffix 하위 주소만 사용할 수 있습니다.", "DDNS_ENDPOINT_REQUIRED", domain=domain)
        metadata.pop("zone_id", None)
        metadata.update({
            "dns_provider": "ddns",
            "routing_provider": "nginx",
            "ddns_endpoint_id": str(ddns_endpoint["id"]),
            "ddns_domain_suffix": ddns_endpoint.get("domain_suffix"),
            "domain_prefix": normalized.get("prefix"),
            "ddns_mode": "ddns_management",
        })
        ssl_mode = "none"
        if domain:
            certs = webserver.certificates_for_domain(domain, zone_id=None, env=env)
            ssl_mode = "existing" if int((certs.get("summary") or {}).get("valid") or 0) > 0 else "certbot"
        return ssl_mode, metadata

    def _replace_domain(self, cursor, service_id, payload, env=None):
        domain_rows = self._domain_rows_from_payload(payload, env=env)
        if not domain_rows:
            cursor.execute("DELETE FROM service_domains WHERE service_id = %s", (service_id,))
            return None
        keep = [item["domain"] for item in domain_rows]
        cursor.execute("DELETE FROM service_domains WHERE service_id = %s AND NOT (lower(domain) = ANY(%s))", (service_id, keep))
        saved = []
        for item in domain_rows:
            domain = item["domain"]
            port = item["port"]
            ssl_mode = item["ssl_mode"]
            metadata = item["metadata"]
            cursor.execute(
                """
                INSERT INTO service_domains(service_id, domain, port, proxy_type, ssl_mode, test_run_id, metadata)
                VALUES (%s, %s, %s, 'nginx', %s, %s, %s)
                ON CONFLICT (service_id, domain)
                DO UPDATE SET port = EXCLUDED.port, proxy_type = 'nginx', ssl_mode = EXCLUDED.ssl_mode, metadata = EXCLUDED.metadata, updated_at = now()
                RETURNING *
                """,
                (service_id, domain, port, ssl_mode, payload.get("test_run_id"), Jsonb(metadata)),
            )
            saved.append(_row(cursor.fetchone()))
        return saved[0] if saved else None

    def _domain_rows_from_payload(self, payload, env=None):
        payload = payload or {}
        raw_domains = payload.get("domains") if isinstance(payload.get("domains"), list) else []
        rows = []
        for item in raw_domains:
            if not isinstance(item, dict):
                continue
            domain = str(item.get("domain") or "").strip().lower()
            if not domain:
                continue
            port = _safe_int(item.get("port") or item.get("domain_target_port") or item.get("target_port") or payload.get("domain_target_port"), 80)
            metadata = dict(item.get("metadata") or {})
            metadata.update({
                "source": metadata.get("source") or "service_update",
                "compose_service": item.get("compose_service") or item.get("service_key") or metadata.get("compose_service"),
                "target_port": port,
                "published_port": _safe_int(item.get("published_port") or metadata.get("published_port") or port, port),
            })
            zone_id = item.get("zone_id") or payload.get("zone_id") or metadata.get("zone_id")
            normalized = ddns_model.normalize_service_domain(
                domain,
                endpoint_id=zone_id,
                prefix=item.get("domain_prefix") or item.get("prefix") or payload.get("domain_prefix") or metadata.get("domain_prefix"),
                fallback_prefix=payload.get("name") or payload.get("namespace") or metadata.get("compose_service"),
                env=env,
            )
            domain = normalized.get("domain") or domain
            ddns_endpoint = normalized.get("endpoint") or (ddns_model.match_domain(domain, endpoint_id=zone_id, env=env) if zone_id else ddns_model.match_domain(domain, env=env))
            if not ddns_endpoint:
                raise ServiceError(400, "서비스 도메인은 DDNS 관리 서버에 등록된 suffix 하위 주소만 사용할 수 있습니다.", "DDNS_ENDPOINT_REQUIRED", domain=domain)
            metadata.pop("zone_id", None)
            metadata.update({
                "dns_provider": "ddns",
                "routing_provider": "nginx",
                "ddns_endpoint_id": str(ddns_endpoint["id"]),
                "ddns_domain_suffix": ddns_endpoint.get("domain_suffix"),
                "domain_prefix": normalized.get("prefix"),
                "ddns_mode": "ddns_management",
            })
            ssl_mode = item.get("ssl_mode")
            if not ssl_mode:
                ssl_mode, metadata = self._domain_payload({**payload, "domain_metadata": metadata, "zone_id": zone_id}, domain, port, env=env)
            rows.append({"domain": domain, "port": port, "ssl_mode": ssl_mode, "metadata": metadata})
        if not rows and str(payload.get("domain") or "").strip():
            domain = str(payload.get("domain") or "").strip().lower()
            port = _safe_int(payload.get("port") or payload.get("domain_target_port"), 80)
            normalized = ddns_model.normalize_service_domain(
                domain,
                endpoint_id=payload.get("zone_id") or (payload.get("domain_metadata") or {}).get("zone_id"),
                prefix=payload.get("domain_prefix"),
                fallback_prefix=payload.get("name") or payload.get("namespace"),
                env=env,
            )
            domain = normalized.get("domain") or domain
            ssl_mode, metadata = self._domain_payload(payload, domain, port, env=env)
            rows.append({"domain": domain, "port": port, "ssl_mode": ssl_mode, "metadata": metadata})
        deduped = []
        seen = set()
        for item in rows:
            if item["domain"] in seen:
                continue
            seen.add(item["domain"])
            deduped.append(item)
        return deduped

    def update_wizard(self, payload, env=None):
        payload = payload or {}
        service_id = payload.get("service_id")
        if not service_id:
            raise ServiceError(400, "service_id는 필수입니다.", "SERVICE_ID_REQUIRED")
        name = str(payload.get("name") or "").strip()
        if not name:
            raise ServiceError(400, "서비스 이름을 입력해주세요.", "SERVICE_NAME_REQUIRED")
        content = payload.get("content")
        if not content:
            raise ServiceError(400, "수정할 Compose 내용이 필요합니다.", "SERVICE_CONTENT_REQUIRED")

        with connect(env=env) as connection:
            with connection.cursor() as cursor:
                service = self._service_row(cursor, service_id)

        namespace = service["namespace"]
        deployment_context = self._service_deployment_validation_context(service, env=env)
        validation = validator.validate({
            "namespace": namespace,
            "filename": "docker-compose.yaml",
            "content": content,
            **deployment_context,
        })
        preflight = preflight_model.check({**payload, "service_id": service_id}, content, namespace, validation=validation, env=env)
        if preflight.get("ok") is not True:
            raise ServiceError(409, "서비스 수정 전에 해결해야 할 항목이 있습니다.", "SERVICE_PREFLIGHT_BLOCKED", preflight=preflight)

        normalized_content = yaml.safe_dump(validation["normalized"], sort_keys=False, allow_unicode=False)
        compose_path = Path(service["compose_path"]).expanduser()
        compose_path.parent.mkdir(parents=True, exist_ok=True)
        history_id = _history_id()
        history_dir = compose_path.parent / ".history" / history_id
        history_dir.mkdir(parents=True, exist_ok=True)
        if compose_path.exists():
            shutil.copy2(compose_path, history_dir / f"previous-{compose_path.name}")
        compose_path.write_text(normalized_content, encoding="utf-8")
        shutil.copy2(compose_path, history_dir / compose_path.name)

        metadata = dict(service.get("metadata") or {})
        metadata.update({
            "description": str(payload.get("description") or "").strip(),
            "source": metadata.get("source") or "ui_wizard",
            "last_update": {"history_id": history_id, "source": "service_update"},
            "wizard": payload.get("wizard") or {"components": payload.get("components") or [], "domain_mode": payload.get("domain_mode")},
        })
        if payload.get("operator_comment") is not None:
            operator_comment = str(payload.get("operator_comment") or "").strip()
            if operator_comment:
                metadata["operator_comment"] = operator_comment
            else:
                metadata.pop("operator_comment", None)

        with connect(env=env) as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    UPDATE services
                    SET name = %s, status = 'draft', metadata = %s, updated_at = now()
                    WHERE id = %s
                    RETURNING *
                    """,
                    (name, Jsonb(metadata), service_id),
                )
                service = _row(cursor.fetchone())
                domain = self._replace_domain(cursor, service_id, payload, env=env)
        return {"service": service, "domain": domain, "validation": validation, "preflight": preflight, "history_id": history_id}

    def update_basic(self, payload, env=None):
        payload = payload or {}
        service_id = payload.get("service_id")
        if not service_id:
            raise ServiceError(400, "service_id는 필수입니다.", "SERVICE_ID_REQUIRED")
        name = str(payload.get("name") or "").strip()
        if not name:
            raise ServiceError(400, "서비스 이름을 입력해주세요.", "SERVICE_NAME_REQUIRED")

        include_domain = bool(payload.get("include_domain"))
        if include_domain and payload.get("domain_mode") == "registered" and not str(payload.get("domain") or "").strip():
            raise ServiceError(400, "DDNS 도메인을 입력해주세요.", "SERVICE_DOMAIN_REQUIRED")

        with connect(env=env) as connection:
            with connection.cursor() as cursor:
                service = self._service_row(cursor, service_id)
                metadata = dict(service.get("metadata") or {})
                metadata["description"] = str(payload.get("description") or "").strip()
                if payload.get("operator_comment") is not None:
                    operator_comment = str(payload.get("operator_comment") or "").strip()
                    if operator_comment:
                        metadata["operator_comment"] = operator_comment
                    else:
                        metadata.pop("operator_comment", None)
                metadata["last_basic_update"] = {
                    "source": "service_basic_update",
                    "updated_at": datetime.datetime.utcnow().isoformat() + "Z",
                    "domain_included": include_domain,
                }
                cursor.execute(
                    """
                    UPDATE services
                    SET name = %s, metadata = %s, updated_at = now()
                    WHERE id = %s
                    RETURNING *
                    """,
                    (name, Jsonb(metadata), service_id),
                )
                service = _row(cursor.fetchone())
                domain = self._replace_domain(cursor, service_id, payload, env=env) if include_domain else None
        return {"service": service, "domain": domain, "domain_updated": include_domain}

    def update_compose_content(self, payload, env=None):
        payload = payload or {}
        service_id = payload.get("service_id")
        if not service_id:
            raise ServiceError(400, "service_id는 필수입니다.", "SERVICE_ID_REQUIRED")
        content = payload.get("content")
        if not content:
            raise ServiceError(400, "수정할 Compose 내용이 필요합니다.", "SERVICE_CONTENT_REQUIRED")

        with connect(env=env) as connection:
            with connection.cursor() as cursor:
                service = self._service_row(cursor, service_id)

        namespace = service["namespace"]
        deployment_context = self._service_deployment_validation_context(service, env=env)
        validation = validator.validate({
            "namespace": namespace,
            "filename": "docker-compose.yaml",
            "content": content,
            **deployment_context,
        })
        preflight = preflight_model.check({**payload, "service_id": service_id}, content, namespace, validation=validation, env=env)
        if preflight.get("ok") is not True:
            raise ServiceError(409, "Compose 원문을 저장하기 전에 해결해야 할 항목이 있습니다.", "SERVICE_PREFLIGHT_BLOCKED", preflight=preflight)

        normalized_content = yaml.safe_dump(validation["normalized"], sort_keys=False, allow_unicode=False)
        compose_path = Path(service["compose_path"]).expanduser()
        compose_path.parent.mkdir(parents=True, exist_ok=True)
        history_id = _history_id()
        history_dir = compose_path.parent / ".history" / history_id
        history_dir.mkdir(parents=True, exist_ok=True)
        if compose_path.exists():
            shutil.copy2(compose_path, history_dir / f"previous-{compose_path.name}")
        compose_path.write_text(normalized_content, encoding="utf-8")
        shutil.copy2(compose_path, history_dir / compose_path.name)

        metadata = dict(service.get("metadata") or {})
        if payload.get("description") is not None:
            metadata["description"] = str(payload.get("description") or "").strip()
        metadata.update({
            "source": metadata.get("source") or "ui_wizard",
            "last_update": {"history_id": history_id, "source": "compose_raw_update"},
        })

        name = str(payload.get("name") or service.get("name") or "").strip()
        with connect(env=env) as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    UPDATE services
                    SET name = %s, status = 'draft', metadata = %s, updated_at = now()
                    WHERE id = %s
                    RETURNING *
                    """,
                    (name, Jsonb(metadata), service_id),
                )
                service = _row(cursor.fetchone())
        return {"service": service, "validation": validation, "preflight": preflight, "history_id": history_id}

    def _remote_compose_service_up(self, node, compose_path, stack_name, service_name, network_name, force_pull=False, timeout_seconds=300, env=None):
        node_detail = nodes.detail(node.get("id"), env=env)
        compose_bytes = Path(compose_path).expanduser().read_bytes()
        compose_payload = base64.b64encode(compose_bytes).decode("ascii")
        script = (
            "set -eu\n"
            f"STACK={shlex.quote(stack_name)}\n"
            f"SERVICE={shlex.quote(service_name)}\n"
            f"NETWORK={shlex.quote(network_name)}\n"
            'DIR="$HOME/.docker-infra/services/$STACK"\n'
            'FILE="$DIR/docker-compose.yaml"\n'
            'mkdir -p "$DIR"\n'
            'cat > "$FILE.b64" <<\'__DOCKER_INFRA_COMPOSE__\'\n'
            f"{compose_payload}\n"
            "__DOCKER_INFRA_COMPOSE__\n"
            'base64 -d "$FILE.b64" > "$FILE"\n'
            'rm -f "$FILE.b64"\n'
            'if [ -n "$NETWORK" ] && ! docker network inspect "$NETWORK" >/dev/null 2>&1; then\n'
            '  docker network create --driver bridge "$NETWORK"\n'
            "fi\n"
        )
        if force_pull:
            script += 'docker compose -p "$STACK" -f "$FILE" pull "$SERVICE"\n'
            script += 'docker compose -p "$STACK" -f "$FILE" up -d --no-deps --force-recreate "$SERVICE"\n'
        else:
            script += 'docker compose -p "$STACK" -f "$FILE" up -d --no-deps "$SERVICE"\n'
        return nodes._run_ssh_command(
            node_detail,
            ["sh", "-lc", script],
            timeout_seconds=timeout_seconds,
            env=env,
            capture_limit=20000,
        )

    def _compose_service_up_result(self, node, compose_path, stack_name, service_name, network_name, force_pull=False, env=None):
        if node.get("is_local_master"):
            return local_executor.run(
                "service.compose.up.service",
                params={
                    "compose_path": str(compose_path),
                    "stack_name": stack_name,
                    "service_name": service_name,
                    "force_pull": force_pull,
                },
                timeout_seconds=300,
                env=env,
                capture_limit=20000,
            )
        return self._remote_compose_service_up(
            node,
            compose_path,
            stack_name,
            service_name,
            network_name,
            force_pull=force_pull,
            timeout_seconds=300,
            env=env,
        )

    def _stack_service_update_image_result(self, stack_name, compose_service, image_ref, force_pull=False, full_target=None, env=None):
        return local_executor.run(
            "service.stack.update.image",
            params={
                "stack_name": stack_name,
                "service_name": compose_service,
                "swarm_service_name": _swarm_service_name(stack_name, compose_service, full_target),
                "image_ref": image_ref,
                "force": force_pull,
            },
            timeout_seconds=300,
            env=env,
            capture_limit=20000,
        )

    def _container_version_apply_result(self, context, image_ref, force_pull=False, env=None):
        deployment_mode = (context.get("deployment_context") or {}).get("deployment_mode")
        if deployment_mode == "swarm":
            return self._stack_service_update_image_result(
                context["stack_name"],
                context["compose_service"],
                image_ref,
                force_pull=force_pull,
                full_target=context.get("full_target"),
                env=env,
            )
        return self._compose_service_up_result(
            context["node"],
            context["compose_path"],
            context["stack_name"],
            context["compose_service"],
            (context.get("deployment_context") or {}).get("network_name") or (context.get("deployment_context") or {}).get("network") or "",
            force_pull=force_pull,
            env=env,
        )

    def _container_version_context(self, payload, env=None, require_compose=True):
        payload = payload or {}
        service_id = payload.get("service_id")
        container_id = str(payload.get("container_id") or "").strip()
        requested_node_id = str(payload.get("node_id") or "").strip()
        if not service_id:
            raise ServiceError(400, "service_id는 필수입니다.", "SERVICE_ID_REQUIRED")
        if not container_id:
            raise ServiceError(400, "container_id는 필수입니다.", "CONTAINER_ID_REQUIRED")

        with connect(env=env) as connection:
            with connection.cursor() as cursor:
                service = self._service_row(cursor, service_id)

        deployment_context = self._service_deployment_validation_context(service, env=env)
        deployment_mode = deployment_context.get("deployment_mode")

        refreshed = self.refresh_deploy_status(service_id, env=env)
        runtime = refreshed.get("runtime_status") or {}
        containers = ((runtime.get("containers") or {}).get("containers") or [])
        target = next(
            (
                item for item in containers
                if _container_id_matches(item.get("id"), container_id)
                and (not requested_node_id or str(item.get("node_id") or "") == requested_node_id)
            ),
            None,
        )
        if target is None:
            raise ServiceError(404, "선택한 서비스의 컨테이너를 찾을 수 없습니다.", "SERVICE_CONTAINER_NOT_FOUND")
        target_node_id = str(target.get("node_id") or "").strip()
        if not target_node_id:
            raise ServiceError(409, "컨테이너가 실행 중인 서버를 확인할 수 없습니다.", "SERVICE_CONTAINER_NODE_MISSING")

        stack_name = service.get("stack_name") or service.get("namespace")
        try:
            panel = nodes.service_containers(target_node_id, service.get("namespace"), stack_name=stack_name, env=env)
        except nodes.NodeError as exc:
            raise ServiceError(exc.status_code, exc.message, exc.error_code, **exc.extra)
        full_target = next((item for item in panel.get("items") or [] if _container_id_matches(item.get("id"), container_id)), None)
        if full_target is None:
            raise ServiceError(404, "선택한 컨테이너를 해당 서버에서 찾을 수 없습니다.", "CONTAINER_NOT_FOUND")
        try:
            node = nodes.detail(target_node_id, env=env)
        except nodes.NodeError as exc:
            raise ServiceError(exc.status_code, exc.message, exc.error_code, **exc.extra)

        base_context = {
            "service": service,
            "deployment_context": deployment_context,
            "target": target,
            "target_node_id": target_node_id,
            "stack_name": stack_name,
            "full_target": full_target,
            "node": node,
        }

        def runtime_context(reason):
            runtime_image = _container_image_ref(full_target, target)
            if not runtime_image:
                raise ServiceError(400, "컨테이너 이미지 정보를 확인할 수 없습니다.", "SERVICE_CONTAINER_IMAGE_REQUIRED")
            compose_service = str(
                full_target.get("runtime_service_name")
                or full_target.get("name")
                or target.get("runtime_service_name")
                or target.get("name")
                or ""
            ).strip().lstrip("/")
            return {
                **base_context,
                "compose_path": None,
                "previous_content": "",
                "compose": {},
                "compose_service": compose_service,
                "target_config": {},
                "previous_image": runtime_image,
                "runtime_image": runtime_image,
                "image_source": reason,
            }

        if not require_compose and deployment_mode != "compose":
            return runtime_context("runtime")

        compose_path = Path(service.get("compose_path") or "").expanduser()
        if not compose_path.is_file():
            if not require_compose:
                return runtime_context("runtime")
            if deployment_mode != "compose":
                raise ServiceError(409, "컨테이너별 버전 변경은 Docker Compose 파일이 있는 서비스에서만 사용할 수 있습니다.", "SERVICE_CONTAINER_VERSION_COMPOSE_ONLY")
            raise ServiceError(404, "서비스 Compose 파일을 찾을 수 없습니다.", "SERVICE_COMPOSE_NOT_FOUND")
        previous_content = compose_path.read_text(encoding="utf-8")
        compose = yaml.safe_load(previous_content) or {}
        deployment_context = _deployment_context_for_compose(compose, deployment_context)
        deployment_mode = deployment_context.get("deployment_mode")
        base_context = {**base_context, "deployment_context": deployment_context}
        services = compose.get("services") or {}
        if not isinstance(services, dict) or not services:
            if not require_compose:
                return runtime_context("runtime")
            raise ServiceError(400, "Compose 서비스 구성을 찾을 수 없습니다.", "SERVICE_COMPOSE_SERVICES_EMPTY")
        compose_service = _compose_service_from_container(full_target, stack_name, service.get("namespace"), list(services.keys()))
        if not compose_service or compose_service not in services:
            if not require_compose:
                return runtime_context("runtime")
            raise ServiceError(404, "컨테이너와 연결된 Compose 서비스를 찾을 수 없습니다.", "SERVICE_COMPOSE_SERVICE_NOT_FOUND")
        target_config = services.get(compose_service)
        if not isinstance(target_config, dict):
            if not require_compose:
                return runtime_context("runtime")
            raise ServiceError(400, "Compose 서비스 형식이 올바르지 않습니다.", "SERVICE_COMPOSE_SERVICE_INVALID")
        previous_image = str(target_config.get("image") or "").strip()
        if not previous_image:
            if not require_compose:
                return runtime_context("runtime")
            raise ServiceError(400, "이미지 기반 Compose 서비스만 버전을 변경할 수 있습니다.", "SERVICE_COMPOSE_IMAGE_REQUIRED")
        runtime_image = _container_image_ref(full_target, target)
        return {
            **base_context,
            "compose_path": compose_path,
            "previous_content": previous_content,
            "compose": compose,
            "compose_service": compose_service,
            "target_config": target_config,
            "previous_image": previous_image,
            "runtime_image": runtime_image,
            "image_source": "compose",
        }

    def _manifest_inspect_result(self, node, image_ref, env=None):
        if node.get("is_local_master"):
            return local_executor.run(
                "docker.image.manifest.inspect",
                params={"image_ref": image_ref},
                timeout_seconds=45,
                env=env,
                capture_limit=20000,
            )
        return nodes._run_ssh_command(
            node,
            ["docker", "manifest", "inspect", image_ref],
            timeout_seconds=45,
            env=env,
            capture_limit=20000,
        )

    def validate_container_version_image(self, payload, env=None):
        version = _validate_image_version((payload or {}).get("version"))
        context = self._container_version_context(payload, env=env, require_compose=False)
        image_ref = _image_ref_with_version(context["previous_image"], version)
        try:
            result = self._manifest_inspect_result(context["node"], image_ref, env=env)
        except nodes.NodeError as exc:
            raise ServiceError(exc.status_code, exc.message, exc.error_code, **exc.extra)
        except local_executor.LocalCommandError as exc:
            raise ServiceError(exc.status_code, exc.message, exc.error_code, **exc.extra)

        exists = result.get("status") == "ok"
        node = context["node"]
        return {
            "exists": exists,
            "image_ref": image_ref,
            "version": version,
            "compose_service": context["compose_service"],
            "image_source": context.get("image_source") or "compose",
            "node_id": context["target_node_id"],
            "node_name": node.get("name") or node.get("hostname") or node.get("host") or context["target_node_id"],
            "source": "docker_manifest",
            "message": "이미지 manifest를 확인했습니다." if exists else "이미지 manifest를 확인하지 못했습니다. 이미지 이름, tag/digest, registry 인증을 확인해주세요.",
            "manifest": _manifest_summary(result.get("stdout")) if exists else {},
            "check": {
                "status": result.get("status"),
                "exit_code": result.get("exit_code"),
                "message": _short_command_output(result),
            },
        }

    def change_container_version(self, payload, env=None):
        payload = payload or {}
        service_id = payload.get("service_id")
        container_id = str(payload.get("container_id") or "").strip()
        version = _validate_image_version(payload.get("version"))
        force_pull = _truthy(payload.get("force_pull"))
        context = self._container_version_context(payload, env=env)
        service = context["service"]
        deployment_context = context["deployment_context"]
        target_node_id = context["target_node_id"]
        stack_name = context["stack_name"]
        full_target = context["full_target"]
        node = context["node"]
        compose_path = context["compose_path"]
        previous_content = context["previous_content"]
        compose = context["compose"]
        compose_service = context["compose_service"]
        target_config = context["target_config"]
        previous_image = context["previous_image"]
        runtime_image = context.get("runtime_image") or ""
        next_image = _image_ref_with_version(previous_image, version)
        compose_changed = next_image != previous_image
        runtime_changed = bool(runtime_image and not _image_ref_matches_target(runtime_image, next_image))
        apply_force = force_pull or runtime_changed
        if not compose_changed and not runtime_changed and not force_pull:
            raise ServiceError(
                409,
                "입력한 버전이 현재 버전과 같습니다. 같은 tag의 digest 갱신이 필요하면 강제 다시 불러오기를 선택하세요.",
                "SERVICE_IMAGE_VERSION_UNCHANGED",
            )

        try:
            image_check = self._manifest_inspect_result(node, next_image, env=env)
        except nodes.NodeError as exc:
            raise ServiceError(exc.status_code, exc.message, exc.error_code, **exc.extra)
        except local_executor.LocalCommandError as exc:
            raise ServiceError(exc.status_code, exc.message, exc.error_code, **exc.extra)
        if image_check.get("status") != "ok":
            raise ServiceError(
                409,
                "이미지 검증에 실패해 버전을 변경할 수 없습니다. 이미지 tag/digest와 registry 접근 상태를 확인해주세요.",
                "SERVICE_IMAGE_VERSION_NOT_VERIFIED",
                image_ref=next_image,
                check=image_check,
            )

        history_id = f"container_version_{_history_id()}"
        history_dir = compose_path.parent / ".history" / history_id
        history_dir.mkdir(parents=True, exist_ok=True)
        shutil.copy2(compose_path, history_dir / f"previous-{compose_path.name}")
        if compose_changed:
            target_config["image"] = next_image
            next_content = yaml.safe_dump(compose, sort_keys=False, allow_unicode=False)
            validation = validator.validate({
                "namespace": service["namespace"],
                "filename": compose_path.name,
                "content": next_content,
                **deployment_context,
            })
            compose_path.write_text(yaml.safe_dump(validation["normalized"], sort_keys=False, allow_unicode=False), encoding="utf-8")
        else:
            validation = validator.validate({
                "namespace": service["namespace"],
                "filename": compose_path.name,
                "content": previous_content,
                **deployment_context,
            })
        shutil.copy2(compose_path, history_dir / compose_path.name)

        operation = operations.create(
            "service.container.version_change",
            target_type="service",
            target_id=service_id,
            message=f"{compose_service} 컨테이너 버전 변경",
            requested_payload={
                "service_id": service_id,
                "container_id": full_target.get("id") or container_id,
                "node_id": target_node_id,
                "compose_service": compose_service,
                "version": version,
                "force_pull": force_pull,
                "runtime_image": runtime_image,
                "runtime_changed": runtime_changed,
            },
            metadata={
                "service_id": service_id,
                "namespace": service.get("namespace"),
                "compose_service": compose_service,
                "runtime_changed": runtime_changed,
            },
            env=env,
        )

        try:
            result = self._container_version_apply_result(context, next_image, force_pull=apply_force, env=env)
            _append_operation_result(operation["id"], result, "container version apply", env=env)
            if result.get("status") != "ok":
                if compose_changed:
                    compose_path.write_text(previous_content, encoding="utf-8")
                operations.transition(
                    operation["id"],
                    "failed",
                    message="컨테이너 버전 변경에 실패했습니다.",
                    result_payload={"check": result, "compose_reverted": compose_changed},
                    env=env,
                )
                raise ServiceError(409, "버전 변경을 적용할 수 없어 Compose 파일을 이전 내용으로 되돌렸습니다.", "SERVICE_CONTAINER_VERSION_APPLY_FAILED", check=result)

            metadata = dict(service.get("metadata") or {})
            metadata["last_container_version_change"] = {
                "history_id": history_id,
                "operation_id": operation["id"],
                "compose_service": compose_service,
                "node_id": target_node_id,
                "previous_image": previous_image,
                "runtime_image": runtime_image,
                "next_image": next_image,
                "force_pull": force_pull,
                "apply_force": apply_force,
                "compose_changed": compose_changed,
                "runtime_changed": runtime_changed,
                "updated_at": datetime.datetime.utcnow().isoformat() + "Z",
            }
            with connect(env=env) as connection:
                with connection.cursor() as cursor:
                    cursor.execute(
                        """
                        UPDATE services
                        SET status = 'deployed', metadata = %s, updated_at = now()
                        WHERE id = %s
                        RETURNING *
                        """,
                        (Jsonb(metadata), service_id),
                    )
                    updated_service = _row(cursor.fetchone())

            runtime_status = None
            runtime_error = None
            try:
                refreshed = self.refresh_deploy_status(service_id, operation_id=operation["id"], env=env)
                updated_service = refreshed["service"]
                runtime_status = refreshed.get("runtime_status")
            except Exception as exc:
                runtime_error = str(exc)
                operations.append_output(operation["id"], f"runtime status refresh failed: {exc}", stream="stderr", metadata={"step": "runtime status"}, env=env)

            operation = operations.transition(
                operation["id"],
                "succeeded",
                message=f"{compose_service} 컨테이너 버전을 {version} 기준으로 적용했습니다.",
                result_payload={
                    "compose_service": compose_service,
                    "previous_image": previous_image,
                    "runtime_image": runtime_image,
                    "next_image": next_image,
                    "force_pull": force_pull,
                    "apply_force": apply_force,
                    "compose_changed": compose_changed,
                    "runtime_changed": runtime_changed,
                    "history_id": history_id,
                    "runtime_refresh_error": runtime_error,
                },
                env=env,
            )
        except nodes.NodeError as exc:
            if compose_changed:
                compose_path.write_text(previous_content, encoding="utf-8")
            operations.transition(operation["id"], "failed", message=exc.message, result_payload={"error_code": exc.error_code, **exc.extra}, env=env)
            raise ServiceError(exc.status_code, exc.message, exc.error_code, **exc.extra)
        except local_executor.LocalCommandError as exc:
            if compose_changed:
                compose_path.write_text(previous_content, encoding="utf-8")
            operations.transition(operation["id"], "failed", message=exc.message, result_payload={"error_code": exc.error_code, **exc.extra}, env=env)
            raise ServiceError(exc.status_code, exc.message, exc.error_code, **exc.extra)

        return {
            "service": updated_service,
            "operation": operation,
            "compose_service": compose_service,
            "previous_image": previous_image,
            "runtime_image": runtime_image,
            "next_image": next_image,
            "force_pull": force_pull,
            "apply_force": apply_force,
            "compose_changed": compose_changed,
            "runtime_changed": runtime_changed,
            "history_id": history_id,
            "validation": validation,
            "runtime_status": runtime_status,
        }


Model = ServiceUpdateMixin
