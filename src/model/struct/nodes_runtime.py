import datetime

from psycopg.types.json import Jsonb

connect = wiz.model("db/postgres").connect
local_catalog = wiz.model("struct/local_command_catalog")
shared = wiz.model("struct/nodes_shared")
node_view = wiz.model("struct/nodes_view")
runtime_state = wiz.model("struct/nodes_runtime_state")
files_mixin = wiz.model("struct/nodes_runtime_files")
_load_json = shared.load_json
_parse_docker_ps_lines = shared.parse_docker_ps_lines
_container_summary = shared.container_summary
_container_items = shared.container_items
_normalize_container_item = shared.normalize_container_item
_container_matches_service = shared.container_matches_service
NodeError = shared.NodeError
SYSTEM_METRICS_SCRIPT = local_catalog.SYSTEM_METRICS_SCRIPT


class NodeRuntimeMixin(files_mixin):
    def _command_failure(self, result, default_message):
        if result.get("status") == "timeout" or result.get("timed_out"):
            return "응답 시간이 초과되었습니다."
        if result.get("status") == "missing":
            return "실행 파일을 찾을 수 없습니다."
        output = result.get("stderr") or result.get("stdout") or ""
        if output:
            return str(output).strip().splitlines()[-1][:160]
        return default_message

    def _target_node(self, node_id, env=None):
        node = self.detail(node_id, env=env)
        return node, node.get("test_run_id")

    def _run_node_command(self, node, local_command_id=None, local_params=None, remote_command=None, timeout_seconds=None, env=None):
        if self._is_local_master_node(node):
            return self.local_executor.run(local_command_id, params=local_params or {}, timeout_seconds=timeout_seconds, env=env)
        return self._run_ssh_command(node, remote_command, timeout_seconds=timeout_seconds, env=env)

    def _latest_metric_payload(self, node_id, env=None):
        latest = self.latest_metric(node_id, env=env) or {}
        return {
            "cpu_percent": latest.get("cpu_percent"),
            "memory": latest.get("memory") or {},
            "storage": latest.get("storage") or {},
            "containers": latest.get("containers") or {"summary": {"total": 0, "running": 0, "stopped": 0}, "items": []},
        }

    def _write_snapshot(self, node_id, payload, source, test_run_id=None, env=None):
        with connect(env=env) as connection:
            with connection.cursor() as cursor:
                self._write_node_metric(cursor, node_id, payload, test_run_id=test_run_id, metadata={"source": source})

    def _system_metric_payload(self, node_id, env=None):
        node, test_run_id = self._target_node(node_id, env=env)
        result = self._run_node_command(
            node,
            local_command_id="system.metrics",
            remote_command=["sh", "-lc", SYSTEM_METRICS_SCRIPT],
            timeout_seconds=8,
            env=env,
        )
        if result["status"] != "ok":
            raise NodeError(409, f"서버 자원 정보를 갱신할 수 없습니다. {self._command_failure(result, 'metric refresh failed')}", "NODE_METRIC_REFRESH_FAILED", check=result)
        payload = self._latest_metric_payload(node_id, env=env)
        payload.update(_load_json(result["stdout"]))
        payload["reported_at"] = datetime.datetime.now(datetime.timezone.utc).isoformat().replace("+00:00", "Z")
        return node, test_run_id, payload, result

    def metric_snapshot(self, node_id, env=None):
        node, test_run_id, payload, result = self._system_metric_payload(node_id, env=env)
        self._write_snapshot(node_id, payload, "metric_refresh", test_run_id=test_run_id, env=env)
        return {"node_id": node_id, "latest_metric": node_view.metric(self.latest_metric(node_id, env=env) or payload)}

    def live_metric(self, node_id, env=None):
        node, test_run_id, payload, result = self._system_metric_payload(node_id, env=env)
        return {"node_id": node_id, "latest_metric": node_view.metric(payload)}

    def _services_map(self, env=None):
        with connect(env=env) as connection:
            with connection.cursor() as cursor:
                cursor.execute("SELECT id, name, namespace, status, compose_path, stack_name, metadata FROM services ORDER BY created_at DESC")
                services = [dict(row) for row in cursor.fetchall()]
        by_namespace = {service["namespace"]: service for service in services if service.get("namespace")}
        by_stack = {service["stack_name"]: service for service in services if service.get("stack_name")}
        return by_namespace, by_stack

    def _match_service(self, item, by_namespace, by_stack):
        namespace = item.get("service_namespace")
        if namespace and namespace in by_namespace:
            return by_namespace[namespace]
        runtime_name = item.get("runtime_service_name") or ""
        if runtime_name and "_" in runtime_name:
            stack_name = runtime_name.split("_", 1)[0]
            if stack_name in by_stack:
                return by_stack[stack_name]
        if namespace and namespace in by_stack:
            return by_stack[namespace]
        seen = set()
        for service in list(by_namespace.values()) + list(by_stack.values()):
            service_id = str(service.get("id") or service.get("namespace") or service.get("stack_name") or "")
            if service_id in seen:
                continue
            seen.add(service_id)
            if _container_matches_service(item, service):
                return service
        return None

    def _decorate_containers(self, items, env=None):
        by_namespace, by_stack = self._services_map(env=env)
        groups = {}
        unmanaged = []
        for raw_item in items:
            item = _normalize_container_item(raw_item)
            service = self._match_service(item, by_namespace, by_stack)
            if service is None:
                item["registered_service"] = None
                unmanaged.append(item)
                continue
            ref = {
                "id": str(service["id"]),
                "name": service["name"],
                "namespace": service["namespace"],
                "status": service["status"],
                "stack_name": service.get("stack_name"),
            }
            item["registered_service"] = ref
            key = ref["namespace"]
            if key not in groups:
                groups[key] = {"service": ref, "containers": []}
            groups[key]["containers"].append(item)

        service_groups = []
        for key in sorted(groups):
            group = groups[key]
            summary = _container_summary(group["containers"])
            service_groups.append({"service": group["service"], "containers": group["containers"], "summary": summary})
        return {"service_groups": service_groups, "unmanaged_containers": unmanaged}

    def _remember_containers(self, node_id, items, test_run_id=None, env=None):
        refreshed_at = datetime.datetime.now(datetime.timezone.utc).isoformat().replace("+00:00", "Z")
        containers = {"summary": _container_summary(items), "items": items}
        with connect(env=env) as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT id
                    FROM node_metrics
                    WHERE node_id = %s
                    ORDER BY reported_at DESC, created_at DESC
                    LIMIT 1
                    """,
                    (node_id,),
                )
                row = cursor.fetchone()
                if row is None:
                    return
                cursor.execute(
                    """
                    UPDATE node_metrics
                    SET containers = %s,
                        metadata = COALESCE(metadata, '{}'::jsonb) || %s
                    WHERE id = %s
                    """,
                    (
                        Jsonb(containers),
                        Jsonb({"containers_refreshed_at": refreshed_at, "containers_refresh_test_run_id": test_run_id}),
                        row["id"],
                    ),
                )

    def cached_containers_panel(self, node_id, env=None):
        latest = self.latest_metric(node_id, env=env) or {}
        items = _container_items(latest.get("containers") or {})
        groups = self._decorate_containers(items, env=env)
        return node_view.panel(items, groups)

    def cached_detail(self, node_id, env=None):
        return {"node": node_view.node(self.detail(node_id, env=env)), **self.cached_containers_panel(node_id, env=env)}

    def live_containers(self, node_id, persist=True, env=None):
        node, test_run_id = self._target_node(node_id, env=env)
        result = self._run_node_command(
            node,
            local_command_id="docker.containers",
            remote_command=["docker", "ps", "-a", "--no-trunc", "--format", "{{json .}}"],
            timeout_seconds=10,
            env=env,
        )
        if result["status"] != "ok":
            if runtime_state.docker_unavailable(result):
                if persist:
                    self._remember_containers(node_id, [], test_run_id=test_run_id, env=env)
                return {"items": [], "groups": {"service_groups": [], "unmanaged_containers": []}, "check": result, "docker_result": result}
            raise NodeError(409, f"컨테이너 목록을 불러올 수 없습니다. {self._command_failure(result, 'docker ps failed')}", "NODE_CONTAINERS_REFRESH_FAILED", check=result)
        items = _parse_docker_ps_lines(result["stdout"])
        if persist:
            self._remember_containers(node_id, items, test_run_id=test_run_id, env=env)
        groups = self._decorate_containers(items, env=env)
        return {"items": items, "groups": groups, "check": result}

    def _service_container_command(self, namespace):
        return ["docker", "ps", "-a", "--no-trunc", "--filter", f"name={namespace}", "--format", "{{json .}}"]

    def _service_container_items(self, items, namespace, stack_name=None):
        service_ref = {"namespace": namespace, "stack_name": stack_name or namespace}
        return [
            item for item in items
            if _container_matches_service(item, service_ref)
        ]

    def service_containers(self, node_id, namespace, stack_name=None, env=None):
        node, _test_run_id = self._target_node(node_id, env=env)
        result = self._run_node_command(
            node,
            local_command_id="docker.containers.service",
            local_params={"namespace": stack_name or namespace},
            remote_command=self._service_container_command(stack_name or namespace),
            timeout_seconds=4,
            env=env,
        )
        if result["status"] != "ok":
            if runtime_state.docker_unavailable(result):
                return {"items": [], "check": result, "docker_result": result}
            raise NodeError(409, f"컨테이너 목록을 불러올 수 없습니다. {self._command_failure(result, 'docker ps failed')}", "NODE_CONTAINERS_REFRESH_FAILED", check=result)
        items = self._service_container_items(_parse_docker_ps_lines(result["stdout"]), namespace, stack_name=stack_name)
        return {"items": items, "check": result}

    def server_detail(self, node_id, env=None):
        panel = self.live_containers(node_id, persist=True, env=env)
        return {
            "node": node_view.node(self.detail(node_id, env=env), docker_result=panel.get("docker_result")),
            **node_view.panel(panel["items"], panel["groups"]),
        }

    def refresh_containers_panel(self, node_id, env=None):
        panel = self.live_containers(node_id, persist=True, env=env)
        return {
            "node": node_view.node(self.detail(node_id, env=env), docker_result=panel.get("docker_result")),
            **node_view.panel(panel["items"], panel["groups"]),
        }

    def _run_container_action(self, node, action, ids, env=None):
        command_id = f"docker.container.{action}"
        remote_actions = {
            "start": ["docker", "start", *ids],
            "stop": ["docker", "stop", *ids],
            "restart": ["docker", "restart", *ids],
            "delete": ["docker", "rm", "-f", *ids],
        }
        return self._run_node_command(
            node,
            local_command_id=command_id,
            local_params={"ids": ids},
            remote_command=remote_actions.get(action, ["docker", action, *ids]),
            timeout_seconds=20,
            env=env,
        )

    def _container_id_matches(self, actual, requested):
        actual = str(actual or "").strip()
        requested = str(requested or "").strip()
        if not actual or not requested:
            return False
        return actual == requested or actual.startswith(requested) or requested.startswith(actual)

    def _record_runtime_operation(self, node_id, operation_type, action, result, payload=None, env=None):
        status = "succeeded" if result.get("status") == "ok" else "failed"
        operation = self.operations.create(
            operation_type,
            target_type="node",
            target_id=node_id,
            message=f"{operation_type} {action} {status}",
            status=status,
            requested_payload=payload or {},
            result_payload={
                "command_id": result.get("command_id"),
                "status": result.get("status"),
                "exit_code": result.get("exit_code"),
                "duration_ms": result.get("duration_ms"),
            },
            env=env,
        )
        output = result.get("stdout") if result.get("status") == "ok" else (result.get("stderr") or result.get("stdout"))
        if output:
            self.operations.append_output(
                operation["id"],
                output,
                stream="stdout" if result.get("status") == "ok" else "stderr",
                env=env,
            )
        return operation

    def container_action(self, node_id, payload, env=None):
        payload = payload or {}
        action = str(payload.get("action") or "").strip().lower()
        container_id = str(payload.get("container_id") or "").strip()
        if action not in {"start", "stop", "restart", "delete"}:
            raise NodeError(400, "지원하지 않는 컨테이너 동작입니다.", "INVALID_CONTAINER_ACTION")
        if not container_id:
            raise NodeError(400, "container_id는 필수입니다.", "CONTAINER_ID_REQUIRED")
        panel = self.live_containers(node_id, persist=False, env=env)
        target = next((item for item in panel.get("items") or [] if self._container_id_matches(item.get("id"), container_id)), None)
        if target is None:
            raise NodeError(404, "선택한 컨테이너를 이 서버에서 찾을 수 없습니다.", "CONTAINER_NOT_FOUND")
        container_id = str(target.get("id") or container_id)
        node, _ = self._target_node(node_id, env=env)
        result = self._run_container_action(node, action, [container_id], env=env)
        operation = self._record_runtime_operation(
            node_id,
            "container.action",
            action,
            result,
            payload={"action": action, "container_id": container_id},
            env=env,
        )
        if result["status"] != "ok":
            raise NodeError(409, f"컨테이너 동작에 실패했습니다. {self._command_failure(result, 'container action failed')}", "CONTAINER_ACTION_FAILED", check=result)
        refreshed = self.refresh_containers_panel(node_id, env=env)
        refreshed["result"] = {"action": action, "scope": "container", "container_id": container_id, "check": result, "operation": operation}
        return refreshed

    def service_action(self, node_id, payload, env=None):
        payload = payload or {}
        action = str(payload.get("action") or "").strip().lower()
        namespace = str(payload.get("service_namespace") or "").strip()
        if action not in {"start", "stop", "restart"}:
            raise NodeError(400, "지원하지 않는 서비스 동작입니다.", "INVALID_SERVICE_ACTION")
        if not namespace:
            raise NodeError(400, "service_namespace는 필수입니다.", "SERVICE_NAMESPACE_REQUIRED")
        panel = self.live_containers(node_id, persist=False, env=env)
        group = next((item for item in panel["groups"]["service_groups"] if item["service"]["namespace"] == namespace), None)
        if group is None:
            raise NodeError(404, "선택한 서비스의 컨테이너를 찾을 수 없습니다.", "SERVICE_CONTAINERS_NOT_FOUND")
        ids = [item["id"] for item in group["containers"] if item.get("id")]
        if not ids:
            raise NodeError(409, "선택한 서비스에 제어할 컨테이너가 없습니다.", "SERVICE_CONTAINER_IDS_EMPTY")
        node, _ = self._target_node(node_id, env=env)
        result = self._run_container_action(node, action, ids, env=env)
        operation = self._record_runtime_operation(
            node_id,
            "service.action",
            action,
            result,
            payload={"action": action, "service_namespace": namespace, "container_ids": ids},
            env=env,
        )
        if result["status"] != "ok":
            raise NodeError(409, f"서비스 동작에 실패했습니다. {self._command_failure(result, 'service action failed')}", "SERVICE_CONTAINER_ACTION_FAILED", check=result)
        refreshed = self.refresh_containers_panel(node_id, env=env)
        refreshed["result"] = {"action": action, "scope": "service", "service_namespace": namespace, "container_ids": ids, "check": result, "operation": operation}
        return refreshed

Model = NodeRuntimeMixin
