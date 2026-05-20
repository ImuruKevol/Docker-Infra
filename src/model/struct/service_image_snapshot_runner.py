import datetime
import re
import shlex
import subprocess
from urllib.parse import urlparse


backup_system = wiz.model("struct/backup_system")
harbor = wiz.model("struct/images_harbor")
nodes = wiz.model("struct/nodes")
operations = wiz.model("struct/operations")
shared = wiz.model("struct/services_shared")
ServiceError = shared.ServiceError


def _clean(value):
    return re.sub(r"[^a-z0-9_.-]+", "-", str(value or "").lower()).strip("-") or "snapshot"


def _timestamp():
    return datetime.datetime.utcnow().strftime("%Y%m%d%H%M%S")


def _output(result):
    return "\n".join(part for part in [result.get("stdout"), result.get("stderr")] if part)


def _local_run(argv, timeout=900):
    try:
        done = subprocess.run(argv, capture_output=True, text=True, timeout=timeout, check=False)
        return {"status": "ok" if done.returncode == 0 else "error", "exit_code": done.returncode, "stdout": done.stdout, "stderr": done.stderr}
    except subprocess.TimeoutExpired as exc:
        return {"status": "timeout", "exit_code": None, "stdout": exc.stdout or "", "stderr": exc.stderr or "command timed out"}


class ServiceImageSnapshotRunner:
    ServiceError = ServiceError

    def _config(self, env=None):
        config = backup_system.connection_config(env=env)
        if not config.get("enabled"):
            raise ServiceError(409, "서비스 백업 시스템이 꺼져 있습니다.", "BACKUP_SYSTEM_DISABLED")
        if config.get("status") != "running":
            raise ServiceError(409, "서비스 백업 시스템이 실행 중이 아닙니다.", "BACKUP_SYSTEM_NOT_RUNNING")
        if not config.get("password"):
            raise ServiceError(409, "서비스 백업 시스템 관리자 정보가 없습니다.", "BACKUP_SYSTEM_SECRET_REQUIRED")
        parsed = urlparse(config["harbor_url"])
        return {**config, "registry": parsed.netloc or parsed.path}

    def _compose_service_name(self, item):
        runtime = str(item.get("runtime_service_name") or "")
        namespace = str(item.get("service_namespace") or "")
        prefix = f"{namespace}_"
        if namespace and runtime.startswith(prefix):
            return runtime[len(prefix):]
        return runtime

    def _target_container(self, service, backup, env=None):
        for node_ref in nodes.list(env=env):
            try:
                panel = nodes.live_containers(node_ref["id"], persist=False, env=env)
            except Exception:
                continue
            for item in panel.get("items") or []:
                registered = item.get("registered_service") or {}
                same_service = registered.get("id") == service["id"] or item.get("service_namespace") == service.get("namespace")
                same_compose = self._compose_service_name(item) == backup.get("compose_service")
                if same_service and same_compose and item.get("id"):
                    return {"node": nodes.detail(node_ref["id"], env=env), "container": item}
        raise ServiceError(404, "스냅샷을 만들 실행 중인 서비스 컨테이너를 찾을 수 없습니다.", "SERVICE_SNAPSHOT_CONTAINER_NOT_FOUND")

    def _registry_for_node(self, node, config, env=None):
        return nodes.backup_registry_reference_for_node(node, backup_config=config, env=env)

    def _ensure_registry_for_snapshot_node(self, node, operation_id, env=None):
        try:
            result = nodes.configure_backup_registry_for_node(node["id"], operation_id=operation_id, env=env)
        except Exception as exc:
            raise ServiceError(
                409,
                "스냅샷 이미지를 push할 수 있도록 노드 레지스트리 설정을 적용할 수 없습니다.",
                "SERVICE_IMAGE_SNAPSHOT_REGISTRY_CONFIG_FAILED",
                node_id=node.get("id"),
                message=getattr(exc, "message", str(exc)),
                registry_error_code=getattr(exc, "error_code", "BACKUP_REGISTRY_NODE_CONFIG_FAILED"),
            )
        return {
            "status": result.get("status"),
            "registries": result.get("registries") or [],
        }

    def backup_ref(self, service, backup, node, env=None):
        config = self._config(env=env)
        registry = self._registry_for_node(node, config, env=env)
        service_name = _clean(backup.get("compose_service"))
        return f"{registry}/{_clean(service.get('namespace'))}/snapshot-{service_name}:{_timestamp()}"

    def execute(self, service, backup, pause=True, env=None):
        target = self._target_container(service, backup, env=env)
        node = target["node"]
        container = target["container"]
        config = self._config(env=env)
        operation = operations.create(
            "service.image.snapshot",
            target_type="service",
            target_id=service["id"],
            requested_payload={"service_id": service["id"], "backup_id": backup["id"], "container_id": container["id"], "pause": bool(pause)},
            metadata={"service_id": service["id"], "namespace": service.get("namespace"), "node_id": node["id"]},
            env=env,
        )
        secrets = [config.get("password")]
        try:
            registry_setup = self._ensure_registry_for_snapshot_node(node, operation["id"], env=env)
            target = self._target_container(service, backup, env=env)
            node = target["node"]
            container = target["container"]
            backup_ref = self.backup_ref(service, backup, node, env=env)
            project_names = {item.get("name") for item in harbor.list_projects(env=env)}
            if service["namespace"] not in project_names:
                harbor.create_project(service["namespace"], public=False, env=env)
            self._step(operation["id"], node, ["docker", "commit", f"--pause={str(bool(pause)).lower()}", container["id"], backup_ref], secrets, env=env)
            self._login(operation["id"], node, config, secrets, env=env)
            self._step(operation["id"], node, ["docker", "push", backup_ref], secrets, timeout=1200, env=env)
            cleanup = self._step(operation["id"], node, ["docker", "image", "rm", backup_ref], secrets, timeout=120, allow_failure=True, env=env)
            operation = operations.transition(
                operation["id"],
                "succeeded",
                result_payload={
                    "backup_ref": backup_ref,
                    "container_id": container["id"],
                    "registry_setup": registry_setup,
                    "local_cleanup": {"ref": backup_ref, "removed": cleanup.get("status") == "ok"},
                },
                env=env,
            )
            return {"backup_ref": backup_ref, "operation": operation, "node": node, "container": container}
        except Exception as exc:
            operations.transition(operation["id"], "failed", message=str(exc), env=env)
            if isinstance(exc, ServiceError):
                raise
            raise ServiceError(502, str(exc), "SERVICE_IMAGE_SNAPSHOT_FAILED")

    def _step(self, operation_id, node, argv, secret_values, timeout=900, allow_failure=False, env=None):
        if node.get("is_local_master"):
            result = _local_run(argv, timeout=timeout)
        else:
            result = nodes._run_ssh_command(node, argv, timeout_seconds=timeout, env=env)
        text = f"$ {' '.join(argv)}\n{_output(result)}".strip()
        if text:
            operations.append_output(operation_id, text, stream="stdout" if result.get("status") == "ok" else "stderr", secret_values=secret_values, env=env)
        if result.get("status") != "ok" and not allow_failure:
            raise ServiceError(409, f"스냅샷 명령 실행에 실패했습니다: {' '.join(argv[:2])}", "SERVICE_IMAGE_SNAPSHOT_COMMAND_FAILED", exit_code=result.get("exit_code"))
        return result

    def _login(self, operation_id, node, config, secret_values, env=None):
        registry = self._registry_for_node(node, config, env=env)
        script = "printf %s {password} | docker login {registry} -u {username} --password-stdin".format(
            password=shlex.quote(config["password"]),
            registry=shlex.quote(registry),
            username=shlex.quote(config["username"]),
        )
        return self._step(operation_id, node, ["sh", "-lc", script], secret_values, timeout=120, env=env)


Model = ServiceImageSnapshotRunner()
