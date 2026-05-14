import shutil
import threading
from pathlib import Path


local_executor = wiz.model("struct/local_executor")
operations = wiz.model("struct/operations")
resources = wiz.model("struct/backup_system_resources")
config = wiz.config("docker_infra")


class BackupSystemRuntimeMixin:
    def _masked_result(self, result, secret_values=None):
        masked = dict(result or {})
        for key in ["stdout", "stderr"]:
            text = str(masked.get(key) or "")
            for secret in secret_values or []:
                if secret:
                    text = text.replace(str(secret), "********")
            masked[key] = text
        return masked

    def _failure_message(self, result, secret_values=None):
        masked = self._masked_result(result, secret_values=secret_values)
        text = (masked.get("stderr") or masked.get("stdout") or "").strip()
        if not text:
            return "백업 시스템 명령 실행에 실패했습니다."
        lines = [line.strip() for line in text.splitlines() if line.strip()]
        detail = lines[-1] if lines else text
        return f"백업 시스템 명령 실행에 실패했습니다: {detail[:500]}"

    def _append_operation_output(self, operation_id, message, stream="system", secret_values=None, env=None):
        if not operation_id or not message:
            return
        operations.append_output(operation_id, message, stream=stream, secret_values=secret_values or [], env=env)

    def _set_state(self, status, message=None, env=None):
        current = self.status(env=env)
        storage = self._storage(current["data_path"])
        with self.connect(env=env) as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    UPDATE backup_system_settings
                    SET status = %s,
                        used_bytes = %s,
                        available_bytes = %s,
                        total_bytes = %s,
                        last_error = %s,
                        last_checked_at = now()
                    WHERE singleton_key = 'default'
                    RETURNING *
                    """,
                    (status, storage["used_bytes"], storage["available_bytes"], storage["total_bytes"], message),
                )
                return self._row(cursor.fetchone(), env=env)

    def _run_operation(self, operation_type, command_id, params, secret_values=None, operation=None, env=None):
        if operation is None:
            operation = operations.create(operation_type, target_type="backup_system", target_id="default", requested_payload=params, env=env)
        try:
            if hasattr(local_executor, "run_stream"):
                result = local_executor.run_stream(
                    command_id,
                    params=params,
                    env=env,
                    on_output=lambda stream, text: self._append_operation_output(
                        operation["id"], text, stream=stream, secret_values=secret_values or [], env=env
                    ),
                )
                streamed = True
            else:
                result = local_executor.run(command_id, params=params, env=env)
                streamed = False
        except local_executor.LocalCommandError as exc:
            operation = operations.transition(
                operation["id"],
                "failed",
                message=exc.message,
                result_payload={"error_code": exc.error_code, **exc.extra},
                env=env,
            )
            raise self.BackupSystemError(exc.status_code, exc.message, exc.error_code, operation=operation, **exc.extra)

        if not streamed and result.get("stdout"):
            operations.append_output(operation["id"], result.get("stdout"), stream="stdout", secret_values=secret_values or [], env=env)
        if not streamed and result.get("stderr"):
            operations.append_output(operation["id"], result.get("stderr"), stream="stderr", secret_values=secret_values or [], env=env)
        failed = result.get("status") != "ok"
        message = self._failure_message(result, secret_values=secret_values) if failed else None
        operation = operations.transition(
            operation["id"],
            "failed" if failed else "succeeded",
            message=message,
            result_payload={"status": result.get("status"), "exit_code": result.get("exit_code")},
            env=env,
        )
        if failed:
            raise self.BackupSystemError(409, message, "BACKUP_SYSTEM_COMMAND_FAILED", operation=operation, check=self._masked_result(result, secret_values=secret_values))
        return operation

    def _finish_async_failure(self, operation_id, exc, env=None):
        message = getattr(exc, "message", str(exc))
        result_payload = {"error_code": getattr(exc, "error_code", "BACKUP_SYSTEM_ENABLE_FAILED")}
        try:
            operations.transition(operation_id, "failed", message=message, result_payload=result_payload, env=env)
        except Exception:
            pass

    def enable_async(self, env=None):
        operation = operations.create(
            "backup.harbor.enable",
            target_type="backup_system",
            target_id="default",
            message="백업 시스템 설치를 준비합니다.",
            requested_payload={"background": True},
            metadata={"background": True},
            env=env,
        )

        def worker():
            try:
                self.enable(env=env, operation=operation)
            except Exception as exc:
                self._finish_async_failure(operation["id"], exc, env=env)

        threading.Thread(target=worker, daemon=True).start()
        return {"backup_system": self.status(env=env), "operation": operation}

    def enable(self, env=None, operation=None):
        with self.connect(env=env) as connection:
            with connection.cursor() as cursor:
                row = self._fetch(cursor, decrypt=True, env=env)
        if row is None or not row["enabled"] or not row["admin_password_enc"]:
            payload = {"enabled": True}
            if row is not None and row["data_path"]:
                payload["data_path"] = row["data_path"]
            self.configure(payload, env=env)
            with self.connect(env=env) as connection:
                with connection.cursor() as cursor:
                    row = self._fetch(cursor, decrypt=True, env=env)
        status = self._row(row, env=env)
        admin_password = row["admin_password"]
        if not admin_password:
            raise self.BackupSystemError(409, "백업 시스템 관리자 정보가 준비되지 않았습니다.", "BACKUP_SYSTEM_SECRET_REQUIRED")
        db_password = f"db_{admin_password}"
        try:
            if operation is None:
                operation = operations.create(
                    "backup.harbor.enable",
                    target_type="backup_system",
                    target_id="default",
                    message="백업 시스템 설치를 준비합니다.",
                    requested_payload={"data_path": status["data_path"]},
                    env=env,
                )
            self._append_operation_output(operation["id"], "설치 패키지를 확인합니다.\n", stream="system", env=env)
            installer_dir = resources.ensure_installer(status["data_path"], env=env)
            self._append_operation_output(operation["id"], "Harbor 설정 파일을 생성합니다.\n", stream="system", env=env)
            resources.write_harbor_yml(status["data_path"], admin_password, db_password, env=env)
            command_id = "backup.harbor.install" if not Path(status["compose_path"]).is_file() else "backup.harbor.up"
            params = {"installer_dir": installer_dir} if command_id.endswith("install") else {"compose_path": status["compose_path"]}
            self._append_operation_output(operation["id"], "Harbor installer를 실행합니다.\n", stream="system", env=env)
            operation = self._run_operation("backup.harbor.enable", command_id, params, secret_values=[admin_password, db_password], operation=operation, env=env)
            return {"backup_system": self._set_state("running", None, env=env), "operation": operation}
        except self.BackupSystemError as exc:
            self._set_state("failed", exc.message, env=env)
            raise
        except Exception as exc:
            self._set_state("failed", str(exc), env=env)
            if operation is not None:
                self._finish_async_failure(operation["id"], exc, env=env)
            raise self.BackupSystemError(502, str(exc), "BACKUP_SYSTEM_ENABLE_FAILED")

    def stop(self, env=None):
        status = self.status(env=env)
        if not status["installed"]:
            return {"backup_system": self._set_state("stopped", None, env=env), "operation": None}
        operation = self._run_operation("backup.harbor.stop", "backup.harbor.down", {"compose_path": status["compose_path"]}, env=env)
        return {"backup_system": self._set_state("stopped", None, env=env), "operation": operation}

    def disable(self, env=None):
        status = self.status(env=env)
        operation = None
        if status["installed"]:
            operation = self._run_operation("backup.harbor.disable", "backup.harbor.down", {"compose_path": status["compose_path"]}, env=env)
        backup = self.configure({"enabled": False, "data_path": status["data_path"]}, env=env)
        return {"backup_system": backup, "operation": operation}

    def _assert_resettable_path(self, data_path, env=None):
        root = Path(data_path).expanduser().resolve()
        allowed_root = Path(config.data_dir(env)).expanduser().resolve()
        if root == allowed_root or allowed_root not in root.parents:
            raise self.BackupSystemError(
                400,
                "백업 시스템 기본 데이터 디렉토리 밖의 경로는 화면에서 초기화할 수 없습니다.",
                "BACKUP_RESET_PATH_NOT_ALLOWED",
                data_path=str(root),
            )
        return root

    def reset(self, payload=None, env=None):
        payload = payload or {}
        confirm = str(payload.get("confirm") or "").strip()
        if confirm != "초기화":
            raise self.BackupSystemError(400, "초기화를 진행하려면 확인 문구를 정확히 입력해야 합니다.", "BACKUP_RESET_CONFIRM_REQUIRED")

        status = self.status(env=env)
        operation = operations.create(
            "backup.harbor.reset",
            target_type="backup_system",
            target_id="default",
            requested_payload={"delete_data": bool(payload.get("delete_data", True)), "data_path": status["data_path"]},
            env=env,
        )
        try:
            if status["installed"]:
                self._run_operation("backup.harbor.reset.stop", "backup.harbor.down", {"compose_path": status["compose_path"]}, env=env)
            if bool(payload.get("delete_data", True)):
                root = self._assert_resettable_path(status["data_path"], env=env)
                if root.exists():
                    shutil.rmtree(root)
            with self.connect(env=env) as connection:
                with connection.cursor() as cursor:
                    cursor.execute("DELETE FROM backup_system_settings WHERE singleton_key = 'default'")
            operation = operations.transition(
                operation["id"],
                "succeeded",
                result_payload={"delete_data": bool(payload.get("delete_data", True))},
                env=env,
            )
            return {"backup_system": self.status(env=env), "operation": operation}
        except self.BackupSystemError as exc:
            operations.transition(operation["id"], "failed", message=exc.message, result_payload={"error_code": exc.error_code}, env=env)
            raise
        except Exception as exc:
            operations.transition(operation["id"], "failed", message=str(exc), env=env)
            raise self.BackupSystemError(500, str(exc), "BACKUP_RESET_FAILED")

    def restart(self, env=None):
        status = self.status(env=env)
        if not status["installed"]:
            return self.enable(env=env)
        operation = self._run_operation("backup.harbor.restart", "backup.harbor.restart", {"compose_path": status["compose_path"]}, env=env)
        return {"backup_system": self._set_state("running", None, env=env), "operation": operation}

    def refresh(self, env=None):
        status = self.status(env=env)
        if not status["enabled"]:
            return self._set_state("disabled", None, env=env) if status["id"] else status
        if not status["installed"]:
            if status.get("status") == "failed":
                return self._set_state("failed", status.get("last_error") or "백업 시스템 설치가 완료되지 않았습니다.", env=env)
            return self._set_state("pending_install", None, env=env)
        result = local_executor.run("backup.harbor.ps", params={"compose_path": status["compose_path"]}, env=env)
        if result.get("status") != "ok":
            return self._set_state("failed", result.get("stderr") or result.get("stdout") or "백업 시스템 상태 확인에 실패했습니다.", env=env)
        next_status = "running" if "running" in str(result.get("stdout") or "").lower() else "stopped"
        return self._set_state(next_status, None, env=env)


Model = BackupSystemRuntimeMixin
