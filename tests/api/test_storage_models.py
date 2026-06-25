import unittest
import importlib.util
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
STRUCT = ROOT / "src" / "model" / "struct"
MIGRATION = ROOT / "src" / "model" / "db" / "migrations" / "023_ceph_storage.sql"
MANAGED_LOOP_MIGRATION = ROOT / "src" / "model" / "db" / "migrations" / "025_ceph_osd_managed_loop_check.sql"


class StorageModelStaticContractTest(unittest.TestCase):
    def test_storage_models_are_split_by_domain(self):
        expected = [
            "storage.py",
            "storage_ceph.py",
            "storage_ceph_cluster.py",
            "storage_ceph_bootstrap.py",
            "storage_ceph_runtime.py",
            "storage_ceph_preflight.py",
            "storage_ceph_osd.py",
            "storage_ceph_osd_retry.py",
            "storage_ceph_osd_plan.py",
            "storage_ceph_volume.py",
            "storage_ceph_mount.py",
            "storage_mounts.py",
            "storage_snapshots.py",
            "storage_snapshot_policies.py",
            "storage_health.py",
        ]
        for filename in expected:
            with self.subTest(filename=filename):
                text = (STRUCT / filename).read_text(encoding="utf-8")
                self.assertIn("Model =", text)
                self.assertLessEqual(len(text.splitlines()), 300)

    def test_storage_overview_uses_storage_structs_not_backup_system(self):
        storage = (STRUCT / "storage.py").read_text(encoding="utf-8")
        health = (STRUCT / "storage_health.py").read_text(encoding="utf-8")

        for token in [
            'wiz.model("struct/storage_ceph_cluster")',
            'wiz.model("struct/storage_mounts")',
            'wiz.model("struct/storage_snapshots")',
            'wiz.model("struct/storage_snapshot_policies")',
            '"clusters"',
            '"osd_slots"',
            '"policies"',
            '"master"',
            '"master_configured"',
        ]:
            self.assertIn(token, storage)
        self.assertIn("schema_ready", health)
        self.assertIn("_node_osd_summary", storage)
        self.assertIn('"osd_slots": self._node_osd_summary', storage)
        self.assertNotIn("backup_system", storage)

    def test_server_storage_mode_branches_on_swarm_node_id(self):
        shared = (STRUCT / "nodes_shared.py").read_text(encoding="utf-8")
        view = (STRUCT / "nodes_view.py").read_text(encoding="utf-8")
        storage = (STRUCT / "storage.py").read_text(encoding="utf-8")
        servers_view = (ROOT / "src" / "app" / "page.servers" / "view.pug").read_text(encoding="utf-8")
        servers_ts = (ROOT / "src" / "app" / "page.servers" / "view.ts").read_text(encoding="utf-8")

        for token in [
            "def has_swarm_node_id",
            "def is_local_master_node",
            '"server_mode": mode',
            '"storage_backend": "cephfs" if is_swarm else "local_bind"',
            '"osd_slot_candidate": is_swarm',
        ]:
            self.assertIn(token, shared)
        self.assertIn("shared.server_mode_payload(node)", view)
        self.assertIn("shared.server_mode_payload", storage)
        self.assertIn("ready_for_osd", storage)
        self.assertIn("shared.is_local_master_node", (STRUCT / "storage_ceph_preflight.py").read_text(encoding="utf-8"))
        self.assertIn("return Boolean(String(node?.swarm_node_id || '').trim())", servers_ts)
        self.assertIn("setDetailTab('storage')", servers_view)
        self.assertIn("servers-storage-independent-warning", servers_view)
        self.assertIn("아직 Swarm 클러스터로 연결되어 있지 않아 스토리지를 적용할 수 없습니다.", servers_view)
        self.assertNotIn("showStorageJoinSwarmCta", servers_ts)
        self.assertNotIn("Swarm 클러스터에 등록", servers_view)
        self.assertIn("showOsdSlotWizardButton(selected())", servers_view)
        self.assertIn("OSD 슬롯 구성 마법사", servers_view)

    def test_ceph_cluster_preflight_and_bootstrap_contract(self):
        cluster = (STRUCT / "storage_ceph_cluster.py").read_text(encoding="utf-8")
        bootstrap = (STRUCT / "storage_ceph_bootstrap.py").read_text(encoding="utf-8")
        preflight = (STRUCT / "storage_ceph_preflight.py").read_text(encoding="utf-8")
        catalog = (STRUCT / "local_command_catalog.py").read_text(encoding="utf-8")
        storage = (STRUCT / "storage.py").read_text(encoding="utf-8")
        api = (ROOT / "src" / "app" / "page.storage" / "api.py").read_text(encoding="utf-8")
        view = (ROOT / "src" / "app" / "page.storage" / "view.pug").read_text(encoding="utf-8")
        view_ts = (ROOT / "src" / "app" / "page.storage" / "view.ts").read_text(encoding="utf-8")

        for token in [
            "def cluster_preflight",
            "def cluster_bootstrap",
            "def cluster_master_bootstrap",
            "def master_status",
            "node_is_local_master",
            '"storage.cluster.preflight"',
            "threading.Thread",
            "on_progress",
            '"status": "running"',
        ]:
            self.assertIn(token, cluster)
        for token in [
            '"storage.cluster.bootstrap"',
            '"struct/storage_ceph_runtime"',
            "def run_master",
            "def _active_cluster",
            "existing_cluster_id",
            "master_only=False",
            "allow_single_host",
            "master_only",
            "runtime.ensure_nodes",
            "ensure_master_metadata_keyrings",
            '"storage.ceph.daemon.service.create"',
            "ceph_nodes",
        ]:
            self.assertIn(token, bootstrap)
        for token in [
            "shared.has_swarm_node_id(node)",
            "GUIDANCE",
            '"reason"',
            '"remediation"',
            '"auto_fix"',
            '"docker"',
            '"kernel_module"',
            '"host_network"',
            '"free_space"',
            '"gpt_partition"',
            '"lvm_optional"',
            '"swarm_host_count"',
            "ThreadPoolExecutor",
            "as_completed",
            "on_progress",
            "allow_single_host",
            "parallelism",
            "timeout_seconds",
            '"osd_candidate_device"',
            '"osd_candidate_size_bytes"',
        ]:
            self.assertIn(token, preflight)
        self.assertNotIn("excluded.append", preflight)
        self.assertNotIn('"excluded"', preflight)
        for token in [
            "STORAGE_CEPH_PREFLIGHT_SCRIPT",
            '"storage.ceph.node.preflight"',
            '"storage.ceph.node.runtime.ensure"',
            '"storage.ceph.master.metadata.ensure"',
            '"storage.ceph.daemon.service.create"',
            '"storage.ceph.osd.slot.create"',
            "STORAGE_CEPH_MASTER_METADATA_SCRIPT",
            "metadata_keyrings",
            '"docker", "run"',
            '"docker\", \"service\", \"create"',
            '"--network", "host"',
            '"--constraint", f"node.id == {swarm_node_id}"',
            "chown -R ceph:ceph",
        ]:
            self.assertIn(token, catalog)
        self.assertIn("def operation_status", storage)
        self.assertIn("def cluster_preflight", api)
        self.assertIn("def cluster_bootstrap", api)
        self.assertIn("def cluster_master_bootstrap", api)
        self.assertIn("operation.get(\"status\") == \"failed\"", api)
        self.assertIn("storage-dashboard-metrics", view)
        self.assertIn("storage-osd-placement", view)
        self.assertIn("OSD 배치", view)
        self.assertNotIn("Dockerized Ceph cluster bootstrap", view)
        self.assertIn("storage-ceph-master-bootstrap", view)
        self.assertIn("showMasterBootstrap()", view)
        self.assertIn("마스터 노드 설치 및 구성", view)
        self.assertIn("storage-cluster-server-list", view)
        self.assertIn("openOsdWizard(node)", view)
        self.assertIn("[disabled]=\"actionBusy() || !node.osd_slot_candidate\"", view)
        self.assertIn("aria-label=\"OSD 슬롯 만들기\"", view)
        self.assertIn("fa-plus", view)
        self.assertNotIn('aria-label="사전 점검"', view)
        self.assertNotIn('aria-label="Ceph cluster 만들기"', view)
        self.assertIn("preflightModalOpen()", view)
        self.assertIn("operationModalOpen()", view)
        self.assertIn("storage-operation-modal", view)
        self.assertIn("Warning / Error 보정 안내", view)
        self.assertIn("왜 떴나요", view)
        self.assertIn("어떻게 보정하나요", view)
        self.assertIn("fixPreflightIssue(issue)", view)
        self.assertNotIn("preflightExcludedRows()", view)
        self.assertNotIn("제외 독립 서버", view)
        self.assertNotIn("Ceph preflight 제외 서버", view)
        self.assertNotIn("storage_note", view)
        self.assertNotIn("nodeModeLabel(node)", view)
        self.assertNotIn("nodeModeClass(node)", view)
        self.assertNotIn("grid-cols-[minmax(0,1fr)_minmax(112px,180px)_132px]", view)
        self.assertNotIn("storage-operation-log-tab", view)
        self.assertNotIn("Ceph OSD slot 후보이며 CephFS bind mount 대상입니다.", storage)
        self.assertNotIn("{ key: 'operations'", view_ts)
        self.assertNotIn("this.activeTab.set('operations')", view_ts)
        for token in ["schedulePreflightPoll", "pollPreflightOperation", "applyPreflightFromOperation", "isActiveOperation"]:
            self.assertIn(token, view_ts)
        self.assertIn("public master()", view_ts)
        self.assertIn("public showMasterBootstrap()", view_ts)
        self.assertIn("applyBootstrapResult", view_ts)
        self.assertIn("openOperationModal", view_ts)
        self.assertIn("operationModalOpen.set(true)", view_ts)
        self.assertIn("dashboardMetrics()", view_ts)
        self.assertIn("osdPlacementSummary()", view_ts)
        self.assertIn("nodeOsdRows(node: any)", view_ts)

    def test_osd_slot_wizard_uses_dockerized_ceph_container(self):
        osd = (STRUCT / "storage_ceph_osd.py").read_text(encoding="utf-8")
        retry = (STRUCT / "storage_ceph_osd_retry.py").read_text(encoding="utf-8")
        plan = (STRUCT / "storage_ceph_osd_plan.py").read_text(encoding="utf-8")
        cluster = (STRUCT / "storage_ceph_cluster.py").read_text(encoding="utf-8")
        catalog = (STRUCT / "local_command_catalog.py").read_text(encoding="utf-8")
        config = (ROOT / "config" / "docker_infra.py").read_text(encoding="utf-8")
        api = (ROOT / "src" / "app" / "page.storage" / "api.py").read_text(encoding="utf-8")
        view = (ROOT / "src" / "app" / "page.storage" / "view.pug").read_text(encoding="utf-8")
        ts = (ROOT / "src" / "app" / "page.storage" / "view.ts").read_text(encoding="utf-8")

        for token in [
            "def slot_plan",
            "def slot_create",
            '"storage.osd.slot.create"',
            '"storage.ceph.osd.slot.create"',
            '"storage.ceph.osd.daemon.container.run"',
            "ceph-volume",
            '"slots"',
            "REMOTE_RUNTIME_SYNC_SCRIPT",
            "def _sync_remote_runtime",
            "def _delete_empty_failed_slots",
            "이전 실패 슬롯",
            "struct/storage_ceph_osd_retry",
            "이전 prepared OSD 슬롯",
        ]:
            self.assertIn(token, osd)
        for token in ["def prepared_slots", "def service_plan", "status = 'prepared'"]:
            self.assertIn(token, retry)
        self.assertIn('"storage.ceph.mount.ensure"', config)
        self.assertIn('"storage.ceph.osd.daemon.container.run"', config)
        for token in [
            "DEFAULT_SLOT_SIZE_GB = 128",
            "SLOT_SIZE_OPTIONS_GB = {64, 128, 256}",
            '"managed_loop"',
            "MAX_AUTO_SLOTS",
            '"auto_slot_count"',
            '"max_slot_count"',
            '"requested_slot_count"',
            "def build",
            '"slot_count"',
            '"capacity"',
            '"candidate_device"',
            "storage.ceph.node.preflight",
            "status = 'failed'",
            "COALESCE(backing_path, '') = ''",
        ]:
            self.assertIn(token, plan)
        for token in ["def osd_slot_plan", "def osd_slot_create"]:
            self.assertIn(token, cluster)
            self.assertIn(token, api)
        for token in [
            "STORAGE_CEPH_OSD_SLOT_CREATE_SCRIPT",
            "docker run --rm --privileged --net host --pid host",
            "docker run -d --privileged --net host --pid host --restart unless-stopped",
            "--detach=true",
            "ceph-volume lvm activate --bluestore --no-systemd --no-tmpfs",
            "ceph-volume lvm activate --bluestore --no-systemd --no-tmpfs --all",
            "ceph-volume lvm prepare",
            "set -e; ceph-volume lvm prepare",
            "ceph.client.bootstrap-osd.keyring",
            "pvcreate -ff -y",
            "lvcreate --noudevsync --wipesignatures n --zero n",
            'ln -sf "../mapper/${vg}-${lv}"',
            "managed_vg",
            "exit 70",
            "losetup --find --show",
            'if daemon == "osd"',
        ]:
            self.assertIn(token, catalog)
        self.assertIn("storage-osd-wizard", view)
        self.assertIn("slotSizeOptions", view)
        self.assertIn("selectOsdSize(size)", view)
        self.assertIn("슬롯 개수", view)
        self.assertIn("changeOsdSlotCount(-1)", view)
        self.assertIn("storage-osd-slot-count", view)
        self.assertIn("Ceph container runtime", view)
        self.assertIn("createOsdPlan()", view)
        self.assertIn("createOsdSlot()", view)
        self.assertIn("osdCapacityItems()", view)
        self.assertIn("OSD 슬롯 만들기", view)
        self.assertNotIn("selectBackingType", view)
        self.assertNotIn("setOsdFormField", view)
        self.assertIn("osd_slot_plan", ts)
        self.assertIn("osd_slot_create", ts)
        self.assertIn("slot_size_gb: this.osdSlotSize()", ts)
        self.assertIn("const count = this.osdSlotCount()", ts)
        self.assertIn("volume.lvm_artifact", osd)
        self.assertIn("osd_fsid", osd)
        self.assertIn("payload.slot_count = count", ts)
        self.assertIn("osdMaxSlotCount()", ts)
        self.assertIn("setOsdSlotCount(value: any)", ts)
        self.assertIn("cluster_master_bootstrap", ts)
        self.assertIn("osdCapacityItems", ts)
        self.assertNotIn("data_device: this.osdForm", ts)

    def test_cephfs_host_mount_and_service_mount_contract(self):
        mount = (STRUCT / "storage_ceph_mount.py").read_text(encoding="utf-8")
        mounts = (STRUCT / "storage_mounts.py").read_text(encoding="utf-8")
        catalog = (STRUCT / "local_command_catalog.py").read_text(encoding="utf-8")
        services = (STRUCT / "services.py").read_text(encoding="utf-8")
        preflight = (STRUCT / "services_preflight.py").read_text(encoding="utf-8")
        deploy = (STRUCT / "services_deploy.py").read_text(encoding="utf-8")
        storage = (STRUCT / "storage.py").read_text(encoding="utf-8")
        health = (STRUCT / "storage_health.py").read_text(encoding="utf-8")
        api = (ROOT / "src" / "app" / "page.storage" / "api.py").read_text(encoding="utf-8")

        for token in [
            "def ensure_node_mount",
            "missing_swarm_nodes",
            "client_keyring_b64",
            "mount_status = %s",
            '"storage.ceph.mount.ensure"',
        ]:
            self.assertIn(token, mount)
        for token in [
            "STORAGE_CEPH_MOUNT_ENSURE_SCRIPT",
            "mountpoint -q",
            "systemctl enable",
            "ceph-fuse",
            '"storage.ceph.mount.ensure"',
        ]:
            self.assertIn(token, catalog)
        for token in [
            "def normalize_compose",
            "def record_service_mounts",
            'CEPHFS_ROOT = "/srv/docker-infra/storage/cephfs"',
            '"x-docker-infra.storage"',
            '"docker_managed_volume_allowed": False',
            '"removed_top_level_volumes"',
            "health IN ('HEALTH_OK', 'HEALTH_WARN')",
        ]:
            self.assertIn(token, mounts)
        self.assertIn("storage_mounts.normalize_compose", services)
        self.assertIn("storage_mounts.record_service_mounts", services)
        self.assertIn("_check_storage", preflight)
        self.assertIn("_ensure_storage_mount_paths", deploy)
        self.assertIn("storage_ceph_mount.ensure_node_mount", deploy)
        self.assertIn("CephFS host mount를 준비할 수 없습니다.", deploy)
        self.assertIn("def ensure_node_mount", storage)
        self.assertIn("cephfs_mount_node_missing", health)
        self.assertIn("def ensure_node_mount", api)

    def test_storage_mount_normalizer_removes_docker_managed_volumes(self):
        class FakeCommon:
            def fetchone(self, *args, **kwargs):
                return {"mount_root": "/srv/docker-infra/storage/cephfs"}

        class FakeWiz:
            def model(self, name):
                if name == "struct/storage_ceph":
                    return FakeCommon()
                raise AssertionError(f"unexpected model: {name}")

        spec = importlib.util.spec_from_file_location("storage_mounts_contract", STRUCT / "storage_mounts.py")
        module = importlib.util.module_from_spec(spec)
        module.wiz = FakeWiz()
        spec.loader.exec_module(module)

        plan = module.Model.normalize_compose(
            "wiki",
            """
services:
  app:
    image: nginx:alpine
    volumes:
      - data:/app/data
volumes:
  data:
  unused:
""",
            backend="cephfs",
        )

        self.assertNotIn("\nvolumes:", plan["content"])
        self.assertIn("/srv/docker-infra/storage/cephfs/services/wiki/mounts/data/current:/app/data", plan["content"])
        self.assertEqual(plan["converted_sources"], ["data"])
        self.assertEqual(plan["removed_top_level_volumes"], ["data", "unused"])
        self.assertEqual(plan["mounts"][0]["original_source"], "data")

    def test_ceph_storage_migration_declares_required_relationships(self):
        sql = MIGRATION.read_text(encoding="utf-8")
        managed_loop_sql = MANAGED_LOOP_MIGRATION.read_text(encoding="utf-8")
        for token in [
            "CREATE TABLE IF NOT EXISTS ceph_clusters",
            "CREATE TABLE IF NOT EXISTS ceph_nodes",
            "CREATE TABLE IF NOT EXISTS ceph_osd_slots",
            "CREATE TABLE IF NOT EXISTS storage_mounts",
            "CREATE TABLE IF NOT EXISTS storage_snapshots",
            "CREATE TABLE IF NOT EXISTS storage_snapshot_policies",
            "'managed_loop'",
            "REFERENCES nodes(id) ON DELETE CASCADE",
            "REFERENCES services(id) ON DELETE CASCADE",
            "REFERENCES compose_versions(id) ON DELETE SET NULL",
            "REFERENCES storage_snapshot_policies(id) ON DELETE SET NULL",
            "REFERENCES storage_mounts(id) ON DELETE CASCADE",
        ]:
            self.assertIn(token, sql)
        self.assertIn("DROP CONSTRAINT IF EXISTS ceph_osd_slots_backing_type_check", managed_loop_sql)
        self.assertIn("'managed_loop'", managed_loop_sql)


if __name__ == "__main__":
    unittest.main()
