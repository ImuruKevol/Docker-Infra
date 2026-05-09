import shutil
from pathlib import Path


local_executor = wiz.model("struct/local_executor")
operations = wiz.model("struct/operations")
resources = wiz.model("struct/backup_system_resources")
config = wiz.config("docker_infra")


class BackupSystemRuntimeMixin:
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

    def _run_operation(self, operation_type, command_id, params, secret_values=None, env=None):
        operation = operations.create(operation_type, target_type="backup_system", target_id="default", requested_payload=params, env=env)
        result = local_executor.run(command_id, params=params, env=env)
        output = result.get("stdout") or result.get("stderr") or ""
        if output:
            stream = "stdout" if result.get("status") == "ok" else "stderr"
            operations.append_output(operation["id"], output, stream=stream, secret_values=secret_values or [], env=env)
        operation = operations.transition(
            operation["id"],
            "succeeded" if result.get("status") == "ok" else "failed",
            result_payload={"status": result.get("status"), "exit_code": result.get("exit_code")},
            env=env,
        )
        if result.get("status") != "ok":
            raise self.BackupSystemError(409, "백업 시스템 명령 실행에 실패했습니다.", "BACKUP_SYSTEM_COMMAND_FAILED", operation=operation, check=result)
        return operation

    def enable(self, env=None):
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
            installer_dir = resources.ensure_installer(status["data_path"], env=env)
            resources.write_harbor_yml(status["data_path"], admin_password, db_password, env=env)
            command_id = "backup.harbor.install" if not Path(status["compose_path"]).is_file() else "backup.harbor.up"
            params = {"installer_dir": installer_dir} if command_id.endswith("install") else {"compose_path": status["compose_path"]}
            operation = self._run_operation("backup.harbor.enable", command_id, params, secret_values=[admin_password, db_password], env=env)
            return {"backup_system": self._set_state("running", None, env=env), "operation": operation}
        except self.BackupSystemError as exc:
            self._set_state("failed", exc.message, env=env)
            raise
        except Exception as exc:
            self._set_state("failed", str(exc), env=env)
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
            return self._set_state("pending_install", None, env=env)
        result = local_executor.run("backup.harbor.ps", params={"compose_path": status["compose_path"]}, env=env)
        next_status = "running" if result.get("status") == "ok" and "running" in str(result.get("stdout") or "").lower() else "stopped"
        return self._set_state(next_status, None if result.get("status") == "ok" else result.get("stderr"), env=env)


Model = BackupSystemRuntimeMixin
