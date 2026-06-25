import base64


catalog = wiz.model("struct/local_command_catalog")
shared = wiz.model("struct/nodes_shared")


def _b64(text):
    return base64.b64encode(str(text or "").encode("utf-8")).decode("ascii")


class StorageCephRuntime:
    def __init__(self, local_executor=None, nodes=None, operations=None):
        self.local_executor = local_executor or wiz.model("struct/local_executor")
        self.nodes = nodes or wiz.model("struct/nodes")
        self.operations = operations or wiz.model("struct/operations")

    def _generate_key(self, ceph_image, env=None):
        result = self.local_executor.run(
            "storage.ceph.auth.key.generate",
            timeout_seconds=120,
            params={"image": ceph_image},
            env=env,
        )
        if result.get("status") != "ok":
            raise RuntimeError(result.get("stderr") or result.get("stdout") or "Ceph auth key 생성에 실패했습니다.")
        key = str(result.get("stdout") or "").strip().splitlines()[-1].strip()
        if not key:
            raise RuntimeError("Ceph auth key 생성 결과가 비어 있습니다.")
        return key

    def keyrings(self, ceph_image, env=None):
        mon_key = self._generate_key(ceph_image, env=env)
        admin_key = self._generate_key(ceph_image, env=env)
        bootstrap_key = self._generate_key(ceph_image, env=env)
        mon_keyring = "\n".join([
            "[mon.]",
            f"    key = {mon_key}",
            '    caps mon = "allow *"',
            "[client.admin]",
            f"    key = {admin_key}",
            '    caps mon = "allow *"',
            '    caps osd = "allow *"',
            '    caps mds = "allow *"',
            '    caps mgr = "allow *"',
            "[client.bootstrap-osd]",
            f"    key = {bootstrap_key}",
            '    caps mon = "profile bootstrap-osd"',
            '    caps mgr = "allow r"',
            "",
        ])
        admin_keyring = "\n".join([
            "[client.admin]",
            f"    key = {admin_key}",
            '    caps mon = "allow *"',
            '    caps osd = "allow *"',
            '    caps mds = "allow *"',
            '    caps mgr = "allow *"',
            "",
        ])
        bootstrap_keyring = "\n".join([
            "[client.bootstrap-osd]",
            f"    key = {bootstrap_key}",
            '    caps mon = "profile bootstrap-osd"',
            '    caps mgr = "allow r"',
            "",
        ])
        return {
            "mon_keyring_b64": _b64(mon_keyring),
            "admin_keyring_b64": _b64(admin_keyring),
            "bootstrap_osd_keyring_b64": _b64(bootstrap_keyring),
        }

    def _append(self, operation_id, message, metadata=None, env=None, stream="system"):
        return self.operations.append_output(operation_id, message, stream=stream, metadata=metadata or {}, env=env)

    def _run_remote_runtime(self, node, params, env=None):
        detail = self.nodes.detail(node["id"], env=env)
        command = [
            "sh", "-lc", catalog.STORAGE_CEPH_NODE_RUNTIME_SCRIPT, "sh",
            params["fsid"], params["image"], params["ceph_hostname"],
            params["mon_initial_members"], params["mon_host"],
            params.get("public_network") or "", params.get("cluster_network") or "",
            params["mount_root"], params["admin_keyring_b64"],
            params["bootstrap_osd_keyring_b64"], params["mon_keyring_b64"], params["roles"],
        ]
        return self.nodes._run_ssh_command(detail, command, timeout_seconds=300, env=env)

    def ensure_nodes(self, operation_id, plan, payload, keyrings, env=None):
        for node in plan["nodes"]:
            roles = ",".join(plan["roles"].get(node["id"], []))
            params = {
                **keyrings,
                "fsid": plan["fsid"],
                "image": payload["ceph_image"],
                "ceph_hostname": node["ceph_hostname"],
                "mon_initial_members": plan["mon_initial_members"],
                "mon_host": plan["mon_host"],
                "public_network": payload.get("public_network") or "",
                "cluster_network": payload.get("cluster_network") or "",
                "mount_root": payload.get("mount_root") or "/srv/docker-infra/storage/cephfs",
                "roles": roles,
            }
            self._append(operation_id, f"{node.get('label')}: Ceph container runtime/config를 준비합니다.", metadata={"node_id": node["id"], "roles": roles}, env=env)
            if shared.is_local_master_node(node):
                result = self.local_executor.run("storage.ceph.node.runtime.ensure", timeout_seconds=300, params=params, env=env)
            else:
                result = self._run_remote_runtime(node, params, env=env)
            if result.get("stdout"):
                self._append(operation_id, result["stdout"], metadata={"node_id": node["id"]}, env=env, stream="stdout")
            if result.get("status") != "ok":
                self._append(operation_id, result.get("stderr") or "Ceph node runtime ensure failed", metadata=result, env=env, stream="stderr")
                raise RuntimeError(f"{node.get('label')} Ceph runtime 준비에 실패했습니다.")

    def ensure_master_metadata_keyrings(self, operation_id, node, plan, ceph_image, env=None):
        daemon_id = node.get("ceph_hostname") or "master"
        self._append(
            operation_id,
            f"{node.get('label')}: MON 응답을 기다린 뒤 MGR/MDS keyring을 구성합니다.",
            metadata={"step": "metadata-daemon-keyrings", "node_id": node.get("id"), "daemon_id": daemon_id},
            env=env,
        )
        result = self.local_executor.run(
            "storage.ceph.master.metadata.ensure",
            timeout_seconds=300,
            params={"fsid": plan["fsid"], "image": ceph_image, "daemon_id": daemon_id},
            env=env,
            capture_limit=12000,
        )
        if result.get("stdout"):
            self._append(operation_id, result["stdout"], metadata={"node_id": node.get("id")}, env=env, stream="stdout")
        if result.get("status") != "ok":
            self._append(operation_id, result.get("stderr") or "MGR/MDS keyring ensure failed", metadata=result, env=env, stream="stderr")
            raise RuntimeError(f"{node.get('label')} MGR/MDS keyring 구성에 실패했습니다.")
        return result


Model = StorageCephRuntime()
