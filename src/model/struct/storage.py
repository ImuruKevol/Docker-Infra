class StorageError(Exception):
    def __init__(self, status_code, message, error_code="STORAGE_ERROR", **extra):
        super().__init__(message)
        self.status_code = status_code
        self.message = message
        self.error_code = error_code
        self.extra = extra


shared = wiz.model("struct/nodes_shared")
GIB = 1024 * 1024 * 1024


def _text(value):
    return str(value or "").strip()


class StorageService:
    StorageError = StorageError

    def __init__(self, nodes=None, health=None, ceph_cluster=None, mounts=None, snapshots=None, policies=None):
        self.nodes = nodes or wiz.model("struct/nodes")
        self.health = health or wiz.model("struct/storage_health")
        self.ceph_cluster = ceph_cluster or wiz.model("struct/storage_ceph_cluster")
        self.mounts = mounts or wiz.model("struct/storage_mounts")
        self.snapshots = snapshots or wiz.model("struct/storage_snapshots")
        self.policies = policies or wiz.model("struct/storage_snapshot_policies")

    def _cluster_payload(self, cluster=None, schema_ready=True, schema_missing=None):
        if cluster:
            return {
                "configured": True,
                "status": cluster.get("status") or "pending",
                "health": cluster.get("health") or "HEALTH_UNKNOWN",
                "fsid": cluster.get("fsid") or "",
                "ceph_image": cluster.get("ceph_image") or "",
                "public_network": cluster.get("public_network") or "",
                "cluster_network": cluster.get("cluster_network") or "",
                "mount_root": cluster.get("mount_root") or "",
                "metadata": cluster.get("metadata") or {},
                "message": "Ceph cluster 읽기 전용 상태를 표시합니다.",
            }
        if not schema_ready:
            missing = ", ".join(schema_missing or [])
            return {
                "configured": False,
                "schema_ready": False,
                "schema_missing": schema_missing or [],
                "status": "schema_pending",
                "health": "HEALTH_UNKNOWN",
                "fsid": "",
                "message": f"Ceph storage migration이 아직 적용되지 않았습니다: {missing}",
            }
        return {
            "configured": False,
            "schema_ready": True,
            "status": "not_configured",
            "health": "HEALTH_UNKNOWN",
            "fsid": "",
            "message": "Ceph cluster가 아직 구성되지 않았습니다.",
        }

    def _capacity_placeholder(self):
        return {
            "raw_bytes": 0,
            "usable_bytes": 0,
            "recommended_bytes": 0,
            "used_bytes": 0,
        }

    def _daemon_placeholder(self):
        return {
            "mon": {"ready": 0, "wanted": 3},
            "mgr": {"active": 0, "standby": 0},
            "mds": {"active": 0, "standby": 0},
            "osd": {"up": 0, "in": 0, "total": 0},
        }

    def _slot_row(self, slot):
        size_gb = int((slot or {}).get("size_gb") or 0)
        return {
            "id": slot.get("id"),
            "slot_name": slot.get("slot_name") or "",
            "status": slot.get("status") or "unknown",
            "size_gb": size_gb,
            "raw_bytes": size_gb * GIB,
            "backing_type": slot.get("backing_type") or "",
            "backing_path": slot.get("backing_path") or "",
            "ceph_device_path": slot.get("ceph_device_path") or "",
            "osd_id": slot.get("osd_id"),
            "osd_fsid": slot.get("osd_fsid") or "",
        }

    def _node_osd_summary(self, slots):
        rows = [self._slot_row(slot) for slot in slots or [] if slot.get("status") != "removed"]
        by_status = {}
        raw_bytes = 0
        for row in rows:
            status = row["status"]
            by_status[status] = by_status.get(status, 0) + 1
            raw_bytes += int(row.get("raw_bytes") or 0)
        return {
            "total": len(rows),
            "active": by_status.get("active", 0),
            "prepared": by_status.get("prepared", 0),
            "allocated": by_status.get("allocated", 0),
            "failed": by_status.get("failed", 0),
            "raw_bytes": raw_bytes,
            "by_status": by_status,
            "rows": rows,
        }

    def _node_row(self, node, ceph_nodes=None, osd_slots=None):
        node = node or {}
        swarm_node_id = _text(node.get("swarm_node_id"))
        mode = shared.server_mode_payload({"swarm_node_id": swarm_node_id})
        ceph_node = (ceph_nodes or {}).get(str(node.get("id"))) or {}
        return {
            "id": node.get("id"),
            "name": node.get("name"),
            "host": node.get("host"),
            "status": node.get("status"),
            "swarm_node_id": swarm_node_id,
            "mode": mode["server_mode"],
            **mode,
            "ceph_status": ceph_node.get("status") or "",
            "mount_status": ceph_node.get("mount_status") or "",
            "ceph_hostname": ceph_node.get("ceph_hostname") or "",
            "osd_slots": self._node_osd_summary(osd_slots or []),
        }

    def _swarm_nodes(self, nodes):
        return [node for node in nodes or [] if shared.has_swarm_node_id(node)]

    def _nodes_summary(self, nodes, ceph_nodes=None, osd_slots=None):
        ceph_by_node = {str(row.get("node_id")): row for row in ceph_nodes or []}
        slots_by_node = {}
        for slot in osd_slots or []:
            slots_by_node.setdefault(str(slot.get("node_id")), []).append(slot)
        rows = [self._node_row(node, ceph_by_node, slots_by_node.get(str(node.get("id")))) for node in self._swarm_nodes(nodes)]
        return {
            "total": len(rows),
            "swarm": len(rows),
            "independent": 0,
            "ready_for_osd": len([node for node in rows if node.get("osd_slot_candidate")]),
            "ceph_registered": len([node for node in rows if node["ceph_status"]]),
            "osd_slots": self._node_osd_summary(osd_slots or []),
            "rows": rows,
        }

    def load_overview(self, env=None):
        nodes = self._swarm_nodes(self.nodes.list(env=env))
        ceph = self.ceph_cluster.overview(env=env)
        schema_ready = ceph.get("schema_ready") is True

        mounts = []
        snapshots = []
        policies = []
        if schema_ready:
            mounts = self.mounts.list(env=env)
            snapshots = self.snapshots.list_recent(env=env)
            policies = self.policies.list(env=env)

        cluster = self._cluster_payload(
            ceph.get("cluster"),
            schema_ready=schema_ready,
            schema_missing=ceph.get("schema_missing") or [],
        )
        master = ceph.get("master") or {"configured": False, "status": "unknown", "message": "Ceph master 상태를 확인할 수 없습니다."}
        cluster["master_configured"] = master.get("configured") is True
        overview = self.health.overview(
            cluster=cluster,
            nodes=nodes,
            capacity=ceph.get("capacity") or self._capacity_placeholder(),
            daemons=ceph.get("daemons") or self._daemon_placeholder(),
            storage={
                "schema_ready": schema_ready,
                "schema_missing": ceph.get("schema_missing") or [],
                "osd_slots": ceph.get("osd_summary") or {},
                "node_mounts": ceph.get("node_mount_summary") or {},
                "mounts": self.mounts.summary(mounts),
                "snapshots": self.snapshots.summary(snapshots),
                "policies": self.policies.summary(policies),
            },
        )
        overview["nodes"] = self._nodes_summary(
            nodes,
            ceph_nodes=ceph.get("ceph_nodes") or [],
            osd_slots=ceph.get("osd_slots") or [],
        )
        overview["master"] = master
        return {
            "overview": overview,
            "clusters": ceph.get("clusters") or [],
            "ceph_nodes": ceph.get("ceph_nodes") or [],
            "osd_slots": ceph.get("osd_slots") or [],
            "node_mounts": ceph.get("node_mounts") or [],
            "mounts": mounts,
            "snapshots": snapshots,
            "policies": policies,
        }

    def cluster_preflight(self, payload=None, env=None):
        return self.ceph_cluster.cluster_preflight(payload or {}, env=env)

    def cluster_bootstrap(self, payload=None, env=None):
        return self.ceph_cluster.cluster_bootstrap(payload or {}, env=env)

    def cluster_master_bootstrap(self, payload=None, env=None):
        return self.ceph_cluster.cluster_master_bootstrap(payload or {}, env=env)

    def osd_nodes(self, payload=None, env=None):
        return self.ceph_cluster.osd_nodes(payload or {}, env=env)

    def osd_slot_plan(self, payload=None, env=None):
        return self.ceph_cluster.osd_slot_plan(payload or {}, env=env)

    def osd_slot_create(self, payload=None, env=None):
        return self.ceph_cluster.osd_slot_create(payload or {}, env=env)

    def ensure_node_mount(self, payload=None, env=None):
        return self.ceph_cluster.mount.ensure_node_mount(payload or {}, env=env)

    def operation_status(self, operation_id, env=None):
        if not operation_id:
            raise StorageError(400, "operation_id는 필수입니다.", "OPERATION_ID_REQUIRED")
        return {"operation": wiz.model("struct/operations").detail(operation_id, env=env)}


Model = StorageService()
