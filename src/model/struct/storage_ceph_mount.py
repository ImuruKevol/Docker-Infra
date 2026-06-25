import base64
import re
from datetime import datetime
from pathlib import Path

from psycopg.types.json import Jsonb


catalog = wiz.model("struct/local_command_catalog")
shared = wiz.model("struct/nodes_shared")


def _ceph_image(value):
    image = str(value or "").strip()
    return "quay.io/ceph/ceph:v19.2.4" if image in {"", "quay.io/ceph/ceph:latest", "quay.io/ceph/ceph:v19"} else image


def _utc_now():
    return datetime.utcnow().replace(microsecond=0).isoformat() + "Z"


def _safe_id(*values):
    for value in values:
        clean = re.sub(r"[^a-z0-9_.-]+", "-", str(value or "").strip().lower()).strip(".-")
        if clean:
            return clean[:63]
    return "node"


def _safe_result(result):
    result = result or {}
    return {
        "status": result.get("status"),
        "exit_code": result.get("exit_code"),
        "stdout": (result.get("stdout") or "")[-4000:],
        "stderr": (result.get("stderr") or "")[-4000:],
    }


class StorageCephMount:
    def __init__(self, common=None, nodes=None, local_executor=None, operations=None):
        self.common = common or wiz.model("struct/storage_ceph")
        self.nodes = nodes or wiz.model("struct/nodes")
        self.local_executor = local_executor or wiz.model("struct/local_executor")
        self.operations = operations or wiz.model("struct/operations")

    def list_node_mounts(self, cluster_id=None, env=None):
        query = """
            SELECT
                ceph_node.*,
                cluster.mount_root AS mount_root,
                node.name AS node_name,
                node.host AS node_host,
                node.swarm_node_id AS swarm_node_id
            FROM ceph_nodes ceph_node
            JOIN ceph_clusters cluster ON cluster.id = ceph_node.cluster_id
            LEFT JOIN nodes node ON node.id = ceph_node.node_id
        """
        params = []
        if cluster_id:
            query += " WHERE ceph_node.cluster_id = %s"
            params.append(cluster_id)
        query += " ORDER BY node.name ASC NULLS LAST, ceph_node.created_at ASC"
        rows = self.common.fetchall(query, params, env=env)
        if cluster_id:
            rows.extend(self.missing_swarm_nodes(cluster_id, env=env))
        return rows

    def missing_swarm_nodes(self, cluster_id, env=None):
        if not cluster_id:
            return []
        rows = self.common.fetchall(
            """
            SELECT node.*
            FROM nodes node
            WHERE COALESCE(NULLIF(node.swarm_node_id, ''), '') <> ''
              AND NOT EXISTS (
                SELECT 1 FROM ceph_nodes ceph_node
                WHERE ceph_node.cluster_id = %s
                  AND ceph_node.node_id = node.id
              )
            ORDER BY node.name ASC NULLS LAST, node.created_at ASC
            """,
            [cluster_id],
            env=env,
        )
        return [
            {
                "id": None,
                "cluster_id": str(cluster_id),
                "node_id": row.get("id"),
                "node_name": row.get("name"),
                "node_host": row.get("host"),
                "swarm_node_id": row.get("swarm_node_id"),
                "ceph_hostname": _safe_id(row.get("name"), row.get("host"), row.get("id")),
                "mount_root": "",
                "status": "warning",
                "mount_status": "missing",
                "metadata": {"reason": "ceph_node_missing", "message": "Swarm node가 CephFS mount 관리 대상에 아직 등록되지 않았습니다."},
            }
            for row in rows
        ]

    def summary(self, rows):
        by_status = {}
        for row in rows or []:
            status = str(row.get("mount_status") or "unknown")
            by_status[status] = by_status.get(status, 0) + 1
        return {
            "total": len(rows or []),
            "mounted": by_status.get("mounted", 0),
            "unmounted": by_status.get("unmounted", 0),
            "failed": by_status.get("failed", 0),
            "missing": by_status.get("missing", 0),
            "by_status": by_status,
        }

    def _current_cluster(self, env=None):
        return self.common.fetchone(
            """
            SELECT *
            FROM ceph_clusters
            WHERE status IN ('running', 'degraded', 'bootstrapping')
            ORDER BY
                CASE status WHEN 'running' THEN 0 WHEN 'degraded' THEN 1 ELSE 2 END,
                created_at ASC
            LIMIT 1
            """,
            env=env,
        )

    def _operation(self, message, payload=None, env=None):
        return self.operations.create(
            "storage.ceph.mount.ensure",
            target_type="storage",
            message=message,
            requested_payload=payload or {},
            metadata={"domain": "storage", "component": "cephfs_mount"},
            env=env,
        )

    def _append(self, operation_id, message, metadata=None, env=None, stream="system"):
        if operation_id:
            return self.operations.append_output(operation_id, message, stream=stream, metadata=metadata or {}, env=env)
        return None

    def _swarm_nodes(self, node_id=None, env=None):
        params = []
        query = """
            SELECT *
            FROM nodes
            WHERE COALESCE(NULLIF(swarm_node_id, ''), '') <> ''
        """
        if node_id:
            query += " AND id = %s"
            params.append(node_id)
        query += " ORDER BY is_local_master DESC, created_at ASC, name ASC"
        return self.common.fetchall(query, params, env=env)

    def _upsert_ceph_node(self, cluster, node, env=None):
        metadata = {
            "swarm_node_id": node.get("swarm_node_id"),
            "mount_managed": True,
            "mount_registered_at": _utc_now(),
        }
        return self.common.fetchone(
            """
            INSERT INTO ceph_nodes(cluster_id, node_id, ceph_hostname, ip_address, roles, status, mount_status, metadata)
            VALUES (%s, %s, %s, %s, '[]'::jsonb, 'ready', 'unmounted', %s)
            ON CONFLICT(cluster_id, node_id) DO UPDATE
            SET status = CASE WHEN ceph_nodes.status = 'failed' THEN 'warning' ELSE ceph_nodes.status END,
                metadata = ceph_nodes.metadata || EXCLUDED.metadata,
                updated_at = now()
            RETURNING *
            """,
            [
                cluster["id"],
                node["id"],
                _safe_id(node.get("name"), node.get("host"), node.get("id")),
                node.get("host") or "",
                Jsonb(metadata),
            ],
            env=env,
        )

    def _admin_keyring_b64(self, cluster):
        metadata = (cluster or {}).get("metadata") or {}
        for key in ["mount_client_keyring_b64", "admin_keyring_b64"]:
            value = str(metadata.get(key) or "").strip()
            if value:
                return value
        fsid = str((cluster or {}).get("fsid") or "").strip()
        if not fsid:
            return ""
        keyring_path = Path("/srv/docker-infra/ceph") / fsid / "etc" / "ceph.client.admin.keyring"
        if not keyring_path.is_file():
            return ""
        return base64.b64encode(keyring_path.read_bytes()).decode("ascii")

    def _mount_params(self, cluster, keyring_b64):
        metadata = (cluster or {}).get("metadata") or {}
        mount_client = str(metadata.get("mount_client") or "client.admin").strip()
        return {
            "fsid": cluster.get("fsid"),
            "image": _ceph_image(cluster.get("ceph_image")),
            "mount_root": cluster.get("mount_root") or "/srv/docker-infra/storage/cephfs",
            "mon_host": (metadata.get("mon_host") or "").strip(),
            "client_name": mount_client,
            "client_keyring_b64": keyring_b64,
        }

    def _remote_command(self, params):
        return [
            "sh", "-lc", catalog.STORAGE_CEPH_MOUNT_ENSURE_SCRIPT, "sh",
            params["fsid"], params["image"], params["mount_root"], params["mon_host"],
            params["client_name"], params["client_keyring_b64"],
        ]

    def _run_node_mount(self, node, params, env=None):
        if shared.is_local_master_node(node):
            return self.local_executor.run("storage.ceph.mount.ensure", timeout_seconds=180, params=params, env=env, capture_limit=12000)
        detail = self.nodes.detail(node["id"], env=env)
        return self.nodes._run_ssh_command(detail, self._remote_command(params), timeout_seconds=180, env=env, capture_limit=12000)

    def _set_mount_status(self, cluster_id, node_id, status, metadata=None, env=None):
        return self.common.fetchone(
            """
            UPDATE ceph_nodes
            SET mount_status = %s,
                status = CASE WHEN %s = 'failed' THEN 'warning' ELSE status END,
                metadata = metadata || %s,
                updated_at = now()
            WHERE cluster_id = %s AND node_id = %s
            RETURNING *
            """,
            [status, status, Jsonb(metadata or {}), cluster_id, node_id],
            env=env,
        )

    def ensure_node_mount(self, payload=None, env=None):
        payload = payload or {}
        cluster = self._current_cluster(env=env)
        if not cluster:
            raise RuntimeError("Ceph cluster가 구성되어 있지 않아 CephFS mount를 보장할 수 없습니다.")
        keyring_b64 = self._admin_keyring_b64(cluster)
        if not keyring_b64:
            raise RuntimeError("CephFS mount용 cephx keyring을 찾을 수 없습니다.")

        node_id = str(payload.get("node_id") or "").strip()
        nodes = self._swarm_nodes(node_id=node_id, env=env)
        if node_id and not nodes:
            raise RuntimeError("대상 node가 Swarm/Ceph mount 대상이 아닙니다.")
        operation_id = payload.get("operation_id")
        operation = None
        if not operation_id:
            operation = self._operation("CephFS host mount 보장을 시작했습니다.", payload, env=env)
            operation_id = operation["id"]

        params = self._mount_params(cluster, keyring_b64)
        results = []
        try:
            for node in nodes:
                ceph_node = self._upsert_ceph_node(cluster, node, env=env)
                label = node.get("name") or node.get("host") or node.get("id")
                self._append(operation_id, f"{label}: CephFS mount 상태를 확인하고 필요 시 remount합니다.", {"node_id": node.get("id")}, env=env)
                result = self._run_node_mount(node, params, env=env)
                safe = _safe_result(result)
                status = "mounted" if result.get("status") == "ok" else "failed"
                metadata = {
                    "mount_checked_at": _utc_now(),
                    "mount_root": params["mount_root"],
                    "mount_result": safe,
                    "ceph_node_id": str((ceph_node or {}).get("id") or ""),
                }
                self._set_mount_status(cluster["id"], node["id"], status, metadata=metadata, env=env)
                self._append(operation_id, f"{label}: CephFS mount {status}", {"node_id": node.get("id"), **safe}, env=env, stream="system" if status == "mounted" else "stderr")
                results.append({"node_id": node["id"], "node": label, "mount_status": status, "result": safe})
            if operation:
                operation = self.operations.transition(
                    operation_id,
                    "succeeded" if all(row["mount_status"] == "mounted" for row in results) else "failed",
                    message="CephFS host mount 보장을 완료했습니다.",
                    result_payload={"results": results},
                    env=env,
                )
            return {"cluster": cluster, "results": results, "operation": operation or (self.operations.detail(operation_id, env=env) if operation_id else None)}
        except Exception as exc:
            if operation:
                operation = self.operations.transition(
                    operation_id,
                    "failed",
                    message="CephFS host mount 보장 중 오류가 발생했습니다.",
                    result_payload={"message": str(exc), "results": results},
                    env=env,
                )
            raise


Model = StorageCephMount()
