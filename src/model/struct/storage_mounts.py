import re
from pathlib import PurePosixPath

import yaml
from psycopg.types.json import Jsonb


CEPHFS_ROOT = "/srv/docker-infra/storage/cephfs"
LOCAL_ROOT = "/srv/docker-infra/storage/local"


def _safe_name(value, fallback="data"):
    clean = re.sub(r"[^a-z0-9_.-]+", "_", str(value or "").strip().lower()).strip("_.-")
    return (clean or fallback)[:80]


def _safe_mount_name(source, service_name, target):
    if source:
        return _safe_name(source, fallback="data")
    target_name = PurePosixPath(str(target or "/data")).name or "data"
    return _safe_name(f"{service_name}_{target_name}", fallback="data")


def _quota_bytes(value):
    if value in (None, ""):
        return None
    try:
        return int(value)
    except Exception:
        try:
            return int(float(value) * 1024 * 1024 * 1024)
        except Exception:
            return None


def _is_absolute_path(value):
    value = str(value or "").strip()
    return value.startswith("/") or re.match(r"^[A-Za-z]:[\\/]", value) is not None


def _is_docker_volume_source(source):
    source = str(source or "").strip()
    if not source or _is_absolute_path(source):
        return False
    if source.startswith(".") or source.startswith("~") or "/" in source or "\\" in source:
        return False
    return True


def _parse_volume_string(raw):
    parts = str(raw or "").split(":")
    if len(parts) == 1:
        return {"source": "", "target": parts[0], "mode": "", "raw": raw}
    if len(parts) == 2:
        return {"source": parts[0], "target": parts[1], "mode": "", "raw": raw}
    return {"source": parts[0], "target": parts[1], "mode": ":".join(parts[2:]), "raw": raw}


class StorageMounts:
    def __init__(self, common=None):
        self.common = common or wiz.model("struct/storage_ceph")

    def list(self, service_id=None, limit=100, env=None):
        query = """
            SELECT
                mount.*,
                service.namespace AS service_namespace,
                service.name AS service_name,
                policy.name AS snapshot_policy_name
            FROM storage_mounts mount
            LEFT JOIN services service ON service.id = mount.service_id
            LEFT JOIN storage_snapshot_policies policy ON policy.id = mount.snapshot_policy_id
        """
        params = []
        if service_id:
            query += " WHERE mount.service_id = %s"
            params.append(service_id)
        query += " ORDER BY mount.created_at DESC LIMIT %s"
        params.append(int(limit or 100))
        return self.common.fetchall(query, params, env=env)

    def summary(self, rows):
        by_backend = {}
        by_status = {}
        for row in rows or []:
            backend = str(row.get("backend") or "unknown")
            status = str(row.get("status") or "unknown")
            by_backend[backend] = by_backend.get(backend, 0) + 1
            by_status[status] = by_status.get(status, 0) + 1
        return {
            "total": len(rows or []),
            "active": by_status.get("active", 0),
            "failed": by_status.get("failed", 0),
            "by_backend": by_backend,
            "by_status": by_status,
        }

    def _healthy_cluster(self, env=None):
        try:
            return self.common.fetchone(
                "SELECT id FROM ceph_clusters WHERE status IN ('running', 'degraded') AND health IN ('HEALTH_OK', 'HEALTH_WARN') ORDER BY created_at ASC LIMIT 1",
                env=env,
            )
        except Exception:
            return None

    def default_backend(self, deployment_mode=None, node=None, requested=None, env=None):
        requested = str(requested or "").strip()
        if requested in {"cephfs", "local_bind"}:
            return requested
        if node is not None:
            if not str(node.get("swarm_node_id") or "").strip():
                return "local_bind"
            return "cephfs" if self._healthy_cluster(env=env) else "local_bind"
        if str(deployment_mode or "").strip() != "swarm":
            return "local_bind"
        return "cephfs" if self._healthy_cluster(env=env) else "local_bind"

    def mount_root(self, backend, env=None):
        if backend == "cephfs":
            try:
                cluster = self.common.fetchone(
                    "SELECT mount_root FROM ceph_clusters WHERE status IN ('running', 'degraded', 'bootstrapping') ORDER BY CASE status WHEN 'running' THEN 0 WHEN 'degraded' THEN 1 ELSE 2 END, created_at ASC LIMIT 1",
                    env=env,
                )
            except Exception:
                cluster = None
            return (cluster or {}).get("mount_root") or CEPHFS_ROOT
        return LOCAL_ROOT

    def host_path(self, namespace, mount_name, backend="cephfs", mount_root=None):
        root = mount_root or (CEPHFS_ROOT if backend == "cephfs" else LOCAL_ROOT)
        service = _safe_name(namespace, fallback="service")
        mount = _safe_name(mount_name, fallback="data")
        return f"{root.rstrip('/')}/services/{service}/mounts/{mount}/current"

    def _storage_mount_config(self, storage, service_name, source, target):
        storage = storage if isinstance(storage, dict) else {}
        rows = storage.get("mounts") if isinstance(storage.get("mounts"), list) else []
        for row in rows:
            if not isinstance(row, dict):
                continue
            if str(row.get("component_key") or row.get("service") or "") not in {"", service_name}:
                continue
            if str(row.get("target") or row.get("container_path") or "") == str(target or ""):
                return row
            if source and str(row.get("name") or row.get("mount_name") or row.get("original_source") or "") == str(source):
                return row
        return {}

    def _convert_volume(self, namespace, backend, mount_root, service_name, raw, storage=None):
        if isinstance(raw, dict):
            source = str(raw.get("source") or raw.get("src") or "").strip()
            target = str(raw.get("target") or raw.get("dst") or raw.get("destination") or "").strip()
            volume_type = str(raw.get("type") or ("bind" if _is_absolute_path(source) else "volume")).strip()
            should_convert = bool(target) and (volume_type == "volume" or _is_docker_volume_source(source) or not source)
            if not should_convert:
                return raw, None
            config = self._storage_mount_config(storage, service_name, source, target)
            mount_name = _safe_mount_name(config.get("name") or config.get("mount_name") or source, service_name, target)
            host_path = self.host_path(namespace, mount_name, backend=backend, mount_root=mount_root)
            next_raw = {key: value for key, value in raw.items() if key not in {"source", "src", "type", "volume"}}
            next_raw.update({"type": "bind", "source": host_path, "target": target})
            spec = self._spec(service_name, mount_name, backend, source, host_path, target, config)
            return next_raw, spec

        parsed = _parse_volume_string(raw)
        source = str(parsed.get("source") or "").strip()
        target = str(parsed.get("target") or "").strip()
        should_convert = bool(target) and (_is_docker_volume_source(source) or not source)
        if not should_convert:
            return raw, None
        config = self._storage_mount_config(storage, service_name, source, target)
        mount_name = _safe_mount_name(config.get("name") or config.get("mount_name") or source, service_name, target)
        host_path = self.host_path(namespace, mount_name, backend=backend, mount_root=mount_root)
        mode = f":{parsed['mode']}" if parsed.get("mode") else ""
        spec = self._spec(service_name, mount_name, backend, source, host_path, target, config)
        return f"{host_path}:{target}{mode}", spec

    def _spec(self, service_name, mount_name, backend, original_source, host_path, target, config=None):
        config = config or {}
        return {
            "component_key": service_name,
            "mount_name": mount_name,
            "backend": backend,
            "original_source": original_source or "",
            "host_path": host_path,
            "container_path": target,
            "quota_bytes": _quota_bytes(config.get("quota_bytes") if config.get("quota_bytes") is not None else config.get("quota_gb")),
            "snapshot_policy_id": config.get("snapshot_policy_id"),
            "metadata": {
                "storage_normalizer": "cephfs_bind_mount_v1",
                "snapshot_policy": config.get("snapshot_policy") or "",
                "component_key": service_name,
            },
        }

    def normalize_compose(self, namespace, content, backend="cephfs", storage=None, env=None):
        compose = yaml.safe_load(content or "{}") or {}
        if not isinstance(compose, dict):
            return {"content": content, "mounts": [], "changed": False, "backend": backend}
        mount_root = self.mount_root(backend, env=env)
        converted_sources = set()
        removed_top_level_volumes = []
        mounts = []
        changed = False
        for service_name, service in (compose.get("services") or {}).items():
            if not isinstance(service, dict):
                continue
            next_volumes = []
            for raw in service.get("volumes") or []:
                next_raw, spec = self._convert_volume(namespace, backend, mount_root, service_name, raw, storage=storage)
                next_volumes.append(next_raw)
                if spec:
                    mounts.append(spec)
                    changed = True
                    if spec["original_source"]:
                        converted_sources.add(spec["original_source"])
            if next_volumes:
                service["volumes"] = next_volumes
            elif "volumes" in service:
                service.pop("volumes", None)
        if "volumes" in compose:
            root_volumes = compose.get("volumes")
            if isinstance(root_volumes, dict):
                removed_top_level_volumes = list(root_volumes.keys())
            compose.pop("volumes", None)
            changed = True
        if mounts:
            compose["x-docker-infra.storage"] = {
                "backend": backend,
                "mounts": [
                    {
                        "name": row["mount_name"],
                        "component_key": row["component_key"],
                        "source": row["host_path"],
                        "target": row["container_path"],
                        "original_source": row["original_source"],
                    }
                    for row in mounts
                ],
                "docker_managed_volume_allowed": False,
            }
        return {
            "content": yaml.safe_dump(compose, sort_keys=False, allow_unicode=False),
            "mounts": mounts,
            "changed": changed,
            "backend": backend,
            "mount_root": mount_root,
            "converted_sources": sorted(converted_sources),
            "removed_top_level_volumes": removed_top_level_volumes,
        }

    def record_service_mounts(self, service_id, mounts, test_run_id=None, env=None):
        rows = []
        with self.common.connect(env=env) as connection:
            with connection.cursor() as cursor:
                for spec in mounts or []:
                    cursor.execute(
                        """
                        INSERT INTO storage_mounts(service_id, mount_name, backend, original_source, host_path, container_path, quota_bytes, snapshot_policy_id, status, test_run_id, metadata)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, 'active', %s, %s)
                        ON CONFLICT(service_id, mount_name, host_path) DO UPDATE
                        SET backend = EXCLUDED.backend,
                            original_source = EXCLUDED.original_source,
                            container_path = EXCLUDED.container_path,
                            quota_bytes = EXCLUDED.quota_bytes,
                            snapshot_policy_id = EXCLUDED.snapshot_policy_id,
                            status = 'active',
                            metadata = storage_mounts.metadata || EXCLUDED.metadata,
                            updated_at = now()
                        RETURNING *
                        """,
                        (
                            service_id,
                            spec["mount_name"],
                            spec["backend"],
                            spec.get("original_source") or "",
                            spec["host_path"],
                            spec["container_path"],
                            spec.get("quota_bytes"),
                            spec.get("snapshot_policy_id"),
                            test_run_id,
                            Jsonb(spec.get("metadata") or {}),
                        ),
                    )
                    rows.append(self.common.row(cursor.fetchone()))
        return rows
Model = StorageMounts()
