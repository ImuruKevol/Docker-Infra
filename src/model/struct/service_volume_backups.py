import datetime
import hashlib
import re
import shlex
import subprocess
import shutil
from pathlib import Path
from urllib.parse import urlparse

import yaml
from psycopg.types.json import Jsonb


connect = wiz.model("db/postgres").connect
backup_system = wiz.model("struct/backup_system")
harbor = wiz.model("struct/images_harbor")
nodes = wiz.model("struct/nodes")
operations = wiz.model("struct/operations")
shared = wiz.model("struct/services_shared")
ServiceError = shared.ServiceError
_row = shared.row

ARCHIVE_IMAGE = "alpine:3.20"
VOLUME_MEDIA_TYPE = "application/vnd.docker-infra.volume.layer.v1+gzip"


def _clean(value):
    return re.sub(r"[^a-z0-9_.-]+", "-", str(value or "").lower()).strip("-") or "volume"


def _checksum(content):
    return hashlib.sha256(str(content or "").encode("utf-8")).hexdigest()


def _history_id():
    return datetime.datetime.utcnow().strftime("backup_%Y%m%d_%H%M%S_%f")


def _timestamp():
    return datetime.datetime.utcnow().strftime("%Y%m%d%H%M%S")


def _output(result):
    return "\n".join(part for part in [result.get("stdout"), result.get("stderr")] if part)


def _failure_tail(result):
    lines = [line.strip() for line in _output(result).splitlines() if line.strip()]
    return lines[-1][:300] if lines else ""


def _ref_registry(ref):
    return str(ref or "").strip().split("/", 1)[0]


def _is_running_container(item):
    state = str((item or {}).get("state") or "").strip().lower()
    status = str((item or {}).get("status") or "").strip().lower()
    return state == "running" or status.startswith("up ")


def _local_run(argv, timeout=1800):
    try:
        done = subprocess.run(argv, capture_output=True, text=True, timeout=timeout, check=False)
        return {"status": "ok" if done.returncode == 0 else "error", "exit_code": done.returncode, "stdout": done.stdout, "stderr": done.stderr}
    except subprocess.TimeoutExpired as exc:
        return {"status": "timeout", "exit_code": None, "stdout": exc.stdout or "", "stderr": exc.stderr or "command timed out"}


def _compose_service_name(service, item):
    runtime = str((item or {}).get("runtime_service_name") or "").strip()
    namespace = str((service or {}).get("namespace") or "").strip()
    stack_name = str((service or {}).get("stack_name") or "").strip()
    for prefix in [namespace, stack_name]:
        for separator in ("_", "-"):
            marker = f"{prefix}{separator}" if prefix else ""
            if marker and runtime.startswith(marker):
                return runtime[len(marker):]
    labels = (item or {}).get("labels") or {}
    if isinstance(labels, dict) and labels.get("com.docker.compose.service"):
        return str(labels.get("com.docker.compose.service") or "").strip()
    return runtime


class ServiceVolumeBackups:
    ServiceError = ServiceError

    def ensure_schema(self, env=None):
        with connect(env=env) as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    CREATE TABLE IF NOT EXISTS service_volume_backups (
                        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                        service_id UUID NOT NULL REFERENCES services(id) ON DELETE CASCADE,
                        compose_version_id UUID REFERENCES compose_versions(id) ON DELETE SET NULL,
                        compose_service TEXT NOT NULL,
                        volume_name TEXT NOT NULL,
                        docker_volume TEXT NOT NULL,
                        mount_target TEXT,
                        node_id UUID REFERENCES nodes(id) ON DELETE SET NULL,
                        container_id TEXT,
                        artifact_ref TEXT,
                        artifact_status TEXT NOT NULL DEFAULT 'recorded',
                        artifact_error TEXT,
                        source TEXT NOT NULL DEFAULT 'backup_policy_snapshot',
                        test_run_id TEXT,
                        metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
                        created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
                        updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
                    )
                    """
                )
                cursor.execute(
                    "CREATE INDEX IF NOT EXISTS service_volume_backups_service_idx ON service_volume_backups(service_id, created_at DESC)"
                )
                cursor.execute(
                    "CREATE INDEX IF NOT EXISTS service_volume_backups_volume_idx ON service_volume_backups(service_id, docker_volume, created_at DESC)"
                )
                cursor.execute(
                    """
                    DO $$
                    BEGIN
                        IF to_regprocedure('docker_infra_set_updated_at()') IS NOT NULL THEN
                            EXECUTE 'DROP TRIGGER IF EXISTS service_volume_backups_set_updated_at ON service_volume_backups';
                            EXECUTE 'CREATE TRIGGER service_volume_backups_set_updated_at
                                BEFORE UPDATE ON service_volume_backups
                                FOR EACH ROW EXECUTE FUNCTION docker_infra_set_updated_at()';
                        END IF;
                    END $$;
                    """
                )

    def _runtime_services(self, env=None):
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

    def _compose_document(self, service):
        compose_path = Path(str(service.get("compose_path") or "")).expanduser()
        if not compose_path.is_file():
            return {}
        try:
            return yaml.safe_load(compose_path.read_text(encoding="utf-8") or "{}") or {}
        except Exception:
            return {}

    def _docker_volume_name(self, namespace, source, top_level):
        source = str(source or "").strip()
        config = (top_level or {}).get(source) if isinstance(top_level, dict) else {}
        config = config if isinstance(config, dict) else {}
        explicit_name = str(config.get("name") or "").strip()
        if explicit_name:
            return explicit_name
        external = config.get("external")
        if isinstance(external, dict):
            return str(external.get("name") or source).strip()
        if external is True:
            return source
        return f"{namespace}_{source}" if namespace else source

    def _is_named_volume_source(self, source):
        source = str(source or "").strip()
        return bool(source) and not source.startswith(("/", ".", "~"))

    def _parse_volume_ref(self, raw, namespace, top_level):
        if isinstance(raw, dict):
            mount_type = str(raw.get("type") or "volume").strip().lower()
            if mount_type not in {"", "volume"}:
                return None
            source = str(raw.get("source") or raw.get("src") or raw.get("name") or "").strip()
            target = str(raw.get("target") or raw.get("dst") or raw.get("destination") or "").strip()
            if not self._is_named_volume_source(source):
                return None
            return {"compose_volume": source, "docker_volume": self._docker_volume_name(namespace, source, top_level), "target": target}

        text = str(raw or "").strip()
        if not text:
            return None
        parts = text.split(":")
        if len(parts) < 2:
            return None
        source = parts[0].strip()
        target = parts[1].strip()
        if not self._is_named_volume_source(source):
            return None
        return {"compose_volume": source, "docker_volume": self._docker_volume_name(namespace, source, top_level), "target": target}

    def compose_named_volumes(self, service):
        compose = self._compose_document(service)
        namespace = str(service.get("namespace") or service.get("stack_name") or "").strip()
        top_level = compose.get("volumes") or {}
        refs = []
        for service_name, service_def in (compose.get("services") or {}).items():
            if not isinstance(service_def, dict):
                continue
            for raw in service_def.get("volumes") or []:
                ref = self._parse_volume_ref(raw, namespace, top_level)
                if not ref:
                    continue
                refs.append({**ref, "compose_service": str(service_name)})
        return refs

    def _insert_runtime_volume_target(self, service, ref, node, container, source, env=None):
        metadata = {
            "service_name": service.get("name") or service.get("namespace"),
            "service_namespace": service.get("namespace"),
            "namespace": service.get("namespace"),
            "backup_kind": "named_volume_snapshot",
            "snapshot_request_source": source,
            "volume_target_node_id": str(node.get("id") or ""),
            "volume_target_node_name": node.get("name") or node.get("host") or "",
            "volume_target_container_id": str(container.get("id") or ""),
            "volume_target_container_name": container.get("name") or "",
            "mount_target": ref.get("target") or "",
        }
        with connect(env=env) as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    INSERT INTO service_volume_backups(
                        service_id, compose_version_id, compose_service, volume_name, docker_volume,
                        mount_target, node_id, container_id, artifact_status, source, test_run_id, metadata
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, 'recorded', %s, %s, %s)
                    RETURNING *
                    """,
                    (
                        service["id"],
                        service.get("latest_compose_version_id"),
                        ref["compose_service"],
                        ref["compose_volume"],
                        ref["docker_volume"],
                        ref.get("target") or "",
                        node.get("id"),
                        str(container.get("id") or ""),
                        source,
                        service.get("test_run_id"),
                        Jsonb(metadata),
                    ),
                )
                return _row(cursor.fetchone())

    def record_runtime_volume_targets(self, source="backup_policy_snapshot", env=None):
        self.ensure_schema(env=env)
        services = self._runtime_services(env=env)
        if not services:
            return []
        services_by_id = {str(item.get("id")): item for item in services if item.get("id")}
        services_by_namespace = {str(item.get("namespace")): item for item in services if item.get("namespace")}
        volume_maps = {}
        for service in services:
            by_compose = {}
            for ref in self.compose_named_volumes(service):
                by_compose.setdefault(ref["compose_service"], []).append(ref)
            volume_maps[str(service.get("id"))] = by_compose

        rows = []
        seen = set()
        node_rows = nodes.list(env=env)
        node_errors = []
        for node_ref in node_rows:
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
                by_compose = volume_maps.get(str(service.get("id"))) or {}
                if not by_compose:
                    continue
                for container in group.get("containers") or []:
                    if not _is_running_container(container) or not container.get("id"):
                        continue
                    compose_service = _compose_service_name(service, container)
                    for ref in by_compose.get(compose_service) or []:
                        key = (str(service["id"]), str(node_ref.get("id") or ""), ref["docker_volume"])
                        if key in seen:
                            continue
                        seen.add(key)
                        rows.append(self._insert_runtime_volume_target(service, ref, node_ref, container, source, env=env))
        if not rows and node_rows and len(node_errors) == len(node_rows):
            raise ServiceError(
                409,
                "등록 서버의 컨테이너 목록을 확인할 수 없습니다.",
                "SERVICE_VOLUME_TARGET_REFRESH_FAILED",
                node_errors=node_errors,
            )
        return rows

    def _config(self, env=None):
        config = backup_system.connection_config(env=env)
        if not config.get("enabled"):
            raise ServiceError(409, "서비스 백업 시스템이 꺼져 있습니다.", "BACKUP_SYSTEM_DISABLED")
        if config.get("status") != "running":
            raise ServiceError(409, "서비스 백업 시스템이 실행 중이 아닙니다.", "BACKUP_SYSTEM_NOT_RUNNING")
        if not config.get("password"):
            raise ServiceError(409, "서비스 백업 시스템 관리자 정보가 없습니다.", "BACKUP_SYSTEM_SECRET_REQUIRED")
        parsed = urlparse(config["harbor_url"])
        return {**config, "registry": parsed.netloc or parsed.path, "plain_http": parsed.scheme == "http"}

    def _fetch_backup_target(self, service_id, backup_id, env=None):
        self.ensure_schema(env=env)
        with connect(env=env) as connection:
            with connection.cursor() as cursor:
                cursor.execute("SELECT * FROM services WHERE id = %s", (service_id,))
                service = cursor.fetchone()
                if service is None:
                    raise ServiceError(404, "서비스를 찾을 수 없습니다.", "SERVICE_NOT_FOUND")
                cursor.execute("SELECT * FROM service_volume_backups WHERE id = %s AND service_id = %s", (backup_id, service_id))
                backup = cursor.fetchone()
                if backup is None:
                    raise ServiceError(404, "volume 백업 이력을 찾을 수 없습니다.", "SERVICE_VOLUME_BACKUP_NOT_FOUND")
                cursor.execute("UPDATE service_volume_backups SET artifact_status = 'backup_pending', artifact_error = NULL WHERE id = %s", (backup_id,))
                return _row(service), _row(backup)

    def _registry_for_node(self, node, config, env=None):
        return nodes.backup_registry_reference_for_node(node, backup_config=config, env=env)

    def artifact_ref(self, service, backup, node, config, env=None):
        registry = self._registry_for_node(node, config, env=env)
        node_part = _clean(node.get("name") or node.get("host") or node.get("id"))[:32]
        tag = "-".join(part for part in [_timestamp(), node_part] if part)
        repository = f"volume-{_clean(backup.get('compose_service'))}-{_clean(backup.get('docker_volume'))}"
        return f"{registry}/{_clean(service.get('namespace'))}/{repository}:{tag}"

    def _step(self, operation_id, node, argv, secret_values=None, timeout=1800, env=None):
        if node.get("is_local_master"):
            result = _local_run(argv, timeout=timeout)
        else:
            result = nodes._run_ssh_command(node, argv, timeout_seconds=timeout, env=env)
        text = f"$ {' '.join(argv)}\n{_output(result)}".strip()
        if text:
            operations.append_output(
                operation_id,
                text,
                stream="stdout" if result.get("status") == "ok" else "stderr",
                secret_values=secret_values or [],
                env=env,
            )
        if result.get("status") != "ok":
            detail = _failure_tail(result)
            message = "named volume 백업 명령 실행에 실패했습니다."
            if detail:
                message = f"{message} {detail}"
            raise ServiceError(409, message, "SERVICE_VOLUME_BACKUP_COMMAND_FAILED", exit_code=result.get("exit_code"))
        return result

    def _ensure_oras(self, operation_id, node, env=None):
        argv = ["sh", "-lc", "command -v oras >/dev/null 2>&1"]
        if node.get("is_local_master"):
            result = _local_run(argv, timeout=30)
        else:
            result = nodes._run_ssh_command(node, argv, timeout_seconds=30, env=env)
        text = f"$ {' '.join(argv)}\n{_output(result)}".strip()
        if text:
            operations.append_output(operation_id, text, stream="stdout" if result.get("status") == "ok" else "stderr", env=env)
        if result.get("status") != "ok":
            raise ServiceError(
                409,
                "named volume 백업에는 target node의 oras 명령어가 필요합니다. 서버 관리에서 snap install oras --classic 설치 과정을 확인해주세요.",
                "SERVICE_VOLUME_BACKUP_ORAS_REQUIRED",
                node_id=node.get("id"),
                exit_code=result.get("exit_code"),
            )
        return result

    def _backup_script(self, service, backup, node, config, artifact_ref):
        registry = self._registry_for_node(node, config)
        archive_name = f"{_clean(backup.get('docker_volume'))}-{_timestamp()}.tar.gz"
        plain = "--plain-http " if config.get("plain_http") else ""
        annotations = [
            "docker-infra.kind=named_volume_snapshot",
            f"docker-infra.service={service.get('namespace')}",
            f"docker-infra.compose_service={backup.get('compose_service')}",
            f"docker-infra.volume={backup.get('docker_volume')}",
        ]
        annotation_args = " ".join(f"--annotation {shlex.quote(item)}" for item in annotations)
        return "\n".join([
            "set -eu",
            "command -v oras >/dev/null 2>&1 || { echo 'oras command is required' >&2; exit 127; }",
            f"work=$(mktemp -d /tmp/docker-infra-volume-backup.XXXXXX)",
            "cleanup() { rm -rf \"$work\"; }",
            "trap cleanup EXIT",
            f"docker volume inspect {shlex.quote(backup['docker_volume'])} >/dev/null",
            (
                "docker run --rm "
                f"-v {shlex.quote(str(backup['docker_volume']) + ':/volume:ro')} "
                "-v \"$work:/backup\" "
                f"{shlex.quote(ARCHIVE_IMAGE)} sh -lc "
                f"{shlex.quote('cd /volume && tar -czf /backup/' + archive_name + ' .')}"
            ),
            f"printf %s {shlex.quote(config['password'])} | oras login {plain}{shlex.quote(registry)} -u {shlex.quote(config['username'])} --password-stdin",
            "cd \"$work\"",
            f"oras push {plain}{shlex.quote(artifact_ref)} {shlex.quote(archive_name + ':' + VOLUME_MEDIA_TYPE)} {annotation_args}",
        ])

    def execute(self, service, backup, env=None):
        config = self._config(env=env)
        node = nodes.detail(backup["node_id"], env=env)
        operation = operations.create(
            "service.volume.snapshot",
            target_type="service",
            target_id=service["id"],
            requested_payload={"service_id": service["id"], "backup_id": backup["id"], "volume": backup.get("docker_volume")},
            metadata={"service_id": service["id"], "namespace": service.get("namespace"), "node_id": node.get("id"), "volume": backup.get("docker_volume")},
            env=env,
        )
        secrets = [config.get("password")]
        try:
            project_names = {item.get("name") for item in harbor.list_projects(env=env)}
            if service["namespace"] not in project_names:
                harbor.create_project(service["namespace"], public=False, env=env)
            artifact_ref = self.artifact_ref(service, backup, node, config, env=env)
            self._ensure_oras(operation["id"], node, env=env)
            script = self._backup_script(service, backup, node, config, artifact_ref)
            self._step(operation["id"], node, ["sh", "-lc", script], secret_values=secrets, timeout=1800, env=env)
            operation = operations.transition(
                operation["id"],
                "succeeded",
                result_payload={"artifact_ref": artifact_ref, "volume": backup.get("docker_volume"), "media_type": VOLUME_MEDIA_TYPE},
                env=env,
            )
            return {"artifact_ref": artifact_ref, "operation": operation, "node": node, "volume": backup.get("docker_volume")}
        except Exception as exc:
            operations.transition(operation["id"], "failed", message=str(exc), env=env)
            if isinstance(exc, ServiceError):
                raise
            raise ServiceError(502, str(exc), "SERVICE_VOLUME_BACKUP_FAILED")

    def _mark_succeeded(self, backup_id, result, env=None):
        metadata = {
            "backup_kind": "named_volume_snapshot",
            "node_id": (result.get("node") or {}).get("id"),
            "node_name": (result.get("node") or {}).get("name"),
            "operation_id": (result.get("operation") or {}).get("id"),
            "media_type": VOLUME_MEDIA_TYPE,
        }
        with connect(env=env) as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    UPDATE service_volume_backups
                    SET artifact_ref = %s,
                        artifact_status = 'backup_succeeded',
                        artifact_error = NULL,
                        metadata = metadata || %s::jsonb
                    WHERE id = %s
                    RETURNING *
                    """,
                    (result["artifact_ref"], Jsonb(metadata), backup_id),
                )
                return _row(cursor.fetchone())

    def _mark_failed(self, backup_id, message, env=None):
        with connect(env=env) as connection:
            with connection.cursor() as cursor:
                cursor.execute("UPDATE service_volume_backups SET artifact_status = 'backup_failed', artifact_error = %s WHERE id = %s", (message, backup_id))

    def volume_to_harbor(self, service_id, backup_id, env=None):
        service, backup = self._fetch_backup_target(service_id, backup_id, env=env)
        try:
            result = self.execute(service, backup, env=env)
            return {"volume_backup": self._mark_succeeded(backup_id, result, env=env), "operation": result["operation"]}
        except ServiceError as exc:
            self._mark_failed(backup_id, exc.message, env=env)
            raise

    def version_restore_context(self, service_id, compose_version_id, env=None):
        self.ensure_schema(env=env)
        with connect(env=env) as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT *
                    FROM service_volume_backups
                    WHERE service_id = %s
                      AND compose_version_id = %s
                    ORDER BY
                      CASE
                        WHEN artifact_status = 'backup_succeeded' AND artifact_ref IS NOT NULL THEN 0
                        WHEN artifact_status = 'deleted' THEN 1
                        ELSE 2
                      END,
                      updated_at DESC,
                      created_at DESC
                    """,
                    (service_id, compose_version_id),
                )
                rows = [_row(row) for row in cursor.fetchall()]

        grouped = {}
        for row in rows:
            key = (row.get("compose_service"), row.get("docker_volume"))
            grouped.setdefault(key, row)

        items = []
        pending = []
        expired = []
        for row in grouped.values():
            public = {
                "id": row.get("id"),
                "compose_service": row.get("compose_service"),
                "volume_name": row.get("volume_name"),
                "docker_volume": row.get("docker_volume"),
                "mount_target": row.get("mount_target"),
                "artifact_ref": row.get("artifact_ref"),
                "artifact_status": row.get("artifact_status"),
                "node_id": row.get("node_id"),
                "metadata": row.get("metadata") or {},
            }
            if row.get("artifact_status") == "backup_succeeded" and row.get("artifact_ref"):
                items.append(public)
            elif row.get("artifact_status") == "deleted":
                expired.append(public)
            else:
                pending.append(public)

        return {
            "can_apply": bool(items),
            "available_count": len(items),
            "pending_count": len(pending),
            "expired_count": len(expired),
            "items": items,
            "pending": pending,
            "expired": expired,
        }

    def _restore_script(self, backup, node, config):
        artifact_ref = backup.get("artifact_ref")
        registry = _ref_registry(artifact_ref)
        plain = "--plain-http " if config.get("plain_http") else ""
        return "\n".join([
            "set -eu",
            "command -v oras >/dev/null 2>&1 || { echo 'oras command is required' >&2; exit 127; }",
            "work=$(mktemp -d /tmp/docker-infra-volume-restore.XXXXXX)",
            "cleanup() { rm -rf \"$work\"; }",
            "trap cleanup EXIT",
            f"printf %s {shlex.quote(config['password'])} | oras login {plain}{shlex.quote(registry)} -u {shlex.quote(config['username'])} --password-stdin",
            f"oras pull {plain}{shlex.quote(artifact_ref)} -o \"$work\"",
            "archive=$(find \"$work\" -maxdepth 1 -type f -name '*.tar.gz' | sort | head -n 1)",
            "if [ -z \"$archive\" ]; then archive=$(find \"$work\" -maxdepth 1 -type f | sort | head -n 1); fi",
            "if [ -z \"$archive\" ]; then echo 'pulled artifact file not found' >&2; exit 44; fi",
            "archive_name=$(basename \"$archive\")",
            f"docker volume create {shlex.quote(backup['docker_volume'])} >/dev/null",
            (
                "docker run --rm "
                "-e ARCHIVE_NAME=\"$archive_name\" "
                f"-v {shlex.quote(str(backup['docker_volume']) + ':/volume')} "
                "-v \"$work:/backup:ro\" "
                f"{shlex.quote(ARCHIVE_IMAGE)} sh -lc "
                "'set -eu; cd /volume; find . -mindepth 1 -maxdepth 1 -exec rm -rf -- {} +; tar -xzf \"/backup/$ARCHIVE_NAME\"'"
            ),
        ])

    def restore_volume(self, service, backup, operation_id=None, env=None):
        config = self._config(env=env)
        if not backup.get("artifact_ref"):
            raise ServiceError(409, "복원할 volume artifact가 없습니다.", "SERVICE_VOLUME_RESTORE_ARTIFACT_REQUIRED")
        if not backup.get("node_id"):
            raise ServiceError(409, "volume 백업의 대상 노드 정보가 없습니다.", "SERVICE_VOLUME_RESTORE_NODE_REQUIRED")
        node = nodes.detail(backup["node_id"], env=env)
        operation = None
        if operation_id is None:
            operation = operations.create(
                "service.volume.restore",
                target_type="service",
                target_id=service["id"],
                requested_payload={"service_id": service["id"], "backup_id": backup["id"], "volume": backup.get("docker_volume")},
                metadata={"service_id": service["id"], "namespace": service.get("namespace"), "node_id": node.get("id"), "volume": backup.get("docker_volume")},
                env=env,
            )
            operation_id = operation["id"]
        secrets = [config.get("password")]
        try:
            self._ensure_oras(operation_id, node, env=env)
            script = self._restore_script(backup, node, config)
            self._step(operation_id, node, ["sh", "-lc", script], secret_values=secrets, timeout=1800, env=env)
            result = {
                "backup_id": backup.get("id"),
                "artifact_ref": backup.get("artifact_ref"),
                "volume": backup.get("docker_volume"),
                "node_id": node.get("id"),
            }
            if operation is not None:
                operation = operations.transition(operation_id, "succeeded", result_payload=result, env=env)
            return {**result, "operation": operation}
        except Exception as exc:
            if operation is not None:
                operations.transition(operation_id, "failed", message=str(exc), env=env)
            if isinstance(exc, ServiceError):
                raise
            raise ServiceError(502, str(exc), "SERVICE_VOLUME_RESTORE_FAILED")

    def restore_version(self, service, compose_version_id, operation_id=None, env=None):
        context = self.version_restore_context(service["id"], compose_version_id, env=env)
        if context["expired_count"]:
            raise ServiceError(
                409,
                "보존 정책으로 volume artifact가 삭제된 버전은 복원할 수 없습니다.",
                "SERVICE_VOLUME_RESTORE_BACKUP_EXPIRED",
                expired=context.get("expired") or [],
            )
        restored = []
        for item in context["items"]:
            restored.append(self.restore_volume(service, item, operation_id=operation_id, env=env))
        return {"restored": restored, "summary": {key: context[key] for key in ["available_count", "pending_count", "expired_count"]}}


Model = ServiceVolumeBackups()
