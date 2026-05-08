setup = wiz.model("struct/setup")
shared = wiz.model("struct/nodes_shared")
NODE_ROLES = shared.NODE_ROLES
NodeError = shared.NodeError
_load_json = shared.load_json
_swarm_from_docker_info = shared.swarm_from_docker_info
_node_status_from_swarm = shared.node_status_from_swarm


class NodeJoinMixin:
    def _append_command_result(self, operation_id, step_name, result, stream_if_ok="stdout", secret_values=None, env=None):
        stream = stream_if_ok if result["status"] == "ok" else "stderr"
        message = result["stdout"] if result["status"] == "ok" else (result["stderr"] or result["stdout"])
        if message:
            self.operations.append_output(
                operation_id,
                message,
                stream=stream,
                metadata={"step": step_name, "status": result["status"], "exit_code": result["exit_code"]},
                secret_values=secret_values or [],
                env=env,
            )

    def _step(self, operation_id, step_name, status, metadata=None, env=None):
        self.operations.append_output(
            operation_id,
            f"{step_name}: {status}",
            stream="system",
            metadata={"step": step_name, "status": status, **(metadata or {})},
            env=env,
        )

    def _fail_join(self, operation_id, step_name, message, error_code, result=None, env=None):
        if result is not None:
            self._append_command_result(operation_id, step_name, result, env=env)
        self.operations.append_output(
            operation_id,
            message,
            stream="system",
            metadata={"step": step_name, "error_code": error_code},
            env=env,
        )
        return self.operations.transition(
            operation_id,
            "failed",
            message=message,
            result_payload={"message": message, "error_code": error_code, "failed_step": step_name},
            env=env,
        )

    def join_slave(self, node_id, payload=None, env=None):
        payload = payload or {}
        node = self.detail(node_id, env=env)
        if node["is_local_master"]:
            raise NodeError(400, "local master는 join 대상이 아닙니다.", "LOCAL_MASTER_JOIN_UNSUPPORTED")
        role = "worker"
        if role not in NODE_ROLES:
            raise NodeError(400, "지원하지 않는 node role입니다.", "INVALID_NODE_ROLE")

        operation = self.operations.create(
            "node.join",
            target_type="node",
            target_id=node_id,
            message="Swarm 연결을 시작했습니다.",
            requested_payload={"node_id": node_id, "role": role, "host": node["host"]},
            test_run_id=node["test_run_id"],
            metadata={"node_id": node_id, "host": node["host"]},
            env=env,
        )
        operation_id = operation["id"]

        step = "SSH check"
        self._step(operation_id, step, "running", env=env)
        ssh_result = self._run_ssh_command(node, ["true"], timeout_seconds=10, env=env)
        if ssh_result["status"] != "ok":
            return {"operation": self._fail_join(operation_id, step, "SSH check에 실패했습니다.", "SSH_CHECK_FAILED", ssh_result, env=env)}
        self._step(operation_id, step, "succeeded", {"host": node["host"]}, env=env)

        step = "Docker daemon check"
        self._step(operation_id, step, "running", env=env)
        docker_result = self._run_ssh_command(node, ["docker", "info", "--format", "{{json .}}"], timeout_seconds=15, env=env)
        if docker_result["status"] != "ok":
            return {"operation": self._fail_join(operation_id, step, "Slave Docker daemon check에 실패했습니다.", "SLAVE_DOCKER_UNAVAILABLE", docker_result, env=env)}
        docker_info, remote_swarm = _swarm_from_docker_info(docker_result["stdout"])
        self._step(operation_id, step, "succeeded", {"swarm": remote_swarm}, env=env)

        if remote_swarm.get("LocalNodeState") == "active":
            self._step(operation_id, "Join token fetch", "skipped", {"reason": "already_joined"}, env=env)
            self._step(operation_id, "Swarm join", "skipped", {"reason": "already_joined"}, env=env)
        else:
            step = "Join token fetch"
            self._step(operation_id, step, "running", env=env)
            token_command = "swarm.join-token.manager" if role == "manager" else "swarm.join-token.worker"
            token_result = self.local_executor.run(token_command, timeout_seconds=10, env=env)
            if token_result["status"] != "ok":
                return {"operation": self._fail_join(operation_id, step, "Swarm join token 조회에 실패했습니다.", "JOIN_TOKEN_FAILED", token_result, env=env)}
            token = token_result["stdout"].strip()
            self._step(operation_id, step, "succeeded", {"role": role}, env=env)

            local_info_result = self.local_executor.run("docker.info", timeout_seconds=10, env=env)
            local_info = _load_json(local_info_result["stdout"])
            manager_addr = payload.get("manager_addr") or self._manager_addr(
                local_info,
                payload.get("advertise_address") or setup.detect_advertise_address(),
            )
            join_command = ["docker", "swarm", "join", "--token", token, manager_addr]

            step = "Swarm join"
            self._step(operation_id, step, "running", env=env)
            join_result = self._run_ssh_command(node, join_command, timeout_seconds=60, env=env)
            already_joined = "already part of a swarm" in (join_result["stderr"] or join_result["stdout"])
            if join_result["status"] != "ok" and not already_joined:
                return {"operation": self._fail_join(operation_id, step, "Slave swarm join에 실패했습니다.", "SWARM_JOIN_FAILED", join_result, env=env)}
            self._append_command_result(operation_id, step, join_result, secret_values=[token], env=env)
            self._step(operation_id, step, "succeeded", {"manager_addr": manager_addr}, env=env)

        step = "Swarm verify"
        self._step(operation_id, step, "running", env=env)
        verify_result = self._run_ssh_command(node, ["docker", "info", "--format", "{{json .}}"], timeout_seconds=15, env=env)
        if verify_result["status"] != "ok":
            return {"operation": self._fail_join(operation_id, step, "Join 검증에 실패했습니다.", "SWARM_VERIFY_FAILED", verify_result, env=env)}
        docker_info, swarm = _swarm_from_docker_info(verify_result["stdout"])
        if swarm.get("LocalNodeState") != "active":
            return {"operation": self._fail_join(operation_id, step, "Slave가 active swarm node가 아닙니다.", "SWARM_NODE_NOT_ACTIVE", verify_result, env=env)}
        self._update_node_after_check(node_id, _node_status_from_swarm(swarm), docker_info=docker_info, docker_result=verify_result, env=env)
        self._step(operation_id, step, "succeeded", {"swarm_node_id": swarm.get("NodeID")}, env=env)
        result_payload = {
            "node_id": node_id,
            "swarm_node_id": swarm.get("NodeID"),
            "role": role,
            "state": swarm.get("LocalNodeState"),
        }
        return {
            "operation": self.operations.transition(
                operation_id,
                "succeeded",
                message="Swarm 연결이 완료되었습니다.",
                result_payload=result_payload,
                env=env,
            )
        }


Model = NodeJoinMixin
