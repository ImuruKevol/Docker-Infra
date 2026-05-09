from psycopg.types.json import Jsonb
connect = wiz.model("db/postgres").connect
shared = wiz.model("struct/nodes_shared")
NODE_ROLES = shared.NODE_ROLES
REPORTER_TOKEN_TYPE = shared.REPORTER_TOKEN_TYPE
NodeError = shared.NodeError
_node_to_dict = shared.node_to_dict
_credential_to_public = shared.credential_to_public
_load_json = shared.load_json
_parse_docker_ps_lines = shared.parse_docker_ps_lines
_container_summary = shared.container_summary
_swarm_from_docker_info = shared.swarm_from_docker_info
_node_status_from_swarm = shared.node_status_from_swarm
class NodeRegistryMixin:
    def _upsert_credential(self, cursor, node_id, payload, username, fingerprint, key_file, test_run_id):
        cursor.execute(
            "DELETE FROM node_credentials WHERE node_id = %s AND COALESCE(metadata->>'type', 'ssh') <> %s",
            (node_id, REPORTER_TOKEN_TYPE),
        )
        cursor.execute(
            """
            INSERT INTO node_credentials(
                node_id, username, password_enc, private_key_enc, passphrase_enc,
                key_file, ssh_fingerprint, test_run_id, metadata
            )
            VALUES (
                %s,
                %s,
                NULL,
                NULL,
                NULL,
                %s,
                %s,
                %s,
                %s
            )
            RETURNING *
            """,
            (
                node_id,
                username,
                key_file,
                fingerprint,
                test_run_id,
                Jsonb({"auth_type": "managed_key", "key_file": key_file}),
            ),
        )
        return _credential_to_public(cursor.fetchone())
    def _required_register_fields(self, payload):
        host = payload.get("host") or payload.get("ssh_host")
        username = payload.get("username")
        password = payload.get("password")
        if not host:
            raise NodeError(400, "서버 IP 또는 host를 입력해주세요.", "NODE_HOST_REQUIRED")
        if not username:
            raise NodeError(400, "SSH 계정을 입력해주세요.", "NODE_SSH_USERNAME_REQUIRED")
        if not password:
            raise NodeError(400, "최초 연결 확인을 위한 SSH 비밀번호를 입력해주세요.", "NODE_SSH_PASSWORD_REQUIRED")
        return host, username, password
    def _prepare_managed_ssh_key(self, payload, env=None):
        host, username, password = self._required_register_fields(payload)
        ssh_port = payload.get("ssh_port") or 22
        password_check = self.ssh_executor.run_with_password(
            host,
            username,
            password,
            ["true"],
            port=ssh_port,
            timeout_seconds=payload.get("timeout_seconds") or 15,
            env=env,
        )
        if password_check["status"] != "ok":
            hint = self.ssh_executor.failure_reason(password_check)
            raise NodeError(
                409,
                f"SSH 비밀번호로 서버에 접속할 수 없습니다. {hint}",
                "SSH_PASSWORD_CONNECT_FAILED",
                check={"status": password_check["status"], "exit_code": password_check["exit_code"], "reason": hint},
            )
        fingerprint = self.ssh_executor.scan_fingerprint(host, port=ssh_port) or self.ssh_executor.known_fingerprint(host, port=ssh_port)
        key = self.ssh_executor.ensure_key_file(env=env)
        install_result = self.ssh_executor.install_public_key(
            host,
            username,
            password,
            key["public_key"],
            port=ssh_port,
            timeout_seconds=payload.get("timeout_seconds") or 20,
            env=env,
        )
        if install_result["status"] != "ok":
            hint = self.ssh_executor.failure_reason(install_result)
            raise NodeError(
                409,
                f"서버에 관리용 SSH key를 등록할 수 없습니다. {hint}",
                "SSH_KEY_INSTALL_FAILED",
                check={"status": install_result["status"], "exit_code": install_result["exit_code"], "reason": hint},
            )
        key_check = self.ssh_executor.run(
            host,
            ["true"],
            username=username,
            port=ssh_port,
            key_file=key["key_file"],
            timeout_seconds=payload.get("timeout_seconds") or 15,
            env=env,
        )
        if key_check["status"] != "ok":
            hint = self.ssh_executor.failure_reason(key_check)
            raise NodeError(
                409,
                f"관리용 SSH key로 서버에 접속할 수 없습니다. {hint}",
                "SSH_KEY_CONNECT_FAILED",
                check={"status": key_check["status"], "exit_code": key_check["exit_code"], "reason": hint},
            )
        return {
            "host": host,
            "username": username,
            "ssh_port": ssh_port,
            "key_file": key["key_file"],
            "fingerprint": fingerprint,
            "checks": {
                "password": {"status": password_check["status"], "exit_code": password_check["exit_code"]},
                "fingerprint": {"status": "ok" if fingerprint else "unknown", "value": fingerprint},
                "key_install": {"status": install_result["status"], "exit_code": install_result["exit_code"]},
                "key": {"status": key_check["status"], "exit_code": key_check["exit_code"]},
            },
        }

    def _remote_metric_payload(self, node, env=None):
        metric_result = self._run_ssh_command(
            node,
            ["sh", "-lc", wiz.model("struct/local_command_catalog").SYSTEM_METRICS_SCRIPT],
            timeout_seconds=8,
            env=env,
        )
        containers_result = self._run_ssh_command(
            node,
            ["docker", "ps", "-a", "--no-trunc", "--format", "{{json .}}"],
            timeout_seconds=10,
            env=env,
        )
        metric = _load_json(metric_result["stdout"]) if metric_result["status"] == "ok" else {}
        items = _parse_docker_ps_lines(containers_result["stdout"]) if containers_result["status"] == "ok" else []
        metric["containers"] = {"summary": _container_summary(items), "items": items}
        return metric, {"system": metric_result, "containers": containers_result}

    def register_slave(self, payload, env=None):
        payload = payload or {}
        prepared = self._prepare_managed_ssh_key(payload, env=env)
        host = prepared["host"]
        name = payload.get("name") or host
        role = "worker"
        test_run_id = payload.get("test_run_id")
        auth_type = "managed_key"
        ssh_config = self.ssh_executor.ssh_config(host)
        username = prepared["username"]
        fingerprint = prepared["fingerprint"]
        labels = payload.get("labels") or {}
        metadata = {
            "source": "node_register",
            "ssh_config": {
                "hostname": ssh_config.get("hostname"),
                "user": ssh_config.get("user"),
                "port": ssh_config.get("port"),
            },
            "availability": payload.get("availability", "active"),
            "connection_checks": prepared["checks"],
        }

        with connect(env=env) as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT *
                    FROM nodes
                    WHERE is_local_master = false
                      AND host = %s
                      AND test_run_id IS NOT DISTINCT FROM %s
                    ORDER BY created_at DESC
                    LIMIT 1
                    """,
                    (host, test_run_id),
                )
                existing = cursor.fetchone()
                if existing is None:
                    cursor.execute(
                        """
                        INSERT INTO nodes(name, role, host, ssh_port, auth_type, status, labels, test_run_id, metadata)
                        VALUES (%s, %s, %s, %s, %s, 'pending', %s, %s, %s)
                        RETURNING *
                        """,
                        (
                            name,
                            role,
                            host,
                            prepared["ssh_port"],
                            auth_type,
                            Jsonb(labels),
                            test_run_id,
                            Jsonb(metadata),
                        ),
                    )
                else:
                    cursor.execute(
                        """
                        UPDATE nodes
                        SET name = %s,
                            role = %s,
                            ssh_port = %s,
                            auth_type = %s,
                            labels = %s,
                            metadata = metadata || %s
                        WHERE id = %s
                        RETURNING *
                        """,
                        (
                            name,
                            role,
                            prepared["ssh_port"],
                            auth_type,
                            Jsonb(labels),
                            Jsonb(metadata),
                            existing["id"],
                        ),
                    )
                node = _node_to_dict(cursor.fetchone())
                credential = self._upsert_credential(
                    cursor,
                    node["id"],
                    payload,
                    username,
                    fingerprint,
                    prepared["key_file"],
                    test_run_id,
                )
                node["credential"] = credential
                return node

    def _update_node_after_check(self, node_id, status, docker_info=None, ssh_result=None, docker_result=None, env=None):
        docker_info = docker_info or {}
        swarm = docker_info.get("Swarm") or {}
        metadata = {"last_check": {"ssh": ssh_result, "docker": docker_result, "docker_info": docker_info}}
        with connect(env=env) as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    UPDATE nodes
                    SET status = %s,
                        swarm_node_id = COALESCE(%s, swarm_node_id),
                        metadata = metadata || %s
                    WHERE id = %s
                    RETURNING *
                    """,
                    (status, swarm.get("NodeID"), Jsonb(metadata), node_id),
                )
                return _node_to_dict(cursor.fetchone())

    def check_slave(self, node_id, env=None):
        node = self.detail(node_id, env=env)
        if node["is_local_master"]:
            raise NodeError(400, "local master는 SSH slave check 대상이 아닙니다.", "LOCAL_MASTER_CHECK_UNSUPPORTED")

        ssh_result = self._run_ssh_command(node, ["true"], timeout_seconds=10, env=env)
        if ssh_result["status"] != "ok":
            updated = self._update_node_after_check(node_id, "unreachable", ssh_result=ssh_result, env=env)
            return {"node": updated, "ssh": ssh_result, "docker": None, "ok": False}

        docker_result = self._run_ssh_command(node, ["docker", "info", "--format", "{{json .}}"], timeout_seconds=15, env=env)
        if docker_result["status"] != "ok":
            updated = self._update_node_after_check(
                node_id,
                "reachable",
                ssh_result=ssh_result,
                docker_result=docker_result,
                env=env,
            )
            return {"node": updated, "ssh": ssh_result, "docker": docker_result, "ok": False}

        docker_info, swarm = _swarm_from_docker_info(docker_result["stdout"])
        updated = self._update_node_after_check(
            node_id,
            _node_status_from_swarm(swarm),
            docker_info=docker_info,
            ssh_result=ssh_result,
            docker_result=docker_result,
            env=env,
        )
        metric, metric_checks = self._remote_metric_payload(self.detail(node_id, env=env), env=env)
        with connect(env=env) as connection:
            with connection.cursor() as cursor:
                self._write_node_metric(
                    cursor,
                    node_id,
                    metric,
                    test_run_id=updated["test_run_id"],
                    metadata={"source": "node_check", "checks": metric_checks},
                )
        return {"node": updated, "ssh": ssh_result, "docker": docker_result, "docker_info": docker_info, "ok": True}
Model = NodeRegistryMixin
