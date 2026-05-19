import json
import datetime
import errno
import os
import pty
import re
import select
import shutil
import subprocess
import tempfile
import threading
import time
import uuid
from pathlib import Path

nodes_model = wiz.model("struct/nodes")
placement_selector = wiz.model("struct/services_placement")


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
        if (candidate / "codex" / "codex-rs").exists():
            return candidate

    source_file = Path(__file__).resolve()
    for parent in [project_root] + list(project_root.parents) + list(source_file.parents):
        if (parent / "codex" / "codex-rs").exists():
            return parent

    fallback = Path("/root/docker-infra")
    if (fallback / "codex" / "codex-rs").exists():
        return fallback
    return project_root.parents[1]


PROJECT_ROOT = _find_project_root()
WORKSPACE_ROOT = _find_workspace_root(PROJECT_ROOT)
CODEX_SOURCE_ROOT = WORKSPACE_ROOT / "codex"
PYTHON_BIN = "/opt/conda/envs/docker-infra/bin/python"
MCP_SCRIPT = PROJECT_ROOT / "tools" / "docker_infra_mcp.py"
CODEX_RUNTIME_ROOT = PROJECT_ROOT / ".runtime" / "codex"
CODEX_TIMEOUT_SECONDS = 1200
CODEX_BUILD_TIMEOUT_SECONDS = 1800
CODEX_BUILD_CHECK_INTERVAL_SECONDS = 60
CODEX_STATUS_TIMEOUT_SECONDS = 15
CODEX_TEST_TIMEOUT_SECONDS = 180
CODEX_DEVICE_LOGIN_START_TIMEOUT_SECONDS = 5
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


def _is_relative_to(path, parent):
    try:
        Path(path).resolve().relative_to(Path(parent).resolve())
        return True
    except Exception:
        return False


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
        self._last_build_check_at = 0
        self._last_source_mtime = 0
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
                "uses_custom_cli": False,
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

    def _codex_login_executable(self, config):
        config = self._normalize_codex_config(config or {})
        if config["cli_mode"] == "custom":
            return self.codex_executable()
        executable = self._system_codex_executable()
        if executable and _is_executable_file(executable):
            return executable
        raise CodexRuntimeError(
            503,
            "로그인 세션을 사용할 Codex CLI를 찾을 수 없습니다. /usr/local/bin/codex 또는 DOCKER_INFRA_SYSTEM_CODEX_BIN을 확인하세요.",
            "CODEX_LOGIN_EXECUTABLE_NOT_FOUND",
            {"path_codex": executable},
        )

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

    def _custom_codex_status(self):
        try:
            executable = self.codex_executable()
            available = bool(executable and _is_executable_file(executable))
            binary_mtime = Path(executable).stat().st_mtime if available else None
            return {
                "source": "custom",
                "executable": executable or "",
                "available": available,
                "version": self._version_for(executable) if available else "",
                "workspace_root": str(WORKSPACE_ROOT),
                "source_root": str(CODEX_SOURCE_ROOT),
                "binary_mtime": binary_mtime,
                "source_mtime": self._last_source_mtime or self._codex_source_mtime(),
            }
        except Exception as exc:
            return {
                "source": "custom",
                "executable": "",
                "available": False,
                "workspace_root": str(WORKSPACE_ROOT),
                "source_root": str(CODEX_SOURCE_ROOT),
                "error": getattr(exc, "message", str(exc)),
                "error_code": getattr(exc, "error_code", "CODEX_CUSTOM_STATUS_FAILED"),
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

    def codex_executable(self):
        explicit = os.environ.get("DOCKER_INFRA_CODEX_BIN")
        explicit_details = None
        if explicit:
            candidate = Path(explicit).expanduser()
            if _is_executable_file(candidate):
                return str(candidate)
            explicit_details = {
                "path": explicit,
                "exists": candidate.exists(),
                "is_file": candidate.is_file(),
                "executable": os.access(candidate, os.X_OK),
            }

        checked = []
        candidate = self._existing_codex_binary(checked=checked)
        if candidate:
            return self._ensure_codex_binary_current(candidate, explicit_details=explicit_details, checked=checked)

        path_executable = shutil.which("codex")
        if path_executable and _is_relative_to(path_executable, CODEX_SOURCE_ROOT) and _is_executable_file(path_executable):
            return self._ensure_codex_binary_current(Path(path_executable), explicit_details=explicit_details, checked=checked)

        build_result = self._build_codex_binary(skip_existing=False)
        if build_result.get("executable"):
            return build_result["executable"]
        candidate = self._existing_codex_binary()
        if candidate:
            return str(candidate)

        raise CodexRuntimeError(
            503,
            "수정한 Codex 소스의 실행 파일을 찾을 수 없습니다. /root/docker-infra/codex/codex-rs에서 Codex CLI 빌드가 가능한지 확인하거나 DOCKER_INFRA_CODEX_BIN을 지정하세요.",
            "CODEX_EXECUTABLE_NOT_FOUND",
            {
                "workspace_root": str(WORKSPACE_ROOT),
                "codex_source_root": str(CODEX_SOURCE_ROOT),
                "explicit": explicit_details,
                "checked": checked,
                "path_codex": path_executable,
                "build": build_result,
            },
        )

    def _existing_codex_binary(self, checked=None):
        for candidate in self._candidate_codex_binaries():
            if checked is not None:
                checked.append(str(candidate))
            if _is_executable_file(candidate):
                return candidate
        return None

    def _ensure_codex_binary_current(self, candidate, explicit_details=None, checked=None):
        if not self._build_check_due():
            return str(candidate)
        if not self._source_newer_than(candidate):
            self._mark_build_checked()
            return str(candidate)

        build_result = self._build_codex_binary(skip_existing=False)
        if build_result.get("success") and build_result.get("executable"):
            self._mark_build_checked()
            return build_result["executable"]

        raise CodexRuntimeError(
            503,
            "수정한 Codex CLI 소스가 실행 파일보다 최신이지만 자동 빌드에 실패했습니다.",
            "CODEX_BUILD_FAILED",
            {
                "workspace_root": str(WORKSPACE_ROOT),
                "codex_source_root": str(CODEX_SOURCE_ROOT),
                "current_executable": str(candidate),
                "explicit": explicit_details,
                "checked": checked or [],
                "source_mtime": self._last_source_mtime,
                "executable_mtime": Path(candidate).stat().st_mtime if Path(candidate).exists() else None,
                "build": build_result,
            },
        )

    def _build_check_due(self):
        return time.time() - self._last_build_check_at >= CODEX_BUILD_CHECK_INTERVAL_SECONDS

    def _mark_build_checked(self):
        self._last_build_check_at = time.time()

    def _source_newer_than(self, executable):
        try:
            executable_mtime = Path(executable).stat().st_mtime
            source_mtime = self._codex_source_mtime()
            self._last_source_mtime = source_mtime
            return source_mtime > executable_mtime + 1
        except Exception:
            return False

    def _codex_source_mtime(self):
        source_root = CODEX_SOURCE_ROOT / "codex-rs"
        latest = 0
        for base, dirs, files in os.walk(source_root):
            dirs[:] = [name for name in dirs if name not in {"target", ".git"}]
            for name in files:
                if not name.endswith((".rs", ".toml", ".lock")):
                    continue
                try:
                    latest = max(latest, (Path(base) / name).stat().st_mtime)
                except Exception:
                    pass
        return latest

    def _candidate_codex_binaries(self):
        target_root = CODEX_SOURCE_ROOT / "codex-rs" / "target"
        preferred = [
            target_root / "release" / "codex",
            target_root / "debug" / "codex",
        ]
        discovered = []
        if target_root.exists():
            try:
                discovered = sorted(
                    [path for path in target_root.glob("**/codex") if path.is_file()],
                    key=self._candidate_sort_key,
                )
            except Exception:
                discovered = []
        return _dedupe_paths(preferred + discovered)

    def _candidate_sort_key(self, path):
        parts = Path(path).parts
        if "release" in parts:
            tier = 0
        elif "debug" in parts:
            tier = 1
        else:
            tier = 2
        return (tier, len(parts), str(path))

    def _build_codex_binary(self, skip_existing=True):
        enabled = str(os.environ.get("DOCKER_INFRA_CODEX_AUTO_BUILD", "1")).lower()
        if enabled in {"0", "false", "no", "off"}:
            return {"attempted": False, "disabled": True}

        manifest = CODEX_SOURCE_ROOT / "codex-rs" / "Cargo.toml"
        if not manifest.exists():
            return {"attempted": False, "reason": "manifest_not_found", "manifest": str(manifest)}

        cargo = shutil.which("cargo")
        if not cargo:
            return {"attempted": False, "reason": "cargo_not_found"}

        CODEX_RUNTIME_ROOT.mkdir(parents=True, exist_ok=True)
        lock_path = CODEX_RUNTIME_ROOT / "codex-build.lock"
        command = [cargo, "build", "-p", "codex-cli", "--bin", "codex"]
        try:
            with lock_path.open("w", encoding="utf-8") as lock_file:
                try:
                    import fcntl

                    fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX)
                except Exception:
                    pass

                if skip_existing:
                    for candidate in self._candidate_codex_binaries():
                        if _is_executable_file(candidate):
                            return {"attempted": False, "executable": str(candidate), "reason": "built_by_other_process"}

                completed = subprocess.run(
                    command,
                    cwd=str(CODEX_SOURCE_ROOT / "codex-rs"),
                    capture_output=True,
                    text=True,
                    timeout=CODEX_BUILD_TIMEOUT_SECONDS,
                    check=False,
                )
        except subprocess.TimeoutExpired as exc:
            return {
                "attempted": True,
                "success": False,
                "reason": "timeout",
                "command": command,
                "stdout": _trim(exc.stdout),
                "stderr": _trim(exc.stderr),
            }
        except Exception as exc:
            return {"attempted": True, "success": False, "reason": "exception", "command": command, "message": str(exc)}

        if completed.returncode != 0:
            return {
                "attempted": True,
                "success": False,
                "reason": "cargo_build_failed",
                "exit_code": completed.returncode,
                "command": command,
                "stdout": _trim(completed.stdout),
                "stderr": _trim(completed.stderr),
            }

        for candidate in self._candidate_codex_binaries():
            if _is_executable_file(candidate):
                return {
                    "attempted": True,
                    "success": True,
                    "executable": str(candidate),
                    "exit_code": completed.returncode,
                }

        return {
            "attempted": True,
            "success": False,
            "reason": "binary_not_found_after_build",
            "exit_code": completed.returncode,
            "command": command,
            "stdout": _trim(completed.stdout),
            "stderr": _trim(completed.stderr),
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
            mcp_context_path.write_text(
                json.dumps(self._mcp_context(env=env, request_context=mcp_request_context), ensure_ascii=False),
                encoding="utf-8",
            )
            if provider["type"] != "codex":
                (runtime_home_path / "config.toml").write_text(
                    self._config_toml(provider, mcp_context_path, mcp_enabled_tools),
                    encoding="utf-8",
                )
            last_message_path = runtime_home_path / "last-message.txt"
            prompt = self._prompt(system, prompt_context, provider, mcp_enabled_tools)
            result = self._run_codex(provider, runtime_home_path, last_message_path, prompt, mcp_context_path, mcp_enabled_tools)
            metadata = {
                "engine": "codex",
                "provider": provider["type"],
                "provider_id": provider["provider_id"],
                "provider_label": _provider_label(provider["type"]),
                "model": provider["model"],
                "reasoning_effort": provider.get("reasoning_effort") or "",
                "cli_mode": provider.get("cli_mode") or ("system" if provider["type"] == "codex" else "custom"),
                "uses_custom_cli": provider["type"] != "codex",
                "executable": result.get("executable") or "",
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
                    "base_url": "https://generativelanguage.googleapis.com/%s/openai" % api_version.strip("/"),
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

    def _config_toml(self, provider, mcp_context_path, enabled_tools):
        provider_lines = [
            f"model = {_json_string(provider['model'])}",
            f"model_provider = {_json_string(provider['provider_id'])}",
            'sandbox_mode = "read-only"',
            "",
            f"[model_providers.{provider['provider_id']}]",
            f"name = {_json_string(provider['provider_name'])}",
            f"base_url = {_json_string(provider['base_url'])}",
            'wire_api = "responses"',
            "requires_openai_auth = false",
            "request_max_retries = 0",
            "stream_max_retries = 0",
            "stream_idle_timeout_ms = 1200000",
        ]
        if provider.get("env_key"):
            provider_lines.append(f"env_key = {_json_string(provider['env_key'])}")

        python_bin = _python_executable()
        return "\n".join(
            provider_lines
            + [
                "",
                "[mcp_servers.docker_infra]",
                f"command = {_json_string(python_bin)}",
                f"args = [{_json_string(str(MCP_SCRIPT))}]",
                f"enabled_tools = {_toml_string_list(enabled_tools)}",
                'default_tools_approval_mode = "approve"',
                "",
                "[mcp_servers.docker_infra.env]",
                f"DOCKER_INFRA_ROOT = {_json_string(str(WORKSPACE_ROOT))}",
                f"DOCKER_INFRA_MCP_CONTEXT_FILE = {_json_string(str(mcp_context_path))}",
                'DOCKER_INFRA_MCP_TIMEOUT_SECONDS = "30"',
                "",
            ]
        )

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
        execution_note = (
            "You are running inside Docker Infra through the logged-in Codex CLI session.\n"
            if provider.get("type") == "codex"
            else "You are running inside Docker Infra through the locally modified Codex CLI source.\n"
        )
        return (
            execution_note
            +
            "Return only one JSON object that satisfies the system and context below. "
            "Do not edit files, do not include markdown fences, and do not describe the answer outside JSON.\n"
            "Use only the docker_infra MCP tools explicitly enabled for this request. "
            f"Enabled docker_infra MCP tools: {enabled_label}.\n"
            "The request context embedded below is compacted; do not assume omitted runtime logs are unavailable. "
            "Call docker_infra.infra_context for Docker Infra's registered servers, DDNS endpoints, runtime values, and request summary when needed.\n"
            "If another MCP tool is unavailable or not exposed in this session, do not report that as an operator-facing error; "
            "fall back to the enabled tools and provided Docker Infra context.\n\n"
            "<docker_infra_ai_request>\n"
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

    def _run_codex(self, provider, runtime_home, last_message_path, prompt, mcp_context_path, enabled_tools):
        if provider["type"] == "codex":
            executable = self._codex_login_executable(provider)
            config_args = self._codex_login_config_args(provider, mcp_context_path, enabled_tools)
        else:
            executable = self.codex_executable()
            config_args = []
        command = [
            executable,
            "exec",
            "--json",
            "--ephemeral",
            "--skip-git-repo-check",
            *(["--ignore-user-config"] if provider["type"] == "codex" else []),
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
        if provider["type"] != "codex":
            provider_arg_index = command.index("-C")
            command[provider_arg_index:provider_arg_index] = ["--model-provider", provider["provider_id"]]
        run_env = _subprocess_env()
        if provider["type"] == "codex":
            run_env = self._codex_env(provider)
        else:
            run_env["CODEX_HOME"] = str(runtime_home)
        run_env["NO_COLOR"] = "1"
        if provider.get("env_key") and provider.get("env_value"):
            run_env[provider["env_key"]] = provider["env_value"]
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
