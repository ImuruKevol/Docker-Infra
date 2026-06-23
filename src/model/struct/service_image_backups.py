import datetime
import hashlib
import re
import shutil
from pathlib import Path

import yaml
from psycopg.types.json import Jsonb


connect = wiz.model("db/postgres").connect
actions_mixin = wiz.model("struct/service_image_backup_actions")
nodes = wiz.model("struct/nodes")
shared = wiz.model("struct/services_shared")
ServiceError = shared.ServiceError
_row = shared.row


def _normalize_image_part(value):
    return re.sub(r"[^a-zA-Z0-9_.-]+", "-", str(value or "").strip()).strip("-") or "image"


def _checksum(content):
    return hashlib.sha256(str(content or "").encode("utf-8")).hexdigest()


def _history_id():
    return datetime.datetime.utcnow().strftime("backup_%Y%m%d_%H%M%S_%f")


def parse_image_ref(image_ref):
    raw = str(image_ref or "").strip()
    digest = ""
    without_digest = raw
    if "@" in raw:
        without_digest, digest = raw.split("@", 1)

    tag = "latest"
    repository_ref = without_digest
    last_segment = without_digest.rsplit("/", 1)[-1]
    if ":" in last_segment:
        repository_ref, tag = without_digest.rsplit(":", 1)

    first = repository_ref.split("/", 1)[0]
    has_registry = "." in first or ":" in first or first == "localhost"
    registry = first if has_registry else "docker.io"
    repository = repository_ref.split("/", 1)[1] if has_registry and "/" in repository_ref else repository_ref
    return {
        "image_ref": raw,
        "registry": registry,
        "repository": repository,
        "tag": tag,
        "digest": digest,
    }


def extract_images(compose):
    if isinstance(compose, str):
        try:
            compose = yaml.safe_load(compose) or {}
        except yaml.YAMLError as exc:
            raise ServiceError(400, f"Compose를 읽을 수 없습니다: {exc}", "COMPOSE_PARSE_FAILED")
    services = (compose or {}).get("services") or {}
    images = []
    for service_name, service in services.items():
        image_ref = str((service or {}).get("image") or "").strip()
        if not image_ref:
            continue
        images.append({"compose_service": str(service_name), **parse_image_ref(image_ref)})
    return images


def _is_running_container(item):
    state = str((item or {}).get("state") or "").strip().lower()
    status = str((item or {}).get("status") or "").strip().lower()
    return state == "running" or status.startswith("up ")


def _compose_service_name(service, item):
    runtime = str((item or {}).get("runtime_service_name") or "").strip()
    namespace = str((service or {}).get("namespace") or "").strip()
    stack_name = str((service or {}).get("stack_name") or "").strip()
    for prefix in [namespace, stack_name]:
        for separator in ("_", "-"):
            marker = f"{prefix}{separator}" if prefix else ""
            if marker and runtime.startswith(marker):
                return runtime[len(marker):]
    if runtime and "_" not in runtime:
        return runtime
    labels = (item or {}).get("labels") or {}
    if isinstance(labels, dict) and labels.get("com.docker.compose.service"):
        return str(labels.get("com.docker.compose.service") or "").strip()
    return runtime


class ServiceImageBackups(actions_mixin):
    ServiceError = ServiceError

    def ensure_schema(self, env=None):
        with connect(env=env) as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    CREATE TABLE IF NOT EXISTS service_image_backups (
                        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                        service_id UUID NOT NULL REFERENCES services(id) ON DELETE CASCADE,
                        compose_version_id UUID REFERENCES compose_versions(id) ON DELETE SET NULL,
                        compose_service TEXT NOT NULL,
                        image_ref TEXT NOT NULL,
                        registry TEXT,
                        repository TEXT,
                        tag TEXT,
                        digest TEXT,
                        backup_ref TEXT,
                        backup_status TEXT NOT NULL DEFAULT 'recorded',
                        backup_error TEXT,
                        source TEXT NOT NULL DEFAULT 'compose',
                        test_run_id TEXT,
                        metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
                        created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
                        updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
                    )
                    """
                )
                cursor.execute(
                    "CREATE INDEX IF NOT EXISTS service_image_backups_service_idx ON service_image_backups(service_id, created_at DESC)"
                )
                cursor.execute(
                    "CREATE INDEX IF NOT EXISTS service_image_backups_digest_idx ON service_image_backups(digest) WHERE digest IS NOT NULL"
                )
                cursor.execute(
                    """
                    DO $$
                    BEGIN
                        IF to_regprocedure('docker_infra_set_updated_at()') IS NOT NULL THEN
                            EXECUTE 'DROP TRIGGER IF EXISTS service_image_backups_set_updated_at ON service_image_backups';
                            EXECUTE 'CREATE TRIGGER service_image_backups_set_updated_at
                                BEFORE UPDATE ON service_image_backups
                                FOR EACH ROW EXECUTE FUNCTION docker_infra_set_updated_at()';
                        END IF;
                    END $$;
                    """
                )

    def record(self, service, compose, compose_version_id=None, source="compose", test_run_id=None, metadata=None, env=None):
        self.ensure_schema(env=env)
        images = extract_images(compose)
        if not images:
            return []
        rows = []
        with connect(env=env) as connection:
            with connection.cursor() as cursor:
                for image in images:
                    cursor.execute(
                        """
                        SELECT *
                        FROM service_image_backups
                        WHERE service_id = %s
                          AND compose_version_id IS NOT DISTINCT FROM %s
                          AND compose_service = %s
                          AND image_ref = %s
                        LIMIT 1
                        """,
                        (service["id"], compose_version_id, image["compose_service"], image["image_ref"]),
                    )
                    existing = cursor.fetchone()
                    if existing is not None:
                        rows.append(_row(existing))
                        continue
                    backup_tag = _normalize_image_part(image["tag"])
                    backup_name = _normalize_image_part(image["repository"].split("/")[-1])
                    backup_ref = None
                    cursor.execute(
                        """
                        INSERT INTO service_image_backups(
                            service_id, compose_version_id, compose_service, image_ref, registry,
                            repository, tag, digest, backup_ref, backup_status, source, test_run_id, metadata
                        )
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, 'recorded', %s, %s, %s)
                        RETURNING *
                        """,
                        (
                            service["id"],
                            compose_version_id,
                            image["compose_service"],
                            image["image_ref"],
                            image["registry"],
                            image["repository"],
                            image["tag"],
                            image["digest"],
                            backup_ref,
                            source,
                            test_run_id,
                            Jsonb({**(metadata or {}), "suggested_backup_name": backup_name, "suggested_backup_tag": backup_tag}),
                        ),
                    )
                    rows.append(_row(cursor.fetchone()))
        return rows

    def _runtime_snapshot_services(self, env=None):
        with connect(env=env) as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT s.*, v.id AS latest_compose_version_id
                    FROM services s
                    LEFT JOIN LATERAL (
                        SELECT id
                        FROM compose_versions
                        WHERE service_id = s.id
                        ORDER BY version DESC, created_at DESC
                        LIMIT 1
                    ) v ON true
                    WHERE COALESCE(s.status, '') <> 'deleted'
                      AND COALESCE(s.compose_path, '') <> ''
                    ORDER BY s.created_at ASC
                    """
                )
                rows = [_row(row) for row in cursor.fetchall()]
        for row in rows:
            row["latest_compose_version_id"] = self._ensure_backup_compose_version(row, source="backup_policy_snapshot", env=env)
        return rows

    def _ensure_backup_compose_version(self, service, source="backup_policy_snapshot", env=None):
        existing_id = service.get("latest_compose_version_id")
        compose_path = Path(str(service.get("compose_path") or "")).expanduser()
        if not compose_path.is_file():
            return existing_id
        content = compose_path.read_text(encoding="utf-8")
        checksum = _checksum(content)
        with connect(env=env) as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT id
                    FROM compose_versions
                    WHERE service_id = %s AND checksum = %s
                    ORDER BY version DESC, created_at DESC
                    LIMIT 1
                    """,
                    (service["id"], checksum),
                )
                current = cursor.fetchone()
                if current is not None:
                    return current["id"]

                history_id = _history_id()
                history_dir = compose_path.parent / ".history" / history_id
                history_dir.mkdir(parents=True, exist_ok=True)
                version_path = history_dir / compose_path.name
                shutil.copy2(compose_path, version_path)

                cursor.execute("SELECT COALESCE(max(version), 0) + 1 AS next_version FROM compose_versions WHERE service_id = %s", (service["id"],))
                version_number = int(cursor.fetchone()["next_version"])
                cursor.execute(
                    """
                    INSERT INTO compose_versions(service_id, version, path, checksum, test_run_id, metadata)
                    VALUES (%s, %s, %s, %s, %s, %s)
                    RETURNING id
                    """,
                    (
                        service["id"],
                        version_number,
                        str(version_path),
                        checksum,
                        service.get("test_run_id"),
                        Jsonb({
                            "source": source,
                            "history_id": history_id,
                            "backup_checkpoint": True,
                        }),
                    ),
                )
                return cursor.fetchone()["id"]

    def _compose_image_map(self, service):
        compose_path = Path(str(service.get("compose_path") or "")).expanduser()
        if not compose_path.is_file():
            return {}
        try:
            images = extract_images(compose_path.read_text(encoding="utf-8"))
        except Exception:
            return {}
        return {item["compose_service"]: item for item in images if item.get("compose_service")}

    def _insert_runtime_snapshot_target(self, service, image, node, container, source, env=None):
        metadata = {
            "service_name": service.get("name") or service.get("namespace"),
            "service_namespace": service.get("namespace"),
            "namespace": service.get("namespace"),
            "backup_kind": "container_snapshot_target",
            "snapshot_target_node_id": str(node.get("id") or ""),
            "snapshot_target_node_name": node.get("name") or node.get("host") or "",
            "snapshot_target_container_id": str(container.get("id") or ""),
            "snapshot_target_container_name": container.get("name") or "",
            "snapshot_target_container_image": container.get("image") or "",
            "snapshot_request_source": source,
        }
        with connect(env=env) as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    INSERT INTO service_image_backups(
                        service_id, compose_version_id, compose_service, image_ref, registry,
                        repository, tag, digest, backup_ref, backup_status, source, test_run_id, metadata
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, NULL, 'recorded', %s, %s, %s)
                    RETURNING *
                    """,
                    (
                        service["id"],
                        service.get("latest_compose_version_id"),
                        image["compose_service"],
                        image["image_ref"],
                        image.get("registry"),
                        image.get("repository"),
                        image.get("tag"),
                        image.get("digest"),
                        source,
                        service.get("test_run_id"),
                        Jsonb(metadata),
                    ),
                )
                return _row(cursor.fetchone())

    def record_runtime_snapshot_targets(self, limit=None, source="backup_policy_snapshot", env=None):
        self.ensure_schema(env=env)
        try:
            limit = int(limit) if limit not in (None, "") else None
        except (TypeError, ValueError):
            limit = None
        if limit is not None and limit <= 0:
            limit = None

        def reached_limit():
            return limit is not None and len(rows) >= limit

        services = self._runtime_snapshot_services(env=env)
        if not services:
            return []
        services_by_id = {str(item.get("id")): item for item in services if item.get("id")}
        services_by_namespace = {str(item.get("namespace")): item for item in services if item.get("namespace")}
        image_maps = {str(service.get("id")): self._compose_image_map(service) for service in services}
        rows = []
        seen = set()
        node_rows = nodes.list(env=env)
        node_errors = []
        for node_ref in node_rows:
            if reached_limit():
                break
            try:
                panel = nodes.live_containers(node_ref["id"], persist=False, env=env)
            except Exception as exc:
                node_errors.append({
                    "node_id": str(node_ref.get("id") or ""),
                    "node_name": node_ref.get("name") or node_ref.get("host") or "",
                    "message": getattr(exc, "message", str(exc)),
                    "error_code": getattr(exc, "error_code", "NODE_CONTAINERS_REFRESH_FAILED"),
                })
                continue
            for group in (panel.get("groups") or {}).get("service_groups") or []:
                service_ref = group.get("service") or {}
                service = services_by_id.get(str(service_ref.get("id") or "")) or services_by_namespace.get(str(service_ref.get("namespace") or ""))
                if service is None:
                    continue
                for container in group.get("containers") or []:
                    if reached_limit():
                        break
                    if not _is_running_container(container) or not container.get("id"):
                        continue
                    compose_service = _compose_service_name(service, container)
                    if not compose_service:
                        continue
                    key = (str(service["id"]), str(node_ref.get("id") or ""), str(container["id"]))
                    if key in seen:
                        continue
                    seen.add(key)
                    image = (image_maps.get(str(service["id"])) or {}).get(compose_service)
                    if image is None:
                        image_ref = str(container.get("image") or "").strip()
                        if not image_ref:
                            continue
                        image = {"compose_service": compose_service, **parse_image_ref(image_ref)}
                    rows.append(self._insert_runtime_snapshot_target(service, image, node_ref, container, source, env=env))
        if not rows and node_rows and len(node_errors) == len(node_rows):
            raise ServiceError(
                409,
                "등록 서버의 컨테이너 목록을 확인할 수 없습니다.",
                "SERVICE_SNAPSHOT_TARGET_REFRESH_FAILED",
                node_errors=node_errors,
            )
        return rows

    def list_for_service(self, service_id, env=None):
        self.ensure_schema(env=env)
        with connect(env=env) as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT *
                    FROM service_image_backups
                    WHERE service_id = %s
                    ORDER BY created_at DESC, compose_service ASC
                    LIMIT 100
                    """,
                    (service_id,),
                )
                return [_row(row) for row in cursor.fetchall()]

    def record_snapshot(self, service, backup, result, test_run_id=None, env=None):
        self.ensure_schema(env=env)
        metadata = {
            **(backup.get("metadata") or {}),
            "backup_kind": "container_snapshot",
            "source_backup_id": backup.get("id"),
            "node_id": (result.get("node") or {}).get("id"),
            "node_name": (result.get("node") or {}).get("name"),
            "container_id": (result.get("container") or {}).get("id"),
            "container_name": (result.get("container") or {}).get("name"),
            "operation_id": (result.get("operation") or {}).get("id"),
        }
        with connect(env=env) as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    INSERT INTO service_image_backups(
                        service_id, compose_version_id, compose_service, image_ref, registry,
                        repository, tag, digest, backup_ref, backup_status, source, test_run_id, metadata
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, %s, NULL, %s, 'backup_succeeded', 'container_snapshot', %s, %s)
                    RETURNING *
                    """,
                    (
                        service["id"],
                        backup.get("compose_version_id"),
                        backup["compose_service"],
                        backup["image_ref"],
                        backup.get("registry"),
                        backup.get("repository"),
                        backup.get("tag"),
                        result["backup_ref"],
                        test_run_id or backup.get("test_run_id"),
                        Jsonb(metadata),
                    ),
                )
                return _row(cursor.fetchone())


Model = ServiceImageBackups()
