import os
from pathlib import Path


config = wiz.config("docker_infra")


class CronFileError(Exception):
    def __init__(self, status_code, message, error_code, **extra):
        super().__init__(message)
        self.status_code = status_code
        self.message = message
        self.error_code = error_code
        self.extra = extra


def _runtime_env(env=None):
    try:
        return config.runtime_env(env)
    except Exception:
        values = {}
        values.update(os.environ)
        if env:
            values.update(env)
        return values


def _safe_name(value, prefix="docker-infra-"):
    raw = str(value or "").strip()
    safe = "".join(ch if ch.isalnum() or ch in {"-", "_"} else "-" for ch in raw)
    safe = "-".join(part for part in safe.split("-") if part)
    if not safe:
        raise CronFileError(400, "cron 파일 이름이 올바르지 않습니다.", "CRON_FILE_NAME_INVALID")
    if not safe.startswith(prefix):
        safe = f"{prefix}{safe}"
    return safe[:180]


class CronFiles:
    CronFileError = CronFileError

    def directory(self, env=None, directory_env=None):
        values = _runtime_env(env)
        raw = ""
        if directory_env:
            raw = str(values.get(directory_env) or "").strip()
        raw = raw or str(values.get("DOCKER_INFRA_CRON_DIR") or "/etc/cron.d").strip()
        path = Path(raw).expanduser()
        return path if path.is_absolute() else Path(config.data_dir(env)) / path

    def user(self, env=None, user_env=None):
        values = _runtime_env(env)
        raw = ""
        if user_env:
            raw = str(values.get(user_env) or "").strip()
        return raw or str(values.get("DOCKER_INFRA_CRON_USER") or "root").strip() or "root"

    def file_path(self, name, env=None, directory_env=None, prefix="docker-infra-"):
        return self.directory(env=env, directory_env=directory_env) / _safe_name(name, prefix=prefix)

    def write(self, name, schedule, command, marker, env=None, directory_env=None, user_env=None, prefix="docker-infra-"):
        cron_dir = self.directory(env=env, directory_env=directory_env)
        cron_user = self.user(env=env, user_env=user_env)
        file_path = cron_dir / _safe_name(name, prefix=prefix)
        schedule = str(schedule or "").strip()
        command = str(command or "").strip()
        marker = str(marker or "docker-infra").strip()
        if len(schedule.split()) != 5:
            raise CronFileError(400, "cron 실행 주기가 올바르지 않습니다.", "CRON_SCHEDULE_INVALID")
        if not command:
            raise CronFileError(400, "cron 실행 명령이 비어 있습니다.", "CRON_COMMAND_REQUIRED")
        content = "\n".join(
            [
                f"# {marker}",
                "SHELL=/bin/sh",
                "PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin",
                f"{schedule} {cron_user} {command} # {marker}",
                "",
            ]
        )
        temp_path = file_path.with_name(f".{file_path.name}.tmp")
        try:
            cron_dir.mkdir(parents=True, exist_ok=True)
            temp_path.write_text(content, encoding="utf-8")
            temp_path.chmod(0o644)
            os.replace(temp_path, file_path)
        except PermissionError as exc:
            raise CronFileError(500, f"cron.d 파일을 저장할 권한이 없습니다: {file_path}", "CRON_FILE_PERMISSION_DENIED", path=str(file_path)) from exc
        except OSError as exc:
            raise CronFileError(500, f"cron.d 파일을 저장할 수 없습니다: {exc}", "CRON_FILE_WRITE_FAILED", path=str(file_path)) from exc
        finally:
            try:
                if temp_path.exists():
                    temp_path.unlink()
            except Exception:
                pass
        return {"path": str(file_path), "user": cron_user}

    def remove(self, name, env=None, directory_env=None, prefix="docker-infra-"):
        file_path = self.file_path(name, env=env, directory_env=directory_env, prefix=prefix)
        try:
            file_path.unlink(missing_ok=True)
        except PermissionError as exc:
            raise CronFileError(500, f"cron.d 파일을 삭제할 권한이 없습니다: {file_path}", "CRON_FILE_PERMISSION_DENIED", path=str(file_path)) from exc
        except OSError as exc:
            raise CronFileError(500, f"cron.d 파일을 삭제할 수 없습니다: {exc}", "CRON_FILE_DELETE_FAILED", path=str(file_path)) from exc
        return {"path": str(file_path), "removed": True}


Model = CronFiles()
