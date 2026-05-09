import datetime
import re
import subprocess
from urllib.parse import urlparse


backup_system = wiz.model("struct/backup_system")
harbor = wiz.model("struct/images_harbor")
operations = wiz.model("struct/operations")
shared = wiz.model("struct/services_shared")
ServiceError = shared.ServiceError


def _clean(value):
    return re.sub(r"[^a-z0-9_.-]+", "-", str(value or "").lower()).strip("-") or "image"


def _timestamp():
    return datetime.datetime.utcnow().strftime("%Y%m%d%H%M%S")


def _run(argv, input_text=None, timeout=600):
    return subprocess.run(argv, input=input_text, capture_output=True, text=True, timeout=timeout, check=False)


def _output(result):
    return "\n".join(part for part in [result.stdout, result.stderr] if part)


class ServiceImageBackupRunner:
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
        registry = parsed.netloc or parsed.path
        return {**config, "registry": registry}

    def backup_ref(self, service, backup, env=None):
        config = self._config(env=env)
        repository = _clean((backup.get("metadata") or {}).get("suggested_backup_name") or backup.get("repository"))
        tag = _clean(backup.get("tag") or "latest")
        return f"{config['registry']}/{_clean(service.get('namespace'))}/{repository}:{tag}-{_timestamp()}"

    def execute(self, service, backup, env=None):
        config = self._config(env=env)
        backup_ref = self.backup_ref(service, backup, env=env)
        operation = operations.create(
            "service.image.backup",
            target_type="service",
            target_id=service["id"],
            requested_payload={"service_id": service["id"], "backup_id": backup["id"], "image_ref": backup["image_ref"]},
            metadata={"service_id": service["id"], "namespace": service.get("namespace")},
            env=env,
        )
        secret_values = [config.get("password")]
        try:
            project_names = {item.get("name") for item in harbor.list_projects(env=env)}
            if service["namespace"] not in project_names:
                harbor.create_project(service["namespace"], public=False, env=env)

            self._run_step(operation["id"], ["docker", "image", "inspect", backup["image_ref"]], secret_values, allow_failure=True, env=env)
            inspect = _run(["docker", "image", "inspect", backup["image_ref"]], timeout=30)
            if inspect.returncode != 0:
                self._run_step(operation["id"], ["docker", "pull", backup["image_ref"]], secret_values, timeout=900, env=env)
            self._run_step(operation["id"], ["docker", "tag", backup["image_ref"], backup_ref], secret_values, env=env)
            self._run_step(
                operation["id"],
                ["docker", "login", config["registry"], "-u", config["username"], "--password-stdin"],
                secret_values,
                input_text=f"{config['password']}\n",
                env=env,
            )
            self._run_step(operation["id"], ["docker", "push", backup_ref], secret_values, timeout=1200, env=env)
            operation = operations.transition(operation["id"], "succeeded", result_payload={"backup_ref": backup_ref}, env=env)
            return {"backup_ref": backup_ref, "operation": operation}
        except Exception as exc:
            operations.transition(operation["id"], "failed", message=str(exc), env=env)
            if isinstance(exc, ServiceError):
                raise
            raise ServiceError(502, str(exc), "SERVICE_IMAGE_BACKUP_FAILED")

    def _run_step(self, operation_id, argv, secret_values, input_text=None, timeout=600, allow_failure=False, env=None):
        result = _run(argv, input_text=input_text, timeout=timeout)
        text = f"$ {' '.join(argv)}\n{_output(result)}".strip()
        if text:
            operations.append_output(operation_id, text, stream="stdout" if result.returncode == 0 else "stderr", secret_values=secret_values, env=env)
        if result.returncode != 0 and not allow_failure:
            raise ServiceError(409, f"명령 실행에 실패했습니다: {' '.join(argv[:2])}", "SERVICE_IMAGE_BACKUP_COMMAND_FAILED", exit_code=result.returncode)
        return result


Model = ServiceImageBackupRunner()
