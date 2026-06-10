from pathlib import Path
import subprocess
import threading
import time

import yaml
from psycopg.types.json import Jsonb


connect = wiz.model("db/postgres").connect
local_executor = wiz.model("struct/local_executor")
operations = wiz.model("struct/operations")
backup_system = wiz.model("struct/backup_system")
compose_rules = wiz.model("struct/compose_rules")
service_ports = wiz.model("struct/services_ports")
service_nginx = wiz.model("struct/service_nginx")
deploy_targets = wiz.model("struct/services_deploy_targets")
placement_selector = wiz.model("struct/services_placement")
nodes = wiz.model("struct").nodes
shared = wiz.model("struct/services_shared")
ServiceError = shared.ServiceError
_serialize = shared.serialize


def _command_text(result):
    if not result:
        return ""
    return result.get("stdout") or result.get("stderr") or ""


def _image_registry(image_ref):
    first = str(image_ref or "").split("/", 1)[0]
    if "." in first or ":" in first or first == "localhost":
        return first
    return ""


def _safe_int(value, fallback=0):
    try:
        return int(value)
    except Exception:
        return fallback


def _has_host_published_ports(service):
    for item in service.get("ports") or []:
        if not isinstance(item, dict):
            continue
        mode = str(item.get("mode") or "").strip().lower()
        published = _safe_int(item.get("published") or item.get("target"), 0)
        if mode == "host" and published > 0:
            return True
    return False


class ServiceDeployMixin:
    def _deploy_operation_payload(self, service, stack_name, compose_path):
        return {
            "service_id": str(service.get("id")),
            "namespace": service.get("namespace"),
            "stack_name": stack_name,
            "compose_path": str(compose_path),
        }

    def _create_deploy_operation(self, service, stack_name, compose_path, status="running", message="서비스 배포를 시작했습니다.", env=None):
        return operations.create(
            "service.deploy",
            target_type="service",
            target_id=service.get("id"),
            status=status,
            message=message,
            requested_payload=self._deploy_operation_payload(service, stack_name, compose_path),
            metadata={"service_id": str(service.get("id")), "namespace": service.get("namespace"), "background": status == "pending"},
            env=env,
        )

    def _prepare_deploy(self, payload, env=None):
        payload = payload or {}
        service_id = payload.get("service_id")
        if not service_id:
            raise ServiceError(400, "service_id는 필수입니다.", "SERVICE_ID_REQUIRED")

        with connect(env=env) as connection:
            with connection.cursor() as cursor:
                service = self._service_row(cursor, service_id)

        compose_path = Path(service.get("compose_path") or "").expanduser()
        if not compose_path.is_file():
            raise ServiceError(404, "서비스 Compose 파일을 찾을 수 없습니다.", "SERVICE_COMPOSE_NOT_FOUND")
        stack_name = service.get("stack_name") or service.get("namespace")
        return service, compose_path, stack_name

    def _active_deploy_operation(self, service, env=None):
        service_id = str(service.get("id") or "")
        namespace = str(service.get("namespace") or "")
        with connect(env=env) as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT id
                    FROM operation_logs
                    WHERE type = 'service.deploy'
                      AND status IN ('pending', 'running')
                      AND (
                        requested_payload->>'service_id' = %s
                        OR metadata->>'service_id' = %s
                        OR requested_payload->>'namespace' = %s
                        OR metadata->>'namespace' = %s
                      )
                    ORDER BY created_at DESC
                    LIMIT 1
                    """,
                    (service_id, service_id, namespace, namespace),
                )
                row = cursor.fetchone()
        if row is None:
            return None
        return operations.detail(row["id"], env=env)

    def _deploy_background_worker(self, payload, operation_id, env=None):
        try:
            body = dict(payload or {})
            body["operation_id"] = operation_id
            self.deploy(body, env=env)
        except ServiceError:
            return
        except Exception as exc:
            try:
                operations.append_output(
                    operation_id,
                    str(exc),
                    stream="stderr",
                    metadata={"step": "background deploy", "error": str(exc)},
                    env=env,
                )
                operations.transition(
                    operation_id,
                    "failed",
                    message="서비스 배포 중 예기치 않은 오류가 발생했습니다.",
                    result_payload={"error": str(exc)},
                    env=env,
                )
            except Exception:
                pass

    def deploy_background(self, payload, env=None):
        payload = dict(payload or {})
        service, compose_path, stack_name = self._prepare_deploy(payload, env=env)
        if payload.get("force_new_operation") is not True:
            active = self._active_deploy_operation(service, env=env)
            if active:
                return {"accepted": True, "service": service, "operation": active, "deduplicated": True}
        operation = self._create_deploy_operation(
            service,
            stack_name,
            compose_path,
            status="pending",
            message="서비스 배포를 백그라운드에서 준비했습니다.",
            env=env,
        )
        thread = threading.Thread(
            target=self._deploy_background_worker,
            args=(payload, operation["id"], env),
            name=f"service-deploy-{operation['id']}",
            daemon=True,
        )
        thread.start()
        return {"accepted": True, "service": service, "operation": operation}

    def _append_result(self, operation_id, result, label, env=None):
        text = _command_text(result)
        if not text:
            text = f"{label}: {result.get('status')}"
        stream = "stdout" if result.get("status") == "ok" else "stderr"
        operations.append_output(operation_id, text, stream=stream, metadata={"step": label}, env=env)

    def _runtime_task_text(self, task, *keys):
        for key in keys:
            value = task.get(key)
            if value not in (None, ""):
                return str(value).strip()
        return ""

    def _runtime_progress_snapshot(self, runtime, fallback_message=""):
        runtime = runtime or {}
        stack = runtime.get("stack") or {}
        stack_summary = stack.get("summary") or {}
        container_summary = ((runtime.get("containers") or {}).get("summary") or {})
        desired = int(stack_summary.get("desired") or 0)
        running = int(stack_summary.get("running") or 0)
        container_total = int(container_summary.get("total") or 0)
        container_running = int(container_summary.get("running") or 0)

        tasks = []
        for task in stack.get("tasks") or []:
            if not isinstance(task, dict):
                continue
            state = self._runtime_task_text(task, "CurrentState", "Current state", "current_state")
            desired_state = self._runtime_task_text(task, "DesiredState", "Desired state", "desired_state")
            error = self._runtime_task_text(task, "Error", "error")
            name = self._runtime_task_text(task, "Name", "name", "Service", "service")
            node = self._runtime_task_text(
                task,
                "registered_node_label",
                "registered_node_name",
                "Node",
                "node",
                "Hostname",
                "hostname",
            )
            image = self._runtime_task_text(task, "Image", "image")
            tasks.append({
                "name": name,
                "image": image,
                "node": node,
                "desired_state": desired_state,
                "current_state": state,
                "error": error,
            })

        state_text = " ".join(task.get("current_state", "").lower() for task in tasks)
        has_pull_wait = any(token in state_text for token in ["preparing", "assigned", "accepted", "new", "pending"])
        if desired <= 0:
            message = "Docker 작업을 아직 확인하지 못했습니다."
        elif running < desired and has_pull_wait:
            message = f"이미지 pull 또는 Docker 작업 준비 중입니다. Docker 작업 {running}/{desired}"
        elif running < desired:
            message = f"Docker 작업 실행 대기 중입니다. Docker 작업 {running}/{desired}"
        elif container_total <= 0:
            message = "Docker 작업은 확인됐지만 컨테이너 목록은 아직 비어 있습니다."
        elif container_running < container_total:
            message = f"컨테이너 실행 대기 중입니다. {container_running}/{container_total}"
        else:
            message = fallback_message or "컨테이너 실행 상태를 확인했습니다."

        return {
            "message": message,
            "stack_summary": stack_summary,
            "container_summary": container_summary,
            "tasks": tasks[:8],
            "checked_at": runtime.get("checked_at"),
        }

    def _runtime_ready_result(self, runtime):
        stack = ((runtime or {}).get("stack") or {}).get("summary") or {}
        containers = ((runtime or {}).get("containers") or {}).get("summary") or {}
        health = ((runtime or {}).get("containers") or {}).get("health") or {}
        desired = int(stack.get("desired") or 0)
        running = int(stack.get("running") or 0)
        task_errors = int(stack.get("task_errors") or 0)
        task_error_history = int(stack.get("task_error_history") or 0)
        if task_errors > 0:
            return False, f"Docker 작업 오류 {task_errors}개가 감지되었습니다."
        if desired <= 0:
            return False, "실행 대상 Docker 작업을 아직 확인하지 못했습니다."
        if running <= 0 and task_error_history > 0:
            return False, f"Docker 작업 오류 이력 {task_error_history}개로 새 작업이 실행되지 못했습니다."
        if running < desired:
            return False, f"Docker 작업 실행 대기 중입니다. {running}/{desired}"
        if int(containers.get("total") or 0) > 0 and int(containers.get("running") or 0) <= 0:
            return False, "컨테이너가 아직 실행 상태가 아닙니다."
        if int(health.get("unhealthy") or 0) > 0:
            return False, f"상태 점검 실패 컨테이너 {health.get('unhealthy')}개가 있습니다."
        if int(health.get("starting") or 0) > 0:
            return False, f"컨테이너 상태 점검이 진행 중입니다. starting {health.get('starting')}개"
        return True, "컨테이너 실행 상태를 확인했습니다."

    def _wait_runtime_ready(self, service_id, operation_id, timeout_seconds=120, delay_seconds=3, env=None):
        timeout = max(10, min(int(timeout_seconds or 120), 600))
        delay = max(1, min(int(delay_seconds or 3), 15))
        deadline = time.monotonic() + timeout
        attempts = 0
        last = {"message": "컨테이너 실행 상태를 아직 확인하지 못했습니다."}
        last_progress_message = ""
        while time.monotonic() <= deadline:
            attempts += 1
            try:
                refreshed = self.refresh_deploy_status(service_id, operation_id=operation_id, env=env)
                runtime = refreshed.get("runtime_status") or {}
                ready, message = self._runtime_ready_result(runtime)
                progress = self._runtime_progress_snapshot(runtime, fallback_message=message)
                progress["ready"] = ready
                progress["attempt"] = attempts
                last = {"message": progress.get("message") or message, "runtime_status": runtime, "progress": progress}
                if operation_id:
                    should_append = (
                        attempts == 1
                        or ready
                        or progress.get("message") != last_progress_message
                        or attempts % 5 == 0
                    )
                    operations.transition(
                        operation_id,
                        "running",
                        message=progress.get("message") or message,
                        metadata={"runtime_progress": progress},
                        env=env,
                    )
                    if should_append:
                        operations.append_output(
                            operation_id,
                            progress.get("message") or message,
                            stream="system",
                            metadata={"step": "runtime wait", "attempt": attempts, "progress": progress},
                            env=env,
                        )
                        last_progress_message = progress.get("message") or message
                if ready:
                    return {"status": "ok", "message": message, "attempts": attempts, "runtime_status": runtime}
            except Exception as exc:
                last = {"message": str(exc)}
            time.sleep(delay)
        return {"status": "error", "message": last.get("message") or "컨테이너 실행 대기 시간이 초과되었습니다.", "attempts": attempts, **last}

    def _deploy_failure(self, operation_id, message, result=None, env=None):
        payload = {"check": result or {}}
        operation = operations.transition(operation_id, "failed", message=message, result_payload=payload, env=env)
        raise ServiceError(409, message, "SERVICE_DEPLOY_FAILED", operation=operation, check=result)

    def _sync_domain_published_ports(self, service_id, compose_path, env=None):
        return deploy_targets.sync_domain_published_ports(service_id, compose_path, env=env)

    def _ensure_host_port_update_order(self, compose_path):
        path = Path(compose_path).expanduser()
        compose = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        changed = []
        for service_name, service in (compose.get("services") or {}).items():
            if not isinstance(service, dict) or not _has_host_published_ports(service):
                continue
            deploy = service.setdefault("deploy", {})
            if not isinstance(deploy, dict):
                continue
            update_config = deploy.get("update_config")
            if not isinstance(update_config, dict):
                update_config = dict(compose_rules.DEFAULT_UPDATE_CONFIG)
                deploy["update_config"] = update_config
            previous = update_config.get("order")
            if previous != "stop-first":
                update_config["order"] = "stop-first"
                changed.append({"service": service_name, "previous": previous or "", "order": "stop-first"})
        if changed:
            path.write_text(yaml.safe_dump(compose, sort_keys=False, allow_unicode=False), encoding="utf-8")
        return changed

    def _record_deploy_adjustments(self, service_id, allocations, domain_port_updates, update_order_adjustments=None, env=None):
        payload = {
            "port_allocation": (allocations or {}).get("allocations") or [],
            "port_allocation_changed": bool((allocations or {}).get("changed")),
            "domain_port_updates": domain_port_updates or [],
            "update_order_adjustments": update_order_adjustments or [],
        }
        return payload

    def _ensure_backup_registry_for_deploy(self, service, operation_id, env=None):
        node = self._deployment_node(service, env=env)
        if not node:
            return self._deploy_failure(
                operation_id,
                "백업 저장소 이미지를 pull할 배포 노드를 찾을 수 없습니다.",
                {"status": "error", "message": "deployment node unavailable"},
                env=env,
            )
        try:
            result = nodes.configure_backup_registry_for_node(node["id"], operation_id=operation_id, env=env)
        except Exception as exc:
            return self._deploy_failure(
                operation_id,
                "백업 저장소 이미지를 pull할 수 있도록 노드 레지스트리 설정을 적용할 수 없습니다.",
                {
                    "status": "error",
                    "message": getattr(exc, "message", str(exc)),
                    "error_code": getattr(exc, "error_code", "BACKUP_REGISTRY_NODE_CONFIG_FAILED"),
                },
                env=env,
            )
        return result

    def _ensure_manager_backup_registry_for_deploy(self, operation_id, env=None):
        manager = next((node for node in nodes.list(env=env) if node.get("is_local_master")), None)
        if not manager:
            return None
        try:
            result = nodes.configure_backup_registry_for_node(manager["id"], operation_id=operation_id, env=env)
        except Exception as exc:
            return self._deploy_failure(
                operation_id,
                "백업 저장소 이미지를 로그인할 수 있도록 매니저 노드 레지스트리 설정을 적용할 수 없습니다.",
                {
                    "status": "error",
                    "message": getattr(exc, "message", str(exc)),
                    "error_code": getattr(exc, "error_code", "BACKUP_REGISTRY_MANAGER_CONFIG_FAILED"),
                },
                env=env,
            )
        node = result.get("node") or manager
        return {
            "node": {
                "id": node.get("id"),
                "name": node.get("name"),
                "host": node.get("host"),
                "is_local_master": node.get("is_local_master"),
            },
            "registries": result.get("registries") or [],
            "status": result.get("status"),
        }

    def _compose_image_registries(self, compose_path):
        compose = yaml.safe_load(compose_path.read_text(encoding="utf-8")) or {}
        result = []
        for item in (compose.get("services") or {}).values():
            if not isinstance(item, dict):
                continue
            registry = _image_registry(item.get("image"))
            if registry and registry not in result:
                result.append(registry)
        return result

    def _docker_login_result(self, registry, username, password):
        command = ["docker", "login", registry, "-u", username, "--password-stdin"]
        try:
            completed = subprocess.run(
                command,
                input=f"{password}\n",
                capture_output=True,
                text=True,
                timeout=60,
                check=False,
            )
            return {
                "command": command,
                "command_display": "docker login %s -u %s --password-stdin" % (registry, username),
                "status": "ok" if completed.returncode == 0 else "error",
                "exit_code": completed.returncode,
                "stdout": completed.stdout,
                "stderr": completed.stderr,
            }
        except subprocess.TimeoutExpired as exc:
            return {
                "command": command,
                "command_display": "docker login %s -u %s --password-stdin" % (registry, username),
                "status": "timeout",
                "exit_code": None,
                "stdout": exc.stdout or "",
                "stderr": exc.stderr or "docker login timed out",
                "timed_out": True,
            }

    def _docker_login_retryable(self, result):
        text = " ".join(str(result.get(key) or "") for key in ["stdout", "stderr"]).lower()
        if result.get("status") == "timeout":
            return True
        return any(token in text for token in ["connection refused", "connection reset", "i/o timeout", "no route to host", "temporarily unavailable"])

    def _docker_login_for_deploy(self, registry, username, password, operation_id, env=None):
        attempts = 12
        delay_seconds = 5
        result = None
        for attempt in range(1, attempts + 1):
            result = self._docker_login_result(registry, username, password)
            result["attempts"] = attempt
            if result.get("status") == "ok" or attempt >= attempts or not self._docker_login_retryable(result):
                return result
            operations.append_output(
                operation_id,
                f"백업 저장소 registry 응답 대기 중입니다: {registry} ({attempt}/{attempts})",
                stream="system",
                metadata={"step": "backup registry login wait", "registry": registry, "attempt": attempt, "attempts": attempts},
                env=env,
            )
            time.sleep(delay_seconds)
        return result or {"status": "error", "stderr": "docker login failed"}

    def _ensure_backup_system_running_for_deploy(self, operation_id, env=None):
        try:
            status = backup_system.refresh(env=env)
        except Exception as exc:
            return self._deploy_failure(
                operation_id,
                "백업 저장소 상태를 확인할 수 없습니다.",
                {"status": "error", "message": getattr(exc, "message", str(exc)), "error_code": getattr(exc, "error_code", "BACKUP_SYSTEM_STATUS_FAILED")},
                env=env,
            )
        if not status.get("enabled"):
            return self._deploy_failure(
                operation_id,
                "백업 저장소가 꺼져 있어 스냅샷 이미지를 복원할 수 없습니다.",
                {"status": "error", "backup_system": status},
                env=env,
            )
        if status.get("status") != "running":
            operations.append_output(
                operation_id,
                f"백업 저장소가 실행 중이 아니어서 먼저 시작합니다: {status.get('status')}",
                stream="system",
                metadata={"step": "backup registry start", "backup_system": status},
                env=env,
            )
            try:
                started = backup_system.enable(env=env)
            except Exception as exc:
                return self._deploy_failure(
                    operation_id,
                    "백업 저장소를 시작할 수 없어 스냅샷 이미지를 복원할 수 없습니다.",
                    {"status": "error", "message": getattr(exc, "message", str(exc)), "error_code": getattr(exc, "error_code", "BACKUP_SYSTEM_START_FAILED")},
                    env=env,
                )
            status = started.get("backup_system") or backup_system.refresh(env=env)
            operation = started.get("operation") or {}
            operations.append_output(
                operation_id,
                f"백업 저장소 시작 작업을 완료했습니다: {operation.get('status') or status.get('status')}",
                stream="system",
                metadata={"step": "backup registry start", "backup_system": status, "operation_id": operation.get("id")},
                env=env,
            )
        if status.get("status") != "running":
            return self._deploy_failure(
                operation_id,
                "백업 저장소가 실행 상태가 아니어서 스냅샷 이미지를 복원할 수 없습니다.",
                {"status": "error", "backup_system": status},
                env=env,
            )
        return status

    def _login_backup_registry_for_deploy(self, compose_path, operation_id, env=None):
        self._ensure_backup_system_running_for_deploy(operation_id, env=env)
        manager_setup = self._ensure_manager_backup_registry_for_deploy(operation_id, env=env)
        self._ensure_backup_system_running_for_deploy(operation_id, env=env)
        connection = backup_system.connection_config(env=env)
        if not connection.get("configured"):
            return self._deploy_failure(
                operation_id,
                "백업 저장소 로그인 정보를 확인할 수 없습니다.",
                {"status": "error", "message": "backup registry credentials unavailable"},
                env=env,
            )
        registry_config = nodes.backup_registry_config(env=env)
        backup_registries = {
            value
            for value in [registry_config.get("local_registry"), registry_config.get("remote_registry")]
            if value
        }
        registries = [registry for registry in self._compose_image_registries(compose_path) if registry in backup_registries]
        if not registries and registry_config.get("remote_registry"):
            registries = [registry_config["remote_registry"]]

        results = []
        for registry in registries:
            operations.append_output(
                operation_id,
                f"백업 저장소 Docker login을 적용합니다: {registry}",
                stream="system",
                metadata={"step": "backup registry login", "registry": registry},
                env=env,
            )
            result = self._docker_login_for_deploy(registry, connection.get("username") or "admin", connection.get("password") or "", operation_id, env=env)
            self._append_result(operation_id, result, f"backup registry login {registry}", env=env)
            results.append({"registry": registry, "status": result.get("status"), "exit_code": result.get("exit_code")})
            if result.get("status") != "ok":
                return self._deploy_failure(operation_id, "백업 저장소 Docker login에 실패했습니다.", result, env=env)
        return {"manager_setup": manager_setup, "registries": registries, "results": results}

    def _stack_remove_missing(self, result):
        text = _command_text(result).lower()
        return "nothing found" in text or "not found" in text or "no such" in text

    def _wait_stack_removed(self, stack_name, operation_id, env=None):
        for attempt in range(1, 41):
            services = local_executor.run(
                "service.stack.services",
                params={"stack_name": stack_name},
                timeout_seconds=20,
                env=env,
            )
            if services.get("status") != "ok" or not str(services.get("stdout") or "").strip():
                operations.append_output(
                    operation_id,
                    f"stack down confirmed after {attempt} checks",
                    stream="system",
                    metadata={"step": "stack down wait", "attempt": attempt},
                    env=env,
                )
                return {"status": "ok", "attempts": attempt}
            time.sleep(2)
        return {"status": "error", "message": "기존 Docker stack 종료 대기 시간이 초과되었습니다.", "attempts": 40}

    def _remove_stack_before_deploy(self, stack_name, operation_id, env=None):
        operations.append_output(
            operation_id,
            "기존 Docker stack을 내린 뒤 새 Compose로 다시 적용합니다.",
            stream="system",
            metadata={"step": "stack down"},
            env=env,
        )
        result = local_executor.run(
            "service.stack.remove",
            params={"stack_name": stack_name},
            timeout_seconds=120,
            env=env,
        )
        self._append_result(operation_id, result, "stack down", env=env)
        if result.get("status") != "ok" and not self._stack_remove_missing(result):
            return self._deploy_failure(operation_id, "기존 Docker stack을 내릴 수 없습니다.", result, env=env)
        wait = self._wait_stack_removed(stack_name, operation_id, env=env)
        if wait.get("status") != "ok":
            return self._deploy_failure(operation_id, wait.get("message") or "기존 Docker stack 종료를 확인할 수 없습니다.", wait, env=env)
        return {"remove": result, "wait": wait}

    def _deployment_node(self, service, env=None):
        policy = dict(service.get("target_node_policy") or {})
        metadata = dict(service.get("metadata") or {})
        placement = dict(metadata.get("placement") or {})
        selected_id = str(policy.get("node_id") or placement.get("node_id") or "").strip()
        with connect(env=env) as connection:
            with connection.cursor() as cursor:
                if selected_id:
                    cursor.execute("SELECT * FROM nodes WHERE id = %s LIMIT 1", (selected_id,))
                    row = cursor.fetchone()
                    if row is not None:
                        return dict(row)
                try:
                    recommendation = placement_selector.recommend(env=env)
                    selected = recommendation.get("selected") or {}
                    recommended_id = ((selected.get("node") or {}).get("id") or "").strip()
                except Exception:
                    recommended_id = ""
                if recommended_id:
                    cursor.execute("SELECT * FROM nodes WHERE id = %s LIMIT 1", (recommended_id,))
                    row = cursor.fetchone()
                    if row is not None:
                        return dict(row)
                cursor.execute(
                    """
                    SELECT *
                    FROM nodes
                    WHERE is_local_master = true
                    ORDER BY created_at ASC
                    LIMIT 1
                    """
                )
                row = cursor.fetchone()
                if row is not None:
                    return dict(row)
                cursor.execute("SELECT * FROM nodes ORDER BY created_at ASC LIMIT 1")
                row = cursor.fetchone()
                return dict(row) if row is not None else None

    def _deployment_node_summary(self, node):
        if not node:
            return {}
        return {
            "id": str(node.get("id") or ""),
            "name": str(node.get("name") or ""),
            "host": str(node.get("host") or ""),
            "swarm_node_id": str(node.get("swarm_node_id") or ""),
            "is_local_master": bool(node.get("is_local_master")),
        }

    def _apply_stack_placement(self, compose_path, service, operation_id, env=None):
        node = self._deployment_node(service, env=env)
        swarm_node_id = str((node or {}).get("swarm_node_id") or "").strip()
        if not swarm_node_id:
            return {"applied": False, "reason": "node_unavailable"}
        node_summary = self._deployment_node_summary(node)
        compose = yaml.safe_load(compose_path.read_text(encoding="utf-8")) or {}
        services = compose.get("services") or {}
        constraint = f"node.id == {swarm_node_id}"
        changed = False
        for item in services.values():
            if not isinstance(item, dict):
                continue
            deploy = item.setdefault("deploy", {})
            if not isinstance(deploy, dict):
                continue
            placement = deploy.setdefault("placement", {})
            if not isinstance(placement, dict):
                continue
            constraints = placement.setdefault("constraints", [])
            if not isinstance(constraints, list):
                constraints = []
                placement["constraints"] = constraints
            next_constraints = [
                value
                for value in constraints
                if not str(value).strip().startswith("node.id ==")
                and not str(value).strip().startswith("node.hostname ==")
            ]
            if constraint not in next_constraints:
                next_constraints.append(constraint)
            if next_constraints != constraints:
                placement["constraints"] = next_constraints
                changed = True
        if changed:
            compose_path.write_text(yaml.safe_dump(compose, sort_keys=False, allow_unicode=False), encoding="utf-8")
        operations.append_output(
            operation_id,
            f"stack placement: {node_summary.get('name') or node_summary.get('host') or swarm_node_id}",
            stream="system",
            metadata={"step": "stack placement", "node": node_summary, "constraint": constraint, "changed": changed},
            env=env,
        )
        return {"applied": True, "node": node_summary, "constraint": constraint, "changed": changed}

    def deploy(self, payload, env=None):
        payload = dict(payload or {})
        service, compose_path, stack_name = self._prepare_deploy(payload, env=env)
        service_id = service.get("id")
        operation_id = payload.get("operation_id")
        if operation_id:
            operation = operations.transition(
                operation_id,
                "running",
                message="서비스 배포를 시작했습니다.",
                metadata={"service_id": str(service_id), "namespace": service.get("namespace"), "background": True},
                env=env,
            )
        else:
            operation = self._create_deploy_operation(service, stack_name, compose_path, env=env)
        operation_id = operation["id"]
        operations.append_output(
            operation_id,
            "Docker stack 배포를 시작합니다. 이미지 pull 중에는 docker ps에 컨테이너가 보이지 않을 수 있어 Docker 작업 상태를 함께 추적합니다.",
            stream="system",
            metadata={"step": "deploy start", "stack_name": stack_name},
            env=env,
        )

        inspect = local_executor.run(
            "swarm.network.inspect",
            params={"network_name": compose_rules.OVERLAY_NETWORK},
            timeout_seconds=15,
            env=env,
        )
        if inspect.get("status") != "ok":
            ensure = local_executor.run(
                "swarm.network.ensure",
                params={"network_name": compose_rules.OVERLAY_NETWORK},
                timeout_seconds=30,
                env=env,
            )
            self._append_result(operation_id, ensure, "overlay network", env=env)
            if ensure.get("status") != "ok":
                return self._deploy_failure(operation_id, "서비스 네트워크를 준비할 수 없습니다.", ensure, env=env)

        placement = self._apply_stack_placement(compose_path, service, operation_id, env=env)
        if not placement.get("applied") or not placement.get("node"):
            return self._deploy_failure(
                operation_id,
                "배포 서버를 확인할 수 없어 공개 포트 점검을 중단했습니다.",
                {"status": "error", "message": "deployment node unavailable", "placement": placement},
                env=env,
            )
        update_order_adjustments = self._ensure_host_port_update_order(compose_path)
        if update_order_adjustments:
            operations.append_output(
                operation_id,
                f"update order adjusted for host-mode ports: {update_order_adjustments}",
                stream="system",
                metadata={"step": "update order", "adjustments": update_order_adjustments},
                env=env,
            )
        try:
            allocations = service_ports.allocate_file(compose_path, node=placement.get("node"), env=env)
        except Exception as exc:
            return self._deploy_failure(
                operation_id,
                "배포 서버의 공개 포트를 확인할 수 없습니다.",
                {"status": "error", "message": str(exc), "placement": placement},
                env=env,
            )
        if allocations.get("allocations"):
            operations.append_output(
                operation_id,
                f"port allocation: {allocations['allocations']}",
                stream="system",
                metadata={"step": "port allocation"},
                env=env,
            )
        domain_port_updates = self._sync_domain_published_ports(service_id, compose_path, env=env)
        if domain_port_updates:
            operations.append_output(
                operation_id,
                f"domain port mapping: {domain_port_updates}",
                stream="system",
                metadata={"step": "domain port mapping"},
                env=env,
            )
        deploy_adjustments = self._record_deploy_adjustments(
            service_id,
            allocations,
            domain_port_updates,
            update_order_adjustments=update_order_adjustments,
            env=env,
        )

        backup_registry_setup = None
        backup_registry_login = None
        if payload.get("ensure_backup_registry") is True:
            backup_registry_setup = self._ensure_backup_registry_for_deploy(service, operation_id, env=env)
            backup_registry_login = self._login_backup_registry_for_deploy(compose_path, operation_id, env=env)

        stack_recreate = None
        if payload.get("force_recreate") is True:
            stack_recreate = self._remove_stack_before_deploy(stack_name, operation_id, env=env)

        deploy = local_executor.run(
            "service.stack.deploy",
            params={"compose_path": str(compose_path), "stack_name": stack_name},
            timeout_seconds=payload.get("timeout_seconds") or 300,
            env=env,
        )
        self._append_result(operation_id, deploy, "stack deploy", env=env)
        if deploy.get("status") != "ok":
            return self._deploy_failure(operation_id, "서비스 배포에 실패했습니다.", deploy, env=env)

        runtime_wait = self._wait_runtime_ready(
            service_id,
            operation_id,
            timeout_seconds=payload.get("runtime_ready_timeout_seconds") or 600,
            env=env,
        )
        operations.append_output(
            operation_id,
            runtime_wait.get("message") or "runtime readiness checked",
            stream="system" if runtime_wait.get("status") == "ok" else "stderr",
            metadata={"step": "runtime ready", "runtime_wait": runtime_wait},
            env=env,
        )
        if runtime_wait.get("status") != "ok":
            return self._deploy_failure(operation_id, "컨테이너가 실행 상태가 아니어서 nginx와 SSL 적용을 중단했습니다.", runtime_wait, env=env)

        proxy_targets = deploy_targets.sync_domain_proxy_targets(service_id, stack_name, env=env)
        if proxy_targets.get("updated") or proxy_targets.get("skipped") is not True:
            operations.append_output(
                operation_id,
                f"domain proxy target: {proxy_targets}",
                stream="system",
                metadata={"step": "domain proxy target", "proxy_targets": proxy_targets},
                env=env,
            )

        nginx = service_nginx.apply(service_id, env=env)
        for command in nginx.get("commands") or []:
            self._append_result(operation_id, command.get("result") or {}, command.get("step") or "nginx", env=env)
        operations.append_output(
            operation_id,
            nginx.get("message") or "nginx status updated",
            stream="system" if nginx.get("status") in {"ok", "skipped"} else "stderr",
            metadata={"step": "nginx apply", "nginx": nginx},
            env=env,
        )
        if nginx.get("status") == "error":
            return self._deploy_failure(operation_id, "nginx 설정을 적용할 수 없습니다.", nginx, env=env)

        metadata = dict(service.get("metadata") or {})
        metadata["last_deploy"] = {
            "operation_id": operation_id,
            "stack_name": stack_name,
            "nginx": nginx,
            "deploy_adjustments": deploy_adjustments,
            "placement": placement,
            "backup_registry_setup": backup_registry_setup,
            "backup_registry_login": backup_registry_login,
            "stack_recreate": stack_recreate,
        }
        with connect(env=env) as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    UPDATE services
                    SET status = 'deployed',
                        metadata = %s,
                        updated_at = now()
                    WHERE id = %s
                    RETURNING *
                    """,
                    (Jsonb(_serialize(metadata)), service_id),
                )
                service = self._service_row(cursor, service_id)

        runtime_status = None
        try:
            refreshed = self.refresh_deploy_status(service_id, operation_id=operation_id, env=env)
            service = refreshed["service"]
            runtime_status = refreshed["runtime_status"]
            stack_summary = runtime_status.get("stack", {}).get("summary", {})
            container_summary = runtime_status.get("containers", {}).get("summary", {})
            operations.append_output(
                operation_id,
                f"runtime status: stack {stack_summary}, containers {container_summary}",
                stream="system",
                metadata={"step": "runtime status", "runtime_status": runtime_status},
                env=env,
            )
        except Exception as exc:
            operations.append_output(
                operation_id,
                f"runtime status refresh failed: {exc}",
                stream="stderr",
                metadata={"step": "runtime status"},
                env=env,
            )

        ai_verification = None
        if payload.get("start_ai_verification") is True:
            try:
                ai_assistant = wiz.model("struct/ai_assistant")
                ai_verification = ai_assistant.start_runtime_verification(
                    {
                        "service_id": service_id,
                        "source_operation_id": operation_id,
                        "model_ref": payload.get("model_ref") or "auto",
                        "intent": payload.get("ai_verification_intent") or payload.get("intent") or "",
                        "client_runtime_issues": payload.get("client_runtime_issues") if isinstance(payload.get("client_runtime_issues"), dict) else {},
                        "allow_container_terminal_actions": payload.get("allow_container_terminal_actions") is not False,
                        "allow_ssh_command": payload.get("allow_ssh_command") is not False,
                        "apply": payload.get("ai_verify_apply") is not False,
                        "deploy": payload.get("ai_verify_deploy") is not False,
                    },
                    env=env,
                )
                operations.append_output(
                    operation_id,
                    "AI 백그라운드 검증을 시작했습니다.",
                    stream="system",
                    metadata={"step": "ai verification", "operation": ai_verification.get("operation")},
                    env=env,
                )
            except Exception as exc:
                operations.append_output(
                    operation_id,
                    "AI 백그라운드 검증을 시작할 수 없습니다: %s" % exc,
                    stream="stderr",
                    metadata={"step": "ai verification", "error": str(exc)},
                    env=env,
                )

        operation = operations.transition(
            operation_id,
            "succeeded",
            message="서비스 배포를 완료했습니다.",
            result_payload={
                "service_id": service_id,
                "stack_name": stack_name,
                "runtime_status": runtime_status,
                "ai_verification": ai_verification,
                "backup_registry_setup": backup_registry_setup,
                "backup_registry_login": backup_registry_login,
                "stack_recreate": stack_recreate,
            },
            env=env,
        )
        return {"service": service, "operation": operation, "runtime_status": runtime_status, "ai_verification": ai_verification}


Model = ServiceDeployMixin
