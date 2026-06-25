import os
import threading

REQUIRED_TABLES = [
    "ceph_clusters",
    "ceph_nodes",
    "ceph_osd_slots",
    "storage_mounts",
    "storage_snapshots",
    "storage_snapshot_policies",
]


def _metadata(row):
    value = (row or {}).get("metadata") or {}
    return value if isinstance(value, dict) else {}


def _roles(row):
    roles = (row or {}).get("roles") or []
    if isinstance(roles, list):
        return {str(role).lower() for role in roles}
    if isinstance(roles, dict):
        return {str(key).lower() for key, enabled in roles.items() if enabled}
    return set()


def _daemon_from_metadata(cluster):
    metadata = _metadata(cluster)
    daemons = metadata.get("daemons") or {}
    return daemons if isinstance(daemons, dict) else {}


class StorageCephCluster:
    def __init__(self, common=None, osd=None, mount=None, preflight=None, bootstrap=None, operations=None):
        self.common = common or wiz.model("struct/storage_ceph")
        self.osd = osd or wiz.model("struct/storage_ceph_osd")
        self.mount = mount or wiz.model("struct/storage_ceph_mount")
        self.preflight = preflight or wiz.model("struct/storage_ceph_preflight")
        self.bootstrap = bootstrap or wiz.model("struct/storage_ceph_bootstrap")
        self.operations = operations or wiz.model("struct/operations")

    def schema_status(self, env=None):
        return self.common.tables_ready(REQUIRED_TABLES, env=env)

    def list_clusters(self, env=None):
        return self.common.fetchall(
            """
            SELECT *
            FROM ceph_clusters
            ORDER BY
                CASE status
                    WHEN 'running' THEN 0
                    WHEN 'degraded' THEN 1
                    WHEN 'bootstrapping' THEN 2
                    WHEN 'pending' THEN 3
                    ELSE 4
                END,
                created_at ASC
            """,
            env=env,
        )

    def current(self, env=None):
        rows = self.list_clusters(env=env)
        return rows[0] if rows else None

    def list_nodes(self, cluster_id=None, env=None):
        query = """
            SELECT
                ceph_node.*,
                node.name AS node_name,
                node.host AS node_host,
                node.status AS node_status,
                node.swarm_node_id AS swarm_node_id,
                node.is_local_master AS node_is_local_master
            FROM ceph_nodes ceph_node
            LEFT JOIN nodes node ON node.id = ceph_node.node_id
        """
        params = []
        if cluster_id:
            query += " WHERE ceph_node.cluster_id = %s"
            params.append(cluster_id)
        query += " ORDER BY node.name ASC NULLS LAST, ceph_node.created_at ASC"
        return self.common.fetchall(query, params, env=env)

    def capacity(self, cluster, slots):
        metadata = _metadata(cluster)
        capacity = metadata.get("capacity") or {}
        osd_summary = self.osd.summary(slots)
        raw_bytes = int(capacity.get("raw_bytes") or osd_summary["raw_bytes"] or 0)
        replica_size = int(metadata.get("replica_size") or 3)
        usable_bytes = int(capacity.get("usable_bytes") or (raw_bytes // max(replica_size, 1)))
        recommended_bytes = int(capacity.get("recommended_bytes") or (usable_bytes * 0.85))
        return {
            "raw_bytes": raw_bytes,
            "usable_bytes": usable_bytes,
            "recommended_bytes": recommended_bytes,
            "used_bytes": int(capacity.get("used_bytes") or 0),
        }

    def daemon_summary(self, cluster, nodes, slots):
        metadata_daemons = _daemon_from_metadata(cluster)
        roles = [_roles(node) for node in nodes or []]
        active_osd = len([slot for slot in slots or [] if slot.get("status") == "active"])
        total_osd = len([slot for slot in slots or [] if slot.get("status") != "removed"])
        slot_osd = {"up": active_osd, "in": active_osd, "total": total_osd}
        if metadata_daemons:
            summary = dict(metadata_daemons)
            if total_osd or "osd" not in summary:
                summary["osd"] = {**(summary.get("osd") or {}), **slot_osd}
            return summary
        return {
            "mon": {"ready": len([item for item in roles if "mon" in item]), "wanted": 3},
            "mgr": {"active": len([item for item in roles if "mgr" in item]), "standby": 0},
            "mds": {"active": len([item for item in roles if "mds" in item]), "standby": 0},
            "osd": slot_osd,
        }

    def master_status(self, cluster, nodes):
        if not cluster:
            return {"configured": False, "status": "not_configured", "message": "Ceph master cluster가 아직 없습니다."}
        local_rows = [row for row in nodes or [] if row.get("node_is_local_master")]
        local = local_rows[0] if local_rows else None
        roles = _roles(local)
        has_master_roles = bool({"mon", "mgr", "mds"} & roles)
        fsid = str(cluster.get("fsid") or "")
        runtime_ready = bool(fsid and os.path.exists(f"/srv/docker-infra/ceph/{fsid}/etc/ceph.conf"))
        configured = bool(local and has_master_roles and runtime_ready)
        return {
            "configured": configured,
            "status": "ready" if configured else "not_configured",
            "node_id": (local or {}).get("node_id") or "",
            "ceph_hostname": (local or {}).get("ceph_hostname") or "",
            "runtime_ready": runtime_ready,
            "roles": sorted(roles),
            "message": "Docker Infra master Ceph runtime이 준비되었습니다." if configured else "Docker Infra master Ceph runtime 구성이 필요합니다.",
        }

    def _operation(self, operation_type, message, payload=None, env=None):
        return self.operations.create(
            operation_type,
            target_type="storage",
            message=message,
            requested_payload=payload or {},
            metadata={"domain": "storage", "component": "ceph"},
            env=env,
        )

    def _append(self, operation_id, message, metadata=None, env=None, stream="system"):
        return self.operations.append_output(operation_id, message, stream=stream, metadata=metadata or {}, env=env)

    def _log_preflight(self, operation_id, result, env=None):
        summary = result.get("summary") or {}
        self._append(
            operation_id,
            f"Ceph preflight 대상 Swarm 서버 {summary.get('swarm_candidates', 0)}대입니다.",
            metadata={"step": "candidate-filter", "summary": summary},
            env=env,
        )
        for check in result.get("checks") or []:
            self._append(operation_id, f"{check['title']}: {check['status']} - {check['message']}", metadata=check, env=env)
        for row in result.get("nodes") or []:
            failed_titles = [check["title"] for check in row.get("checks", []) if check["status"] == "error"]
            suffix = f" 실패 항목: {', '.join(failed_titles)}" if failed_titles else ""
            self._append(operation_id, f"{row.get('label')}: {row.get('status')}{suffix}", metadata={"node_id": row.get("id")}, env=env)
    def _progress_preflight(self, operation_id, message, metadata=None, env=None):
        self._append(operation_id, message, metadata=metadata or {}, env=env)

    def _run_preflight_operation(self, operation_id, payload, env=None):
        def on_progress(message, metadata=None):
            self._progress_preflight(operation_id, message, metadata, env=env)

        try:
            on_progress("Ceph preflight background worker가 시작되었습니다.", {"step": "worker-start"})
            result = self.preflight.run(payload, env=env, on_progress=on_progress)
            summary = result.get("summary") or {}
            on_progress(f"Ceph preflight가 {result.get('status')} 상태로 완료되었습니다.", {"step": "complete", "summary": summary})
            self.operations.transition(
                operation_id,
                "succeeded",
                message="Ceph cluster 사전 점검이 완료되었습니다.",
                result_payload=result,
                env=env,
            )
        except Exception as exc:
            self._append(
                operation_id,
                f"Ceph preflight 실패: {exc}",
                stream="stderr",
                metadata={"step": "failed", "error_code": "CEPH_PREFLIGHT_FAILED"},
                env=env,
            )
            self.operations.transition(
                operation_id,
                "failed",
                message="Ceph cluster 사전 점검 중 오류가 발생했습니다.",
                result_payload={"status": "failed", "bootstrap_allowed": False, "message": str(exc), "error_code": "CEPH_PREFLIGHT_FAILED"},
                env=env,
            )

    def cluster_preflight(self, payload=None, env=None):
        payload = payload or {}
        operation = self._operation("storage.cluster.preflight", "Ceph cluster 사전 점검을 background로 시작했습니다.", payload, env=env)
        operation_id = operation["id"]
        self._append(operation_id, "Ceph preflight operation을 생성했고 node 점검을 background로 예약했습니다.", metadata={"step": "queued"}, env=env)
        if payload.get("sync"):
            self._run_preflight_operation(operation_id, dict(payload), env=env)
            operation = self.operations.detail(operation_id, env=env)
            result = operation.get("result_payload") or {}
            if "status" not in result:
                result = {"status": operation.get("status"), "bootstrap_allowed": False, **result}
            return {**result, "operation": operation}
        thread = threading.Thread(target=self._run_preflight_operation, args=(operation_id, dict(payload), env), daemon=True)
        thread.start()
        return {
            "status": "running",
            "bootstrap_allowed": False,
            "message": "Ceph cluster 사전 점검을 background로 실행 중입니다.",
            "operation": self.operations.detail(operation_id, env=env),
        }

    def cluster_bootstrap(self, payload=None, env=None):
        return self.bootstrap.run(payload or {}, env=env)

    def cluster_master_bootstrap(self, payload=None, env=None):
        return self.bootstrap.run_master(payload or {}, env=env)

    def osd_nodes(self, payload=None, env=None):
        cluster = self.current(env=env)
        cluster_id = None if cluster is None else cluster["id"]
        return {
            "cluster": cluster,
            "nodes": self.list_nodes(cluster_id=cluster_id, env=env) if cluster_id else [],
            "osd_slots": self.osd.list_slots(cluster_id=cluster_id, env=env) if cluster_id else [],
        }

    def osd_slot_plan(self, payload=None, env=None):
        return self.osd.slot_plan(payload or {}, env=env)

    def osd_slot_create(self, payload=None, env=None):
        return self.osd.slot_create(payload or {}, env=env)

    def overview(self, env=None):
        schema = self.schema_status(env=env)
        if not schema["ready"]:
            return {"schema_ready": False, "schema_missing": schema["missing"], "clusters": [], "cluster": None}
        clusters = self.list_clusters(env=env)
        cluster = clusters[0] if clusters else None
        cluster_id = None if cluster is None else cluster["id"]
        nodes = self.list_nodes(cluster_id=cluster_id, env=env) if cluster_id else []
        slots = self.osd.list_slots(cluster_id=cluster_id, env=env) if cluster_id else []
        node_mounts = self.mount.list_node_mounts(cluster_id=cluster_id, env=env) if cluster_id else []
        return {
            "schema_ready": True,
            "schema_missing": [],
            "clusters": clusters,
            "cluster": cluster,
            "ceph_nodes": nodes,
            "osd_slots": slots,
            "node_mounts": node_mounts,
            "master": self.master_status(cluster, nodes),
            "capacity": self.capacity(cluster, slots),
            "daemons": self.daemon_summary(cluster, nodes, slots),
            "osd_summary": self.osd.summary(slots),
            "node_mount_summary": self.mount.summary(node_mounts),
        }


Model = StorageCephCluster()
