from psycopg.types.json import Jsonb

connect = wiz.model("db/postgres").connect
shared = wiz.model("struct/nodes_shared")
NodeError = shared.NodeError
_node_to_dict = shared.node_to_dict


class NodeManageMixin:
    def save_slave(self, payload, env=None):
        payload = payload or {}
        node_id = payload.get("node_id")
        if not node_id:
            return self.register_slave(payload, env=env)

        node = self.detail(node_id, env=env)
        if node["is_local_master"]:
            raise NodeError(400, "중심 서버 정보는 자동으로 동기화됩니다.", "LOCAL_MASTER_UPDATE_UNSUPPORTED")

        current = node.get("credential") or {}
        name = payload.get("name") or node["name"] or node["host"]
        host = payload.get("host") or node["host"]
        username = payload.get("username") or current.get("username")
        ssh_port = int(payload.get("ssh_port") or node.get("ssh_port") or 22)
        timeout_seconds = payload.get("timeout_seconds") or 15
        fingerprint = self.ssh_executor.scan_fingerprint(host, port=ssh_port) or current.get("ssh_fingerprint")
        password = payload.get("password")

        if password:
            prepared = self._prepare_managed_ssh_key(
                {"host": host, "username": username, "password": password, "ssh_port": ssh_port, "timeout_seconds": timeout_seconds},
                env=env,
            )
        else:
            key_file = current.get("key_file") or (current.get("metadata") or {}).get("key_file")
            if not username or not key_file:
                raise NodeError(409, "저장된 SSH key 정보가 없습니다. 비밀번호를 다시 입력해주세요.", "NODE_SSH_KEY_MISSING")
            key_check = self.ssh_executor.run(
                host,
                ["true"],
                username=username,
                port=ssh_port,
                key_file=key_file,
                timeout_seconds=timeout_seconds,
                env=env,
            )
            if key_check["status"] != "ok":
                hint = self.ssh_executor.failure_reason(key_check)
                raise NodeError(
                    409,
                    f"저장된 SSH key로 서버에 다시 연결할 수 없습니다. {hint}",
                    "SSH_KEY_REVALIDATE_FAILED",
                    check={"status": key_check["status"], "exit_code": key_check["exit_code"], "reason": hint},
                )
            prepared = {
                "host": host,
                "username": username,
                "ssh_port": ssh_port,
                "key_file": key_file,
                "fingerprint": fingerprint,
                "checks": {
                    "fingerprint": {"status": "ok" if fingerprint else "unknown", "value": fingerprint},
                    "key": {"status": key_check["status"], "exit_code": key_check["exit_code"]},
                },
            }

        labels = payload.get("labels") or node.get("labels") or {}
        metadata = {
            "source": "node_update",
            "availability": payload.get("availability") or (node.get("metadata") or {}).get("availability") or "active",
            "connection_checks": prepared["checks"],
        }
        test_run_id = payload.get("test_run_id") or node.get("test_run_id")

        with connect(env=env) as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    UPDATE nodes
                    SET name = %s,
                        host = %s,
                        ssh_port = %s,
                        auth_type = 'managed_key',
                        labels = %s,
                        metadata = metadata || %s
                    WHERE id = %s
                    RETURNING *
                    """,
                    (name, host, prepared["ssh_port"], Jsonb(labels), Jsonb(metadata), node_id),
                )
                updated = _node_to_dict(cursor.fetchone())
                updated["credential"] = self._upsert_credential(
                    cursor,
                    node_id,
                    payload,
                    prepared["username"],
                    prepared["fingerprint"],
                    prepared["key_file"],
                    test_run_id,
                )
                return updated

    def sync_detail(self, node_id, env=None):
        node = self.detail(node_id, env=env)
        if node["is_local_master"]:
            self.sync_local_master(env=env)
        else:
            self.check_slave(node_id, env=env)
        return {"node": self.detail(node_id, env=env), "containers": self.containers(node_id, env=env)["containers"]}


Model = NodeManageMixin
