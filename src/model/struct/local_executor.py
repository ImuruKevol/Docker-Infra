import datetime
import shlex
import subprocess
import threading
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

    def check(self, target="docker.version", timeout_seconds=None, params=None, env=None):
        return self.run(
            target or "docker.version",
            timeout_seconds=timeout_seconds,
            params=params,
            env=env,
        )

    def run(self, command_id, timeout_seconds=None, params=None, env=None):
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

        return result

    def run_stream(self, command_id, timeout_seconds=None, params=None, on_output=None, env=None):
        spec = self._command_spec(command_id)
        self._assert_allowed(command_id, spec, env=env)
        argv = self._argv(command_id, spec, params or {})
        timeout = _normalize_timeout(timeout_seconds, default=spec.get("default_timeout_seconds", DEFAULT_TIMEOUT_SECONDS))

        stdout_chunks = []
        stderr_chunks = []
        started = time.monotonic()

        def read_pipe(pipe, stream, chunks):
            try:
                for line in iter(pipe.readline, ""):
                    chunks.append(line)
                    if on_output:
                        try:
                            on_output(stream, line)
                        except Exception:
                            pass
            finally:
                try:
                    pipe.close()
                except Exception:
                    pass

        try:
            process = subprocess.Popen(argv, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, bufsize=1)
            stdout_thread = threading.Thread(target=read_pipe, args=(process.stdout, "stdout", stdout_chunks), daemon=True)
            stderr_thread = threading.Thread(target=read_pipe, args=(process.stderr, "stderr", stderr_chunks), daemon=True)
            stdout_thread.start()
            stderr_thread.start()
            timed_out = False
            try:
                exit_code = process.wait(timeout=timeout)
            except subprocess.TimeoutExpired:
                timed_out = True
                process.kill()
                exit_code = process.wait()
                timeout_message = f"command timed out after {timeout}s"
                stderr_chunks.append(timeout_message)
                if on_output:
                    try:
                        on_output("stderr", timeout_message)
                    except Exception:
                        pass
            stdout_thread.join(timeout=2)
            stderr_thread.join(timeout=2)
            duration_ms = int((time.monotonic() - started) * 1000)
            status = "timeout" if timed_out else ("ok" if exit_code == 0 else "error")
            result = _public_result(
                command_id,
                spec,
                argv,
                status,
                exit_code=exit_code,
                stdout="".join(stdout_chunks),
                stderr="".join(stderr_chunks),
                duration_ms=duration_ms,
                timed_out=timed_out,
            )
        except FileNotFoundError as exc:
            duration_ms = int((time.monotonic() - started) * 1000)
            result = _public_result(command_id, spec, argv, "missing", stdout="", stderr=str(exc), duration_ms=duration_ms)
            if on_output:
                try:
                    on_output("stderr", str(exc))
                except Exception:
                    pass

        return result

    def timestamp(self):
        return datetime.datetime.now(datetime.timezone.utc).isoformat().replace("+00:00", "Z")


Model = LocalExecutor()
