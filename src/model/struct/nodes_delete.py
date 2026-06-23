import shlex
from pathlib import Path

connect = wiz.model("db/postgres").connect
config = wiz.config("docker_infra")
shared = wiz.model("struct/nodes_shared")
NodeError = shared.NodeError
_swarm_from_docker_info = shared.swarm_from_docker_info


class NodeDeleteMixin:
    def _cleanup_script_for(self, command_id, params=None):
        spec = self.local_executor._command_spec(command_id)
        argv = self.local_executor._argv(command_id, spec, params or {})
        return argv[2] if len(argv) >= 3 and argv[:2] == ["sh", "-lc"] else shlex.join(argv)

    def _managed_public_key(self, node):
        credential = node.get("credential") or {}
        key_file = credential.get("key_file") or (credential.get("metadata") or {}).get("key_file")
        if not key_file:
            return ""
        public_key_path = Path(f"{key_file}.pub")
        if not public_key_path.is_file():
            return ""
        return public_key_path.read_text(encoding="utf-8").strip()

    def _authorized_key_cleanup_script(self, public_key):
        if not public_key:
            return "printf 'Managed SSH public key not found locally; authorized_keys cleanup skipped\\n'\n"
        return (
            "set -eu\n"
            f"MANAGED_PUBLIC_KEY={shlex.quote(public_key)}\n"
            "AUTHORIZED_KEYS=\"$HOME/.ssh/authorized_keys\"\n"
            "if [ ! -f \"$AUTHORIZED_KEYS\" ]; then printf 'authorized_keys not found; skipped\\n'; exit 0; fi\n"
            "TMP_AUTH=$(mktemp)\n"
            "grep -vxF \"$MANAGED_PUBLIC_KEY\" \"$AUTHORIZED_KEYS\" > \"$TMP_AUTH\" || true\n"
            "cat \"$TMP_AUTH\" > \"$AUTHORIZED_KEYS\"\n"
            "rm -f \"$TMP_AUTH\"\n"
            "chmod 600 \"$AUTHORIZED_KEYS\" >/dev/null 2>&1 || true\n"
            "printf 'Managed SSH public key removed from authorized_keys\\n'\n"
        )

    def _swarm_leave_script(self):
        return (
            "set -eu\n"
            "SUDO=''\n"
            "if [ \"$(id -u)\" != '0' ]; then SUDO='sudo -n'; fi\n"
            "if command -v docker >/dev/null 2>&1; then $SUDO docker swarm leave --force >/dev/null 2>&1 || true; fi\n"
            "printf 'Remote swarm membership cleanup checked\\n'\n"
        )

    def _remote_swarm_inspect_script(self):
        return (
            "set -eu\n"
            "SUDO=''\n"
            "if [ \"$(id -u)\" != '0' ]; then SUDO='sudo -n'; fi\n"
            "if command -v docker >/dev/null 2>&1; then $SUDO docker info --format '{{json .}}' 2>/dev/null || true; fi\n"
        )

    def _inspect_remote_swarm_membership(self, node, operation_id, env=None):
        step = "Remote swarm inspect"
        self._step(operation_id, step, "running", env=env)
        result = self._run_ssh_command(
            node,
            ["sh", "-lc", self._remote_swarm_inspect_script()],
            timeout_seconds=20,
            env=env,
            capture_limit=8000,
        )
        info, swarm = _swarm_from_docker_info(result.get("stdout") if result.get("status") == "ok" else "")
        state = str(swarm.get("LocalNodeState") or "").strip().lower()
        payload = {
            "status": result.get("status"),
            "exit_code": result.get("exit_code"),
            "state": state,
            "node_id": swarm.get("NodeID") or "",
            "control_available": swarm.get("ControlAvailable"),
            "docker_available": bool(info),
            "swarm_active": state == "active",
            "standalone": state in {"", "inactive", "pending"},
        }
        self._step(operation_id, step, "succeeded" if result.get("status") == "ok" else "failed", payload, env=env)
        if result.get("status") != "ok":
            return payload
        return payload

    def _remote_cleanup_script(self, node, env=None):
        public_key = self._managed_public_key(node)
        collector = self._cleanup_script_for("monitoring.metrics_collector.remove")
        exporter = self._cleanup_script_for(
            "monitoring.node_exporter.remove",
            {"container_name": "docker-infra-node-exporter", "service_name": "docker-infra-node-exporter.service"},
        )
        return "\n".join([
            "set -eu",
            collector,
            exporter,
            self._swarm_leave_script(),
            self._authorized_key_cleanup_script(public_key),
        ])

    def _append_result(self, operation_id, step_name, result, env=None):
        message = result.get("stdout") if result.get("status") == "ok" else (result.get("stderr") or result.get("stdout"))
        if not message:
            message = result.get("status") or "unknown"
        self.operations.append_output(
            operation_id,
            message,
            stream="stdout" if result.get("status") == "ok" else "stderr",
            metadata={"step": step_name, "status": result.get("status"), "exit_code": result.get("exit_code")},
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

    def _cleanup_remote_registration(self, node, operation_id, env=None):
        step = "Remote cleanup"
        self._step(operation_id, step, "running", env=env)
        result = self._run_ssh_command(
            node,
            ["sh", "-lc", self._remote_cleanup_script(node, env=env)],
            timeout_seconds=120,
            env=env,
        )
        self._append_result(operation_id, step, result, env=env)
        if result.get("status") != "ok":
            raise NodeError(
                409,
                "삭제 대상 서버 정리에 실패했습니다. 서버 접속과 sudo 권한을 확인해주세요.",
                "NODE_REMOTE_CLEANUP_FAILED",
                check={"status": result.get("status"), "exit_code": result.get("exit_code"), "reason": self.ssh_executor.failure_reason(result)},
            )
        self._step(operation_id, step, "succeeded", env=env)
        return result

    def _swarm_remove_missing(self, result):
        output = f"{result.get('stdout', '')}\n{result.get('stderr', '')}".lower()
        return "not found" in output or "no such node" in output

    def _master_swarm_skip_reason(self, remote_swarm):
        state = str((remote_swarm or {}).get("state") or "").strip().lower()
        if state == "active":
            return "remote_swarm_node_id_empty"
        if state in {"", "inactive", "pending"}:
            return "standalone_node"
        return "swarm_node_id_empty"

    def _cleanup_master_registration(self, node, operation_id, remote_swarm=None, env=None):
        results = {}
        remote_swarm = remote_swarm or {}
        swarm_node_id = str(node.get("swarm_node_id") or remote_swarm.get("node_id") or "").strip()
        if swarm_node_id:
            step = "Master swarm node remove"
            self._step(
                operation_id,
                step,
                "running",
                {"swarm_node_id": swarm_node_id, "source": "stored" if node.get("swarm_node_id") else "remote_inspect"},
                env=env,
            )
            result = self.local_executor.run(
                "swarm.node.remove",
                params={"node_id": swarm_node_id},
                timeout_seconds=30,
                env=env,
            )
            self._append_result(operation_id, step, result, env=env)
            if result.get("status") != "ok" and not self._swarm_remove_missing(result):
                raise NodeError(
                    409,
                    "마스터 Docker Swarm 노드 정보 삭제에 실패했습니다.",
                    "MASTER_SWARM_NODE_REMOVE_FAILED",
                    check={"status": result.get("status"), "exit_code": result.get("exit_code"), "stderr": result.get("stderr")},
                )
            self._step(
                operation_id,
                step,
                "succeeded",
                {
                    "missing": self._swarm_remove_missing(result),
                    "swarm_node_id": swarm_node_id,
                    "source": "stored" if node.get("swarm_node_id") else "remote_inspect",
                },
                env=env,
            )
            results["swarm_remove"] = result
        else:
            reason = self._master_swarm_skip_reason(remote_swarm)
            self._step(operation_id, "Master swarm node remove", "skipped", {"reason": reason}, env=env)
            results["swarm_remove"] = {"status": "skipped", "reason": reason, "remote_swarm": remote_swarm}

        known_hosts = self.ssh_executor.remove_known_host(node["host"], port=node.get("ssh_port"), env=env)
        self.operations.append_output(
            operation_id,
            f"known_hosts entries removed: {', '.join(known_hosts.get('targets') or [])}",
            stream="system",
            metadata={"step": "Master known_hosts cleanup", "result": known_hosts},
            env=env,
        )
        results["known_hosts"] = known_hosts
        return results

    def _delete_node_row(self, node, env=None):
        credential = node.get("credential") or {}
        key_file = credential.get("key_file") or (credential.get("metadata") or {}).get("key_file")
        with connect(env=env) as connection:
            with connection.cursor() as cursor:
                remaining_key_refs = 0
                if key_file:
                    cursor.execute(
                        "SELECT count(*) AS count FROM node_credentials WHERE key_file = %s AND node_id <> %s",
                        (key_file, node["id"]),
                    )
                    remaining_key_refs = int(cursor.fetchone()["count"])
                cursor.execute("DELETE FROM nodes WHERE id = %s", (node["id"],))
                return {"deleted": cursor.rowcount, "key_file": key_file, "remaining_key_refs": remaining_key_refs}

    def _remove_unused_key_file(self, key_file, remaining_key_refs, env=None):
        if not key_file:
            return {"status": "skipped", "reason": "key_file_empty"}
        if remaining_key_refs > 0:
            return {"status": "skipped", "reason": "key_file_still_referenced", "remaining_refs": remaining_key_refs}
        key_root = Path(config.ssh_key_dir(env)).expanduser().resolve()
        key_path = Path(key_file).expanduser().resolve()
        try:
            key_path.relative_to(key_root)
        except ValueError:
            return {"status": "skipped", "reason": "key_file_outside_managed_dir", "key_file": str(key_path)}
        removed = []
        for path in [key_path, Path(f"{key_path}.pub")]:
            if path.exists():
                path.unlink()
                removed.append(str(path))
        return {"status": "removed" if removed else "skipped", "removed": removed}

    def _selected_after_delete(self, nodes):
        if not nodes:
            return None
        return next((node for node in nodes if node.get("is_local_master")), None) or nodes[0]

    def _running_service_count(self, group):
        summary = group.get("summary") or {}
        try:
            running = int(summary.get("running") or 0)
        except Exception:
            running = 0
        if running > 0:
            return running
        count = 0
        for container in group.get("containers") or []:
            if str(container.get("state") or "").lower() == "running":
                count += 1
        return count

    def _running_registered_services(self, node_id, env=None):
        panel = self.live_containers(node_id, persist=True, env=env)
        groups = (panel.get("groups") or {}).get("service_groups") or []
        running_services = []
        for group in groups:
            running = self._running_service_count(group)
            if running <= 0:
                continue
            service = group.get("service") or {}
            running_services.append({
                "id": service.get("id"),
                "name": service.get("name") or service.get("namespace") or "등록된 서비스",
                "namespace": service.get("namespace"),
                "running": running,
            })
        return running_services

    def _assert_no_running_registered_services(self, node_id, env=None):
        running_services = self._running_registered_services(node_id, env=env)
        if not running_services:
            return
        names = ", ".join([item["name"] for item in running_services[:5]])
        suffix = "" if len(running_services) <= 5 else f" 외 {len(running_services) - 5}개"
        raise NodeError(
            409,
            f"실행 중인 서비스가 있어 서버 등록 해제를 진행할 수 없습니다. 먼저 서비스를 중지하거나 다른 서버로 이동해주세요. ({names}{suffix})",
            "NODE_RUNNING_SERVICES_BLOCK_UNREGISTER",
            services=running_services,
        )

    def unregister_slave(self, node_id, confirmation_name=None, env=None):
        if not node_id:
            raise NodeError(400, "node_id는 필수입니다.", "NODE_ID_REQUIRED")
        node = self.detail(node_id, env=env)
        if node.get("is_local_master"):
            raise NodeError(400, "중심 서버는 등록 해제할 수 없습니다.", "LOCAL_MASTER_DELETE_UNSUPPORTED")
        expected_name = str(node.get("name") or "").strip()
        if str(confirmation_name or "").strip() != expected_name:
            raise NodeError(400, "서버 이름을 정확히 입력해야 등록 해제가 가능합니다.", "NODE_DELETE_CONFIRMATION_MISMATCH")

        self._assert_no_running_registered_services(node_id, env=env)

        operation = self.operations.create(
            "node.unregister",
            target_type="node",
            target_id=node_id,
            message="서버 등록 해제를 시작했습니다.",
            requested_payload={"node_id": node_id, "name": node.get("name"), "host": node.get("host")},
            test_run_id=node.get("test_run_id"),
            metadata={"node_id": node_id, "host": node.get("host")},
            env=env,
        )
        operation_id = operation["id"]
        try:
            remote_swarm = self._inspect_remote_swarm_membership(node, operation_id, env=env)
            remote_cleanup = self._cleanup_remote_registration(node, operation_id, env=env)
            master_cleanup = self._cleanup_master_registration(node, operation_id, remote_swarm=remote_swarm, env=env)
            db_delete = self._delete_node_row(node, env=env)
            key_cleanup = self._remove_unused_key_file(db_delete.get("key_file"), db_delete.get("remaining_key_refs", 0), env=env)
            self.operations.append_output(
                operation_id,
                "database node, credentials, metrics, and scoped macros removed",
                stream="system",
                metadata={"step": "Database cleanup", "deleted": db_delete.get("deleted"), "key_cleanup": key_cleanup},
                env=env,
            )
            rows = self.list(env=env)
            selected = self._selected_after_delete(rows)
            result_payload = {
                "node_id": node_id,
                "name": node.get("name"),
                "host": node.get("host"),
                "remote_cleanup": {"status": remote_cleanup.get("status"), "exit_code": remote_cleanup.get("exit_code")},
                "remote_swarm": remote_swarm,
                "master_cleanup": master_cleanup,
                "database": db_delete,
                "key_file": key_cleanup,
            }
            operation = self.operations.transition(
                operation_id,
                "succeeded",
                message="서버 등록 해제를 완료했습니다.",
                result_payload=result_payload,
                env=env,
            )
            return {
                "deleted_node_id": node_id,
                "operation": operation,
                "nodes": rows,
                "selected": selected,
                "cleanup": result_payload,
            }
        except NodeError as exc:
            operation = self.operations.transition(
                operation_id,
                "failed",
                message=exc.message,
                result_payload={"error_code": exc.error_code, **exc.extra},
                env=env,
            )
            exc.extra["operation"] = operation
            raise
        except Exception as exc:
            operation = self.operations.transition(
                operation_id,
                "failed",
                message=str(exc),
                result_payload={"error": str(exc)},
                env=env,
            )
            raise NodeError(409, "서버 등록 해제를 완료할 수 없습니다.", "NODE_UNREGISTER_FAILED", operation=operation, reason=str(exc))


Model = NodeDeleteMixin
