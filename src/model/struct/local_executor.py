import datetime
import shlex
import subprocess
import time


catalog = wiz.model("struct/local_command_catalog")
config = wiz.config("docker_infra")
ALLOWLIST_ENV = config.LOCAL_EXECUTOR_ALLOWLIST_ENV
DEFAULT_TIMEOUT_SECONDS = catalog.DEFAULT_TIMEOUT_SECONDS
MAX_TIMEOUT_SECONDS = catalog.MAX_TIMEOUT_SECONDS
MAX_CAPTURE_CHARS = catalog.MAX_CAPTURE_CHARS
LocalCommandError = catalog.LocalCommandError
COMMAND_SPECS = catalog.COMMAND_SPECS


def _normalize_timeout(timeout_seconds, default=DEFAULT_TIMEOUT_SECONDS):
    if timeout_seconds in (None, ""):
        timeout_seconds = default
    try:
        timeout = int(timeout_seconds)
    except (TypeError, ValueError):
        raise LocalCommandError(400, "timeout_seconds는 정수여야 합니다.", "INVALID_TIMEOUT")
    return max(1, min(timeout, MAX_TIMEOUT_SECONDS))


def _trim(value):
    if value is None:
        return ""
    text = str(value)
    if len(text) <= MAX_CAPTURE_CHARS:
        return text
    return text[:MAX_CAPTURE_CHARS] + "\n[truncated]"


def _allowlist(env=None):
    return set(config.local_executor_allowlist(env))


def _public_result(command_id, spec, argv, status, exit_code=None, stdout="", stderr="", duration_ms=0, timed_out=False):
    return {
        "command_id": command_id,
        "category": spec["category"],
        "command": argv,
        "command_display": shlex.join(argv),
        "destructive": bool(spec.get("destructive")),
        "status": status,
        "exit_code": exit_code,
        "stdout": _trim(stdout),
        "stderr": _trim(stderr),
        "duration_ms": duration_ms,
        "timed_out": timed_out,
    }


class LocalExecutor:
    LocalCommandError = LocalCommandError

    def command_ids(self):
        return sorted(COMMAND_SPECS)

    def _command_spec(self, command_id):
        spec = COMMAND_SPECS.get(command_id)
        if spec is None:
            raise LocalCommandError(404, "지원하지 않는 local command입니다.", "LOCAL_COMMAND_NOT_FOUND")
        return spec

    def _argv(self, command_id, spec, params):
        if params is None:
            params = {}
        if isinstance(params, dict) is False:
            raise LocalCommandError(400, "params는 object여야 합니다.", "INVALID_COMMAND_PARAMS")
        if "factory" in spec:
            return spec["factory"](params)
        return list(spec["argv"])

    def _assert_allowed(self, command_id, spec, env=None):
        if spec.get("destructive") is not True:
            return
        allowlist = _allowlist(env=env)
        if "*" in allowlist or command_id in allowlist:
            return
        raise LocalCommandError(
            403,
            "destructive local command가 allowlist에 없습니다.",
            "LOCAL_COMMAND_NOT_ALLOWLISTED",
            command_id=command_id,
            allowlist_env=ALLOWLIST_ENV,
        )

    def check(self, target="docker.version", timeout_seconds=None, params=None, job_id=None, step_ref=None, env=None):
        return self.run(
            target or "docker.version",
            timeout_seconds=timeout_seconds,
            params=params,
            job_id=job_id,
            step_ref=step_ref,
            env=env,
        )

    def run(self, command_id, timeout_seconds=None, params=None, job_id=None, step_ref=None, env=None):
        spec = self._command_spec(command_id)
        self._assert_allowed(command_id, spec, env=env)
        argv = self._argv(command_id, spec, params or {})
        timeout = _normalize_timeout(timeout_seconds, default=spec.get("default_timeout_seconds", DEFAULT_TIMEOUT_SECONDS))

        started = time.monotonic()
        try:
            completed = subprocess.run(argv, capture_output=True, text=True, timeout=timeout, check=False)
            duration_ms = int((time.monotonic() - started) * 1000)
            status = "ok" if completed.returncode == 0 else "error"
            result = _public_result(
                command_id,
                spec,
                argv,
                status,
                exit_code=completed.returncode,
                stdout=completed.stdout,
                stderr=completed.stderr,
                duration_ms=duration_ms,
            )
        except FileNotFoundError as exc:
            duration_ms = int((time.monotonic() - started) * 1000)
            result = _public_result(
                command_id,
                spec,
                argv,
                "missing",
                stdout="",
                stderr=str(exc),
                duration_ms=duration_ms,
            )
        except subprocess.TimeoutExpired as exc:
            duration_ms = int((time.monotonic() - started) * 1000)
            result = _public_result(
                command_id,
                spec,
                argv,
                "timeout",
                stdout=exc.stdout,
                stderr=exc.stderr or f"command timed out after {timeout}s",
                duration_ms=duration_ms,
                timed_out=True,
            )

        if job_id:
            self.append_result_to_job(result, job_id=job_id, step_ref=step_ref, env=env)
        return result

    def append_result_to_job(self, result, job_id, step_ref=None, env=None):
        jobs = wiz.model("struct/jobs")
        metadata = {
            "command_id": result["command_id"],
            "command": result["command"],
            "status": result["status"],
            "exit_code": result["exit_code"],
            "duration_ms": result["duration_ms"],
        }
        if result["stdout"]:
            self._append_job_log(jobs, job_id, result["stdout"], "stdout", step_ref, metadata, env)
        if result["stderr"]:
            self._append_job_log(jobs, job_id, result["stderr"], "stderr", step_ref, metadata, env)
        self._append_job_log(
            jobs,
            job_id,
            f"local command {result['command_id']} finished with status={result['status']} exit_code={result['exit_code']}",
            "system",
            step_ref,
            metadata,
            env,
        )

    def _append_job_log(self, jobs, job_id, message, stream, step_ref, metadata, env):
        try:
            jobs.append_log(job_id, message, stream=stream, step_ref=step_ref, metadata=metadata, env=env)
        except Exception as exc:
            if hasattr(exc, "status_code"):
                raise LocalCommandError(exc.status_code, exc.message, exc.error_code, **getattr(exc, "extra", {}))
            raise

    def timestamp(self):
        return datetime.datetime.now(datetime.timezone.utc).isoformat().replace("+00:00", "Z")


Model = LocalExecutor()
