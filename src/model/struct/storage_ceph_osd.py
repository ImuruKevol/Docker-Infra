import base64
from pathlib import Path
from psycopg.types.json import Jsonb

GIB = 1024 * 1024 * 1024
catalog = wiz.model("struct/local_command_catalog")
shared = wiz.model("struct/nodes_shared")
volume = wiz.model("struct/storage_ceph_volume")
REMOTE_RUNTIME_SYNC_SCRIPT = r"""
set -eu
emit() { printf '%s\t%s\n' "$1" "$2"; }
write_b64() {
  value="$1"
  target="$2"
  mode="$3"
  [ -n "$value" ] || { echo "missing runtime payload for $target" >&2; exit 64; }
  printf '%s' "$value" | base64 -d > "$target"
  chmod "$mode" "$target"
}
fsid="$1"
image="$2"
ceph_conf_b64="$3"
admin_keyring_b64="$4"
bootstrap_osd_keyring_b64="$5"
base="/srv/docker-infra/ceph/$fsid"
etc="$base/etc"
lib="$base/var/lib/ceph"
mkdir -p "$etc" "$lib/bootstrap-osd" "$lib/osd" "$base/osd-slots"
write_b64 "$ceph_conf_b64" "$etc/ceph.conf" 0644
write_b64 "$admin_keyring_b64" "$etc/ceph.client.admin.keyring" 0600
write_b64 "$bootstrap_osd_keyring_b64" "$lib/bootstrap-osd/ceph.keyring" 0600
write_b64 "$bootstrap_osd_keyring_b64" "$etc/ceph.client.bootstrap-osd.keyring" 0600
docker image inspect "$image" >/dev/null 2>&1 || docker pull "$image" >/dev/null
emit runtime_synced ok
emit ceph_conf "$etc/ceph.conf"
"""

def _active_capacity_slot(slot):
    return str((slot or {}).get("status") or "") != "removed"

def _safe_id(value, fallback):
    text = "".join(ch if ch.isalnum() else "-" for ch in str(value or "").lower()).strip("-")
    return text[:32].strip("-") or fallback

def _kv(stdout):
    data = {}
    for line in str(stdout or "").splitlines():
        if "\t" in line:
            key, value = line.split("\t", 1)
            data[key.strip()] = value.strip()
    return data

def _file_b64(path):
    data = Path(path).read_bytes()
    if not data:
        raise RuntimeError(f"Ceph runtime 파일이 비어 있습니다: {path}")
    return base64.b64encode(data).decode("ascii")

class StorageCephOsd:
    def __init__(self, common=None, nodes=None, operations=None, local_executor=None, planner=None, retry=None):
        self.common = common or wiz.model("struct/storage_ceph")
        self.nodes = nodes or wiz.model("struct/nodes")
        self.operations = operations or wiz.model("struct/operations")
        self.local_executor = local_executor or wiz.model("struct/local_executor")
        self.planner = planner or wiz.model("struct/storage_ceph_osd_plan")
        self.retry = retry or wiz.model("struct/storage_ceph_osd_retry")

    def list_slots(self, cluster_id=None, env=None):
        query = """
            SELECT
                slot.*,
                node.name AS node_name,
                node.host AS node_host,
                node.swarm_node_id AS swarm_node_id
            FROM ceph_osd_slots slot
            LEFT JOIN nodes node ON node.id = slot.node_id
        """
        params = []
        if cluster_id:
            query += " WHERE slot.cluster_id = %s"
            params.append(cluster_id)
        query += " ORDER BY node.name ASC NULLS LAST, slot.slot_name ASC"
        return self.common.fetchall(query, params, env=env)

    def summary(self, slots):
        slots = slots or []
        by_status = {}
        raw_bytes = 0
        for slot in slots:
            status = str(slot.get("status") or "unknown")
            by_status[status] = by_status.get(status, 0) + 1
            if _active_capacity_slot(slot):
                raw_bytes += int(slot.get("size_gb") or 0) * GIB
        active = by_status.get("active", 0)
        return {
            "total": len(slots),
            "active": active,
            "prepared": by_status.get("prepared", 0),
            "failed": by_status.get("failed", 0),
            "raw_bytes": raw_bytes,
            "by_status": by_status,
        }

    def _operation(self, payload, env=None):
        return self.operations.create(
            "storage.osd.slot.create",
            target_type="storage",
            target_id=payload.get("node_id"),
            message="OSD 슬롯 구성 마법사를 시작했습니다.",
            requested_payload=payload,
            metadata={"domain": "storage", "component": "ceph-osd"},
            env=env,
        )

    def _append(self, operation_id, message, metadata=None, env=None, stream="system"):
        return self.operations.append_output(operation_id, message, stream=stream, metadata=metadata or {}, env=env)

    def slot_plan(self, payload=None, env=None):
        return self.planner.build(payload or {}, env=env)

    def _run_osd_command(self, node, slot_plan, fsid, ceph_image, env=None):
        params = {
            "image": ceph_image,
            "fsid": fsid,
            "slot_name": slot_plan["slot_name"],
            "backing_type": slot_plan["backing_type"],
            "data_path": slot_plan.get("data_device") or slot_plan.get("managed_path") or slot_plan.get("target_path") or "",
            "size_gb": slot_plan["size_gb"],
        }
        if shared.is_local_master_node(node):
            return self.local_executor.run("storage.ceph.osd.slot.create", timeout_seconds=1800, params=params, env=env)
        detail = self.nodes.detail(node["id"], env=env)
        command = [
            "sh", "-lc", catalog.STORAGE_CEPH_OSD_SLOT_CREATE_SCRIPT, "sh",
            params["image"], params["fsid"], params["slot_name"],
            params["backing_type"], params["data_path"], str(params["size_gb"]),
        ]
        return self.nodes._run_ssh_command(detail, command, timeout_seconds=1800, env=env)

    def _sync_remote_runtime(self, operation_id, cluster, node, ceph_image, env=None):
        if shared.is_local_master_node(node):
            return None
        fsid = cluster["fsid"]
        base = Path(f"/srv/docker-infra/ceph/{fsid}")
        params = {
            "ceph_conf_b64": _file_b64(base / "etc" / "ceph.conf"),
            "admin_keyring_b64": _file_b64(base / "etc" / "ceph.client.admin.keyring"),
            "bootstrap_osd_keyring_b64": _file_b64(base / "var" / "lib" / "ceph" / "bootstrap-osd" / "ceph.keyring"),
        }
        self._append(operation_id, f"{node.get('name') or node.get('host')}: Ceph runtime config를 동기화합니다.", metadata={"node_id": node["id"]}, env=env)
        detail = self.nodes.detail(node["id"], env=env)
        result = self.nodes._run_ssh_command(
            detail,
            [
                "sh", "-lc", REMOTE_RUNTIME_SYNC_SCRIPT, "sh",
                fsid, ceph_image,
                params["ceph_conf_b64"], params["admin_keyring_b64"], params["bootstrap_osd_keyring_b64"],
            ],
            timeout_seconds=600,
            env=env,
        )
        if result.get("stdout"):
            self._append(operation_id, result["stdout"], metadata={"node_id": node["id"]}, env=env, stream="stdout")
        if result.get("status") != "ok":
            raise RuntimeError(result.get("stderr") or result.get("stdout") or "Ceph runtime config 동기화에 실패했습니다.")
        return result

    def _delete_empty_failed_slots(self, cluster, node, plan, env=None):
        slot_names = [slot.get("slot_name") for slot in plan.get("slots") or [] if slot.get("slot_name")]
        if not slot_names:
            return 0
        with self.common.connect(env=env) as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    DELETE FROM ceph_osd_slots
                    WHERE cluster_id = %s
                      AND node_id = %s
                      AND slot_name = ANY(%s)
                      AND status = 'failed'
                      AND COALESCE(backing_path, '') = ''
                      AND COALESCE(device_stable_id, '') = ''
                      AND COALESCE(ceph_device_path, '') = ''
                    """,
                    (cluster["id"], node["id"], slot_names),
                )
                return cursor.rowcount or 0

    def _create_slot_row(self, cluster, node, plan, slot_plan, operation_id, env=None):
        with self.common.connect(env=env) as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    INSERT INTO ceph_osd_slots(cluster_id, node_id, slot_name, size_gb, backing_type, status, osd_id, metadata)
                    VALUES (%s, %s, %s, %s, %s, 'allocated', %s, %s)
                    RETURNING *
                    """,
                    (
                        cluster["id"],
                        node["id"],
                        slot_plan["slot_name"],
                        slot_plan["size_gb"],
                        slot_plan["backing_type"],
                        slot_plan["osd_id_hint"],
                        Jsonb({"operation_id": operation_id, "dockerized": True, "plan": plan, "slot_plan": slot_plan}),
                    ),
                )
                return self.common.row(cursor.fetchone())

    def _finish_slot_row(self, slot_id, status, result=None, env=None, osd_id=None):
        result = result or {}
        facts = _kv(result.get("stdout"))
        artifact = volume.lvm_artifact(result.get("stdout"), osd_id)
        with self.common.connect(env=env) as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    UPDATE ceph_osd_slots
                    SET status = %s,
                        backing_path = COALESCE(%s, backing_path),
                        device_stable_id = COALESCE(%s, device_stable_id),
                        ceph_device_path = COALESCE(%s, ceph_device_path),
                        ceph_lvm_artifact = %s,
                        osd_fsid = COALESCE(%s, osd_fsid),
                        metadata = metadata || %s
                    WHERE id = %s
                    RETURNING *
                    """,
                    (status, facts.get("backing_path"), volume.device_uuid(artifact) or facts.get("device_stable_id"),
                     volume.device_path(artifact) or facts.get("backing_path"), Jsonb(artifact),
                     volume.osd_fsid(artifact) or None, Jsonb({"command_result": result}), slot_id),
                )
                return self.common.row(cursor.fetchone())

    def _place_osd_service(self, operation_id, node, plan, env=None):
        service_name = f"docker-infra-ceph-osd-{plan['osd_id_hint']}-{_safe_id(node.get('name') or node.get('host'), node['id'][:8])}"[:120]
        params = {"container_name": service_name, "daemon_id": str(plan["osd_id_hint"]), "osd_fsid": str(plan.get("osd_fsid") or ""), "image": plan["ceph_image"], "fsid": plan["fsid"]}
        if shared.is_local_master_node(node):
            result = self.local_executor.run("storage.ceph.osd.daemon.container.run", timeout_seconds=120, params=params, env=env)
        else:
            detail = self.nodes.detail(node["id"], env=env)
            command = ["sh", "-lc", catalog.STORAGE_CEPH_OSD_DAEMON_RUN_SCRIPT, "sh", params["fsid"], params["image"], params["container_name"], params["daemon_id"], params["osd_fsid"]]
            result = self.nodes._run_ssh_command(detail, command, timeout_seconds=120, env=env)
        if result.get("stdout"):
            self._append(operation_id, result["stdout"], metadata={"service_name": service_name}, env=env, stream="stdout")
        return result

    def slot_create(self, payload=None, env=None):
        payload = payload or {}
        operation = self._operation(payload, env=env)
        operation_id = operation["id"]
        try:
            context = self.planner.build(payload, env=env)
            cluster, node, plan = context["cluster"], context["node"], context["plan"]
            if not plan.get("eligible"):
                raise RuntimeError(plan.get("message") or "자동 OSD 슬롯을 구성할 수 없습니다.")
            self._append(operation_id, "OSD 슬롯 plan 확인을 완료했습니다.", metadata=plan, env=env)
            self._sync_remote_runtime(operation_id, cluster, node, plan["ceph_image"], env=env)
            removed_failed = self._delete_empty_failed_slots(cluster, node, plan, env=env)
            if removed_failed:
                self._append(operation_id, f"이전 실패 슬롯 {removed_failed}개를 재시도 대상으로 정리했습니다.", metadata={"removed_failed_slots": removed_failed}, env=env)
            slots = []
            plan_slots = plan.get("slots") or []
            prepared_slots = self.retry.prepared_slots(cluster, node, limit=len(plan_slots), env=env)
            if prepared_slots:
                self._append(operation_id, f"이전 prepared OSD 슬롯 {len(prepared_slots)}개를 daemon container 생성 단계부터 재시도합니다.", metadata={"prepared_slots": [slot.get("id") for slot in prepared_slots]}, env=env)
            for prepared_slot in prepared_slots:
                service_result = self._place_osd_service(operation_id, node, self.retry.service_plan(plan, prepared_slot), env=env)
                service_text = str(service_result.get("stderr") or service_result.get("stdout") or "").lower()
                if service_result.get("status") != "ok" and "already exists" not in service_text:
                    raise RuntimeError(service_result.get("stderr") or "OSD daemon service 생성에 실패했습니다.")
                slots.append(self._finish_slot_row(prepared_slot["id"], "active", service_result, env=env))
            for slot_plan in plan_slots[:max(0, len(plan_slots) - len(prepared_slots))]:
                slot = self._create_slot_row(cluster, node, plan, slot_plan, operation_id, env=env)
                result = self._run_osd_command(node, slot_plan, plan["fsid"], plan["ceph_image"], env=env)
                if result.get("stdout"):
                    self._append(operation_id, result["stdout"], metadata={"slot_id": slot["id"]}, env=env, stream="stdout")
                if result.get("status") != "ok":
                    self._finish_slot_row(slot["id"], "failed", result, env=env, osd_id=slot_plan["osd_id_hint"])
                    raise RuntimeError(result.get("stderr") or result.get("stdout") or "ceph-volume 실행에 실패했습니다.")
                slot = self._finish_slot_row(slot["id"], "prepared", result, env=env, osd_id=slot_plan["osd_id_hint"])
                service_plan = {**plan, **slot_plan, "osd_fsid": slot.get("osd_fsid")}
                service_result = self._place_osd_service(operation_id, node, service_plan, env=env)
                service_text = str(service_result.get("stderr") or service_result.get("stdout") or "").lower()
                if service_result.get("status") != "ok" and "already exists" not in service_text:
                    raise RuntimeError(service_result.get("stderr") or "OSD daemon service 생성에 실패했습니다.")
                slots.append(self._finish_slot_row(slot["id"], "active", service_result, env=env))
            operation = self.operations.transition(
                operation_id,
                "succeeded",
                message=f"OSD 슬롯 {len(slots)}개 구성을 완료했습니다.",
                result_payload={"slot": slots[0] if slots else None, "slots": slots, "plan": plan},
                env=env,
            )
            return {"slot": slots[0] if slots else None, "slots": slots, "plan": plan, "operation": operation}
        except Exception as exc:
            operation = self.operations.transition(operation_id, "failed", message="OSD 슬롯 구성이 실패했습니다.", result_payload={"message": str(exc)}, env=env)
            return {"message": str(exc), "operation": operation}

Model = StorageCephOsd()
