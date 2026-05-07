import json
import shlex
from pathlib import Path, PurePosixPath

connect = wiz.model("db/postgres").connect
local_catalog = wiz.model("struct/local_command_catalog")
shared = wiz.model("struct/nodes_shared")
node_view = wiz.model("struct/nodes_view")
runtime_state = wiz.model("struct/nodes_runtime_state")
_load_json = shared.load_json
_parse_docker_ps_lines = shared.parse_docker_ps_lines
_container_summary = shared.container_summary
_container_items = shared.container_items
NodeError = shared.NodeError
SYSTEM_METRICS_SCRIPT = local_catalog.SYSTEM_METRICS_SCRIPT


class NodeRuntimeMixin:
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
        if node["is_local_master"]:
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

    def metric_snapshot(self, node_id, env=None):
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
        self._write_snapshot(node_id, payload, "metric_refresh", test_run_id=test_run_id, env=env)
        return {"node_id": node_id, "latest_metric": node_view.metric(self.latest_metric(node_id, env=env) or payload)}

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
        return None

    def _decorate_containers(self, items, env=None):
        by_namespace, by_stack = self._services_map(env=env)
        groups = {}
        unmanaged = []
        for item in items:
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
        payload = self._latest_metric_payload(node_id, env=env)
        payload["containers"] = {"summary": _container_summary(items), "items": items}
        self._write_snapshot(node_id, payload, "containers_refresh", test_run_id=test_run_id, env=env)

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
            remote_command=["docker", "ps", "-a", "--format", "{{json .}}"],
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
        return self._run_node_command(
            node,
            local_command_id=command_id,
            local_params={"ids": ids},
            remote_command=["docker", action, *ids],
            timeout_seconds=20,
            env=env,
        )

    def container_action(self, node_id, payload, env=None):
        payload = payload or {}
        action = str(payload.get("action") or "").strip().lower()
        container_id = str(payload.get("container_id") or "").strip()
        if action not in {"start", "stop", "restart"}:
            raise NodeError(400, "지원하지 않는 컨테이너 동작입니다.", "INVALID_CONTAINER_ACTION")
        if not container_id:
            raise NodeError(400, "container_id는 필수입니다.", "CONTAINER_ID_REQUIRED")
        node, _ = self._target_node(node_id, env=env)
        result = self._run_container_action(node, action, [container_id], env=env)
        if result["status"] != "ok":
            raise NodeError(409, f"컨테이너 동작에 실패했습니다. {self._command_failure(result, 'container action failed')}", "CONTAINER_ACTION_FAILED", check=result)
        refreshed = self.refresh_containers_panel(node_id, env=env)
        refreshed["result"] = {"action": action, "scope": "container", "container_id": container_id, "check": result}
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
        if result["status"] != "ok":
            raise NodeError(409, f"서비스 컨테이너 동작에 실패했습니다. {self._command_failure(result, 'service container action failed')}", "SERVICE_CONTAINER_ACTION_FAILED", check=result)
        refreshed = self.refresh_containers_panel(node_id, env=env)
        refreshed["result"] = {"action": action, "scope": "service", "service_namespace": namespace, "container_ids": ids, "check": result}
        return refreshed

    def _normalize_browse_path(self, value):
        path = str(PurePosixPath(value or "/"))
        return path if path.startswith("/") else f"/{path}"

    def _default_browse_path(self, node, env=None):
        if node["is_local_master"]:
            return self._normalize_browse_path(str(Path.home()))
        credential = node.get("credential") or {}
        username = str(credential.get("username") or "").strip()
        result = self._run_ssh_command(node, ["sh", "-lc", 'printf "%s\\n" "$HOME"'], timeout_seconds=5, env=env)
        if result.get("status") == "ok":
            home = str(result.get("stdout") or "").strip()
            if home:
                return self._normalize_browse_path(home.splitlines()[-1])
        if username == "root":
            return "/root"
        if username:
            return self._normalize_browse_path(f"/home/{username}")
        return "/"

    def _resolve_browse_path(self, node, value, env=None):
        raw = str(value or "").strip()
        if not raw or raw == "~":
            return self._default_browse_path(node, env=env)
        if raw.startswith("~/"):
            home = self._default_browse_path(node, env=env).rstrip("/")
            suffix = raw[2:].strip("/")
            return self._normalize_browse_path(f"{home}/{suffix}") if suffix else home or "/"
        return self._normalize_browse_path(raw)

    def _remote_list_dir(self, node, path, env=None):
        quoted = shlex.quote(path)
        script = f'base={quoted}; [ -d "$base" ] || exit 44; printf "%s\\n" "$base"; find "$base" -mindepth 1 -maxdepth 1 -printf "%f\\t%y\\t%s\\n" 2>/dev/null | sort'
        result = self._run_ssh_command(node, ["sh", "-lc", script], timeout_seconds=8, env=env)
        if result["status"] != "ok":
            raise NodeError(404, "선택한 경로를 열 수 없습니다.", "NODE_PATH_NOT_FOUND", check=result)
        lines = (result["stdout"] or "").splitlines()
        current = lines[0] if lines else path
        items = []
        for line in lines[1:]:
            name, entry_type, size = (line.split("\t", 2) + ["", "", ""])[:3]
            item_path = f"{current.rstrip('/')}/{name}" if current != "/" else f"/{name}"
            items.append({"name": name, "path": item_path, "type": "folder" if entry_type == "d" else "file", "size": int(size or 0)})
        return {"path": current, "items": items}

    def browse_files(self, node_id, payload=None, env=None):
        payload = payload or {}
        node, _ = self._target_node(node_id, env=env)
        path = self._resolve_browse_path(node, payload.get("path"), env=env)
        if node["is_local_master"]:
            result = self.local_executor.run("filesystem.list", params={"path": path}, timeout_seconds=8, env=env)
            if result["status"] != "ok":
                raise NodeError(404, "선택한 경로를 열 수 없습니다.", "NODE_PATH_NOT_FOUND", check=result)
            data = _load_json(result["stdout"])
        else:
            data = self._remote_list_dir(node, path, env=env)
        current = data.get("path") or path
        parent = str(PurePosixPath(current).parent) if current != "/" else None
        show_hidden = str(payload.get("show_hidden") or "").strip().lower() in {"1", "true", "yes", "on"}
        items = data.get("items") or []
        if not show_hidden:
            items = [item for item in items if not str(item.get("name") or "").startswith(".")]
        return {"path": current, "parent": None if parent == current else parent, "items": items}

    def read_file_text(self, node_id, path, env=None):
        path = self._normalize_browse_path(path)
        node, _ = self._target_node(node_id, env=env)
        if node["is_local_master"]:
            result = self.local_executor.run("filesystem.read", params={"path": path}, timeout_seconds=8, env=env)
        else:
            quoted = shlex.quote(path)
            result = self._run_ssh_command(node, ["sh", "-lc", f'[ -f {quoted} ] || exit 44; cat -- {quoted}'], timeout_seconds=8, env=env)
        if result["status"] != "ok":
            raise NodeError(404, "선택한 파일을 읽을 수 없습니다.", "NODE_FILE_READ_FAILED", check=result)
        return result["stdout"]


Model = NodeRuntimeMixin
