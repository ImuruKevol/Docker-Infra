import re

import yaml
from psycopg.types.json import Jsonb


connect = wiz.model("db/postgres").connect
actions_mixin = wiz.model("struct/service_image_backup_actions")
shared = wiz.model("struct/services_shared")
ServiceError = shared.ServiceError
_row = shared.row


def _normalize_image_part(value):
    return re.sub(r"[^a-zA-Z0-9_.-]+", "-", str(value or "").strip()).strip("-") or "image"


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
