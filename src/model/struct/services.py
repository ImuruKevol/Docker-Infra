import datetime
import hashlib
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
shared = wiz.model("struct/services_shared")
service_compose = wiz.model("struct/services_compose")
image_backups = wiz.model("struct/service_image_backups")
placement_selector = wiz.model("struct/services_placement")
ServiceRuntimeMixin = wiz.model("struct/services_runtime")
ServiceDeployMixin = wiz.model("struct/services_deploy")
ServiceDeleteMixin = wiz.model("struct/services_delete")
ServiceUpdateMixin = wiz.model("struct/services_update")
ServiceRollbackMixin = wiz.model("struct/services_rollback")
ServiceStatusMixin = wiz.model("struct/services_status")
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


class ServiceManager(ServiceRollbackMixin, ServiceUpdateMixin, ServiceDeployMixin, ServiceDeleteMixin, ServiceStatusMixin, ServiceRuntimeMixin):
    ServiceError = ServiceError
    ComposeValidationError = validator.ComposeValidationError
    IMPORT_WARNING_CODES = {"FORBIDDEN_CONTAINER_NAME", "HEALTHCHECK_REQUIRED"}

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

    def default_compose(self, namespace, service_name="web", image="nginx:alpine", port=80, env_vars=None, volumes=None):
        return service_compose.default_compose(
            namespace,
            service_name=service_name,
            image=image,
            port=port,
            env_vars=env_vars,
            volumes=volumes,
        )

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

        if not content:
            content = self.default_compose(
                namespace,
                service_name=payload.get("service_name") or "web",
                image=payload.get("image") or "nginx:alpine",
                port=port,
                env_vars=env_vars,
                volumes=volumes,
            )

        validation = validation or validator.validate({
            "namespace": namespace,
            "filename": filename,
            "content": content,
            "health_check": payload.get("health_check"),
            "allow_warnings": payload.get("allow_warnings"),
            "warning_codes": payload.get("warning_codes"),
        })
        normalized_content = yaml.safe_dump(validation["normalized"], sort_keys=False, allow_unicode=False)
        checksum = hashlib.sha256(normalized_content.encode("utf-8")).hexdigest()

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
                        "recommendation": placement_recommendation,
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
                            "mode": "swarm",
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

                cursor.execute(
                    """
                    INSERT INTO compose_versions(service_id, version, path, checksum, test_run_id, metadata)
                    VALUES (%s, 1, %s, %s, %s, %s)
                    RETURNING *
                    """,
                    (
                        service["id"],
                        str(history_dir / filename),
                        checksum,
                        test_run_id,
                        Jsonb({
                            "source": source,
                            "history_id": history_id,
                            "draft": draft_metadata,
                        }),
                    ),
                )
                version = _row(cursor.fetchone())

        image_rows = image_backups.record(
            service,
            validation["normalized"],
            compose_version_id=version["id"],
            source=source,
            test_run_id=test_run_id,
            metadata={"namespace": namespace},
            env=env,
        )
        return {
            "service": service,
            "domain": domain_row,
            "domains": domain_rows,
            "compose_version": version,
            "image_backups": image_rows,
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

        validation = validator.validate({
            "namespace": namespace,
            "filename": filename,
            "content": content,
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
                "source": payload.get("source") or "server_compose_import",
                "source_ref": payload.get("source_ref") or {"node_id": payload.get("node_id"), "path": payload.get("source_path")},
                "allow_warnings": payload.get("allow_warnings"),
                "warning_codes": sorted(self.IMPORT_WARNING_CODES),
            },
            env=env,
            validation=validation,
        )


Model = ServiceManager()
