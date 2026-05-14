postgres = wiz.model("db/postgres")
operations_model = wiz.model("struct/operations")
local_executor_model = wiz.model("struct/local_executor")
ssh_executor_model = wiz.model("struct/ssh_executor")
shared = wiz.model("struct/nodes_shared")
NodeLocalMasterMixin = wiz.model("struct/nodes_local_master")
NodeRegistryMixin = wiz.model("struct/nodes_registry")
NodeManageMixin = wiz.model("struct/nodes_manage")
NodeRuntimeMixin = wiz.model("struct/nodes_runtime")
NodeBackupRegistryMixin = wiz.model("struct/nodes_backup_registry")
NodeJoinMixin = wiz.model("struct/nodes_join")
NodeReporterMixin = wiz.model("struct/nodes_reporter")
connect = postgres.connect

REPORTER_TOKEN_TYPE = shared.REPORTER_TOKEN_TYPE
NodeError = shared.NodeError
_node_to_dict = shared.node_to_dict
_credential_to_public = shared.credential_to_public


class NodeService(NodeLocalMasterMixin, NodeRegistryMixin, NodeManageMixin, NodeRuntimeMixin, NodeBackupRegistryMixin, NodeJoinMixin, NodeReporterMixin):
    NodeError = NodeError
    LocalCommandError = local_executor_model.LocalCommandError

    def __init__(self, local_executor=None, ssh_executor=None, operations=None):
        self.local_executor = local_executor or local_executor_model
        self.ssh_executor = ssh_executor or ssh_executor_model
        self.operations = operations or operations_model

    def _fetch_node(self, cursor, node_id):
        cursor.execute("SELECT * FROM nodes WHERE id = %s", (node_id,))
        row = cursor.fetchone()
        if row is None:
            raise NodeError(404, "node를 찾을 수 없습니다.", "NODE_NOT_FOUND")
        return row

    def _run_ssh_command(self, node, command, timeout_seconds=None, env=None):
        credential = node.get("credential") or {}
        key_file = credential.get("key_file") or (credential.get("metadata") or {}).get("key_file")
        username = credential.get("username")
        if not username:
            raise NodeError(409, "서버 SSH 계정 정보가 없습니다. 서버를 다시 등록해주세요.", "NODE_SSH_USERNAME_MISSING")
        if not key_file:
            raise NodeError(409, "서버 SSH key file 정보가 없습니다. 서버를 다시 등록해주세요.", "NODE_SSH_KEY_MISSING")
        return self.ssh_executor.run(
            node["host"],
            command,
            timeout_seconds=timeout_seconds,
            username=username,
            port=node.get("ssh_port"),
            key_file=key_file,
            env=env,
        )

    def list(self, test_run_id=None, env=None):
        with connect(env=env) as connection:
            with connection.cursor() as cursor:
                if test_run_id:
                    cursor.execute(
                        "SELECT * FROM nodes WHERE test_run_id = %s ORDER BY is_local_master DESC, created_at ASC, name ASC",
                        (test_run_id,),
                    )
                else:
                    cursor.execute("SELECT * FROM nodes ORDER BY is_local_master DESC, created_at ASC, name ASC")
                return [_node_to_dict(row) for row in cursor.fetchall()]

    def overview_summary(self, selected_id=None, auto_sync_local_master=False, env=None):
        sync_result = None
        if auto_sync_local_master:
            try:
                sync_result = self.sync_local_master(env=env)
            except Exception as exc:
                sync_result = {"ok": False, "message": str(exc)}
        nodes = self.list(env=env)
        selected = None
        if nodes:
            selected = next((node for node in nodes if node["id"] == selected_id), None) if selected_id else None
            selected = selected or next((node for node in nodes if node["is_local_master"]), None) or nodes[0]
        return {"nodes": nodes, "selected": selected, "local_master_sync": sync_result}

    def overview(self, selected_id=None, auto_sync_local_master=True, env=None):
        sync_result = None
        if auto_sync_local_master:
            try:
                sync_result = self.sync_local_master(env=env)
            except Exception as exc:
                sync_result = {"ok": False, "message": str(exc)}
        nodes = self.list(env=env)
        selected = None
        panel = {"containers": [], "service_groups": [], "unmanaged_containers": [], "cached": True}
        if nodes:
            selected_ref = next((node for node in nodes if node["id"] == selected_id), None) if selected_id else None
            selected_ref = selected_ref or next((node for node in nodes if node["is_local_master"]), None) or nodes[0]
            selected = self.detail(selected_ref["id"], env=env)
            panel = self.cached_containers_panel(selected["id"], env=env)
        return {"nodes": nodes, "selected": selected, **panel, "local_master_sync": sync_result}

    def detail(self, node_id, env=None):
        with connect(env=env) as connection:
            with connection.cursor() as cursor:
                node = _node_to_dict(self._fetch_node(cursor, node_id))
                cursor.execute(
                    """
                    SELECT *
                    FROM node_credentials
                    WHERE node_id = %s
                      AND COALESCE(metadata->>'type', 'ssh') <> %s
                    ORDER BY created_at DESC
                    LIMIT 1
                    """,
                    (node_id, REPORTER_TOKEN_TYPE),
                )
                node["credential"] = _credential_to_public(cursor.fetchone())
                node["reporter"] = self._reporter_status(cursor, node_id)
                node["latest_metric"] = self._latest_metric(cursor, node_id)
                return node

    def delete_by_test_run_id(self, test_run_id, env=None):
        with connect(env=env) as connection:
            with connection.cursor() as cursor:
                cursor.execute("DELETE FROM nodes WHERE test_run_id = %s", (test_run_id,))
                return cursor.rowcount


Model = NodeService()
