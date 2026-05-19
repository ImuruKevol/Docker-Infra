import json
import datetime
import errno
import os
import pty
import re
import select
import shlex
import shutil
import subprocess
import tempfile
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
from pathlib import Path

nodes_model = wiz.model("struct/nodes")
placement_selector = wiz.model("struct/services_placement")
operations = wiz.model("struct/operations")


def _find_project_root():
    explicit = os.environ.get("DOCKER_INFRA_PROJECT_ROOT")
    if explicit:
        candidate = Path(explicit).expanduser().resolve()
        if (candidate / "src" / "model").exists():
            return candidate

    source_file = Path(__file__).resolve()
    for parent in source_file.parents:
        if (parent / "src" / "model").exists() and (parent / "src" / "app").exists():
            return parent

    fallback = Path("/root/docker-infra/project/main")
    if (fallback / "src" / "model").exists():
        return fallback
    return source_file.parents[3]


def _find_workspace_root(project_root):
    explicit = os.environ.get("DOCKER_INFRA_ROOT")
    if explicit:
        candidate = Path(explicit).expanduser().resolve()
        if candidate.exists():
            return candidate

    source_file = Path(__file__).resolve()
    for parent in [project_root] + list(project_root.parents) + list(source_file.parents):
        if (parent / "project").exists() and (parent / "config").exists():
            return parent

    fallback = Path("/root/docker-infra")
    if fallback.exists():
        return fallback
    return project_root.parents[1]


PROJECT_ROOT = _find_project_root()
WORKSPACE_ROOT = _find_workspace_root(PROJECT_ROOT)
PYTHON_BIN = "/opt/conda/envs/docker-infra/bin/python"
MCP_SCRIPT = PROJECT_ROOT / "tools" / "docker_infra_mcp.py"
CODEX_RUNTIME_ROOT = PROJECT_ROOT / ".runtime" / "codex"
CODEX_TIMEOUT_SECONDS = 1200
CODEX_STATUS_TIMEOUT_SECONDS = 15
CODEX_TEST_TIMEOUT_SECONDS = 180
CODEX_DEVICE_LOGIN_START_TIMEOUT_SECONDS = 5
CODEX_NPM_PACKAGE = "@openai/codex"
CODEX_NPM_VIEW_TIMEOUT_SECONDS = 30
CODEX_NPM_INSTALL_TIMEOUT_SECONDS = 900
CODEX_LOGIN_DEFAULT_MODEL = "gpt-5.5"
CODEX_LOGIN_DEFAULT_REASONING_EFFORT = "xhigh"
CODEX_REASONING_EFFORTS = {"low", "medium", "high", "xhigh"}
PROMPT_CONTEXT_CHAR_BUDGET = 70000
PROMPT_CONTEXT_STRING_LIMIT = 12000
PROMPT_CONTEXT_DEEP_STRING_LIMIT = 3000
PROMPT_CONTEXT_LIST_LIMIT = 24
PROMPT_CONTEXT_DEEP_LIST_LIMIT = 8
PROMPT_CONTEXT_OUTPUT_LIMIT = 5
SENSITIVE_CONTEXT_KEY_RE = re.compile(
    r"(api[_-]?key|authorization|bearer|cookie|password|private[_-]?key|secret|token|x-ddns-key)",
    re.I,
)
SYSTEM_EXECUTABLE_SEARCH_PATHS = [
    "/usr/local/bin",
    "/usr/bin",
    "/bin",
    "/usr/local/sbin",
    "/usr/sbin",
    "/sbin",
    "/root/.local/bin",
    "/root/bin",
    "/opt/conda/bin",
    "/root/.cargo/bin",
    "/opt/homebrew/bin",
]
SYSTEM_CODEX_EXECUTABLE_CANDIDATES = [
    "/usr/local/bin/codex",
    "/usr/bin/codex",
    "/bin/codex",
    "~/.local/bin/codex",
    "/root/.local/bin/codex",
    "/root/.npm-global/bin/codex",
    "/opt/homebrew/bin/codex",
]
SYSTEM_NPM_EXECUTABLE_CANDIDATES = [
    "/usr/local/bin/npm",
    "/usr/bin/npm",
    "/bin/npm",
    "/opt/conda/bin/npm",
    "/opt/homebrew/bin/npm",
]
MCP_TOOL_ALLOWLIST = {
    "infra_context",
    "docker_search",
    "docker_image_check",
    "server_list",
    "server_port_check",
    "container_logs",
    "container_action",
    "service_stack_status",
    "dns_lookup",
    "tcp_connect_check",
    "http_probe",
    "browser_probe",
    "server_collect",
    "ssh_command",
}
SERVICE_DRAFT_MCP_TOOLS = [
    "infra_context",
    "docker_search",
    "docker_image_check",
    "server_list",
    "server_port_check",
    "server_collect",
    "ssh_command",
]
RUNTIME_INSPECTION_MCP_TOOLS = [
    "infra_context",
    "server_list",
    "server_port_check",
    "service_stack_status",
    "container_logs",
    "server_collect",
    "dns_lookup",
    "tcp_connect_check",
    "http_probe",
    "browser_probe",
    "ssh_command",
]
RUNTIME_REPAIR_MCP_TOOLS = [*RUNTIME_INSPECTION_MCP_TOOLS, "container_action"]
MCP_TOOL_SCOPES = {
    "service_draft": SERVICE_DRAFT_MCP_TOOLS,
    "service_preflight_repair": SERVICE_DRAFT_MCP_TOOLS,
    "post_deploy_verification": RUNTIME_INSPECTION_MCP_TOOLS,
    "runtime_inspection": RUNTIME_INSPECTION_MCP_TOOLS,
    "runtime_repair": RUNTIME_REPAIR_MCP_TOOLS,
}


class CodexRuntimeError(Exception):
    def __init__(self, status_code, message, error_code="CODEX_RUNTIME_FAILED", details=None):
        super().__init__(message)
        self.status_code = status_code
        self.message = message
        self.error_code = error_code
        self.details = details or {}


def _json_string(value):
    return json.dumps(str(value), ensure_ascii=False)


def _trim(value, limit=20000):
    text = "" if value is None else str(value)
    if len(text) <= limit:
        return text
    return text[:limit] + "\n[truncated]"


def _provider_label(provider_type):
    return {
        "codex": "Codex 로그인",
        "openai": "OpenAI",
        "gemini": "Gemini",
        "ollama": "Ollama",
    }.get(provider_type, provider_type or "AI")


def _utcnow():
    return datetime.datetime.now(datetime.timezone.utc).isoformat().replace("+00:00", "Z")


def _python_executable():
    if Path(PYTHON_BIN).exists():
        return PYTHON_BIN
    return shutil.which("python3") or shutil.which("python") or "python3"


def _path_segments(value):
    return [segment for segment in str(value or "").split(os.pathsep) if segment]


def _dedupe_path_segments(segments):
    seen = set()
    result = []
    for segment in segments:
        normalized = str(Path(segment).expanduser())
        if normalized in seen:
            continue
        seen.add(normalized)
        result.append(normalized)
    return result


def _augmented_path(env=None):
    env = env or os.environ
    return os.pathsep.join(_dedupe_path_segments(_path_segments(env.get("PATH")) + SYSTEM_EXECUTABLE_SEARCH_PATHS))


def _subprocess_env(env=None):
    run_env = dict(os.environ if env is None else env)
    run_env["PATH"] = _augmented_path(run_env)
    return run_env


def _is_executable_file(path):
    try:
        return Path(path).is_file() and os.access(path, os.X_OK)
    except Exception:
        return False


def _dedupe_paths(paths):
    seen = set()
    result = []
    for path in paths:
        resolved = str(Path(path))
        if resolved in seen:
            continue
        seen.add(resolved)
        result.append(Path(path))
    return result


def _toml_string_list(values):
    return "[" + ", ".join(_json_string(value) for value in values) + "]"


class CodexRuntime:
    CodexRuntimeError = CodexRuntimeError

    def __init__(self):
        self._device_login = None
        self._device_login_lock = threading.Lock()

    def mcp_tools_for_scope(self, scope, allow_container_actions=False, allow_ssh_command=True):
        tools = list(MCP_TOOL_SCOPES.get(str(scope or ""), SERVICE_DRAFT_MCP_TOOLS))
        result = []
        for tool in tools:
            if tool == "container_action" and not allow_container_actions:
                continue
            if tool == "ssh_command" and not allow_ssh_command:
                continue
            if tool in MCP_TOOL_ALLOWLIST and tool not in result:
                result.append(tool)
        return result or ["infra_context"]

    def status(self, config=None):
        config = self._normalize_codex_config(config or {})
        system = self._system_codex_status()
        active = system
        login = self._codex_login_status(active.get("executable"), config)
        return {
            "checked_at": _utcnow(),
            "enabled": config["enabled"],
            "model": config["model"],
            "reasoning_effort": config["reasoning_effort"],
            "cli_mode": "system",
            "codex_home": config["codex_home"],
            "active": {
                "executable": active.get("executable") or "",
                "source": "system",
                "version": active.get("version") or "",
                "available": bool(active.get("available")),
            },
            "system": system,
            "login": login,
        }

    def test_login(self, config=None, prompt=None, env=None):
        config = self._normalize_codex_config(config or {})
        provider = {
            "type": "codex",
            "label": "Codex 로그인",
            "model": config["model"],
            "reasoning_effort": config["reasoning_effort"],
            "cli_mode": config["cli_mode"],
            "codex_home": config["codex_home"],
            "timeout_seconds": CODEX_TEST_TIMEOUT_SECONDS,
        }
        system = (
            "Return one compact JSON object. Do not use markdown fences. "
            "The object must include ok=true, engine, model, and reasoning_effort."
        )
        context = {
            "kind": "codex_login_test",
            "operator_prompt": prompt
            or "Confirm this Docker Infra Codex login execution path with a short JSON response.",
        }
        result = self.complete_json(provider, system, context, env=env)
        return {
            "ok": True,
            "checked_at": _utcnow(),
            "text": result.get("text") or "",
            "metadata": result.get("metadata") or {},
            "status": self.status(config),
        }

    def cli_update_status(self, config=None, env=None):
        config = self._normalize_codex_config(config or {})
        codex_status = self.status(config)
        npm = self._npm_status(env=env)
        latest_version = self._npm_latest_version(npm.get("executable"), env=env)
        active = codex_status.get("active") or {}
        current_raw = active.get("version") or ""
        current_version = self._version_number(current_raw)
        update_available = bool(
            latest_version
            and (
                not current_version
                or self._compare_versions(current_version, latest_version) < 0
            )
        )
        return {
            "checked_at": _utcnow(),
            "package_name": CODEX_NPM_PACKAGE,
            "current_version": current_version,
            "current_version_raw": current_raw,
            "latest_version": latest_version,
            "update_available": update_available,
            "npm": npm,
            "codex_status": codex_status,
            "commands": {
                "check": f"npm view {CODEX_NPM_PACKAGE} version --json",
                "upgrade": f"npm install -g {CODEX_NPM_PACKAGE}@latest",
            },
        }

    def upgrade_cli_async(self, config=None, env=None):
        config = self._normalize_codex_config(config or {})
        update = self.cli_update_status(config, env=env)
        operation = operations.create(
            "codex.cli.upgrade",
            target_type="system",
            target_id="codex-cli",
            message="Codex CLI 업그레이드를 시작합니다.",
            requested_payload={
                "package_name": CODEX_NPM_PACKAGE,
                "current_version": update.get("current_version"),
                "latest_version": update.get("latest_version"),
                "command": update.get("commands", {}).get("upgrade"),
            },
            metadata={"background": True, "package_name": CODEX_NPM_PACKAGE},
            env=env,
        )

        def worker():
            try:
                self._run_cli_upgrade_operation(operation["id"], config, update, env=env)
            except Exception as exc:
                self._finish_cli_upgrade_failure(operation["id"], exc, env=env)

        threading.Thread(target=worker, daemon=True).start()
        return {"operation": operation, "update": update}

    def _run_cli_upgrade_operation(self, operation_id, config, before, env=None):
        npm_executable = ((before or {}).get("npm") or {}).get("executable")
        if not npm_executable or not _is_executable_file(npm_executable):
            raise CodexRuntimeError(
                503,
                "npm 실행 파일을 찾을 수 없습니다.",
                "CODEX_NPM_EXECUTABLE_NOT_FOUND",
                {"npm": before.get("npm") if isinstance(before, dict) else {}},
            )

        current = before.get("current_version") or "미설치"
        latest = before.get("latest_version") or "확인 실패"
        self._append_cli_upgrade_output(
            operation_id,
            f"공식 Codex CLI npm 패키지: {CODEX_NPM_PACKAGE}\n현재 버전: {current}\n최신 버전: {latest}\n",
            env=env,
        )
        command = [npm_executable, "install", "-g", f"{CODEX_NPM_PACKAGE}@latest"]
        result = self._run_logged_command(
            operation_id,
            command,
            timeout=CODEX_NPM_INSTALL_TIMEOUT_SECONDS,
            env=env,
        )
        after_status = self.status(config)
        after_active = after_status.get("active") or {}
        after_raw = after_active.get("version") or ""
        after_version = self._version_number(after_raw)
        after = {
            **before,
            "checked_at": _utcnow(),
            "current_version": after_version,
            "current_version_raw": after_raw,
            "update_available": bool(
                before.get("latest_version")
                and (
                    not after_version
                    or self._compare_versions(after_version, before.get("latest_version")) < 0
                )
            ),
            "codex_status": after_status,
        }
        result_payload = {
            "ok": result.get("exit_code") == 0,
            "exit_code": result.get("exit_code"),
            "timed_out": bool(result.get("timed_out")),
            "package_name": CODEX_NPM_PACKAGE,
            "before": before,
            "after": after,
        }
        if result.get("exit_code") != 0:
            message = self._npm_failure_message(result)
            operations.transition(operation_id, "failed", message=message, result_payload=result_payload, env=env)
            return
        operations.transition(
            operation_id,
            "succeeded",
            message="Codex CLI 업그레이드를 완료했습니다.",
            result_payload=result_payload,
            env=env,
        )

    def _finish_cli_upgrade_failure(self, operation_id, exc, env=None):
        message = getattr(exc, "message", str(exc))
        result_payload = {
            "ok": False,
            "error_code": getattr(exc, "error_code", "CODEX_CLI_UPGRADE_FAILED"),
        }
        details = getattr(exc, "details", None)
        if isinstance(details, dict):
            result_payload.update(details)
        try:
            operations.append_output(operation_id, message + "\n", stream="stderr", env=env)
            operations.transition(operation_id, "failed", message=message, result_payload=result_payload, env=env)
        except Exception:
            pass

    def start_device_login(self, config=None):
        config = self._normalize_codex_config(config or {})
        executable = self._codex_login_executable(config)
        command = [executable, "login", "--device-auth"]
        deduplicated_public = None
        with self._device_login_lock:
            current = self._device_login
            if current and self._device_login_running(current):
                deduplicated_public = self._device_login_public(current)
            if deduplicated_public is None:
                self._device_login = None
        if deduplicated_public is not None:
            return {"device_login": deduplicated_public, "codex_status": self.status(config), "deduplicated": True}

        with self._device_login_lock:
            session = {
                "id": str(uuid.uuid4()),
                "status": "starting",
                "started_at": _utcnow(),
                "finished_at": None,
                "verification_uri": "",
                "user_code": "",
                "expires_in_seconds": 900,
                "message": "Codex device 로그인을 시작합니다.",
                "output": [],
                "exit_code": None,
                "command": "codex login --device-auth",
            }
            master_fd = None
            slave_fd = None
            try:
                master_fd, slave_fd = pty.openpty()
                process = subprocess.Popen(
                    command,
                    stdin=slave_fd,
                    stdout=slave_fd,
                    stderr=slave_fd,
                    close_fds=True,
                    env=self._codex_env(config),
                )
            except Exception as exc:
                for fd in [master_fd, slave_fd]:
                    if fd is not None:
                        try:
                            os.close(fd)
                        except OSError:
                            pass
                raise CodexRuntimeError(
                    502,
                    "Codex device 로그인을 시작할 수 없습니다: %s" % exc,
                    "CODEX_DEVICE_LOGIN_START_FAILED",
                    {"command": command},
                )
            finally:
                if slave_fd is not None:
                    try:
                        os.close(slave_fd)
                    except OSError:
                        pass
            session["process"] = process
            session["pty_master_fd"] = master_fd
            self._device_login = session
            threading.Thread(target=self._read_device_login_output, args=(session,), daemon=True).start()

        deadline = time.time() + CODEX_DEVICE_LOGIN_START_TIMEOUT_SECONDS
        while time.time() < deadline:
            with self._device_login_lock:
                current = self._device_login_public(self._device_login) if self._device_login else {}
            if current.get("user_code") or current.get("status") in {"failed", "succeeded"}:
                break
            time.sleep(0.1)
        return self.device_login_status(config)

    def device_login_status(self, config=None):
        config = self._normalize_codex_config(config or {})
        with self._device_login_lock:
            session = self._device_login
            if session:
                self._refresh_device_login_locked(session)
                public = self._device_login_public(session)
            else:
                public = None
        codex_status = self.status(config)
        if public and (codex_status.get("login") or {}).get("logged_in") and public.get("status") in {"starting", "waiting_for_user"}:
            with self._device_login_lock:
                session = self._device_login
                if session and session.get("id") == public.get("id"):
                    session["status"] = "succeeded"
                    session["message"] = "Codex 로그인이 완료되었습니다."
                    public = self._device_login_public(session)
        return {"device_login": public, "codex_status": codex_status}

    def cancel_device_login(self, config=None):
        config = self._normalize_codex_config(config or {})
        with self._device_login_lock:
            session = self._device_login
            if session and self._device_login_running(session):
                try:
                    session["process"].terminate()
                except Exception:
                    pass
                session["status"] = "canceled"
                session["message"] = "Codex device 로그인을 취소했습니다."
                session["finished_at"] = _utcnow()
            public = self._device_login_public(session) if session else None
        return {"device_login": public, "codex_status": self.status(config)}

    def _device_login_running(self, session):
        process = (session or {}).get("process")
        return bool(process and process.poll() is None)

    def _read_device_login_output(self, session):
        process = session.get("process")
        if not process:
            return
        master_fd = session.get("pty_master_fd")
        if master_fd is not None:
            self._read_device_login_pty(session, process, master_fd)
        elif process.stdout:
            self._read_device_login_pipe(session, process)
        exit_code = process.wait()
        with self._device_login_lock:
            if self._device_login and self._device_login.get("id") == session.get("id"):
                session["exit_code"] = exit_code
                session["finished_at"] = _utcnow()
                if session.get("status") != "canceled":
                    session["status"] = "succeeded" if exit_code == 0 else "failed"
                    session["message"] = "Codex 로그인이 완료되었습니다." if exit_code == 0 else "Codex device 로그인이 종료되었습니다."

    def _read_device_login_pipe(self, session, process):
        try:
            for line in process.stdout:
                self._append_device_login_output(session, line)
        except Exception as exc:
            self._append_device_login_output(session, "Codex device 로그인 출력 수집 오류: %s" % exc)

    def _read_device_login_pty(self, session, process, master_fd):
        buffer = ""
        try:
            while True:
                timeout = 0 if process.poll() is not None else 0.2
                ready, _, _ = select.select([master_fd], [], [], timeout)
                if not ready:
                    if process.poll() is not None:
                        break
                    continue
                try:
                    chunk = os.read(master_fd, 4096)
                except OSError as exc:
                    if exc.errno in {errno.EIO, errno.EBADF}:
                        break
                    raise
                if not chunk:
                    break
                buffer += chunk.decode("utf-8", "replace")
                lines = buffer.replace("\r", "\n").split("\n")
                buffer = lines.pop() or ""
                for line in lines:
                    self._append_device_login_output(session, line)
        except Exception as exc:
            self._append_device_login_output(session, "Codex device 로그인 출력 수집 오류: %s" % exc)
        finally:
            if buffer.strip():
                self._append_device_login_output(session, buffer)
            try:
                os.close(master_fd)
            except OSError:
                pass

    def _append_device_login_output(self, session, line):
        text = re.sub(r"\x1b\[[0-?]*[ -/]*[@-~]", "", str(line or "")).rstrip()
        if not text:
            return
        with self._device_login_lock:
            if self._device_login and self._device_login.get("id") != session.get("id"):
                return
            output = session.setdefault("output", [])
            output.append(text)
            session["output"] = output[-80:]
            url_match = re.search(r"https://\S+", text)
            if url_match:
                session["verification_uri"] = url_match.group(0).rstrip(".,)")
            code_match = re.search(r"\b[A-Z0-9]{4,}-[A-Z0-9]{4,}\b", text)
            if code_match:
                session["user_code"] = code_match.group(0)
            if session.get("user_code") or session.get("verification_uri"):
                if session.get("status") == "starting":
                    session["status"] = "waiting_for_user"
                session["message"] = "브라우저에서 Codex device 로그인을 완료해주세요."

    def _refresh_device_login_locked(self, session):
        if not session:
            return
        process = session.get("process")
        if not process:
            return
        exit_code = process.poll()
        if exit_code is None:
            return
        session["exit_code"] = exit_code
        if not session.get("finished_at"):
            session["finished_at"] = _utcnow()
        if session.get("status") in {"starting", "waiting_for_user"}:
            session["status"] = "succeeded" if exit_code == 0 else "failed"
            session["message"] = "Codex 로그인이 완료되었습니다." if exit_code == 0 else "Codex device 로그인이 종료되었습니다."

    def _device_login_public(self, session):
        if not session:
            return None
        return {
            "id": session.get("id"),
            "status": session.get("status"),
            "started_at": session.get("started_at"),
            "finished_at": session.get("finished_at"),
            "verification_uri": session.get("verification_uri") or "https://auth.openai.com/codex/device",
            "user_code": session.get("user_code") or "",
            "expires_in_seconds": session.get("expires_in_seconds") or 900,
            "message": session.get("message") or "",
            "exit_code": session.get("exit_code"),
            "command": session.get("command") or "codex login --device-auth",
            "output": (session.get("output") or [])[-20:],
        }

    def _normalize_codex_config(self, config):
        config = dict(config or {})
        model = str(config.get("model") or CODEX_LOGIN_DEFAULT_MODEL).strip() or CODEX_LOGIN_DEFAULT_MODEL
        reasoning_effort = str(config.get("reasoning_effort") or CODEX_LOGIN_DEFAULT_REASONING_EFFORT).strip().lower()
        if reasoning_effort not in CODEX_REASONING_EFFORTS:
            reasoning_effort = CODEX_LOGIN_DEFAULT_REASONING_EFFORT
        codex_home = str(config.get("codex_home") or "").strip()
        return {
            "enabled": self._as_bool(config.get("enabled")),
            "cli_mode": "system",
            "model": model,
            "reasoning_effort": reasoning_effort,
            "codex_home": codex_home,
        }

    def _as_bool(self, value):
        if value is None:
            return False
        if isinstance(value, bool):
            return value
        return str(value).strip().lower() in {"1", "true", "yes", "on"}

    def _system_codex_executable(self):
        explicit = os.environ.get("DOCKER_INFRA_SYSTEM_CODEX_BIN")
        if explicit:
            candidate = Path(explicit).expanduser()
            if _is_executable_file(candidate):
                return str(candidate)
        path_executable = shutil.which("codex", path=_augmented_path())
        if path_executable and _is_executable_file(path_executable):
            return path_executable
        for candidate_path in SYSTEM_CODEX_EXECUTABLE_CANDIDATES:
            candidate = Path(candidate_path).expanduser()
            if _is_executable_file(candidate):
                return str(candidate)
        return ""

    def _npm_executable(self):
        explicit = os.environ.get("DOCKER_INFRA_NPM_BIN")
        if explicit:
            candidate = Path(explicit).expanduser()
            if _is_executable_file(candidate):
                return str(candidate)
        path_executable = shutil.which("npm", path=_augmented_path())
        if path_executable and _is_executable_file(path_executable):
            return path_executable
        for candidate_path in SYSTEM_NPM_EXECUTABLE_CANDIDATES:
            candidate = Path(candidate_path).expanduser()
            if _is_executable_file(candidate):
                return str(candidate)
        return ""

    def _npm_status(self, env=None):
        executable = self._npm_executable()
        available = bool(executable and _is_executable_file(executable))
        version = ""
        if available:
            result = self._command_result([executable, "--version"], env=env, timeout=CODEX_STATUS_TIMEOUT_SECONDS)
            if result.get("exit_code") == 0:
                version = (result.get("stdout") or "").strip()
        return {
            "executable": executable or "",
            "available": available,
            "version": version,
        }

    def _npm_latest_version(self, npm_executable=None, env=None):
        executable = npm_executable or self._npm_executable()
        if not executable or not _is_executable_file(executable):
            raise CodexRuntimeError(
                503,
                "npm 실행 파일을 찾을 수 없습니다.",
                "CODEX_NPM_EXECUTABLE_NOT_FOUND",
                {"npm_executable": executable or ""},
            )
        result = self._command_result(
            [executable, "view", CODEX_NPM_PACKAGE, "version", "--json"],
            env=env,
            timeout=CODEX_NPM_VIEW_TIMEOUT_SECONDS,
        )
        if result.get("exit_code") != 0:
            raise CodexRuntimeError(
                502,
                "npm에서 Codex CLI 최신 버전을 확인할 수 없습니다.",
                "CODEX_NPM_VIEW_FAILED",
                {"npm": self._safe_command_result(result)},
            )
        latest = self._version_number(self._npm_json_stdout(result.get("stdout")))
        if not latest:
            raise CodexRuntimeError(
                502,
                "npm 최신 버전 응답을 해석할 수 없습니다.",
                "CODEX_NPM_VERSION_PARSE_FAILED",
                {"npm": self._safe_command_result(result)},
            )
        return latest

    def _codex_login_executable(self, config):
        config = self._normalize_codex_config(config or {})
        executable = self._system_codex_executable()
        if executable and _is_executable_file(executable):
            return executable
        raise CodexRuntimeError(
            503,
            "로그인 세션을 사용할 Codex CLI를 찾을 수 없습니다. /usr/local/bin/codex 또는 DOCKER_INFRA_SYSTEM_CODEX_BIN을 확인하세요.",
            "CODEX_LOGIN_EXECUTABLE_NOT_FOUND",
            {"path_codex": executable},
        )

    def _safe_command_result(self, result):
        return {
            "exit_code": result.get("exit_code"),
            "timeout": bool(result.get("timeout") or result.get("timed_out")),
            "stdout": _trim(result.get("stdout"), 1000),
            "stderr": _trim(result.get("stderr") or result.get("error"), 1000),
        }

    def _command_result(self, command, env=None, timeout=CODEX_STATUS_TIMEOUT_SECONDS):
        try:
            run_env = _subprocess_env(env)
            completed = subprocess.run(
                command,
                capture_output=True,
                text=True,
                timeout=timeout,
                check=False,
                env=run_env,
            )
            return {
                "exit_code": completed.returncode,
                "stdout": _trim(completed.stdout, 2000),
                "stderr": _trim(completed.stderr, 2000),
            }
        except subprocess.TimeoutExpired as exc:
            return {
                "exit_code": None,
                "timeout": True,
                "stdout": _trim(exc.stdout, 2000),
                "stderr": _trim(exc.stderr, 2000),
            }
        except Exception as exc:
            return {"exit_code": None, "error": str(exc), "stdout": "", "stderr": ""}

    def _run_logged_command(self, operation_id, command, timeout=CODEX_STATUS_TIMEOUT_SECONDS, env=None):
        started = time.monotonic()
        self._append_cli_upgrade_output(operation_id, "$ " + shlex.join(command) + "\n", env=env)
        try:
            process = subprocess.Popen(
                command,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                bufsize=1,
                env=_subprocess_env(env),
            )
        except Exception as exc:
            return {
                "exit_code": None,
                "stdout": "",
                "stderr": str(exc),
                "duration_ms": int((time.monotonic() - started) * 1000),
            }

        chunks = {"stdout": [], "stderr": []}

        def consume(pipe, stream):
            try:
                for line in iter(pipe.readline, ""):
                    chunks[stream].append(line)
                    self._append_cli_upgrade_output(operation_id, line, stream=stream, env=env)
            finally:
                try:
                    pipe.close()
                except Exception:
                    pass

        threads = [
            threading.Thread(target=consume, args=(process.stdout, "stdout"), daemon=True),
            threading.Thread(target=consume, args=(process.stderr, "stderr"), daemon=True),
        ]
        for thread in threads:
            thread.start()

        timed_out = False
        try:
            exit_code = process.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            timed_out = True
            process.kill()
            exit_code = process.wait()
            timeout_message = f"npm install timed out after {timeout}s\n"
            chunks["stderr"].append(timeout_message)
            self._append_cli_upgrade_output(operation_id, timeout_message, stream="stderr", env=env)

        for thread in threads:
            thread.join(timeout=2)
        return {
            "exit_code": exit_code,
            "stdout": _trim("".join(chunks["stdout"]), 20000),
            "stderr": _trim("".join(chunks["stderr"]), 20000),
            "duration_ms": int((time.monotonic() - started) * 1000),
            "timed_out": timed_out,
        }

    def _append_cli_upgrade_output(self, operation_id, message, stream="system", env=None):
        if not operation_id or not message:
            return
        operations.append_output(operation_id, message, stream=stream, env=env)

    def _npm_json_stdout(self, stdout):
        text = str(stdout or "").strip()
        if not text:
            return ""
        try:
            value = json.loads(text)
            if isinstance(value, str):
                return value
        except Exception:
            pass
        return text.strip().strip('"').strip("'")

    def _version_number(self, value):
        match = re.search(r"\b\d+\.\d+\.\d+(?:[-+][0-9A-Za-z.-]+)?\b", str(value or ""))
        return match.group(0) if match else ""

    def _version_parts(self, value):
        version = self._version_number(value)
        if not version:
            return None
        core = version.split("-", 1)[0].split("+", 1)[0]
        try:
            return tuple(int(part) for part in core.split(".")[:3])
        except ValueError:
            return None

    def _compare_versions(self, left, right):
        left_parts = self._version_parts(left)
        right_parts = self._version_parts(right)
        if not left_parts or not right_parts:
            return 0
        if left_parts < right_parts:
            return -1
        if left_parts > right_parts:
            return 1
        return 0

    def _npm_failure_message(self, result):
        if result.get("timed_out"):
            return "Codex CLI 업그레이드 시간이 초과되었습니다."
        text = (result.get("stderr") or result.get("stdout") or "").strip()
        if not text:
            return "Codex CLI 업그레이드 명령이 실패했습니다."
        lines = [line.strip() for line in text.splitlines() if line.strip()]
        return "Codex CLI 업그레이드 명령이 실패했습니다: " + (lines[-1] if lines else text)[:500]

    def _version_for(self, executable):
        if not executable:
            return ""
        result = self._command_result([executable, "--version"])
        if result.get("exit_code") == 0:
            return (result.get("stdout") or "").strip()
        return ""

    def _system_codex_status(self):
        executable = self._system_codex_executable()
        available = bool(executable and _is_executable_file(executable))
        return {
            "source": "system",
            "executable": executable or "",
            "available": available,
            "version": self._version_for(executable) if available else "",
        }

    def _codex_env(self, config):
        run_env = _subprocess_env()
        codex_home = str((config or {}).get("codex_home") or "").strip()
        if codex_home:
            run_env["CODEX_HOME"] = str(Path(codex_home).expanduser())
        elif not run_env.get("CODEX_HOME"):
            default_home = self._default_codex_home(run_env)
            if default_home:
                run_env["CODEX_HOME"] = default_home
        return run_env

    def _default_codex_home(self, env):
        candidates = []
        if env.get("HOME"):
            candidates.append(Path(env["HOME"]).expanduser() / ".codex")
        candidates.append(Path("/root/.codex"))
        for candidate in _dedupe_paths(candidates):
            if (candidate / "auth.json").is_file():
                return str(candidate)
        return ""

    def _codex_login_status(self, executable, config):
        if not executable or not _is_executable_file(executable):
            return {
                "status": "missing",
                "logged_in": False,
                "message": "Codex CLI 실행 파일을 찾을 수 없습니다.",
                "exit_code": None,
            }
        result = self._command_result(
            [executable, "login", "status"],
            env=self._codex_env(config),
            timeout=CODEX_STATUS_TIMEOUT_SECONDS,
        )
        output = ((result.get("stdout") or "") + "\n" + (result.get("stderr") or "")).strip()
        lowered = output.lower()
        logged_in = result.get("exit_code") == 0 and "logged in" in lowered and "not logged" not in lowered
        return {
            "status": "ok" if logged_in else "not_logged_in",
            "logged_in": logged_in,
            "message": output or ("로그인됨" if logged_in else "로그인 상태를 확인할 수 없습니다."),
            "exit_code": result.get("exit_code"),
            "checked_at": _utcnow(),
        }

    def complete_json(self, provider, system, context, env=None):
        provider = self._normalize_provider(provider or {})
        request_context = context if isinstance(context, dict) else {}
        mcp_enabled_tools = self._enabled_mcp_tools(request_context)
        prompt_context = self._prompt_context(request_context, mcp_enabled_tools)
        CODEX_RUNTIME_ROOT.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(prefix="run-", dir=str(CODEX_RUNTIME_ROOT)) as runtime_home:
            runtime_home_path = Path(runtime_home)
            mcp_context_path = runtime_home_path / "docker-infra-mcp-context.json"
            mcp_request_context = dict(request_context)
            mcp_request_context["mcp_enabled_tools"] = mcp_enabled_tools
            mcp_request_context["ai_request_summary"] = prompt_context
            mcp_context = self._mcp_context(env=env, request_context=mcp_request_context)
            last_message_path = runtime_home_path / "last-message.txt"
            if provider["type"] == "codex":
                mcp_context_path.write_text(
                    json.dumps(mcp_context, ensure_ascii=False),
                    encoding="utf-8",
                )
            else:
                prompt_context = self._direct_api_prompt_context(prompt_context, mcp_context)
            prompt = self._prompt(system, prompt_context, provider, mcp_enabled_tools)
            if provider["type"] == "codex":
                result = self._run_codex(
                    provider,
                    runtime_home_path,
                    last_message_path,
                    prompt,
                    mcp_context_path,
                    mcp_enabled_tools,
                )
                engine = "codex"
                cli_mode = provider.get("cli_mode") or "system"
            else:
                result = self._run_direct_api(provider, prompt)
                engine = "direct_api"
                cli_mode = "api"
            metadata = {
                "engine": engine,
                "provider": provider["type"],
                "provider_id": provider["provider_id"],
                "provider_label": _provider_label(provider["type"]),
                "model": provider["model"],
                "reasoning_effort": provider.get("reasoning_effort") or "",
                "cli_mode": cli_mode,
                "executable": result.get("executable") or "",
                "api_endpoint": result.get("api_endpoint") or "",
                "codex_exit_code": result["exit_code"],
            }
            return {"text": result["text"], "metadata": metadata}

    def _normalize_provider(self, provider):
        provider = dict(provider or {})
        provider_type = provider.get("type")
        if provider_type not in {"codex", "openai", "gemini", "ollama"}:
            raise CodexRuntimeError(400, "Codex에서 지원하지 않는 AI provider입니다.", "CODEX_PROVIDER_NOT_SUPPORTED")

        model = provider.get("model")
        if not model:
            raise CodexRuntimeError(400, "Codex 실행에 사용할 모델이 없습니다.", "CODEX_MODEL_REQUIRED")

        if provider_type == "codex":
            config = self._normalize_codex_config(provider)
            provider.update(
                {
                    "provider_id": "codex-login",
                    "provider_name": "Codex Login",
                    "model": config["model"],
                    "reasoning_effort": config["reasoning_effort"],
                    "cli_mode": config["cli_mode"],
                    "codex_home": config["codex_home"],
                    "env_key": None,
                    "env_value": None,
                }
            )
            return provider

        if provider_type == "openai":
            token = provider.get("token") or ""
            if not token:
                raise CodexRuntimeError(400, "OpenAI API Token이 필요합니다.", "CODEX_PROVIDER_TOKEN_REQUIRED")
            provider.update(
                {
                    "provider_id": "docker-infra-openai",
                    "provider_name": "Docker Infra OpenAI",
                    "model": str(model),
                    "base_url": self._openai_base_url(provider.get("base_url") or "https://api.openai.com/v1"),
                    "env_key": "OPENAI_API_KEY",
                    "env_value": token,
                }
            )
            return provider

        if provider_type == "gemini":
            token = provider.get("token") or ""
            if not token:
                raise CodexRuntimeError(400, "Gemini API Token이 필요합니다.", "CODEX_PROVIDER_TOKEN_REQUIRED")
            api_version = provider.get("api_version") or "v1beta"
            provider.update(
                {
                    "provider_id": "docker-infra-gemini",
                    "provider_name": "Gemini",
                    "model": str(model).replace("models/", "", 1),
                    "api_version": api_version.strip("/"),
                    "base_url": "https://generativelanguage.googleapis.com/%s" % api_version.strip("/"),
                    "env_key": "GEMINI_API_KEY",
                    "env_value": token,
                }
            )
            return provider

        provider.update(
            {
                "provider_id": "docker-infra-ollama",
                "provider_name": "Ollama",
                "model": str(model),
                "base_url": self._ollama_base_url(provider.get("base_url") or "http://127.0.0.1:11434"),
                "env_key": None,
                "env_value": None,
            }
        )
        return provider

    def _openai_base_url(self, value):
        return str(value or "https://api.openai.com/v1").rstrip("/")

    def _ollama_base_url(self, value):
        base_url = str(value or "http://127.0.0.1:11434").rstrip("/")
        if not base_url.endswith("/v1"):
            base_url = base_url + "/v1"
        return base_url

    def _enabled_mcp_tools(self, request_context):
        request_context = request_context if isinstance(request_context, dict) else {}
        guidance = request_context.get("mcp_guidance") if isinstance(request_context.get("mcp_guidance"), dict) else {}
        permission = request_context.get("ai_permission_scope") if isinstance(request_context.get("ai_permission_scope"), dict) else {}
        requested = (
            guidance.get("enabled_tools")
            or permission.get("mcp_enabled_tools")
            or guidance.get("preferred_tools")
            or []
        )
        if not isinstance(requested, list) or not requested:
            if request_context.get("runtime_diagnostics") or request_context.get("runtime_status"):
                requested = RUNTIME_INSPECTION_MCP_TOOLS
            else:
                requested = SERVICE_DRAFT_MCP_TOOLS

        terminal_actions = request_context.get("terminal_actions") if isinstance(request_context.get("terminal_actions"), dict) else {}
        allow_container_actions = bool(terminal_actions.get("allow_container_actions"))
        allow_ssh_command = bool(guidance.get("allow_ssh_command") or permission.get("allow_ssh_command"))
        enabled = []
        for tool in requested:
            tool = str(tool or "").strip()
            if tool not in MCP_TOOL_ALLOWLIST:
                continue
            if tool == "container_action" and not allow_container_actions:
                continue
            if tool == "ssh_command" and not allow_ssh_command:
                continue
            if tool not in enabled:
                enabled.append(tool)
        return enabled or ["infra_context"]

    def _prompt_context(self, context, enabled_tools=None):
        context = context if isinstance(context, dict) else {"value": context}
        compact = self._truncate_context_value(context)
        if self._json_size(compact) > PROMPT_CONTEXT_CHAR_BUDGET:
            compact = self._semantic_prompt_context(context)
        if not isinstance(compact, dict):
            compact = {"value": compact}
        compact = dict(compact)
        compact["context_delivery"] = {
            "prompt": "compacted_summary",
            "reason": "large Docker Infra runtime data is kept out of the prompt to avoid context-window overflow",
            "mcp_tool": "docker_infra.infra_context",
            "enabled_mcp_tools": enabled_tools or ["infra_context"],
            "instruction": "Use docker_infra.infra_context for registered servers, DDNS endpoints, runtime values, and this request summary before making infra claims.",
        }
        return self._fit_prompt_context(compact)

    def _direct_api_prompt_context(self, prompt_context, mcp_context):
        prompt_context = dict(prompt_context if isinstance(prompt_context, dict) else {})
        prompt_context["context_delivery"] = {
            "prompt": "embedded_direct_api",
            "reason": "OpenAI, Gemini, and Ollama providers are called directly without a Codex CLI or MCP session",
            "enabled_mcp_tools": [],
            "instruction": "Use only the embedded Docker Infra context in this request. Do not claim that MCP tools were called.",
        }
        embedded_runtime_context = self._truncate_context_value(
            {
                "nodes": (mcp_context or {}).get("nodes") or [],
                "placement": (mcp_context or {}).get("placement"),
                "domain_zones": (mcp_context or {}).get("domain_zones") or [],
                "ddns_endpoints": (mcp_context or {}).get("ddns_endpoints") or [],
                "allowed_probe_hosts": (mcp_context or {}).get("allowed_probe_hosts") or [],
                "runtime_values": (mcp_context or {}).get("runtime_values") or {},
            },
            depth=1,
            string_limit=2500,
            list_limit=16,
        )
        current_context = prompt_context.get("docker_infra_context")
        if isinstance(current_context, dict):
            prompt_context["docker_infra_context"] = dict(current_context)
            prompt_context["docker_infra_context"]["embedded_runtime_context"] = embedded_runtime_context
        else:
            prompt_context["docker_infra_context"] = embedded_runtime_context
        return self._fit_prompt_context(prompt_context)

    def _semantic_prompt_context(self, context):
        context = context if isinstance(context, dict) else {}
        priority_keys = [
            "mode",
            "intent",
            "operator_message",
            "user_intent",
            "form",
            "service",
            "domains",
            "zones",
            "ddns_repair_suggestion",
            "ai_permission_scope",
            "mcp_guidance",
            "terminal_actions",
            "runtime_wait",
            "client_runtime_issues",
            "output_format",
            "compose_validation",
            "contract",
            "previous_output",
            "validation_error",
            "repair_diagnostics",
            "repair_attempt",
            "repair_instruction",
            "docker_infra_context",
            "base_content",
            "components",
            "summary",
            "warnings",
        ]
        result = {}
        for key in priority_keys:
            if key not in context:
                continue
            value = context.get(key)
            if key == "runtime_status":
                result[key] = self._runtime_status_summary(value)
            elif key == "runtime_diagnostics":
                result[key] = self._runtime_diagnostics_summary(value)
            elif key == "recent_operations":
                result[key] = self._operation_list_summary(value)
            elif key == "client_runtime_issues":
                result[key] = self._client_runtime_issue_summary(value)
            elif key == "base_content":
                result[key] = self._truncate_string(value, 18000)
            else:
                result[key] = self._truncate_context_value(value, depth=1)

        if "runtime_status" in context and "runtime_status" not in result:
            result["runtime_status"] = self._runtime_status_summary(context.get("runtime_status"))
        if "runtime_diagnostics" in context and "runtime_diagnostics" not in result:
            result["runtime_diagnostics"] = self._runtime_diagnostics_summary(context.get("runtime_diagnostics"))
        if "recent_operations" in context and "recent_operations" not in result:
            result["recent_operations"] = self._operation_list_summary(context.get("recent_operations"))

        omitted = [
            key
            for key in context.keys()
            if key not in result and not self._is_sensitive_context_key(key)
        ]
        if omitted:
            result["omitted_context_keys"] = omitted[:50]
        return result

    def _runtime_status_summary(self, value):
        if not isinstance(value, dict):
            return self._truncate_context_value(value, depth=1)
        stack = value.get("stack") if isinstance(value.get("stack"), dict) else {}
        containers = value.get("containers") if isinstance(value.get("containers"), dict) else {}
        domains = value.get("domains") if isinstance(value.get("domains"), dict) else {}
        return {
            "checked_at": value.get("checked_at"),
            "stack": {
                "summary": self._truncate_context_value(stack.get("summary") or {}, depth=2),
                "tasks": self._task_error_summary(stack.get("tasks") or []),
            },
            "containers": {
                "summary": self._truncate_context_value(containers.get("summary") or {}, depth=2),
                "health": self._truncate_context_value(containers.get("health") or {}, depth=2),
                "containers": self._container_summary(containers.get("containers") or []),
            },
            "domains": {
                "summary": self._truncate_context_value(domains.get("summary") or {}, depth=2),
                "items": self._truncate_context_value(domains.get("domains") or domains.get("items") or [], depth=2),
            },
        }

    def _runtime_diagnostics_summary(self, value):
        if not isinstance(value, dict):
            return self._truncate_context_value(value, depth=1)
        logs = []
        for item in (value.get("logs") if isinstance(value.get("logs"), list) else [])[:3]:
            if not isinstance(item, dict):
                continue
            logs.append(
                {
                    "container": self._truncate_context_value(item.get("container") or {}, depth=2),
                    "inspect": self._command_result_summary(item.get("inspect")),
                    "logs": self._command_result_summary(item.get("logs")),
                }
            )
        return {
            "needs_repair": value.get("needs_repair"),
            "service_status": value.get("service_status"),
            "signals": self._truncate_context_value(value.get("signals") or [], depth=2),
            "failed_operations": self._operation_list_summary(value.get("failed_operations") or []),
            "problem_containers": self._container_summary(value.get("problem_containers") or []),
            "task_errors": self._task_error_summary(value.get("task_errors") or []),
            "stack_summary": self._truncate_context_value(value.get("stack_summary") or {}, depth=2),
            "container_summary": self._truncate_context_value(value.get("container_summary") or {}, depth=2),
            "container_health": self._truncate_context_value(value.get("container_health") or {}, depth=2),
            "logs": logs,
        }

    def _client_runtime_issue_summary(self, value):
        if not isinstance(value, dict):
            return self._truncate_context_value(value, depth=1)
        return {
            "has_runtime_issues": value.get("has_runtime_issues"),
            "service_status": value.get("service_status"),
            "stack_summary": self._truncate_context_value(value.get("stack_summary") or {}, depth=2),
            "container_summary": self._truncate_context_value(value.get("container_summary") or {}, depth=2),
            "container_health": self._truncate_context_value(value.get("container_health") or {}, depth=2),
            "failed_operations": self._operation_list_summary(value.get("failed_operations") or []),
        }

    def _operation_list_summary(self, rows):
        result = []
        for item in (rows if isinstance(rows, list) else [])[:PROMPT_CONTEXT_OUTPUT_LIMIT]:
            if isinstance(item, dict):
                result.append(self._operation_summary(item))
        return result

    def _operation_summary(self, item):
        output = item.get("output") if isinstance(item.get("output"), list) else []
        compact_output = []
        for entry in output[-PROMPT_CONTEXT_OUTPUT_LIMIT:]:
            if not isinstance(entry, dict):
                continue
            metadata = entry.get("metadata") if isinstance(entry.get("metadata"), dict) else {}
            compact_output.append(
                {
                    "stream": entry.get("stream"),
                    "message": self._truncate_string(entry.get("message"), 1000),
                    "created_at": entry.get("created_at"),
                    "metadata": self._truncate_context_value(metadata, depth=3),
                }
            )
        result_payload = item.get("result_payload") if isinstance(item.get("result_payload"), dict) else {}
        return {
            "id": item.get("id"),
            "type": item.get("type"),
            "status": item.get("status"),
            "message": self._truncate_string(item.get("message"), 1000),
            "created_at": item.get("created_at"),
            "started_at": item.get("started_at"),
            "finished_at": item.get("finished_at"),
            "result_payload": {
                "ok": result_payload.get("ok"),
                "summary": self._truncate_string(result_payload.get("summary"), 1000),
                "attempts": result_payload.get("attempts"),
                "error_code": result_payload.get("error_code"),
            },
            "output": compact_output,
        }

    def _task_error_summary(self, rows):
        result = []
        for task in (rows if isinstance(rows, list) else [])[:10]:
            if not isinstance(task, dict):
                continue
            result.append(
                {
                    "Name": task.get("Name") or task.get("name"),
                    "CurrentState": task.get("CurrentState") or task.get("Current state") or task.get("current_state"),
                    "DesiredState": task.get("DesiredState") or task.get("Desired state") or task.get("desired_state"),
                    "Error": self._truncate_string(task.get("Error") or task.get("error"), 1000),
                    "Node": task.get("Node") or task.get("node"),
                }
            )
        return result

    def _container_summary(self, rows):
        result = []
        for item in (rows if isinstance(rows, list) else [])[:10]:
            if not isinstance(item, dict):
                continue
            result.append(
                {
                    "id": item.get("id"),
                    "name": item.get("name"),
                    "image": item.get("image"),
                    "state": item.get("state"),
                    "status": item.get("status"),
                    "node_id": item.get("node_id"),
                    "node_name": item.get("node_name"),
                    "runtime_service_name": item.get("runtime_service_name"),
                    "port_bindings": self._truncate_context_value(item.get("port_bindings") or [], depth=3),
                }
            )
        return result

    def _command_result_summary(self, value):
        if not isinstance(value, dict):
            return self._truncate_context_value(value, depth=2)
        return {
            "status": value.get("status"),
            "exit_code": value.get("exit_code"),
            "stdout": self._truncate_string(value.get("stdout"), 1800),
            "stderr": self._truncate_string(value.get("stderr") or value.get("message"), 1800),
        }

    def _fit_prompt_context(self, value):
        if self._json_size(value) <= PROMPT_CONTEXT_CHAR_BUDGET:
            return value
        value = self._truncate_context_value(value, depth=0, string_limit=1800, list_limit=8)
        if self._json_size(value) <= PROMPT_CONTEXT_CHAR_BUDGET:
            return value
        if not isinstance(value, dict):
            return {"value": self._truncate_string(value, PROMPT_CONTEXT_CHAR_BUDGET // 2)}
        priority_keys = [
            "mode",
            "intent",
            "operator_message",
            "user_intent",
            "form",
            "service",
            "domains",
            "zones",
            "ddns_repair_suggestion",
            "runtime_status",
            "runtime_diagnostics",
            "client_runtime_issues",
            "output_format",
            "compose_validation",
            "base_content",
            "components",
            "context_delivery",
        ]
        result = {}
        omitted = []
        ordered = [key for key in priority_keys if key in value] + [key for key in value.keys() if key not in priority_keys]
        for key in ordered:
            candidate = dict(result)
            candidate[key] = self._truncate_context_value(value.get(key), depth=2, string_limit=1200, list_limit=5)
            if self._json_size(candidate) <= PROMPT_CONTEXT_CHAR_BUDGET:
                result = candidate
            else:
                omitted.append(key)
        if omitted:
            result["omitted_context_keys"] = (result.get("omitted_context_keys") or []) + omitted[:50]
        return result

    def _truncate_context_value(self, value, depth=0, string_limit=None, list_limit=None):
        if isinstance(value, dict):
            result = {}
            for key, item in value.items():
                key_text = str(key)
                if self._is_sensitive_context_key(key_text):
                    result[key_text] = "[redacted]"
                    continue
                result[key_text] = self._truncate_context_value(item, depth + 1, string_limit=string_limit, list_limit=list_limit)
            return result
        if isinstance(value, list):
            limit = list_limit or (PROMPT_CONTEXT_LIST_LIMIT if depth <= 1 else PROMPT_CONTEXT_DEEP_LIST_LIMIT)
            result = [self._truncate_context_value(item, depth + 1, string_limit=string_limit, list_limit=list_limit) for item in value[:limit]]
            if len(value) > limit:
                result.append({"omitted_items": len(value) - limit})
            return result
        if isinstance(value, str):
            limit = string_limit or (PROMPT_CONTEXT_STRING_LIMIT if depth <= 1 else PROMPT_CONTEXT_DEEP_STRING_LIMIT)
            return self._truncate_string(value, limit)
        if value is None or isinstance(value, (bool, int, float)):
            return value
        return self._truncate_string(value, string_limit or PROMPT_CONTEXT_DEEP_STRING_LIMIT)

    def _truncate_string(self, value, limit):
        text = "" if value is None else str(value)
        limit = max(200, int(limit or PROMPT_CONTEXT_DEEP_STRING_LIMIT))
        if len(text) <= limit:
            return text
        return "%s\n[truncated %s chars]" % (text[:limit], len(text) - limit)

    def _json_size(self, value):
        try:
            return len(json.dumps(value, ensure_ascii=False, sort_keys=True))
        except Exception:
            return len(str(value))

    def _is_sensitive_context_key(self, key):
        return bool(SENSITIVE_CONTEXT_KEY_RE.search(str(key or "")))

    def _mcp_context(self, env=None, request_context=None):
        request_context = request_context if isinstance(request_context, dict) else {}
        rows = []
        try:
            for item in nodes_model.list(env=env) or []:
                node = nodes_model.detail(item["id"], env=env)
                credential = node.get("credential") or {}
                rows.append(
                    {
                        "id": node.get("id"),
                        "name": node.get("name"),
                        "host": node.get("host"),
                        "role": node.get("role"),
                        "status": node.get("status"),
                        "is_local_master": node.get("is_local_master"),
                        "ssh_port": node.get("ssh_port"),
                        "ssh": {
                            "username": credential.get("username"),
                            "key_file": credential.get("key_file")
                            or (credential.get("metadata") or {}).get("key_file"),
                        },
                    }
                )
        except Exception:
            rows = []
        try:
            placement = placement_selector.recommend(env=env)
        except Exception:
            placement = None
        domain_zones = request_context.get("zones") if isinstance(request_context.get("zones"), list) else []
        ddns_endpoints = [
            zone
            for zone in domain_zones
            if isinstance(zone, dict) and (zone.get("provider") == "ddns" or zone.get("ddns") is True)
        ]
        return {
            "workspace_root": str(WORKSPACE_ROOT),
            "project_root": str(PROJECT_ROOT),
            "nodes": rows,
            "placement": placement,
            "domain_zones": domain_zones,
            "ddns_endpoints": ddns_endpoints,
            "ai_permission_scope": request_context.get("ai_permission_scope") or {},
            "ai_request_summary": request_context.get("ai_request_summary") or {},
            "request_context_keys": sorted([str(key) for key in request_context.keys() if not self._is_sensitive_context_key(key)]),
            "mcp_enabled_tools": request_context.get("mcp_enabled_tools") or [],
            "allowed_probe_hosts": self._allowed_probe_hosts(request_context, rows),
            "terminal_actions": request_context.get("terminal_actions") or {},
            "runtime_values": {
                "overlay_network": "docker_infra_overlay",
                "service_compose_filename": "docker-compose.yaml",
                "service_root_hint": str(PROJECT_ROOT / ".runtime" / "dev" / "services"),
            },
        }

    def _allowed_probe_hosts(self, request_context, nodes):
        hosts = set()
        for node in nodes or []:
            host = str(node.get("host") or "").strip().lower()
            if host:
                hosts.add(host)
        for item in request_context.get("domains") or []:
            if not isinstance(item, dict):
                continue
            domain = str(item.get("domain") or "").strip().lower()
            if domain:
                hosts.add(domain)
            metadata = item.get("metadata") if isinstance(item.get("metadata"), dict) else {}
            proxy_host = str(metadata.get("proxy_host") or "").strip().lower()
            if proxy_host:
                hosts.add(proxy_host)
        form = request_context.get("form") if isinstance(request_context.get("form"), dict) else {}
        for key in ["domain", "hostname", "host"]:
            value = str(form.get(key) or "").strip().lower()
            if value:
                hosts.add(value)
        for item in request_context.get("allowed_probe_hosts") or []:
            value = str(item or "").strip().lower()
            if value:
                hosts.add(value)
        return sorted(hosts)

    def _prompt(self, system, context, provider, enabled_tools=None):
        enabled_tools = enabled_tools or []
        enabled_label = ", ".join(enabled_tools) or "infra_context"
        payload = {
            "system": system,
            "context": context,
            "provider": {
                "type": provider.get("type"),
                "provider_id": provider.get("provider_id"),
                "label": _provider_label(provider.get("type")),
                "model": provider.get("model"),
            },
        }
        if provider.get("type") == "codex":
            execution_note = "You are running inside Docker Infra through the logged-in Codex CLI session.\n"
            tool_note = (
                "Use only the docker_infra MCP tools explicitly enabled for this request. "
                f"Enabled docker_infra MCP tools: {enabled_label}.\n"
                "The request context embedded below is compacted; do not assume omitted runtime logs are unavailable. "
                "Call docker_infra.infra_context for Docker Infra's registered servers, DDNS endpoints, runtime values, and request summary when needed.\n"
                "If another MCP tool is unavailable or not exposed in this session, do not report that as an operator-facing error; "
                "fall back to the enabled tools and provided Docker Infra context.\n\n"
            )
        else:
            execution_note = "You are running inside Docker Infra through a direct provider API call.\n"
            tool_note = (
                "No Codex CLI or MCP tools are available in this execution path. "
                "Use only the embedded Docker Infra context below, and do not claim that external tools were called.\n\n"
            )
        return (
            execution_note
            + "Return only one JSON object that satisfies the system and context below. "
            "Do not edit files, do not include markdown fences, and do not describe the answer outside JSON.\n"
            + tool_note
            + "<docker_infra_ai_request>\n"
            f"{json.dumps(payload, ensure_ascii=False, sort_keys=True)}\n"
            "</docker_infra_ai_request>"
        )

    def _codex_login_config_args(self, provider, mcp_context_path, enabled_tools):
        python_bin = _python_executable()
        overrides = {
            "model_reasoning_effort": provider.get("reasoning_effort") or CODEX_LOGIN_DEFAULT_REASONING_EFFORT,
            "approval_policy": "never",
            "mcp_servers.docker_infra.command": python_bin,
            "mcp_servers.docker_infra.args": [str(MCP_SCRIPT)],
            "mcp_servers.docker_infra.enabled_tools": enabled_tools,
            "mcp_servers.docker_infra.default_tools_approval_mode": "approve",
            "mcp_servers.docker_infra.env.DOCKER_INFRA_ROOT": str(WORKSPACE_ROOT),
            "mcp_servers.docker_infra.env.DOCKER_INFRA_MCP_CONTEXT_FILE": str(mcp_context_path),
            "mcp_servers.docker_infra.env.DOCKER_INFRA_MCP_TIMEOUT_SECONDS": "30",
        }
        args = []
        for key, value in overrides.items():
            if isinstance(value, list):
                encoded = _toml_string_list(value)
            else:
                encoded = _json_string(value)
            args.extend(["-c", f"{key}={encoded}"])
        return args

    def _run_direct_api(self, provider, prompt):
        provider_type = provider["type"]
        if provider_type == "openai":
            return self._complete_openai_api(provider, prompt)
        if provider_type == "gemini":
            return self._complete_gemini_api(provider, prompt)
        if provider_type == "ollama":
            return self._complete_ollama_api(provider, prompt)
        raise CodexRuntimeError(400, "직접 API 호출을 지원하지 않는 provider입니다.", "AI_API_PROVIDER_NOT_SUPPORTED")

    def _complete_openai_api(self, provider, prompt):
        headers = {
            "Authorization": "Bearer %s" % provider["env_value"],
        }
        responses_url = self._join_url(provider["base_url"], "responses")
        responses_payload = {
            "model": provider["model"],
            "input": prompt,
            "text": {"format": {"type": "json_object"}},
        }
        try:
            response = self._http_post_json(responses_url, responses_payload, headers, provider, "OPENAI_API_REQUEST_FAILED")
            text = self._extract_openai_responses_text(response)
            if text:
                return {"text": text, "exit_code": 0, "executable": "", "api_endpoint": responses_url}
        except CodexRuntimeError as exc:
            if exc.status_code not in {400, 404, 422}:
                raise

        chat_url = self._join_url(provider["base_url"], "chat/completions")
        chat_payload = {
            "model": provider["model"],
            "messages": [
                {"role": "system", "content": "Return only one JSON object. Do not include markdown fences."},
                {"role": "user", "content": prompt},
            ],
            "response_format": {"type": "json_object"},
            "temperature": 0.2,
        }
        response = self._http_post_json(chat_url, chat_payload, headers, provider, "OPENAI_API_REQUEST_FAILED")
        text = self._extract_chat_completion_text(response)
        if not text:
            raise CodexRuntimeError(502, "OpenAI API 응답이 비어 있습니다.", "OPENAI_EMPTY_RESPONSE")
        return {"text": text, "exit_code": 0, "executable": "", "api_endpoint": chat_url}

    def _complete_gemini_api(self, provider, prompt):
        model = urllib.parse.quote(str(provider["model"]).replace("models/", "", 1), safe="")
        api_version = str(provider.get("api_version") or "v1beta").strip("/")
        url = "https://generativelanguage.googleapis.com/%s/models/%s:generateContent?key=%s" % (
            api_version,
            model,
            urllib.parse.quote(provider["env_value"], safe=""),
        )
        payload = {
            "systemInstruction": {
                "parts": [{"text": "Return only one JSON object. Do not include markdown fences."}],
            },
            "contents": [
                {
                    "role": "user",
                    "parts": [{"text": prompt}],
                }
            ],
            "generationConfig": {
                "responseMimeType": "application/json",
                "temperature": 0.2,
            },
        }
        response = self._http_post_json(url, payload, {}, provider, "GEMINI_API_REQUEST_FAILED")
        text = self._extract_gemini_text(response)
        if not text:
            raise CodexRuntimeError(502, "Gemini API 응답이 비어 있습니다.", "GEMINI_EMPTY_RESPONSE")
        safe_url = url.split("?key=", 1)[0]
        return {"text": text, "exit_code": 0, "executable": "", "api_endpoint": safe_url}

    def _complete_ollama_api(self, provider, prompt):
        native_url = self._join_url(self._ollama_native_base_url(provider["base_url"]), "api/chat")
        native_payload = {
            "model": provider["model"],
            "messages": [
                {"role": "system", "content": "Return only one JSON object. Do not include markdown fences."},
                {"role": "user", "content": prompt},
            ],
            "format": "json",
            "stream": False,
            "options": {"temperature": 0.2},
        }
        try:
            response = self._http_post_json(native_url, native_payload, {}, provider, "OLLAMA_API_REQUEST_FAILED")
            message = response.get("message") if isinstance(response.get("message"), dict) else {}
            text = message.get("content") or response.get("response") or ""
            if text:
                return {"text": text, "exit_code": 0, "executable": "", "api_endpoint": native_url}
        except CodexRuntimeError as exc:
            if exc.status_code not in {400, 404, 405}:
                raise

        chat_url = self._join_url(provider["base_url"], "chat/completions")
        chat_payload = {
            "model": provider["model"],
            "messages": [
                {"role": "system", "content": "Return only one JSON object. Do not include markdown fences."},
                {"role": "user", "content": prompt},
            ],
            "response_format": {"type": "json_object"},
            "temperature": 0.2,
        }
        response = self._http_post_json(chat_url, chat_payload, {}, provider, "OLLAMA_API_REQUEST_FAILED")
        text = self._extract_chat_completion_text(response)
        if not text:
            raise CodexRuntimeError(502, "Ollama API 응답이 비어 있습니다.", "OLLAMA_EMPTY_RESPONSE")
        return {"text": text, "exit_code": 0, "executable": "", "api_endpoint": chat_url}

    def _http_post_json(self, url, payload, headers, provider, error_code):
        request_headers = {
            "Accept": "application/json",
            "Content-Type": "application/json",
            "User-Agent": "docker-infra-ai/1.0",
        }
        request_headers.update(headers or {})
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        request = urllib.request.Request(url, data=body, headers=request_headers, method="POST")
        timeout = int(provider.get("timeout_seconds") or CODEX_TIMEOUT_SECONDS)
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                response_body = response.read().decode("utf-8", "replace")
        except urllib.error.HTTPError as exc:
            response_body = exc.read().decode("utf-8", "replace")
            raise CodexRuntimeError(
                exc.code,
                "%s API 호출이 실패했습니다." % _provider_label(provider["type"]),
                error_code,
                {
                    "status": exc.code,
                    "reason": getattr(exc, "reason", ""),
                    "response": _trim(response_body, 4000),
                    "url": self._redact_url(url),
                },
            )
        except urllib.error.URLError as exc:
            raise CodexRuntimeError(
                502,
                "%s API에 연결할 수 없습니다: %s" % (_provider_label(provider["type"]), getattr(exc, "reason", exc)),
                error_code,
                {"url": self._redact_url(url)},
            )
        except TimeoutError:
            raise CodexRuntimeError(
                504,
                "%s API 호출 시간이 초과되었습니다." % _provider_label(provider["type"]),
                error_code,
                {"url": self._redact_url(url)},
            )
        try:
            return json.loads(response_body or "{}")
        except Exception as exc:
            raise CodexRuntimeError(
                502,
                "%s API 응답을 JSON으로 해석할 수 없습니다: %s" % (_provider_label(provider["type"]), exc),
                error_code,
                {"response": _trim(response_body, 4000), "url": self._redact_url(url)},
            )

    def _extract_openai_responses_text(self, response):
        if response.get("output_text"):
            return str(response.get("output_text")).strip()
        chunks = []
        for item in response.get("output") or []:
            if not isinstance(item, dict):
                continue
            for content in item.get("content") or []:
                if not isinstance(content, dict):
                    continue
                text = content.get("text") or content.get("output_text")
                if text:
                    chunks.append(str(text))
        return "".join(chunks).strip()

    def _extract_chat_completion_text(self, response):
        choices = response.get("choices") if isinstance(response.get("choices"), list) else []
        if not choices:
            return ""
        message = choices[0].get("message") if isinstance(choices[0], dict) else {}
        content = message.get("content") if isinstance(message, dict) else ""
        if isinstance(content, list):
            chunks = []
            for item in content:
                if isinstance(item, dict):
                    chunks.append(str(item.get("text") or item.get("content") or ""))
                elif item:
                    chunks.append(str(item))
            return "".join(chunks).strip()
        return str(content or "").strip()

    def _extract_gemini_text(self, response):
        chunks = []
        for candidate in response.get("candidates") or []:
            content = candidate.get("content") if isinstance(candidate, dict) else {}
            for part in (content.get("parts") if isinstance(content, dict) else []) or []:
                if isinstance(part, dict) and part.get("text"):
                    chunks.append(str(part.get("text")))
        return "".join(chunks).strip()

    def _join_url(self, base_url, path):
        return "%s/%s" % (str(base_url or "").rstrip("/"), str(path or "").lstrip("/"))

    def _ollama_native_base_url(self, base_url):
        base_url = str(base_url or "http://127.0.0.1:11434").rstrip("/")
        if base_url.endswith("/v1"):
            return base_url[:-3]
        return base_url

    def _redact_url(self, url):
        return str(url or "").split("?key=", 1)[0]

    def _run_codex(self, provider, runtime_home, last_message_path, prompt, mcp_context_path, enabled_tools):
        executable = self._codex_login_executable(provider)
        config_args = self._codex_login_config_args(provider, mcp_context_path, enabled_tools)
        command = [
            executable,
            "exec",
            "--json",
            "--ephemeral",
            "--skip-git-repo-check",
            "--ignore-user-config",
            "--sandbox",
            "read-only",
            *config_args,
            "-C",
            str(WORKSPACE_ROOT),
            "-m",
            provider["model"],
            "--output-last-message",
            str(last_message_path),
            "-",
        ]
        run_env = self._codex_env(provider)
        run_env["NO_COLOR"] = "1"
        try:
            completed = subprocess.run(
                command,
                input=prompt,
                capture_output=True,
                text=True,
                timeout=int(provider.get("timeout_seconds") or CODEX_TIMEOUT_SECONDS),
                check=False,
                env=run_env,
            )
        except subprocess.TimeoutExpired as exc:
            raise CodexRuntimeError(
                504,
                "Codex 실행 시간이 초과되었습니다.",
                "CODEX_EXEC_TIMEOUT",
                {"stdout": _trim(exc.stdout), "stderr": _trim(exc.stderr), "command": command},
            )

        text = last_message_path.read_text(encoding="utf-8").strip() if last_message_path.exists() else ""
        if completed.returncode != 0:
            raise CodexRuntimeError(
                502,
                "Codex 실행이 실패했습니다.",
                "CODEX_EXEC_FAILED",
                {
                    "exit_code": completed.returncode,
                    "stdout": _trim(completed.stdout),
                    "stderr": _trim(completed.stderr),
                    "command": command,
                },
            )
        if not text:
            text = self._last_json_event_output(completed.stdout)
        if not text:
            raise CodexRuntimeError(
                502,
                "Codex 최종 응답이 비어 있습니다.",
                "CODEX_EMPTY_RESPONSE",
                {"stdout": _trim(completed.stdout), "stderr": _trim(completed.stderr), "command": command},
            )
        return {"text": text, "exit_code": completed.returncode, "executable": executable}

    def _last_json_event_output(self, stdout):
        result = ""
        for line in (stdout or "").splitlines():
            try:
                event = json.loads(line)
            except Exception:
                continue
            if event.get("type") in {"agent_message", "thread.item.completed"}:
                result = event.get("message") or event.get("text") or result
            if event.get("type") in {"item.completed", "thread.item.completed"}:
                item = event.get("item") if isinstance(event.get("item"), dict) else {}
                text = item.get("text") or item.get("message") or item.get("content")
                if isinstance(text, list):
                    chunks = []
                    for chunk in text:
                        if isinstance(chunk, dict):
                            chunks.append(str(chunk.get("text") or chunk.get("content") or ""))
                        elif chunk:
                            chunks.append(str(chunk))
                    text = "".join(chunks)
                if text:
                    result = str(text)
            if event.get("type") == "turn.completed":
                output = event.get("aggregated_output")
                if output:
                    result = output
        return result.strip()


Model = CodexRuntime()
