import datetime
import re
import shutil
import uuid
from pathlib import Path

import yaml
from psycopg.types.json import Jsonb


connect = wiz.model("db/postgres").connect
config = wiz.config("docker_infra")
setup = wiz.model("struct/setup")
validator = wiz.model("struct/compose_validator")
compose_rules = wiz.model("struct/compose_rules")
shared = wiz.model("struct/services_shared")
service_compose = wiz.model("struct/services_compose")
placement_selector = wiz.model("struct/services_placement")
storage_mounts = wiz.model("struct/storage_mounts")
ddns_model = wiz.model("struct/domains_ddns")
ServiceRuntimeMixin = wiz.model("struct/services_runtime")
ServiceDeployMixin = wiz.model("struct/services_deploy")
ServiceMigrationMixin = wiz.model("struct/services_migration")
ServiceDeleteMixin = wiz.model("struct/services_delete")
ServiceUpdateMixin = wiz.model("struct/services_update")
ServiceRollbackMixin = wiz.model("struct/services_rollback")
ServiceReleaseMixin = wiz.model("struct/services_release")
ServiceStatusMixin = wiz.model("struct/services_status")
ServiceCertbotMixin = wiz.model("struct/services_certbot")
ServiceError = shared.ServiceError
_row = shared.row


def _project_root():
    try:
        workspace_root = Path(config._workspace_root())
    except Exception:
        workspace_root = Path(__file__).resolve().parents[5]
    return workspace_root / "project" / "main"


def _safe_int(value, fallback):
    try:
        return int(value)
    except Exception:
        return fallback


def _normalize_namespace(value):
    return re.sub(r"_+", "_", re.sub(r"[^a-z0-9_]+", "_", str(value or "").strip().lower())).strip("_")


class ServiceManager(ServiceReleaseMixin, ServiceRollbackMixin, ServiceUpdateMixin, ServiceDeployMixin, ServiceMigrationMixin, ServiceDeleteMixin, ServiceStatusMixin, ServiceRuntimeMixin, ServiceCertbotMixin):
    ServiceError = ServiceError
    ComposeValidationError = validator.ComposeValidationError
    IMPORT_WARNING_CODES = {"FORBIDDEN_CONTAINER_NAME"}

    def service_root(self):
        status = setup.status(include_checks=False)
        settings = status.get("settings") or {}
        raw = settings.get("service_root") or ".runtime/dev/services"
        root = Path(raw).expanduser()
        if not root.is_absolute():
            root = _project_root() / root
        return root

    def legacy_service_root(self):
        raw = ".runtime/dev/templates"
        root = Path(raw).expanduser()
        if not root.is_absolute():
            root = _project_root() / root
        return root / "services"

    def service_dir(self, namespace):
        return self.service_root() / namespace

    def default_compose(
        self,
        namespace,
        service_name="web",
        image="nginx:alpine",
        port=80,
        env_vars=None,
        volumes=None,
        deployment_mode=None,
        network_name=None,
        swarm_enabled=None,
    ):
        return service_compose.default_compose(
            namespace,
            service_name=service_name,
            image=image,
            port=port,
            env_vars=env_vars,
            volumes=volumes,
            deployment_mode=deployment_mode,
            network_name=network_name,
            swarm_enabled=swarm_enabled,
        )

    def _node_by_id(self, node_id, env=None):
        node_id = str(node_id or "").strip()
        if not node_id:
            return None
        with connect(env=env) as connection:
            with connection.cursor() as cursor:
                cursor.execute("SELECT * FROM nodes WHERE id = %s LIMIT 1", (node_id,))
                row = cursor.fetchone()
                return dict(row) if row is not None else None

    def _deployment_context_for_node(self, node_id, payload=None, env=None):
        payload = payload or {}
        node = self._node_by_id(node_id, env=env)
        requested_mode = payload.get("deployment_mode") or payload.get("deploy_mode")
        if node is not None:
            deployment_mode = "swarm" if str(node.get("swarm_node_id") or "").strip() else "compose"
        else:
            deployment_mode = compose_rules.normalize_deployment_mode(requested_mode)
        network_name = compose_rules.default_network_name(deployment_mode)
        return {"node": node, "deployment_mode": deployment_mode, "network": network_name}

    def _detect_port(self, normalized_compose, fallback=80):
        services = (normalized_compose or {}).get("services") or {}
        for service in services.values():
            for item in service.get("ports") or []:
                raw = str(item)
                target = raw.split("->", 1)[-1] if "->" in raw else raw
                target = target.split("/", 1)[0]
                if ":" in target:
                    target = target.rsplit(":", 1)[-1]
                try:
                    return int(target.strip().strip('"'))
                except Exception:
                    continue
        return fallback

    def create(self, payload, env=None, validation=None):
        payload = payload or {}
        namespace = (payload.get("namespace") or "").strip()
        name = (payload.get("name") or namespace).strip()
        description = (payload.get("description") or "").strip()
        filename = payload.get("filename") or "docker-compose.yaml"
        content = payload.get("content")
        domain = (payload.get("domain") or "").strip()
        domains = payload.get("domains") if isinstance(payload.get("domains"), list) else []
        port = _safe_int(payload.get("port"), 80)
        proxy_type = "nginx"
        ssl_mode = payload.get("ssl_mode") or "none"
        if ssl_mode == "upload":
            ssl_mode = "existing"
        env_vars = payload.get("env_vars") or []
        volumes = payload.get("volumes") or []
        placement_mode = payload.get("placement_mode") or "auto"
        node_id = (payload.get("node_id") or "").strip()
        placement_recommendation = None
        if placement_mode == "auto" and not node_id:
            try:
                placement_recommendation = placement_selector.recommend(payload, env=env)
                selected = placement_recommendation.get("selected") or {}
                node_id = ((selected.get("node") or {}).get("id") or "").strip()
            except Exception as exc:
                placement_recommendation = {"error": str(exc), "strategy": "least_loaded_resource_score"}
        test_run_id = payload.get("test_run_id")
        source = payload.get("source") or "ui_wizard"
        source_ref = payload.get("source_ref")
        draft_metadata = payload.get("draft_metadata") if isinstance(payload.get("draft_metadata"), dict) else {}
        domain_metadata = {"source": "ui_wizard", **dict(payload.get("domain_metadata") or {})}
        if not domains and domain:
            domains = [{"domain": domain, "port": port, "ssl_mode": ssl_mode, "metadata": domain_metadata}]

        deployment_context = self._deployment_context_for_node(node_id, payload=payload, env=env)
        deployment_mode = (validation or {}).get("deployment_mode") or deployment_context["deployment_mode"]
        network_name = (validation or {}).get("network") or deployment_context["network"]
        storage_payload = payload.get("storage") if isinstance(payload.get("storage"), dict) else {}
        storage_backend = storage_mounts.default_backend(
            deployment_mode=deployment_mode,
            node=deployment_context.get("node"),
            requested=storage_payload.get("backend") or payload.get("storage_backend"),
            env=env,
        )

        if not content:
            content = self.default_compose(
                namespace,
                service_name=payload.get("service_name") or "web",
                image=payload.get("image") or "nginx:alpine",
                port=port,
                env_vars=env_vars,
                volumes=volumes,
                deployment_mode=deployment_mode,
                network_name=network_name,
            )

        storage_plan = storage_mounts.normalize_compose(
            namespace,
            content,
            backend=storage_backend,
            storage=storage_payload,
            env=env,
        )
        content = storage_plan["content"]

        if validation is None or storage_plan.get("changed"):
            validation = validator.validate({
                "namespace": namespace,
                "filename": filename,
                "content": content,
                "deployment_mode": deployment_mode,
                "network_name": network_name,
                "health_check": payload.get("health_check"),
                "allow_warnings": payload.get("allow_warnings"),
                "warning_codes": payload.get("warning_codes"),
            })
        deployment_mode = validation.get("deployment_mode") or deployment_mode
        network_name = validation.get("network") or network_name
        normalized_content = yaml.safe_dump(validation["normalized"], sort_keys=False, allow_unicode=False)

        service_dir = self.service_dir(namespace)
        file_path = service_dir / filename
        history_id = datetime.datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        history_dir = service_dir / ".history" / history_id

        with connect(env=env) as connection:
            with connection.cursor() as cursor:
                cursor.execute("SELECT id FROM services WHERE namespace = %s", (namespace,))
                if cursor.fetchone() is not None:
                    raise ServiceError(409, "이미 같은 namespace의 서비스가 있습니다.", "SERVICE_NAMESPACE_EXISTS")

                service_dir.mkdir(parents=True, exist_ok=True)
                history_dir.mkdir(parents=True, exist_ok=True)
                if file_path.exists():
                    shutil.copy2(file_path, history_dir / filename)
                file_path.write_text(normalized_content, encoding="utf-8")
                shutil.copy2(file_path, history_dir / filename)

                metadata = {
                    "source": source,
                    "history_id": history_id,
                    "description": description,
                    "port": port,
                    "proxy_type": proxy_type,
                    "ssl_mode": ssl_mode,
                    "env_vars": env_vars,
                    "volumes": volumes,
                    "placement": {
                        "mode": placement_mode,
                        "node_id": node_id,
                        "auto_selected": placement_mode == "auto" and bool(node_id),
                        "deployment_mode": deployment_mode,
                        "network": network_name,
                        "recommendation": placement_recommendation,
                    },
                    "storage": {
                        "backend": storage_backend,
                        "mount_root": storage_plan.get("mount_root"),
                        "mounts": storage_plan.get("mounts") or [],
                        "docker_managed_volume_allowed": False,
                        "normalized": bool(storage_plan.get("changed")),
                    },
                }
                if source_ref:
                    metadata["source_ref"] = source_ref
                if draft_metadata:
                    metadata["draft"] = draft_metadata
                if payload.get("wizard"):
                    metadata["wizard"] = payload.get("wizard")
                cursor.execute(
                    """
                    INSERT INTO services(namespace, name, status, compose_path, stack_name, target_node_policy, test_run_id, metadata)
                    VALUES (%s, %s, 'draft', %s, %s, %s, %s, %s)
                    RETURNING *
                    """,
                    (
                        namespace,
                        name,
                        str(file_path),
                        validation["stack_name"],
                        Jsonb({
                            "mode": deployment_mode,
                            "network": network_name,
                            "replicas": 1,
                            "placement": placement_mode,
                            "node_id": node_id,
                            "auto_selected": placement_mode == "auto" and bool(node_id),
                            "recommendation": placement_recommendation,
                        }),
                        test_run_id,
                        Jsonb(metadata),
                    ),
                )
                service = _row(cursor.fetchone())

                domain_rows = []
                domain_row = None
                for index, item in enumerate(domains):
                    item_domain = str((item or {}).get("domain") or "").strip().lower()
                    if not item_domain:
                        continue
                    item_port = _safe_int((item or {}).get("port"), port)
                    item_ssl_mode = (item or {}).get("ssl_mode") or ssl_mode
                    item_metadata = {"source": "ui_wizard", **dict((item or {}).get("metadata") or {})}
                    ddns_endpoint = ddns_model.match_domain(item_domain, endpoint_id=item_metadata.get("ddns_endpoint_id"), env=env)
                    if not ddns_endpoint:
                        raise ServiceError(400, "서비스 도메인은 DDNS 관리 서버에 등록된 suffix 하위 주소만 사용할 수 있습니다.", "DDNS_ENDPOINT_REQUIRED", domain=item_domain)
                    item_metadata.pop("zone_id", None)
                    item_metadata.update({
                        "dns_provider": "ddns",
                        "routing_provider": "nginx",
                        "ddns_endpoint_id": str(ddns_endpoint["id"]),
                        "ddns_domain_suffix": ddns_endpoint.get("domain_suffix"),
                        "ddns_mode": "ddns_management",
                    })
                    cursor.execute(
                        """
                        INSERT INTO service_domains(service_id, domain, port, proxy_type, ssl_mode, test_run_id, metadata)
                        VALUES (%s, %s, %s, %s, %s, %s, %s)
                        ON CONFLICT (service_id, domain)
                        DO UPDATE SET port = EXCLUDED.port, proxy_type = EXCLUDED.proxy_type, ssl_mode = EXCLUDED.ssl_mode, metadata = EXCLUDED.metadata, updated_at = now()
                        RETURNING *
                        """,
                        (
                            service["id"],
                            item_domain,
                            item_port,
                            proxy_type,
                            item_ssl_mode,
                            test_run_id,
                            Jsonb(item_metadata),
                        ),
                    )
                    row = _row(cursor.fetchone())
                    domain_rows.append(row)
                    if index == 0:
                        domain_row = row

        storage_rows = storage_mounts.record_service_mounts(
            service["id"],
            storage_plan.get("mounts") or [],
            test_run_id=test_run_id,
            env=env,
        )

        return {
            "service": service,
            "domain": domain_row,
            "domains": domain_rows,
            "storage_mounts": storage_rows,
            "validation": validation,
            "paths": {
                "service_dir": str(service_dir),
                "compose_path": str(file_path),
                "history_dir": str(history_dir),
            },
        }

    def import_compose(self, payload, env=None):
        payload = payload or {}
        content = payload.get("content")
        filename = payload.get("filename") or "docker-compose.yaml"
        if not content:
            raise ServiceError(400, "Compose 파일 내용이 필요합니다.", "COMPOSE_CONTENT_REQUIRED")

        suggested_namespace = payload.get("namespace") or payload.get("suggested_namespace")
        if not suggested_namespace:
            source_path = Path(str(payload.get("source_path") or filename))
            suggested_namespace = source_path.parent.name or source_path.stem.replace("docker-compose", "service")
        namespace = _normalize_namespace(suggested_namespace)
        if not namespace:
            namespace = f"service_{uuid.uuid4().hex[:8]}"

        deployment_context = self._deployment_context_for_node(payload.get("node_id"), payload=payload, env=env)
        validation = validator.validate({
            "namespace": namespace,
            "filename": filename,
            "content": content,
            "deployment_mode": deployment_context["deployment_mode"],
            "network_name": deployment_context["network"],
            "allow_warnings": payload.get("allow_warnings"),
            "warning_codes": sorted(self.IMPORT_WARNING_CODES),
        })
        port = _safe_int(payload.get("port"), self._detect_port(validation["normalized"], fallback=80))
        return self.create(
            {
                "namespace": namespace,
                "name": payload.get("name") or namespace,
                "filename": filename,
                "content": content,
                "port": port,
                "domain": payload.get("domain"),
                "proxy_type": "nginx",
                "ssl_mode": payload.get("ssl_mode") or "none",
                "test_run_id": payload.get("test_run_id"),
                "node_id": payload.get("node_id"),
                "deployment_mode": validation.get("deployment_mode") or deployment_context["deployment_mode"],
                "network_name": validation.get("network") or deployment_context["network"],
                "source": payload.get("source") or "server_compose_import",
                "source_ref": payload.get("source_ref") or {"node_id": payload.get("node_id"), "path": payload.get("source_path")},
                "allow_warnings": payload.get("allow_warnings"),
                "warning_codes": sorted(self.IMPORT_WARNING_CODES),
            },
            env=env,
            validation=validation,
        )


Model = ServiceManager()
