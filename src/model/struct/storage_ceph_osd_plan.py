GIB = 1024 * 1024 * 1024
DEFAULT_SLOT_SIZE_GB = 128
SLOT_SIZE_OPTIONS_GB = {64, 128, 256}
MAX_AUTO_SLOTS = 12

catalog = wiz.model("struct/local_command_catalog")
shared = wiz.model("struct/nodes_shared")


def _text(value):
    return str(value or "").strip()


def _int(value, default=0):
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _slot_size(payload):
    size = _int((payload or {}).get("slot_size_gb") or (payload or {}).get("size_gb"), DEFAULT_SLOT_SIZE_GB)
    return size if size in SLOT_SIZE_OPTIONS_GB else DEFAULT_SLOT_SIZE_GB


def _requested_slot_count(payload):
    if not payload or "slot_count" not in payload:
        return None
    value = _int(payload.get("slot_count"))
    return value if value > 0 else None


def _kv(stdout):
    data = {}
    for line in str(stdout or "").splitlines():
        if "\t" not in line:
            continue
        key, value = line.split("\t", 1)
        data[key.strip()] = value.strip()
    return data


class StorageCephOsdPlan:
    def __init__(self, common=None, nodes=None, local_executor=None):
        self.common = common or wiz.model("struct/storage_ceph")
        self.nodes = nodes or wiz.model("struct/nodes")
        self.local_executor = local_executor or wiz.model("struct/local_executor")

    def _current_cluster(self, env=None):
        return self.common.fetchone(
            """
            SELECT *
            FROM ceph_clusters
            WHERE status IN ('running', 'degraded', 'bootstrapping')
            ORDER BY created_at ASC
            LIMIT 1
            """,
            env=env,
        )

    def _node(self, node_id, env=None):
        if not node_id:
            raise RuntimeError("node_id는 필수입니다.")
        node = self.nodes.detail(node_id, env=env)
        if not _text(node.get("swarm_node_id")):
            raise RuntimeError("Swarm 등록 서버만 OSD 슬롯을 구성할 수 있습니다.")
        return node

    def _slot_count(self, cluster_id, env=None):
        row = self.common.fetchone(
            """
            SELECT count(*) AS count
            FROM ceph_osd_slots
            WHERE cluster_id = %s
              AND NOT (
                  status = 'failed'
                  AND COALESCE(backing_path, '') = ''
                  AND COALESCE(device_stable_id, '') = ''
                  AND COALESCE(ceph_device_path, '') = ''
              )
            """,
            [cluster_id],
            env=env,
        )
        return int((row or {}).get("count") or 0)

    def _node_facts(self, node, ceph_image, env=None):
        try:
            if shared.is_local_master_node(node):
                result = self.local_executor.run("storage.ceph.node.preflight", timeout_seconds=60, params={"image": ceph_image}, env=env)
            else:
                result = self.nodes._run_ssh_command(
                    node,
                    ["sh", "-lc", catalog.STORAGE_CEPH_PREFLIGHT_SCRIPT, "sh", ceph_image],
                    timeout_seconds=60,
                    env=env,
                )
        except Exception:
            return {}
        return _kv(result.get("stdout")) if result.get("status") == "ok" else {}

    def _metric_capacity(self, node):
        storage = ((node or {}).get("latest_metric") or {}).get("storage") or {}
        total = _int(storage.get("total"))
        available = _int(storage.get("available"))
        return {
            "total_bytes": total,
            "available_bytes": available,
            "used_bytes": _int(storage.get("used"), max(0, total - available)),
            "source": "latest_metric" if total else "unknown",
        }

    def _capacity(self, node, facts, slot_size_gb, requested_slot_count=None):
        metric = self._metric_capacity(node)
        candidate_bytes = _int(facts.get("osd_candidate_size_bytes"))
        candidate_device = _text(facts.get("osd_candidate_device"))
        candidate_type = _text(facts.get("osd_candidate_type")) or "disk"
        slot_bytes = slot_size_gb * GIB
        total = candidate_bytes or _int(facts.get("storage_total_bytes")) or metric["total_bytes"]
        available = candidate_bytes or _int(facts.get("storage_available_bytes")) or _int(facts.get("free_bytes")) or metric["available_bytes"]
        if candidate_device:
            auto_slot_count = candidate_bytes // slot_bytes if slot_bytes else 0
            if candidate_type == "part":
                auto_slot_count = min(auto_slot_count, 1)
        else:
            auto_slot_count = available // slot_bytes if slot_bytes else 0
        auto_slot_count = max(0, min(int(auto_slot_count), MAX_AUTO_SLOTS))
        if requested_slot_count is None:
            slot_count = auto_slot_count
        elif auto_slot_count > 0:
            slot_count = max(1, min(int(requested_slot_count), auto_slot_count))
        else:
            slot_count = 0
        planned = slot_count * slot_bytes
        return {
            "total_bytes": total,
            "available_bytes": available,
            "used_bytes": max(0, total - available),
            "planned_raw_bytes": planned,
            "remaining_after_bytes": max(0, available - planned),
            "slot_size_gb": slot_size_gb,
            "slot_count": slot_count,
            "auto_slot_count": auto_slot_count,
            "max_slot_count": auto_slot_count,
            "requested_slot_count": requested_slot_count or 0,
            "candidate_device": candidate_device,
            "candidate_type": candidate_type,
            "candidate_count": _int(facts.get("osd_candidate_count")),
            "source": "osd_candidate" if candidate_device else metric["source"],
        }

    def _slot_plan(self, fsid, node, size_gb, capacity, osd_id):
        if capacity["candidate_device"]:
            return {
                "slot_name": f"osd-{osd_id}",
                "size_gb": size_gb,
                "usable_gb": size_gb // 3,
                "backing_type": "gpt_partition",
                "backing_label": "자동 GPT partition",
                "data_device": capacity["candidate_device"],
                "managed_path": "",
                "target_path": capacity["candidate_device"],
                "osd_id_hint": osd_id,
            }
        slot_name = f"osd-{osd_id}"
        managed_path = f"/srv/docker-infra/ceph/{fsid}/osd-slots/{slot_name}.raw"
        return {
            "slot_name": slot_name,
            "size_gb": size_gb,
            "usable_gb": size_gb // 3,
            "backing_type": "managed_loop",
            "backing_label": "마법사 생성 loop block device",
            "data_device": "",
            "managed_path": managed_path,
            "target_path": managed_path,
            "osd_id_hint": osd_id,
        }

    def build(self, payload=None, env=None):
        payload = payload or {}
        cluster = self._current_cluster(env=env)
        if not cluster:
            raise RuntimeError("먼저 Dockerized Ceph cluster를 생성해야 합니다.")
        node = self._node(payload.get("node_id"), env=env)
        ceph_image = _text(payload.get("ceph_image")) or cluster.get("ceph_image") or "quay.io/ceph/ceph:v19.2.4"
        if ceph_image in {"quay.io/ceph/ceph:latest", "quay.io/ceph/ceph:v19"}: ceph_image = "quay.io/ceph/ceph:v19.2.4"
        size_gb = _slot_size(payload)
        requested_slot_count = _requested_slot_count(payload)
        capacity = self._capacity(node, self._node_facts(node, ceph_image, env=env), size_gb, requested_slot_count)
        next_osd_id = self._slot_count(cluster["id"], env=env)
        slots = []
        for offset in range(capacity["slot_count"]):
            osd_id = next_osd_id + offset
            slots.append(self._slot_plan(cluster["fsid"], node, size_gb, capacity, osd_id))
        if slots and requested_slot_count and requested_slot_count > len(slots):
            message = f"요청한 {requested_slot_count}개 중 여유 용량 기준 {len(slots)}개까지 구성할 수 있습니다."
        elif slots and capacity["candidate_device"]:
            message = f"{size_gb}GB OSD 슬롯 {len(slots)}개를 자동 구성할 수 있습니다."
        elif slots:
            message = f"비어 있는 block device가 없어 마법사가 {size_gb}GB loop block device {len(slots)}개를 생성합니다."
        else:
            message = f"{size_gb}GB OSD 슬롯을 만들 수 있는 여유 공간이 부족합니다."
        backing_type = slots[0]["backing_type"] if slots else ("gpt_partition" if capacity["candidate_device"] else "managed_loop")
        backing_label = slots[0]["backing_label"] if slots else ("자동 GPT partition" if capacity["candidate_device"] else "마법사 생성 loop block device")
        data_device = slots[0]["data_device"] if slots else capacity["candidate_device"]
        managed_path = slots[0]["managed_path"] if slots else ""
        return {
            "cluster": cluster,
            "node": node,
            "plan": {
                "node_id": node["id"],
                "node_name": node.get("name") or node.get("host"),
                "swarm_node_id": node.get("swarm_node_id"),
                "slot_name": slots[0]["slot_name"] if slots else "",
                "size_gb": size_gb,
                "usable_gb": (size_gb // 3) * len(slots),
                "backing_type": backing_type,
                "backing_label": backing_label,
                "data_device": data_device,
                "managed_path": managed_path,
                "target_path": data_device or managed_path,
                "ceph_image": ceph_image,
                "fsid": cluster["fsid"],
                "osd_id_hint": next_osd_id,
                "requires_device": False,
                "eligible": bool(slots),
                "message": message,
                "slot_count": len(slots),
                "slot_size_gb": size_gb,
                "capacity": capacity,
                "slots": slots,
                "commands": ["storage.ceph.osd.slot.create", "storage.ceph.osd.daemon.container.run"],
                "steps": [
                    "선택 서버가 Swarm node인지 확인",
                    "비어 있는 block device를 자동 탐지",
                    f"{size_gb}GB 단위 OSD slot {len(slots)}개 산정",
                    "Ceph container로 ceph-volume prepare 실행",
                    "OSD daemon privileged container 생성",
                    "DB에 OSD slot 결과 저장",
                ],
            },
        }


Model = StorageCephOsdPlan()
