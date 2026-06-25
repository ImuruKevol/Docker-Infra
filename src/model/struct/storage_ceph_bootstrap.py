import uuid

from psycopg.types.json import Jsonb


REQUIRED_TABLES = [
    "ceph_clusters",
    "ceph_nodes",
    "ceph_osd_slots",
    "storage_mounts",
    "storage_snapshots",
    "storage_snapshot_policies",
]


def _safe_id(value, fallback):
    text = "".join(ch if ch.isalnum() else "-" for ch in str(value or "").lower()).strip("-")
    return text[:32].strip("-") or fallback


class StorageCephBootstrap:
    def __init__(self, common=None, preflight=None, operations=None, local_executor=None, nodes=None, runtime=None):
        self.common = common or wiz.model("struct/storage_ceph")
        self.preflight = preflight or wiz.model("struct/storage_ceph_preflight")
        self.operations = operations or wiz.model("struct/operations")
        self.local_executor = local_executor or wiz.model("struct/local_executor")
        self.nodes = nodes or wiz.model("struct/nodes")
        self.runtime = runtime or wiz.model("struct/storage_ceph_runtime")

    def _operation(self, payload=None, env=None):
        return self.operations.create(
            "storage.cluster.bootstrap",
            target_type="storage",
            message="Dockerized Ceph cluster bootstrap을 시작했습니다.",
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
            failed = [check["title"] for check in row.get("checks", []) if check["status"] == "error"]
            suffix = f" 실패 항목: {', '.join(failed)}" if failed else ""
            self._append(operation_id, f"{row.get('label')}: {row.get('status')}{suffix}", metadata={"node_id": row.get("id")}, env=env)
    def _schema_ready(self, env=None):
        schema = self.common.tables_ready(REQUIRED_TABLES, env=env)
        if not schema["ready"]:
            raise RuntimeError("Ceph storage migration이 아직 적용되지 않았습니다: " + ", ".join(schema["missing"]))

    def _assert_no_active_cluster(self, env=None):
        if self._active_cluster(env=env):
            raise RuntimeError("이미 Ceph cluster가 구성 중이거나 운영 중입니다.")

    def _active_cluster(self, env=None):
        return self.common.fetchone(
            """
            SELECT *
            FROM ceph_clusters
            WHERE status IN ('pending', 'bootstrapping', 'running', 'degraded')
            ORDER BY created_at ASC
            LIMIT 1
            """,
            env=env,
        )

    def _plan(self, preflight, ceph_image, fsid, master_only=False):
        candidates = [row for row in preflight.get("nodes") or [] if row.get("eligible")][:3]
        if not candidates:
            raise RuntimeError("Ceph daemon을 배치할 eligible Swarm node가 없습니다.")
        letters = ["a", "b", "c"]
        daemons = []
        roles = {}
        for index, node in enumerate(candidates):
            node["ceph_hostname"] = _safe_id(node.get("label") or node.get("swarm_node_id"), letters[index])
        for index, node in enumerate(candidates):
            roles.setdefault(node["id"], set()).add("mon")
            daemons.append({"daemon": "mon", "daemon_id": node["ceph_hostname"], "node": node})
        for daemon in ["mgr", "mds"]:
            for index, node in enumerate(candidates[:1] if master_only else candidates[:2]):
                roles.setdefault(node["id"], set()).add(daemon)
                daemons.append({"daemon": daemon, "daemon_id": node["ceph_hostname"], "node": node})
        for item in daemons:
            node_key = item["node"]["ceph_hostname"]
            item["service_name"] = f"docker-infra-ceph-{item['daemon']}-{item['daemon_id']}-{node_key}"[:120].strip("-")
            item["image"] = ceph_image
            item["fsid"] = fsid
        return {
            "fsid": fsid,
            "nodes": candidates,
            "roles": {node_id: sorted(value) for node_id, value in roles.items()},
            "mon_initial_members": ",".join([node["ceph_hostname"] for node in candidates]),
            "mon_host": ",".join([node.get("host") or "" for node in candidates]),
            "daemons": daemons,
        }

    def _create_cluster(self, plan, payload, operation_id, env=None):
        mon_count = len([item for item in plan["daemons"] if item["daemon"] == "mon"])
        mgr_count = len([item for item in plan["daemons"] if item["daemon"] == "mgr"])
        mds_count = len([item for item in plan["daemons"] if item["daemon"] == "mds"])
        metadata = {
            "bootstrap_poc": False,
            "bootstrap_operation_id": operation_id,
            "dockerized": True,
            "master_only": bool(payload.get("master_only")),
            "placement": [
                {
                    "daemon": item["daemon"],
                    "daemon_id": item["daemon_id"],
                    "service_name": item["service_name"],
                    "node_id": item["node"]["id"],
                    "swarm_node_id": item["node"]["swarm_node_id"],
                    "ceph_hostname": item["node"].get("ceph_hostname"),
                }
                for item in plan["daemons"]
            ],
            "daemons": {
                "mon": {"ready": mon_count, "wanted": max(mon_count, 1)},
                "mgr": {"active": min(mgr_count, 1), "standby": max(mgr_count - 1, 0)},
                "mds": {"active": min(mds_count, 1), "standby": max(mds_count - 1, 0)},
                "osd": {"up": 0, "in": 0, "total": 0},
            },
        }
        with self.common.connect(env=env) as connection:
            with connection.cursor() as cursor:
                if payload.get("existing_cluster_id"):
                    cursor.execute(
                        """
                        UPDATE ceph_clusters
                        SET status = 'bootstrapping', health = 'HEALTH_WARN', ceph_image = %s, metadata = metadata || %s
                        WHERE id = %s
                        RETURNING *
                        """,
                        (payload.get("ceph_image"), Jsonb(metadata), payload.get("existing_cluster_id")),
                    )
                else:
                    cursor.execute(
                        """
                        INSERT INTO ceph_clusters(fsid, status, health, ceph_image, public_network, cluster_network, mount_root, metadata)
                        VALUES (%s, 'bootstrapping', 'HEALTH_WARN', %s, %s, %s, %s, %s)
                        RETURNING *
                        """,
                        (
                            payload.get("fsid") or str(uuid.uuid4()),
                            payload.get("ceph_image"),
                            payload.get("public_network") or "",
                            payload.get("cluster_network") or "",
                            payload.get("mount_root") or "/srv/docker-infra/storage/cephfs",
                            Jsonb(metadata),
                        ),
                    )
                cluster = self.common.row(cursor.fetchone())
                for node in plan["nodes"]:
                    cursor.execute(
                        """
                        INSERT INTO ceph_nodes(cluster_id, node_id, ceph_hostname, ip_address, roles, status, mount_status, metadata)
                        VALUES (%s, %s, %s, %s, %s, 'ready', 'unmounted', %s)
                        ON CONFLICT(cluster_id, node_id) DO UPDATE
                        SET roles = EXCLUDED.roles, ceph_hostname = EXCLUDED.ceph_hostname, ip_address = EXCLUDED.ip_address, updated_at = now()
                        """,
                        (
                            cluster["id"],
                            node["id"],
                            node.get("ceph_hostname") or _safe_id(node.get("label"), node["id"][:8]),
                            node.get("host") or "",
                            Jsonb(plan["roles"].get(node["id"], [])),
                            Jsonb({"bootstrap_operation_id": operation_id, "swarm_node_id": node.get("swarm_node_id")}),
                        ),
                    )
                return cluster

    def _set_cluster_status(self, cluster_id, status, metadata=None, env=None):
        with self.common.connect(env=env) as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    UPDATE ceph_clusters
                    SET status = %s, metadata = metadata || %s
                    WHERE id = %s
                    RETURNING *
                    """,
                    (status, Jsonb(metadata or {}), cluster_id),
                )
                return self.common.row(cursor.fetchone())

    def _place_daemon(self, operation_id, item, env=None):
        self._append(
            operation_id,
            f"{item['daemon'].upper()} {item['daemon_id']} Ceph container를 {item['node'].get('label')} Swarm node에 배치합니다.",
            metadata={"step": "daemon-placement", "service_name": item["service_name"], "swarm_node_id": item["node"].get("swarm_node_id")},
            env=env,
        )
        result = self.local_executor.run(
            "storage.ceph.daemon.service.create",
            timeout_seconds=120,
            params={
                "service_name": item["service_name"],
                "swarm_node_id": item["node"].get("swarm_node_id"),
                "daemon": item["daemon"],
                "daemon_id": item["daemon_id"],
                "image": item["image"],
                "fsid": item["fsid"],
            },
            env=env,
        )
        if result.get("stdout"):
            self._append(operation_id, result["stdout"], metadata={"service_name": item["service_name"]}, env=env, stream="stdout")
        already_exists = "already exists" in (result.get("stderr") or result.get("stdout") or "").lower()
        if result.get("status") != "ok" and not already_exists:
            self._append(operation_id, result.get("stderr") or result.get("stdout") or "docker service create failed", metadata=result, env=env, stream="stderr")
            raise RuntimeError(f"{item['service_name']} 배치에 실패했습니다.")
        return result

    def run(self, payload=None, env=None):
        payload = payload or {}
        operation = self._operation(payload, env=env)
        operation_id = operation["id"]
        try:
            self._schema_ready(env=env)
            if not payload.get("existing_cluster_id"):
                self._assert_no_active_cluster(env=env)
            preflight = self.preflight.run(payload, env=env)
            self._log_preflight(operation_id, preflight, env=env)
            if not preflight.get("bootstrap_allowed"):
                operation = self.operations.transition(
                    operation_id,
                    "failed",
                    message="Ceph preflight 실패로 bootstrap을 중단했습니다.",
                    result_payload={"preflight": preflight},
                    env=env,
                )
                return {"preflight": preflight, "operation": operation}
            ceph_image = "quay.io/ceph/ceph:v19.2.4" if payload.get("ceph_image") in {"quay.io/ceph/ceph:latest", "quay.io/ceph/ceph:v19"} else (payload.get("ceph_image") or "quay.io/ceph/ceph:v19.2.4")
            fsid = payload.get("fsid") or str(uuid.uuid4())
            payload = {**payload, "ceph_image": ceph_image, "fsid": fsid}
            keyrings = self.runtime.keyrings(ceph_image, env=env)
            plan = self._plan(preflight, ceph_image, fsid, master_only=bool(payload.get("master_only")))
            self.runtime.ensure_nodes(operation_id, plan, payload, keyrings, env=env)
            cluster = self._create_cluster(plan, payload, operation_id, env=env)
            results = []
            metadata_ready = not payload.get("master_only")
            for item in plan["daemons"]:
                if item["daemon"] != "mon" and not metadata_ready:
                    self.runtime.ensure_master_metadata_keyrings(operation_id, item["node"], plan, ceph_image, env=env)
                    metadata_ready = True
                results.append(self._place_daemon(operation_id, item, env=env))
            cluster = self._set_cluster_status(cluster["id"], "running", {"bootstrap_results": results}, env=env)
            operation = self.operations.transition(
                operation_id,
                "succeeded",
                message="Dockerized Ceph MON/MGR/MDS 배치를 완료했습니다.",
                result_payload={"cluster": cluster, "preflight": preflight, "plan": plan},
                env=env,
            )
            return {"cluster": cluster, "preflight": preflight, "plan": plan, "operation": operation}
        except Exception as exc:
            self._append(operation_id, str(exc), metadata={"error_code": "CEPH_BOOTSTRAP_FAILED"}, env=env, stream="stderr")
            operation = self.operations.transition(
                operation_id,
                "failed",
                message="Dockerized Ceph cluster bootstrap이 실패했습니다.",
                result_payload={"message": str(exc), "error_code": "CEPH_BOOTSTRAP_FAILED"},
                env=env,
            )
            return {"message": str(exc), "operation": operation}

    def run_master(self, payload=None, env=None):
        payload = dict(payload or {})
        master_result = self.nodes.ensure_local_master(
            {"timeout_seconds": payload.get("timeout_seconds")},
            env=env,
        )
        master = master_result.get("local_master") or {}
        if not master.get("id") or not master.get("swarm_node_id"):
            raise RuntimeError("Docker Infra master를 Swarm manager로 구성할 수 없습니다.")
        active = self._active_cluster(env=env)
        if active:
            payload["existing_cluster_id"] = active["id"]
            payload["fsid"] = active.get("fsid")
            payload["ceph_image"] = payload.get("ceph_image") or (active.get("ceph_image") if active.get("ceph_image") not in {"quay.io/ceph/ceph:latest", "quay.io/ceph/ceph:v19"} else "quay.io/ceph/ceph:v19.2.4")
        payload.update({
            "node_ids": [master["id"]],
            "allow_single_host": True,
            "master_only": True,
            "slot_size_gb": payload.get("slot_size_gb") or 64,
        })
        return self.run(payload, env=env)

Model = StorageCephBootstrap()
