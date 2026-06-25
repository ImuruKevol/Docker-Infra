from datetime import datetime


def _text(value):
    return str(value or "").strip()


def _utc_now():
    return datetime.utcnow().replace(microsecond=0).isoformat() + "Z"


class StorageHealth:
    def placeholder_health(self, configured=False):
        if configured:
            return {
                "status": "unknown",
                "value": "HEALTH_UNKNOWN",
                "placeholder": True,
                "message": "Ceph health 조회가 아직 연결되지 않았습니다.",
            }
        return {
            "status": "not_configured",
            "value": "HEALTH_UNKNOWN",
            "placeholder": True,
            "message": "Ceph cluster가 아직 구성되지 않았습니다.",
        }

    def warnings(self, cluster, nodes, storage=None):
        cluster = cluster or {}
        nodes = nodes or []
        storage = storage or {}
        configured = bool(cluster.get("configured"))
        swarm_count = len([node for node in nodes if _text(node.get("swarm_node_id"))])
        warnings = []

        if storage.get("schema_ready") is False:
            warnings.append({
                "id": "storage_schema_pending",
                "level": "warning",
                "title": "Storage DB migration 대기",
                "message": "Ceph storage 테이블이 아직 DB에 적용되지 않아 overview가 placeholder로 표시됩니다.",
            })
            return warnings

        if not configured:
            warnings.append({
                "id": "cluster_not_configured",
                "level": "warning",
                "title": "Ceph cluster 미구성",
                "message": "공용 스토리지 클러스터가 아직 없어 CephFS 용량과 daemon 상태는 placeholder로 표시됩니다.",
            })

        if swarm_count < 3:
            warnings.append({
                "id": "swarm_nodes_below_recommended",
                "level": "warning",
                "title": "Swarm 서버 3대 미만",
                "message": "운영 모드 Ceph 구성에는 host failure domain 분산을 위해 Swarm 서버 3대 이상이 필요합니다.",
            })

        health = _text(cluster.get("health")).upper()
        if configured and health in {"HEALTH_WARN", "HEALTH_ERR"}:
            warnings.append({
                "id": "ceph_health_warning",
                "level": "error" if health == "HEALTH_ERR" else "warning",
                "title": f"Ceph health {health}",
                "message": "Ceph cluster가 정상 상태가 아니므로 daemon, OSD, mount 상태를 확인해야 합니다.",
            })

        osd_slots = storage.get("osd_slots") or {}
        if configured and int(osd_slots.get("active") or 0) < 3:
            warnings.append({
                "id": "active_osd_below_recommended",
                "level": "warning",
                "title": "Active OSD 3개 미만",
                "message": "운영 모드에서는 host failure domain을 만족할 수 있는 active OSD 구성이 필요합니다.",
            })

        node_mounts = storage.get("node_mounts") or {}
        if int(node_mounts.get("missing") or 0) > 0:
            warnings.append({
                "id": "cephfs_mount_node_missing",
                "level": "warning",
                "title": "CephFS mount 누락 node",
                "message": "일부 Swarm node가 CephFS host mount 관리 대상에 등록되지 않았습니다.",
            })
        if int(node_mounts.get("failed") or 0) > 0:
            warnings.append({
                "id": "cephfs_mount_failed",
                "level": "error",
                "title": "CephFS mount 실패",
                "message": "일부 서버에서 CephFS mount 상태가 failed로 기록되어 있습니다.",
            })

        mounts = storage.get("mounts") or {}
        if int(mounts.get("failed") or 0) > 0:
            warnings.append({
                "id": "storage_mount_failed",
                "level": "error",
                "title": "서비스 저장소 실패",
                "message": "일부 서비스 storage mount가 failed 상태입니다.",
            })

        return warnings

    def overview(self, cluster=None, nodes=None, capacity=None, daemons=None, storage=None):
        cluster = cluster or {}
        nodes = nodes or []
        capacity = capacity or {}
        daemons = daemons or {}
        storage = storage or {}
        configured = bool(cluster.get("configured"))
        health = self.placeholder_health(configured=configured)
        if configured and cluster.get("health"):
            health["value"] = cluster.get("health")
            health["status"] = "ok" if cluster.get("health") == "HEALTH_OK" else "warning"
            health["placeholder"] = False
            health["message"] = "DB에 기록된 Ceph health 상태입니다."
        warning_rows = self.warnings(cluster, nodes, storage=storage)
        if configured and warning_rows:
            health["status"] = "warning"
            health["value"] = "HEALTH_WARN"
        if any(row.get("level") == "error" for row in warning_rows):
            health["status"] = "error"
            health["value"] = "HEALTH_ERR"
        return {
            "generated_at": _utc_now(),
            "cluster": {
                "configured": configured,
                "status": cluster.get("status") or ("running" if configured else "not_configured"),
                "health": cluster.get("health") or health["value"],
                "fsid": cluster.get("fsid") or "",
                "message": cluster.get("message") or (
                    "Ceph cluster가 구성되면 health, capacity, daemon 상태가 이 영역에 표시됩니다."
                    if not configured else
                    "Ceph cluster 상태를 표시합니다."
                ),
            },
            "health": health,
            "capacity": {
                "raw_bytes": int(capacity.get("raw_bytes") or 0),
                "usable_bytes": int(capacity.get("usable_bytes") or 0),
                "recommended_bytes": int(capacity.get("recommended_bytes") or 0),
                "used_bytes": int(capacity.get("used_bytes") or 0),
            },
            "daemons": {
                "mon": {"ready": int((daemons.get("mon") or {}).get("ready") or 0), "wanted": int((daemons.get("mon") or {}).get("wanted") or 3)},
                "mgr": {"active": int((daemons.get("mgr") or {}).get("active") or 0), "standby": int((daemons.get("mgr") or {}).get("standby") or 0)},
                "mds": {"active": int((daemons.get("mds") or {}).get("active") or 0), "standby": int((daemons.get("mds") or {}).get("standby") or 0)},
                "osd": {
                    "up": int((daemons.get("osd") or {}).get("up") or 0),
                    "in": int((daemons.get("osd") or {}).get("in") or 0),
                    "total": int((daemons.get("osd") or {}).get("total") or 0),
                },
            },
            "warnings": warning_rows,
            "storage": storage,
        }


Model = StorageHealth()
