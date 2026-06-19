import json
import datetime
import errno
import os
import pty
import queue
import re
import select
import shlex
import shutil
import subprocess
import tempfile
import threading
import time
import uuid
import yaml
from pathlib import Path
from urllib import request as urlrequest

nodes_model = wiz.model("struct/nodes")
placement_selector = wiz.model("struct/services_placement")
compose_rules = wiz.model("struct/compose_rules")
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


def _find_runtime_project_root(project_root):
    project_root = Path(project_root)
    if project_root.name == "bundle" and (project_root.parent / "src" / "model").exists():
        return project_root.parent
    return project_root


PROJECT_ROOT = _find_project_root()
WORKSPACE_ROOT = _find_workspace_root(PROJECT_ROOT)
RUNTIME_PROJECT_ROOT = _find_runtime_project_root(PROJECT_ROOT)
PYTHON_BIN = "/opt/conda/envs/docker-infra/bin/python"
MCP_SCRIPT = PROJECT_ROOT / "tools" / "docker_infra_mcp.py"
CODEX_RUNTIME_ROOT = PROJECT_ROOT / ".runtime" / "codex"
CODEX_TIMEOUT_SECONDS = 1200
CODEX_STATUS_TIMEOUT_SECONDS = 15
CODEX_TEST_TIMEOUT_SECONDS = 180
CODEX_DEVICE_LOGIN_START_TIMEOUT_SECONDS = 10
CLAUDE_LOGIN_START_TIMEOUT_SECONDS = 10
CODEX_NPM_PACKAGE = "@openai/codex"
CLAUDE_CODE_INSTALL_URL = "https://claude.ai/install.sh"
CLAUDE_CODE_INSTALL_CHANNEL = "latest"
HERMES_AGENT_INSTALL_URL = "https://raw.githubusercontent.com/NousResearch/hermes-agent/main/scripts/install.sh"
HERMES_AGENT_INSTALL_CHANNEL = ""
AGENT_INSTALL_TIMEOUT_SECONDS = 1200
AGENT_MODEL_CATALOG_TIMEOUT_SECONDS = 20
NODE_SOURCE_SETUP_URL = "https://deb.nodesource.com/setup_lts.x"
CODEX_NPM_VIEW_TIMEOUT_SECONDS = 30
CODEX_NPM_INSTALL_TIMEOUT_SECONDS = 900
CODEX_LOGIN_DEFAULT_MODEL = "gpt-5.5"
CODEX_LOGIN_DEFAULT_REASONING_EFFORT = "xhigh"
CODEX_REASONING_EFFORTS = {"low", "medium", "high", "xhigh"}
AGENT_RUNTIME_HOME_ROOT = RUNTIME_PROJECT_ROOT / ".runtime" / "agents"
AGENT_TYPES = {"codex", "claude_code", "hermes"}
AGENT_ORDER = ["codex", "claude_code", "hermes"]
AGENT_DEFAULTS = {
    "codex": {
        "model": CODEX_LOGIN_DEFAULT_MODEL,
        "reasoning_effort": CODEX_LOGIN_DEFAULT_REASONING_EFFORT,
        "home_key": "codex_home",
        "install_script_env": "DOCKER_INFRA_CODEX_INSTALL_SCRIPT",
        "npm_package": CODEX_NPM_PACKAGE,
        "npm_package_env": "DOCKER_INFRA_CODEX_NPM_PACKAGE",
        "binary": "codex",
        "upgrade_policy": "manual",
    },
    "claude_code": {
        "model": "sonnet",
        "home_key": "home",
        "install_script_env": "DOCKER_INFRA_CLAUDE_CODE_INSTALL_SCRIPT",
        "install_method": "native",
        "install_url": CLAUDE_CODE_INSTALL_URL,
        "install_url_env": "DOCKER_INFRA_CLAUDE_CODE_INSTALL_URL",
        "install_channel": CLAUDE_CODE_INSTALL_CHANNEL,
        "install_channel_env": "DOCKER_INFRA_CLAUDE_CODE_INSTALL_CHANNEL",
        "cleanup_npm_package": "@anthropic-ai/claude-code",
        "binary": "claude",
        "upgrade_policy": "automatic",
        "upgrade_command": "claude update",
        "default_command_template": (
            "{executable} --print --output-format text "
            "--mcp-config {mcp_config} --model {model} {session_args} --dangerously-skip-permissions"
        ),
    },
    "hermes": {
        "model": "default",
        "home_key": "home",
        "install_script_env": "DOCKER_INFRA_HERMES_AGENT_INSTALL_SCRIPT",
        "install_method": "native",
        "install_url": HERMES_AGENT_INSTALL_URL,
        "install_url_env": "DOCKER_INFRA_HERMES_AGENT_INSTALL_URL",
        "install_channel": HERMES_AGENT_INSTALL_CHANNEL,
        "install_channel_env": "DOCKER_INFRA_HERMES_AGENT_INSTALL_CHANNEL",
        "cleanup_npm_package": "hermes-agent",
        "binary": "hermes",
        "upgrade_policy": "manual",
        "upgrade_command": "hermes update",
        "default_command_template": (
            "{executable} -z {prompt} --provider {provider} --model {model} "
            "--toolsets docker_infra --accept-hooks --yolo"
        ),
    },
}
MODEL_CATALOG_SOURCES = {
    "openai": {
        "label": "OpenAI",
        "url": "https://platform.openai.com/docs/models",
    },
    "anthropic": {
        "label": "Anthropic",
        "url": "https://code.claude.com/docs/en/model-config",
    },
    "openrouter": {
        "label": "OpenRouter",
        "url": "https://openrouter.ai/api/v1/models",
    },
    "gemini": {
        "label": "Gemini",
        "url": "https://ai.google.dev/gemini-api/docs/models",
    },
    "xai": {
        "label": "xAI",
        "url": "https://docs.x.ai/developers/models",
    },
    "deepseek": {
        "label": "DeepSeek",
        "url": "https://api-docs.deepseek.com/quick_start/pricing",
    },
    "novita": {
        "label": "NovitaAI",
        "url": "https://novita.ai/docs/api-reference/api-reference-overview",
    },
}
MODEL_CATALOG_FALLBACKS = {
    "openai": [
        ("gpt-5.5", "GPT-5.5"),
        ("gpt-5.2-codex", "GPT-5.2 Codex"),
        ("gpt-5.1-codex", "GPT-5.1 Codex"),
        ("gpt-5.1-codex-max", "GPT-5.1 Codex Max"),
        ("gpt-5-codex", "GPT-5 Codex"),
        ("gpt-5.2", "GPT-5.2"),
        ("gpt-5.1", "GPT-5.1"),
        ("gpt-5", "GPT-5"),
        ("gpt-5.1-codex-mini", "GPT-5.1 Codex mini"),
        ("codex-mini-latest", "Codex mini latest"),
    ],
    "anthropic": [
        ("sonnet", "Sonnet"),
        ("opus", "Opus"),
        ("haiku", "Haiku"),
        ("opusplan", "Opus Plan"),
        ("claude-opus-4-8", "Claude Opus 4.8"),
        ("claude-opus-4-7", "Claude Opus 4.7"),
        ("claude-sonnet-4-6", "Claude Sonnet 4.6"),
        ("claude-sonnet-4-5", "Claude Sonnet 4.5"),
    ],
    "gemini": [
        ("gemini-3.1-pro", "Gemini 3.1 Pro"),
        ("gemini-3.1-flash", "Gemini 3.1 Flash"),
        ("gemini-3-pro-preview", "Gemini 3 Pro Preview"),
        ("gemini-2.5-pro", "Gemini 2.5 Pro"),
        ("gemini-2.5-flash", "Gemini 2.5 Flash"),
        ("gemini-2.5-flash-lite", "Gemini 2.5 Flash Lite"),
    ],
    "xai": [
        ("grok-4-1", "Grok 4.1"),
        ("grok-4-1-fast", "Grok 4.1 Fast"),
        ("grok-4-fast", "Grok 4 Fast"),
        ("grok-code-fast-1", "Grok Code Fast 1"),
    ],
    "deepseek": [
        ("deepseek-chat", "DeepSeek Chat"),
        ("deepseek-reasoner", "DeepSeek Reasoner"),
        ("deepseek-v4-flash", "DeepSeek V4 Flash"),
        ("deepseek-v4-pro", "DeepSeek V4 Pro"),
    ],
    "novita": [
        ("meta-llama/llama-3.3-70b-instruct", "Llama 3.3 70B Instruct"),
        ("qwen/qwen3-coder-480b-a35b-instruct", "Qwen3 Coder"),
        ("deepseek/deepseek-v3.1", "DeepSeek V3.1"),
        ("google/gemma-3-27b-it", "Gemma 3 27B"),
    ],
}
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
SYSTEM_CLAUDE_EXECUTABLE_CANDIDATES = [
    "/usr/local/bin/claude",
    "/usr/bin/claude",
    "/bin/claude",
    "~/.local/bin/claude",
    "/root/.local/bin/claude",
    "/root/.npm-global/bin/claude",
    "/opt/homebrew/bin/claude",
]
SYSTEM_HERMES_EXECUTABLE_CANDIDATES = [
    "/usr/local/bin/hermes-agent",
    "/usr/bin/hermes-agent",
    "/bin/hermes-agent",
    "~/.local/bin/hermes-agent",
    "/root/.local/bin/hermes-agent",
    "/opt/hermes/bin/hermes-agent",
    "/usr/local/bin/hermes",
    "/usr/bin/hermes",
    "~/.local/bin/hermes",
    "/root/.local/bin/hermes",
    "/opt/hermes/bin/hermes",
]
SYSTEM_NPM_EXECUTABLE_CANDIDATES = [
    "/usr/local/bin/npm",
    "/usr/bin/npm",
    "/bin/npm",
    "/opt/conda/bin/npm",
    "/opt/homebrew/bin/npm",
]
MCP_PERMISSION_MODE = "agent_full_control_except_critical_destruction"
MCP_TOOL_ORDER = [
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
]
MCP_TOOL_ALLOWLIST = set(MCP_TOOL_ORDER)
AGENT_FULL_CONTROL_MCP_TOOLS = list(MCP_TOOL_ORDER)
SERVICE_DRAFT_MCP_TOOLS = list(AGENT_FULL_CONTROL_MCP_TOOLS)
COMPOSE_TEMPLATE_MCP_TOOLS = list(AGENT_FULL_CONTROL_MCP_TOOLS)
RUNTIME_INSPECTION_MCP_TOOLS = list(AGENT_FULL_CONTROL_MCP_TOOLS)
RUNTIME_REPAIR_MCP_TOOLS = list(AGENT_FULL_CONTROL_MCP_TOOLS)
MCP_TOOL_SCOPES = {
    "service_draft": SERVICE_DRAFT_MCP_TOOLS,
    "compose_template": COMPOSE_TEMPLATE_MCP_TOOLS,
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
        "claude_code": "Claude Code",
        "hermes": "헤르메스 에이전트",
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
        self._claude_login = None
        self._claude_login_lock = threading.Lock()

    def mcp_tools_for_scope(self, scope, allow_container_actions=True, allow_ssh_command=True):
        tools = list(MCP_TOOL_SCOPES.get(str(scope or ""), AGENT_FULL_CONTROL_MCP_TOOLS))
        result = []
        for tool in tools:
            if tool == "container_action" and allow_container_actions is False:
                continue
            if tool == "ssh_command" and allow_ssh_command is False:
                continue
            if tool in MCP_TOOL_ALLOWLIST and tool not in result:
                result.append(tool)
        return result or ["infra_context"]

    def agent_types(self):
        return list(AGENT_ORDER)

    def _agent_npm_package(self, agent_type, env=None):
        agent_type = self._normalize_agent_type(agent_type)
        run_env = os.environ if env is None else env
        defaults = AGENT_DEFAULTS[agent_type]
        return str(
            run_env.get(defaults.get("npm_package_env") or "")
            or defaults.get("npm_package")
            or ""
        ).strip()

    def _agent_install_method(self, agent_type):
        agent_type = self._normalize_agent_type(agent_type)
        return str(AGENT_DEFAULTS[agent_type].get("install_method") or "npm").strip() or "npm"

    def _agent_install_url(self, agent_type, env=None):
        agent_type = self._normalize_agent_type(agent_type)
        run_env = os.environ if env is None else env
        defaults = AGENT_DEFAULTS[agent_type]
        return str(
            run_env.get(defaults.get("install_url_env") or "")
            or defaults.get("install_url")
            or ""
        ).strip()

    def _agent_install_channel(self, agent_type, env=None):
        agent_type = self._normalize_agent_type(agent_type)
        run_env = os.environ if env is None else env
        defaults = AGENT_DEFAULTS[agent_type]
        return str(
            run_env.get(defaults.get("install_channel_env") or "")
            or defaults.get("install_channel")
            or ""
        ).strip()

    def agent_status(self, agent_type, config=None):
        agent_type = self._normalize_agent_type(agent_type)
        if agent_type == "codex":
            return self.status(config)
        config = self._normalize_agent_config(agent_type, config or {})
        executable = self._agent_executable(agent_type, config)
        available = bool(executable and _is_executable_file(executable))
        version = self._version_for(executable) if available else ""
        login = {
            "status": "ok" if available else "missing",
            "logged_in": available,
            "message": "Agent CLI 실행 파일을 찾았습니다." if available else "Agent CLI 실행 파일을 찾을 수 없습니다.",
            "exit_code": 0 if available else None,
            "checked_at": _utcnow(),
        }
        if agent_type == "claude_code":
            login = self._claude_auth_status(executable, config) if available else {
                "status": "missing",
                "logged_in": False,
                "message": "Claude Code CLI 실행 파일을 찾을 수 없습니다.",
                "exit_code": None,
                "checked_at": _utcnow(),
            }
        hermes_config = self.hermes_config_status(config) if agent_type == "hermes" else None
        return {
            "checked_at": _utcnow(),
            "type": agent_type,
            "label": _provider_label(agent_type),
            "enabled": config["enabled"],
            "model": config["model"],
            "home": config["home"],
            "command_template": config["command_template"],
            "active": {
                "executable": executable or "",
                "source": "system",
                "version": version,
                "available": available,
            },
            "login": login,
            **({"hermes_config": hermes_config} if hermes_config is not None else {}),
        }

    def test_agent(self, agent_type, config=None, prompt=None, env=None):
        agent_type = self._normalize_agent_type(agent_type)
        if agent_type == "codex":
            return self.test_login(config, prompt=prompt, env=env)
        config = self._normalize_agent_config(agent_type, config or {})
        provider = {
            "type": agent_type,
            "label": _provider_label(agent_type),
            "model": config["model"],
            "executable": config["executable"],
            "home": config["home"],
            "command_template": config["command_template"],
            "timeout_seconds": CODEX_TEST_TIMEOUT_SECONDS,
        }
        if agent_type == "hermes":
            provider.update(
                {
                    "provider": config.get("provider") or "openrouter",
                    "api_key_env": config.get("api_key_env") or self._default_hermes_api_key_env(config.get("provider")),
                    "terminal_backend": config.get("terminal_backend") or "local",
                    "terminal_cwd": config.get("terminal_cwd") or str(WORKSPACE_ROOT),
                    "terminal_timeout": int(config.get("terminal_timeout") or 180),
                }
            )
        system = (
            "Return one compact JSON object. Do not use markdown fences. "
            "The object must include ok=true, engine, agent, and model."
        )
        context = {
            "kind": "agent_execution_test",
            "agent": agent_type,
            "operator_prompt": prompt
            or "Confirm this Docker Infra agent execution path with a short JSON response.",
        }
        result = self.complete_json(provider, system, context, env=env)
        return {
            "ok": True,
            "checked_at": _utcnow(),
            "text": result.get("text") or "",
            "metadata": result.get("metadata") or {},
            "status": self.agent_status(agent_type, config),
        }

    def agent_model_catalog(self, agent_type, config=None, env=None):
        agent_type = self._normalize_agent_type(agent_type)
        if agent_type == "codex":
            config = self._normalize_codex_config(config or {})
        else:
            config = self._normalize_agent_config(agent_type, config or {})
        provider = self._model_catalog_provider(agent_type, config)
        source = MODEL_CATALOG_SOURCES.get(provider) or MODEL_CATALOG_SOURCES["openai"]
        items = []
        error = ""
        fetched = False
        try:
            if provider == "openrouter":
                items = self._openrouter_model_items(source["url"])
            else:
                text = self._fetch_model_catalog_text(source["url"])
                items = self._model_items_from_text(provider, text, source["label"])
            fetched = bool(items)
        except Exception as exc:
            error = str(exc)
            items = []
        if not items:
            items = self._fallback_model_items(provider, source["label"])
        items = self._ensure_selected_model_item(items, config.get("model"), source["label"])
        return {
            "checked_at": _utcnow(),
            "agent": agent_type,
            "provider": provider,
            "source": source,
            "items": items,
            "fetched": fetched,
            "fallback": not fetched,
            "error": error,
        }

    def _model_catalog_provider(self, agent_type, config):
        if agent_type == "claude_code":
            return "anthropic"
        if agent_type == "hermes":
            provider = str((config or {}).get("provider") or "openrouter").strip().lower()
            aliases = {
                "openai-api": "openai",
                "openai": "openai",
                "google": "gemini",
                "gemini": "gemini",
                "anthropic": "anthropic",
                "claude": "anthropic",
                "openrouter": "openrouter",
                "xai": "xai",
                "deepseek": "deepseek",
                "novita": "novita",
            }
            return aliases.get(provider, "openrouter")
        return "openai"

    def _fetch_model_catalog_text(self, url):
        request = urlrequest.Request(
            url,
            headers={
                "User-Agent": "DockerInfra/1.0 model-catalog",
                "Accept": "text/html,application/json;q=0.9,*/*;q=0.8",
            },
        )
        with urlrequest.urlopen(request, timeout=AGENT_MODEL_CATALOG_TIMEOUT_SECONDS) as response:
            return response.read(1024 * 1024).decode("utf-8", "replace")

    def _openrouter_model_items(self, url):
        text = self._fetch_model_catalog_text(url)
        payload = json.loads(text)
        rows = payload.get("data") if isinstance(payload, dict) else []
        items = []
        for row in rows or []:
            if not isinstance(row, dict):
                continue
            model_id = str(row.get("id") or "").strip()
            if not model_id:
                continue
            name = str(row.get("name") or model_id).strip()
            description = str(row.get("description") or "").strip()
            context = row.get("context_length")
            if context and not description:
                description = "context %s" % context
            items.append(self._model_item(model_id, name, description, "OpenRouter"))
        return sorted(items, key=lambda item: item["label"].lower())[:500]

    def _model_items_from_text(self, provider, text, badge):
        ids = self._extract_model_ids(provider, text)
        return [self._model_item(model_id, self._model_label(model_id), "", badge) for model_id in ids]

    def _extract_model_ids(self, provider, text):
        normalized = str(text or "")
        ids = set()
        if provider == "openai":
            patterns = [
                r"\bgpt-[a-z0-9][a-z0-9.\-]*(?:-[a-z0-9.\-]+)*\b",
                r"\bcodex-mini-latest\b",
                r"\bo[134](?:-[a-z0-9.\-]+)?\b",
            ]
        elif provider == "anthropic":
            patterns = [
                r"\bclaude-(?:opus|sonnet|haiku)-[a-z0-9.\-]+\b",
                r"\b(?:sonnet|opus|haiku|opusplan)\b",
            ]
        elif provider == "gemini":
            patterns = [r"\bgemini-[0-9][a-z0-9.\-]*\b"]
        elif provider == "xai":
            patterns = [r"\bgrok-[a-z0-9.\-]+\b"]
        elif provider == "deepseek":
            patterns = [r"\bdeepseek-(?:chat|reasoner|v[0-9][a-z0-9.\-]*|[a-z0-9.\-]+)\b"]
        elif provider == "novita":
            patterns = [r"\b[a-z0-9_.-]+/[a-z0-9_.:\-]+\b"]
        else:
            patterns = []
        for pattern in patterns:
            for match in re.findall(pattern, normalized, re.I):
                model_id = str(match or "").strip().lower()
                if self._model_id_allowed(provider, model_id):
                    ids.add(model_id)
        if provider == "anthropic":
            ids.update(["sonnet", "opus", "haiku", "opusplan"])
        return sorted(ids, key=lambda value: (self._model_sort_group(provider, value), value))[:500]

    def _model_id_allowed(self, provider, model_id):
        if not model_id or len(model_id) > 120:
            return False
        if provider == "openai":
            if model_id.startswith("gpt-") or model_id == "codex-mini-latest":
                return True
            return model_id in {"o1", "o1-pro", "o3", "o3-pro", "o4-mini"}
        if provider == "anthropic":
            return model_id in {"sonnet", "opus", "haiku", "opusplan"} or bool(re.match(r"^claude-(opus|sonnet|haiku)-", model_id))
        if provider == "gemini":
            return "deprecated" not in model_id
        if provider == "deepseek":
            return model_id not in {"deepseek-ai", "deepseek-api", "deepseek-integration"}
        if provider == "novita":
            return not model_id.startswith(("_next/", "logo/", "css/"))
        return True

    def _model_sort_group(self, provider, model_id):
        fallback_values = [value for value, _ in MODEL_CATALOG_FALLBACKS.get(provider, [])]
        if model_id in fallback_values:
            return fallback_values.index(model_id)
        return 1000

    def _fallback_model_items(self, provider, badge):
        return [
            self._model_item(model_id, label, "공식 출처를 다시 확인할 수 없을 때 쓰는 기본 후보입니다.", badge)
            for model_id, label in MODEL_CATALOG_FALLBACKS.get(provider, MODEL_CATALOG_FALLBACKS["openai"])
        ]

    def _ensure_selected_model_item(self, items, selected_model, badge):
        selected = str(selected_model or "").strip()
        if not selected:
            return items
        if any(str(item.get("value") or "") == selected for item in items):
            return items
        return [
            self._model_item(selected, "%s (현재 설정)" % selected, "현재 저장된 모델입니다.", badge, current=True),
            *items,
        ]

    def _model_item(self, model_id, label, description, badge, current=False):
        return {
            "value": model_id,
            "label": label or model_id,
            "description": description or "",
            "badge": "현재" if current else badge,
            "badgeClass": (
                "border-amber-200 bg-amber-50 text-amber-700 dark:border-amber-900/70 dark:bg-amber-950/40 dark:text-amber-300"
                if current else
                "border-zinc-200 bg-zinc-50 text-zinc-600 dark:border-zinc-700 dark:bg-zinc-950 dark:text-zinc-300"
            ),
        }

    def _model_label(self, model_id):
        text = str(model_id or "").strip()
        if "/" in text:
            return text
        return " ".join(part.upper() if part in {"gpt", "api"} else part.capitalize() for part in re.split(r"[-_]", text) if part)

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

    def agent_update_status(self, agent_type, config=None, env=None):
        agent_type = self._normalize_agent_type(agent_type)
        if agent_type == "codex":
            config = self._normalize_codex_config(config or {})
            agent_status = self.status(config)
        else:
            config = self._normalize_agent_config(agent_type, config or {})
            agent_status = self.agent_status(agent_type, config)
        active = agent_status.get("active") or {}
        current_raw = active.get("version") or ""
        current_version = self._version_number(current_raw)
        install_method = self._agent_install_method(agent_type)
        if install_method == "native":
            defaults = AGENT_DEFAULTS[agent_type]
            binary = str(defaults.get("binary") or agent_type).strip()
            install_url = self._agent_install_url(agent_type, env=env)
            install_channel = self._agent_install_channel(agent_type, env=env)
            upgrade_policy = str(defaults.get("upgrade_policy") or "manual").strip().lower()
            if upgrade_policy not in {"manual", "automatic"}:
                upgrade_policy = "manual"
            update = {
                "checked_at": _utcnow(),
                "agent": agent_type,
                "label": _provider_label(agent_type),
                "install_method": "script",
                "upgrade_policy": upgrade_policy,
                "package_name": "%s 설치 스크립트" % _provider_label(agent_type),
                "current_version": current_version,
                "current_version_raw": current_raw,
                "latest_version": "",
                "update_available": not bool(current_version),
                "script": {
                    "available": True,
                    "install_url": install_url,
                    "channel": install_channel,
                    "auto_updates": upgrade_policy == "automatic",
                },
                "agent_status": agent_status,
                "commands": {
                    "check": "%s --version" % binary,
                    "install": self.agent_install_script(agent_type, env=env),
                    "upgrade": self.agent_upgrade_script(agent_type, env=env),
                },
            }
            return update
        npm = self._npm_status(env=env)
        package_name = self._agent_npm_package(agent_type, env=env)
        latest_version = self._npm_latest_version(package_name, npm.get("executable"), env=env)
        update_available = bool(
            latest_version
            and (
                not current_version
                or self._compare_versions(current_version, latest_version) < 0
            )
        )
        update = {
            "checked_at": _utcnow(),
            "agent": agent_type,
            "label": _provider_label(agent_type),
            "install_method": "npm",
            "upgrade_policy": "manual",
            "package_name": package_name,
            "current_version": current_version,
            "current_version_raw": current_raw,
            "latest_version": latest_version,
            "update_available": update_available,
            "npm": npm,
            "agent_status": agent_status,
            "commands": {
                "check": f"npm view {package_name} version --json",
                "install": self.agent_install_script(agent_type, env=env),
                "upgrade": f"npm install -g {shlex.quote(package_name)}@latest",
            },
        }
        if agent_type == "codex":
            update["codex_status"] = agent_status
        return update

    def cli_update_status(self, config=None, env=None):
        return self.agent_update_status("codex", config or {}, env=env)

    def upgrade_cli_async(self, config=None, env=None):
        config = self._normalize_codex_config(config or {})
        try:
            update = self.cli_update_status(config, env=env)
        except CodexRuntimeError:
            update = {
                "checked_at": _utcnow(),
                "package_name": CODEX_NPM_PACKAGE,
                "current_version": "",
                "current_version_raw": "",
                "latest_version": "",
                "update_available": True,
                "npm": self._npm_status(env=env),
                "codex_status": self.status(config),
                "commands": {"install": self.agent_install_script("codex")},
            }
        operation = operations.create(
            "codex.cli.upgrade",
            target_type="system",
            target_id="codex-cli",
            message="Codex CLI 설치/업데이트 스크립트를 시작합니다.",
            requested_payload={
                "package_name": CODEX_NPM_PACKAGE,
                "current_version": update.get("current_version"),
                "latest_version": update.get("latest_version"),
                "command": update.get("commands", {}).get("install") or update.get("commands", {}).get("upgrade"),
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

    def install_agent_async(self, agent_type, config=None, env=None):
        agent_type = self._normalize_agent_type(agent_type)
        if agent_type == "codex":
            config = self._normalize_codex_config(config or {})
        else:
            config = self._normalize_agent_config(agent_type, config or {})
        before = self.agent_status(agent_type, config)
        before_update = None
        try:
            before_update = self.agent_update_status(agent_type, config, env=env)
        except Exception:
            before_update = None
        script = self.agent_install_script(agent_type, env=env)
        action = "install"
        if (
            self._agent_install_method(agent_type) == "native"
            and (before_update or {}).get("current_version")
            and str((before_update or {}).get("upgrade_policy") or "manual") == "manual"
        ):
            script = self.agent_upgrade_script(agent_type, env=env)
            action = "upgrade"
        operation = operations.create(
            "ai.agent.install",
            target_type="system",
            target_id=agent_type,
            message="%s 설치/업데이트 스크립트를 시작합니다." % _provider_label(agent_type),
            requested_payload={
                "agent": agent_type,
                "label": _provider_label(agent_type),
                "action": action,
                "script": script,
                "update": before_update,
            },
            metadata={"background": True, "agent": agent_type, "label": _provider_label(agent_type)},
            env=env,
        )

        def worker():
            try:
                self._run_agent_install_operation(operation["id"], agent_type, config, before, before_update, script, env=env)
            except Exception as exc:
                self._finish_agent_install_failure(operation["id"], exc, env=env)

        threading.Thread(target=worker, daemon=True).start()
        return {"operation": operation, "status": before, "update": before_update, "script": script, "action": action}

    def agent_install_script(self, agent_type, env=None):
        agent_type = self._normalize_agent_type(agent_type)
        run_env = os.environ if env is None else env
        defaults = AGENT_DEFAULTS[agent_type]
        override = str(run_env.get(defaults.get("install_script_env") or "") or "").strip()
        if override:
            return override
        if self._agent_install_method(agent_type) == "native":
            install_url = self._agent_install_url(agent_type, env=env)
            install_channel = self._agent_install_channel(agent_type, env=env)
            binary = str(defaults.get("binary") or agent_type).strip()
            cleanup_package = str(defaults.get("cleanup_npm_package") or "").strip()
            cleanup_lines = []
            if cleanup_package:
                cleanup_lines = [
                    f"if command -v npm >/dev/null 2>&1 && npm list -g --depth=0 {shlex.quote(cleanup_package)} >/dev/null 2>&1; then",
                    f'  printf "cleaning previous {_provider_label(agent_type)} install\\n"',
                    f"  npm uninstall -g {shlex.quote(cleanup_package)} >/dev/null",
                    "  hash -r || true",
                    "fi",
                ]
            if not install_url:
                raise CodexRuntimeError(
                    400,
                    "%s 설치 스크립트 URL이 설정되지 않았습니다." % _provider_label(agent_type),
                    "AI_AGENT_INSTALL_URL_REQUIRED",
                    {"agent": agent_type},
                )
            return "\n".join(
                [
                    "set -Eeuo pipefail",
                    "export DEBIAN_FRONTEND=noninteractive",
                    'export HOME="${HOME:-/root}"',
                    'export PATH="$HOME/.local/bin:/root/.local/bin:/usr/local/bin:/usr/bin:/bin:$PATH"',
                    "if ! command -v curl >/dev/null 2>&1; then",
                    "  apt-get update",
                    "  apt-get install -y --no-install-recommends ca-certificates curl",
                    "fi",
                    *cleanup_lines,
                    f"install_url={shlex.quote(install_url)}",
                    f"install_channel={shlex.quote(install_channel)}",
                    'installer="$(mktemp)"',
                    'cleanup() { rm -f "$installer"; }',
                    "trap cleanup EXIT",
                    'curl -fsSL "$install_url" -o "$installer"',
                    'if [ -n "$install_channel" ]; then',
                    '  bash "$installer" "$install_channel"',
                    "else",
                    '  bash "$installer"',
                    "fi",
                    f'agent_bin="$(command -v {shlex.quote(binary)} || true)"',
                    f'if [ -z "$agent_bin" ] && [ -x "$HOME/.local/bin/{shlex.quote(binary)}" ]; then agent_bin="$HOME/.local/bin/{shlex.quote(binary)}"; fi',
                    f'if [ -z "$agent_bin" ] && [ -x "/root/.local/bin/{shlex.quote(binary)}" ]; then agent_bin="/root/.local/bin/{shlex.quote(binary)}"; fi',
                    'test -n "$agent_bin"',
                    '"$agent_bin" --version',
                    'printf "installed executable: %s\\n" "$agent_bin"',
                ]
            )
        package = str(run_env.get(defaults.get("npm_package_env") or "") or defaults.get("npm_package") or "").strip()
        binary = str(defaults.get("binary") or agent_type).strip()
        if not package:
            raise CodexRuntimeError(
                400,
                "%s 설치 패키지가 설정되지 않았습니다." % _provider_label(agent_type),
                "AI_AGENT_INSTALL_PACKAGE_REQUIRED",
                {"agent": agent_type},
            )
        binary_check = f"command -v {shlex.quote(binary)}"
        if agent_type == "hermes":
            binary_check = "command -v hermes-agent || command -v hermes"
        return "\n".join(
            [
                "set -Eeuo pipefail",
                "export DEBIAN_FRONTEND=noninteractive",
                "if ! command -v npm >/dev/null 2>&1; then",
                "  apt-get update",
                "  apt-get install -y --no-install-recommends ca-certificates curl gnupg",
                "  setup_script=\"$(mktemp)\"",
                f"  curl -fsSL \"${{NODE_SOURCE_SETUP_URL:-{NODE_SOURCE_SETUP_URL}}}\" -o \"$setup_script\"",
                "  bash \"$setup_script\"",
                "  rm -f \"$setup_script\"",
                "  apt-get install -y --no-install-recommends nodejs",
                "fi",
                "node --version",
                "npm --version",
                f"npm install -g {shlex.quote(package)}@latest",
                f"agent_bin=\"$({binary_check})\"",
                "test -n \"$agent_bin\"",
                "\"$agent_bin\" --version || true",
                "printf 'installed executable: %s\\n' \"$agent_bin\"",
            ]
        )

    def agent_upgrade_script(self, agent_type, env=None):
        agent_type = self._normalize_agent_type(agent_type)
        if agent_type == "codex":
            return self.agent_install_script("codex", env=env)
        defaults = AGENT_DEFAULTS[agent_type]
        upgrade_command = str(defaults.get("upgrade_command") or "").strip()
        if self._agent_install_method(agent_type) != "native" or not upgrade_command:
            return self.agent_install_script(agent_type, env=env)
        binary = str(defaults.get("binary") or agent_type).strip()
        return "\n".join(
            [
                "set -Eeuo pipefail",
                'export HOME="${HOME:-/root}"',
                'export PATH="$HOME/.local/bin:/root/.local/bin:/usr/local/bin:/usr/bin:/bin:$PATH"',
                f'agent_bin="$(command -v {shlex.quote(binary)} || true)"',
                f'if [ -z "$agent_bin" ] && [ -x "$HOME/.local/bin/{shlex.quote(binary)}" ]; then agent_bin="$HOME/.local/bin/{shlex.quote(binary)}"; fi',
                f'if [ -z "$agent_bin" ] && [ -x "/root/.local/bin/{shlex.quote(binary)}" ]; then agent_bin="/root/.local/bin/{shlex.quote(binary)}"; fi',
                'test -n "$agent_bin"',
                f"{upgrade_command}",
                '"$agent_bin" --version',
                'printf "updated executable: %s\\n" "$agent_bin"',
            ]
        )

    def _run_cli_upgrade_operation(self, operation_id, config, before, env=None):
        current = before.get("current_version") or "미설치"
        latest = before.get("latest_version") or "확인 실패"
        self._append_cli_upgrade_output(
            operation_id,
            f"공식 Codex CLI npm 패키지: {CODEX_NPM_PACKAGE}\n현재 버전: {current}\n최신 버전: {latest}\n설치 방식: 시스템 설정 설치 스크립트\n",
            env=env,
        )
        command = ["bash", "-lc", self.agent_install_script("codex", env=env)]
        result = self._run_logged_command(
            operation_id,
            command,
            timeout=AGENT_INSTALL_TIMEOUT_SECONDS,
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
            message = self._agent_install_failure_message("codex", result)
            operations.transition(operation_id, "failed", message=message, result_payload=result_payload, env=env)
            return
        operations.transition(
            operation_id,
            "succeeded",
            message="Codex CLI 설치/업데이트를 완료했습니다.",
            result_payload=result_payload,
            env=env,
        )

    def _run_agent_install_operation(self, operation_id, agent_type, config, before, before_update, script, env=None):
        self._append_cli_upgrade_output(
            operation_id,
            "%s 설치/업데이트 스크립트\n" % _provider_label(agent_type),
            env=env,
        )
        result = self._run_logged_command(
            operation_id,
            ["bash", "-lc", script],
            timeout=AGENT_INSTALL_TIMEOUT_SECONDS,
            env=env,
        )
        after = self.agent_status(agent_type, config)
        after_update = None
        try:
            after_update = self.agent_update_status(agent_type, config, env=env)
        except Exception:
            after_update = None
        result_payload = {
            "ok": result.get("exit_code") == 0,
            "agent": agent_type,
            "label": _provider_label(agent_type),
            "exit_code": result.get("exit_code"),
            "timed_out": bool(result.get("timed_out")),
            "before": before,
            "after": after,
            "before_update": before_update,
            "after_update": after_update,
        }
        if result.get("exit_code") != 0:
            operations.transition(
                operation_id,
                "failed",
                message=self._agent_install_failure_message(agent_type, result),
                result_payload=result_payload,
                env=env,
            )
            return
        operations.transition(
            operation_id,
            "succeeded",
            message="%s 설치/업데이트를 완료했습니다." % _provider_label(agent_type),
            result_payload=result_payload,
            env=env,
        )

    def _finish_agent_install_failure(self, operation_id, exc, env=None):
        message = getattr(exc, "message", str(exc))
        result_payload = {
            "ok": False,
            "error_code": getattr(exc, "error_code", "AI_AGENT_INSTALL_FAILED"),
        }
        details = getattr(exc, "details", None)
        if isinstance(details, dict):
            result_payload.update(details)
        try:
            operations.append_output(operation_id, message + "\n", stream="stderr", env=env)
            operations.transition(operation_id, "failed", message=message, result_payload=result_payload, env=env)
        except Exception:
            pass

    def _finish_cli_upgrade_failure(self, operation_id, exc, env=None):
        message = getattr(exc, "message", str(exc))
        result_payload = {
            "ok": False,
            "error_code": getattr(exc, "error_code", "CODEX_CLI_INSTALL_FAILED"),
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
                    cwd=str(WORKSPACE_ROOT),
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

    def start_claude_login(self, config=None):
        config = self._normalize_agent_config("claude_code", config or {})
        executable = self._claude_login_executable(config)
        command = [executable, "auth", "login"]
        deduplicated_public = None
        with self._claude_login_lock:
            current = self._claude_login
            if current and self._claude_login_running(current):
                deduplicated_public = self._claude_login_public(current)
            if deduplicated_public is None:
                self._claude_login = None
        if deduplicated_public is not None:
            return {"claude_login": deduplicated_public, "agent_status": self.agent_status("claude_code", config), "deduplicated": True}

        with self._claude_login_lock:
            session = {
                "id": str(uuid.uuid4()),
                "status": "starting",
                "started_at": _utcnow(),
                "finished_at": None,
                "verification_uri": "",
                "message": "Claude Code 브라우저 로그인을 시작합니다.",
                "output": [],
                "exit_code": None,
                "command": "claude auth login",
                "requires_code": False,
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
                    cwd=str(WORKSPACE_ROOT),
                    env=self._agent_env({"type": "claude_code", "home": config.get("home")}),
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
                    "Claude Code 브라우저 로그인을 시작할 수 없습니다: %s" % exc,
                    "CLAUDE_LOGIN_START_FAILED",
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
            self._claude_login = session
            threading.Thread(target=self._read_claude_login_output, args=(session,), daemon=True).start()

        deadline = time.time() + CLAUDE_LOGIN_START_TIMEOUT_SECONDS
        while time.time() < deadline:
            with self._claude_login_lock:
                current = self._claude_login_public(self._claude_login) if self._claude_login else {}
            if current.get("verification_uri") or current.get("status") in {"failed", "succeeded", "waiting_for_code"}:
                break
            time.sleep(0.1)
        return self.claude_login_status(config)

    def claude_login_status(self, config=None):
        config = self._normalize_agent_config("claude_code", config or {})
        with self._claude_login_lock:
            session = self._claude_login
            if session:
                self._refresh_claude_login_locked(session)
                public = self._claude_login_public(session)
            else:
                public = None
        agent_status = self.agent_status("claude_code", config)
        if public and (agent_status.get("login") or {}).get("logged_in") and public.get("status") in {"starting", "waiting_for_user", "waiting_for_code", "verifying"}:
            with self._claude_login_lock:
                session = self._claude_login
                if session and session.get("id") == public.get("id"):
                    session["status"] = "succeeded"
                    session["message"] = "Claude Code 로그인이 완료되었습니다."
                    session["finished_at"] = session.get("finished_at") or _utcnow()
                    public = self._claude_login_public(session)
        return {"claude_login": public, "agent_status": agent_status}

    def submit_claude_login_code(self, code, config=None):
        config = self._normalize_agent_config("claude_code", config or {})
        value = str(code or "").strip()
        if not value:
            raise CodexRuntimeError(400, "Claude Code 로그인 코드를 입력하세요.", "CLAUDE_LOGIN_CODE_REQUIRED")
        with self._claude_login_lock:
            session = self._claude_login
            if not session or not self._claude_login_running(session):
                raise CodexRuntimeError(409, "진행 중인 Claude Code 브라우저 로그인이 없습니다.", "CLAUDE_LOGIN_NOT_RUNNING")
            master_fd = session.get("pty_master_fd")
            if master_fd is None:
                raise CodexRuntimeError(409, "Claude Code 로그인 입력 채널을 찾을 수 없습니다.", "CLAUDE_LOGIN_INPUT_UNAVAILABLE")
            try:
                os.write(master_fd, (value + "\n").encode("utf-8"))
            except Exception as exc:
                raise CodexRuntimeError(502, "Claude Code 로그인 코드를 전달할 수 없습니다: %s" % exc, "CLAUDE_LOGIN_CODE_SUBMIT_FAILED")
            session["status"] = "verifying"
            session["message"] = "Claude Code 로그인 코드를 확인하고 있습니다."
            session["submitted_code"] = True
            public = self._claude_login_public(session)
        return {"claude_login": public, "agent_status": self.agent_status("claude_code", config)}

    def cancel_claude_login(self, config=None):
        config = self._normalize_agent_config("claude_code", config or {})
        with self._claude_login_lock:
            session = self._claude_login
            if session and self._claude_login_running(session):
                try:
                    session["process"].terminate()
                except Exception:
                    pass
                session["status"] = "canceled"
                session["message"] = "Claude Code 브라우저 로그인을 취소했습니다."
                session["finished_at"] = _utcnow()
            public = self._claude_login_public(session) if session else None
        return {"claude_login": public, "agent_status": self.agent_status("claude_code", config)}

    def _device_login_running(self, session):
        process = (session or {}).get("process")
        return bool(process and process.poll() is None)

    def _claude_login_running(self, session):
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
            code_match = re.search(r"\b[A-Z0-9]{4,}-[A-Z0-9]{4,}\b", text, re.I)
            if not code_match:
                code_match = re.search(r"(?:user\s*code|device\s*code|code)\s*[:=]?\s*([A-Z0-9]{6,12})\b", text, re.I)
            if not code_match and session.get("verification_uri"):
                code_match = re.search(r"(?:user_code|code)=([A-Z0-9-]{4,20})", session.get("verification_uri"), re.I)
            if code_match:
                session["user_code"] = (code_match.group(1) if code_match.lastindex else code_match.group(0)).upper()
            if session.get("user_code") or session.get("verification_uri"):
                if session.get("status") == "starting":
                    session["status"] = "waiting_for_user"
                session["message"] = "브라우저에서 Codex device 로그인을 완료해주세요."
            lowered = text.lower()
            if "logged in" in lowered or "login successful" in lowered or "authenticated" in lowered:
                session["status"] = "succeeded"
                session["message"] = "Codex 로그인이 완료되었습니다."

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

    def _read_claude_login_output(self, session):
        process = session.get("process")
        if not process:
            return
        master_fd = session.get("pty_master_fd")
        if master_fd is not None:
            self._read_claude_login_pty(session, process, master_fd)
        elif process.stdout:
            self._read_claude_login_pipe(session, process)
        exit_code = process.wait()
        with self._claude_login_lock:
            if self._claude_login and self._claude_login.get("id") == session.get("id"):
                session["exit_code"] = exit_code
                session["finished_at"] = _utcnow()
                if session.get("status") != "canceled":
                    session["status"] = "succeeded" if exit_code == 0 else "failed"
                    session["message"] = "Claude Code 로그인이 완료되었습니다." if exit_code == 0 else "Claude Code 브라우저 로그인이 종료되었습니다."

    def _read_claude_login_pipe(self, session, process):
        try:
            for line in process.stdout:
                self._append_claude_login_output(session, line)
        except Exception as exc:
            self._append_claude_login_output(session, "Claude Code 로그인 출력 수집 오류: %s" % exc)

    def _read_claude_login_pty(self, session, process, master_fd):
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
                    self._append_claude_login_output(session, line)
        except Exception as exc:
            self._append_claude_login_output(session, "Claude Code 로그인 출력 수집 오류: %s" % exc)
        finally:
            if buffer.strip():
                self._append_claude_login_output(session, buffer)
            try:
                os.close(master_fd)
            except OSError:
                pass

    def _append_claude_login_output(self, session, line):
        text = re.sub(r"\x1b\[[0-?]*[ -/]*[@-~]", "", str(line or "")).strip()
        if not text:
            return
        with self._claude_login_lock:
            if self._claude_login and self._claude_login.get("id") != session.get("id"):
                return
            output = session.setdefault("output", [])
            output.append(text)
            session["output"] = output[-80:]
            url_match = re.search(r"https://\S+", text)
            if url_match:
                session["verification_uri"] = url_match.group(0).rstrip(".,)")
            lowered = text.lower()
            if "paste code" in lowered or "code here" in lowered:
                session["requires_code"] = True
                if session.get("status") in {"starting", "waiting_for_user"}:
                    session["status"] = "waiting_for_code"
                session["message"] = "브라우저에서 인증한 뒤 표시되는 코드를 입력하세요."
            elif session.get("verification_uri") and session.get("status") == "starting":
                session["status"] = "waiting_for_user"
                session["message"] = "브라우저에서 Claude Code 로그인을 진행하세요."
            if "successfully" in lowered and "installed" not in lowered:
                session["status"] = "succeeded"
                session["message"] = "Claude Code 로그인이 완료되었습니다."
            if "logged in" in lowered or "login successful" in lowered or "authenticated" in lowered:
                session["status"] = "succeeded"
                session["message"] = "Claude Code 로그인이 완료되었습니다."

    def _refresh_claude_login_locked(self, session):
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
        if session.get("status") in {"starting", "waiting_for_user", "waiting_for_code", "verifying"}:
            session["status"] = "succeeded" if exit_code == 0 else "failed"
            session["message"] = "Claude Code 로그인이 완료되었습니다." if exit_code == 0 else "Claude Code 브라우저 로그인이 종료되었습니다."

    def _claude_login_public(self, session):
        if not session:
            return None
        return {
            "id": session.get("id"),
            "status": session.get("status"),
            "started_at": session.get("started_at"),
            "finished_at": session.get("finished_at"),
            "verification_uri": session.get("verification_uri") or "",
            "requires_code": bool(session.get("requires_code")),
            "submitted_code": bool(session.get("submitted_code")),
            "message": session.get("message") or "",
            "exit_code": session.get("exit_code"),
            "command": session.get("command") or "claude auth login",
            "output": (session.get("output") or [])[-20:],
        }

    def _normalize_codex_config(self, config):
        config = dict(config or {})
        model = str(config.get("model") or CODEX_LOGIN_DEFAULT_MODEL).strip() or CODEX_LOGIN_DEFAULT_MODEL
        reasoning_effort = str(config.get("reasoning_effort") or CODEX_LOGIN_DEFAULT_REASONING_EFFORT).strip().lower()
        if reasoning_effort not in CODEX_REASONING_EFFORTS:
            reasoning_effort = CODEX_LOGIN_DEFAULT_REASONING_EFFORT
        return {
            "enabled": self._as_bool(config.get("enabled")),
            "cli_mode": "system",
            "model": model,
            "reasoning_effort": reasoning_effort,
            "codex_home": "",
        }

    def _normalize_agent_type(self, agent_type):
        agent_type = str(agent_type or "").strip().lower().replace("-", "_")
        aliases = {
            "claude": "claude_code",
            "claudecode": "claude_code",
            "claude_code": "claude_code",
            "hermes_agent": "hermes",
            "hermes": "hermes",
            "codex": "codex",
        }
        agent_type = aliases.get(agent_type, agent_type)
        if agent_type not in AGENT_TYPES:
            raise CodexRuntimeError(400, "지원하지 않는 AI Agent입니다.", "AI_AGENT_NOT_SUPPORTED")
        return agent_type

    def _normalize_agent_config(self, agent_type, config):
        agent_type = self._normalize_agent_type(agent_type)
        if agent_type == "codex":
            normalized = self._normalize_codex_config(config or {})
            normalized.update({"type": "codex", "home": normalized.get("codex_home") or "", "executable": ""})
            return normalized
        config = dict(config or {})
        defaults = AGENT_DEFAULTS[agent_type]
        model = str(config.get("model") or defaults["model"]).strip() or defaults["model"]
        normalized = {
            "type": agent_type,
            "enabled": self._as_bool(config.get("enabled")),
            "model": model,
            "executable": "",
            "home": str(config.get("home") or self._default_agent_home(agent_type)),
            "command_template": defaults.get("default_command_template", ""),
        }
        if agent_type == "hermes":
            provider = str(config.get("provider") or "openrouter").strip() or "openrouter"
            api_key_env = str(config.get("api_key_env") or self._default_hermes_api_key_env(provider)).strip().upper()
            terminal_backend = str(config.get("terminal_backend") or "local").strip().lower() or "local"
            if terminal_backend not in {"local", "docker", "ssh", "modal", "daytona", "singularity"}:
                terminal_backend = "local"
            terminal_timeout = self._safe_int(config.get("terminal_timeout"), 180, 10, 7200)
            normalized.update(
                {
                    "provider": provider,
                    "api_key_env": api_key_env,
                    "terminal_backend": terminal_backend,
                    "terminal_cwd": str(config.get("terminal_cwd") or WORKSPACE_ROOT),
                    "terminal_timeout": terminal_timeout,
                }
            )
        return normalized

    def _safe_int(self, value, default, minimum=None, maximum=None):
        try:
            number = int(value)
        except Exception:
            number = int(default)
        if minimum is not None:
            number = max(int(minimum), number)
        if maximum is not None:
            number = min(int(maximum), number)
        return number

    def _default_hermes_api_key_env(self, provider):
        key_map = {
            "openrouter": "OPENROUTER_API_KEY",
            "anthropic": "ANTHROPIC_API_KEY",
            "openai-api": "OPENAI_API_KEY",
            "openai": "OPENAI_API_KEY",
            "gemini": "GOOGLE_API_KEY",
            "google": "GOOGLE_API_KEY",
            "xai": "XAI_API_KEY",
            "deepseek": "DEEPSEEK_API_KEY",
            "novita": "NOVITA_API_KEY",
        }
        return key_map.get(str(provider or "").strip().lower(), "OPENROUTER_API_KEY")

    def _hermes_api_key_env_names(self, provider, api_key_env=None):
        names = []
        for name in [api_key_env, self._default_hermes_api_key_env(provider)]:
            name = str(name or "").strip().upper()
            if name and name not in names:
                names.append(name)
        if str(provider or "").strip().lower() in {"gemini", "google"}:
            for name in ["GOOGLE_API_KEY", "GEMINI_API_KEY"]:
                if name not in names:
                    names.append(name)
        return names

    def _hermes_api_key_configured(self, env_path, provider, api_key_env):
        for key in self._hermes_api_key_env_names(provider, api_key_env):
            if self._env_file_has_key(env_path, key) or os.environ.get(key):
                return True
        return False

    def _default_agent_home(self, agent_type):
        agent_type = self._normalize_agent_type(agent_type)
        if agent_type == "codex":
            return ""
        env_keys = {
            "claude_code": ["DOCKER_INFRA_CLAUDE_CODE_HOME", "CLAUDE_HOME"],
            "hermes": ["DOCKER_INFRA_HERMES_AGENT_HOME", "HERMES_HOME"],
        }.get(agent_type, [])
        for env_key in env_keys:
            configured = str(os.environ.get(env_key) or "").strip()
            if configured:
                return str(Path(configured).expanduser())
        return str(AGENT_RUNTIME_HOME_ROOT / agent_type)

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

    def _agent_executable(self, agent_type, config=None):
        agent_type = self._normalize_agent_type(agent_type)
        config = self._normalize_agent_config(agent_type, config or {})
        if agent_type == "codex":
            return self._system_codex_executable()
        explicit = os.environ.get(self._agent_env_bin_key(agent_type))
        if explicit:
            candidate = Path(explicit).expanduser()
            if _is_executable_file(candidate):
                return str(candidate)
        path_name = str(AGENT_DEFAULTS[agent_type].get("binary") or ("claude" if agent_type == "claude_code" else "hermes-agent"))
        path_executable = shutil.which(path_name, path=_augmented_path())
        if path_executable and _is_executable_file(path_executable):
            return path_executable
        if agent_type == "hermes":
            fallback = shutil.which("hermes", path=_augmented_path())
            if fallback and _is_executable_file(fallback):
                return fallback
        candidates = SYSTEM_CLAUDE_EXECUTABLE_CANDIDATES if agent_type == "claude_code" else SYSTEM_HERMES_EXECUTABLE_CANDIDATES
        for candidate_path in candidates:
            candidate = Path(candidate_path).expanduser()
            if _is_executable_file(candidate):
                return str(candidate)
        return ""

    def _agent_env_bin_key(self, agent_type):
        return {
            "claude_code": "DOCKER_INFRA_CLAUDE_CODE_BIN",
            "hermes": "DOCKER_INFRA_HERMES_AGENT_BIN",
        }.get(agent_type, "DOCKER_INFRA_SYSTEM_CODEX_BIN")

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

    def _npm_latest_version(self, package_name=CODEX_NPM_PACKAGE, npm_executable=None, env=None):
        package_name = str(package_name or CODEX_NPM_PACKAGE).strip()
        executable = npm_executable or self._npm_executable()
        if not executable or not _is_executable_file(executable):
            raise CodexRuntimeError(
                503,
                "npm 실행 파일을 찾을 수 없습니다.",
                "CODEX_NPM_EXECUTABLE_NOT_FOUND",
                {"npm_executable": executable or ""},
            )
        result = self._command_result(
            [executable, "view", package_name, "version", "--json"],
            env=env,
            timeout=CODEX_NPM_VIEW_TIMEOUT_SECONDS,
        )
        if result.get("exit_code") != 0:
            raise CodexRuntimeError(
                502,
                "npm에서 %s 최신 버전을 확인할 수 없습니다." % package_name,
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

    def _claude_login_executable(self, config):
        config = self._normalize_agent_config("claude_code", config or {})
        executable = self._agent_executable("claude_code", config)
        if executable and _is_executable_file(executable):
            return executable
        raise CodexRuntimeError(
            503,
            "Claude Code CLI를 찾을 수 없습니다. 먼저 설치 스크립트를 실행하세요.",
            "CLAUDE_LOGIN_EXECUTABLE_NOT_FOUND",
            {"path_claude": executable},
        )

    def _claude_auth_status(self, executable, config):
        if not executable or not _is_executable_file(executable):
            return {
                "status": "missing",
                "logged_in": False,
                "message": "Claude Code CLI 실행 파일을 찾을 수 없습니다.",
                "exit_code": None,
                "checked_at": _utcnow(),
            }
        run_env = self._agent_env({"type": "claude_code", "home": (config or {}).get("home")})
        result = self._command_result([executable, "auth", "status", "--text"], env=run_env, timeout=CODEX_STATUS_TIMEOUT_SECONDS)
        output = ((result.get("stdout") or "") + "\n" + (result.get("stderr") or result.get("error") or "")).strip()
        lowered = output.lower()
        logged_in = result.get("exit_code") == 0 and "not logged in" not in lowered
        if logged_in:
            status = "ok"
            message = output.splitlines()[0] if output else "Claude Code 로그인이 확인되었습니다."
        elif "not logged in" in lowered:
            status = "unauthenticated"
            message = output.splitlines()[0] if output else "Claude Code 로그인이 필요합니다."
        elif result.get("timeout"):
            status = "error"
            message = "Claude Code 로그인 상태 확인 시간이 초과되었습니다."
        else:
            status = "error"
            message = output.splitlines()[0] if output else "Claude Code 로그인 상태를 확인할 수 없습니다."
        return {
            "status": status,
            "logged_in": logged_in,
            "message": message,
            "exit_code": result.get("exit_code"),
            "checked_at": _utcnow(),
        }

    def hermes_config_status(self, config=None):
        config = self._normalize_agent_config("hermes", config or {})
        home = Path(config.get("home") or self._default_agent_home("hermes")).expanduser()
        env_path = home / ".env"
        config_path = home / "config.yaml"
        api_key_env = str(config.get("api_key_env") or "").strip().upper()
        api_key_configured = self._hermes_api_key_configured(env_path, config.get("provider"), api_key_env)
        return {
            "home": str(home),
            "config_path": str(config_path),
            "env_path": str(env_path),
            "provider": config.get("provider") or "",
            "model": config.get("model") or "",
            "api_key_env": api_key_env,
            "api_key_configured": api_key_configured,
            "terminal_backend": config.get("terminal_backend") or "local",
            "terminal_cwd": config.get("terminal_cwd") or str(WORKSPACE_ROOT),
            "terminal_timeout": int(config.get("terminal_timeout") or 180),
        }

    def apply_hermes_settings(self, config=None, secret_value=None):
        config = self._normalize_agent_config("hermes", config or {})
        status = self.hermes_config_status(config)
        home = Path(status["home"]).expanduser()
        home.mkdir(parents=True, exist_ok=True)
        config_path = Path(status["config_path"])
        env_path = Path(status["env_path"])
        self._write_hermes_config(config_path, config)
        api_key_env = str(config.get("api_key_env") or self._default_hermes_api_key_env(config.get("provider"))).strip().upper()
        if api_key_env and str(secret_value or "").strip():
            for key in self._hermes_api_key_env_names(config.get("provider"), api_key_env):
                self._upsert_env_file_value(env_path, key, str(secret_value).strip())
        self._upsert_env_file_value(env_path, "HERMES_INFERENCE_PROVIDER", config.get("provider") or "openrouter")
        self._upsert_env_file_value(env_path, "HERMES_INFERENCE_MODEL", config.get("model") or AGENT_DEFAULTS["hermes"]["model"])
        self._upsert_env_file_value(env_path, "TERMINAL_ENV", config.get("terminal_backend") or "local")
        self._upsert_env_file_value(env_path, "TERMINAL_CWD", config.get("terminal_cwd") or str(WORKSPACE_ROOT))
        self._upsert_env_file_value(env_path, "TERMINAL_TIMEOUT", str(int(config.get("terminal_timeout") or 180)))
        return {
            "applied": True,
            "hermes_config": self.hermes_config_status(config),
            "agent_status": self.agent_status("hermes", config),
        }

    def _write_hermes_config(self, config_path, config):
        payload = self._read_hermes_config_file(config_path)
        payload["model"] = {
            **(payload.get("model") if isinstance(payload.get("model"), dict) else {}),
            "provider": config.get("provider") or "openrouter",
            "default": config.get("model") or AGENT_DEFAULTS["hermes"]["model"],
        }
        payload["terminal"] = {
            **(payload.get("terminal") if isinstance(payload.get("terminal"), dict) else {}),
            "backend": config.get("terminal_backend") or "local",
            "cwd": config.get("terminal_cwd") or str(WORKSPACE_ROOT),
            "timeout": int(config.get("terminal_timeout") or 180),
        }
        servers = payload.setdefault("mcp_servers", {})
        servers["docker_infra"] = self._hermes_mcp_server_config("", AGENT_FULL_CONTROL_MCP_TOOLS)
        self._write_hermes_config_file(config_path, payload)

    def _env_file_has_key(self, env_path, key):
        try:
            for line in Path(env_path).read_text(encoding="utf-8").splitlines():
                text = line.strip()
                if not text or text.startswith("#") or "=" not in text:
                    continue
                name, value = text.split("=", 1)
                if name.strip() == key and value.strip():
                    return True
        except FileNotFoundError:
            return False
        except Exception:
            return False
        return False

    def _upsert_env_file_value(self, env_path, key, value):
        env_path = Path(env_path)
        env_path.parent.mkdir(parents=True, exist_ok=True)
        lines = []
        replaced = False
        try:
            lines = env_path.read_text(encoding="utf-8").splitlines()
        except FileNotFoundError:
            lines = []
        next_lines = []
        for line in lines:
            if line.strip().startswith(key + "="):
                next_lines.append("%s=%s" % (key, shlex.quote(value)))
                replaced = True
            else:
                next_lines.append(line)
        if not replaced:
            next_lines.append("%s=%s" % (key, shlex.quote(value)))
        env_path.write_text("\n".join(next_lines).rstrip() + "\n", encoding="utf-8")
        try:
            os.chmod(env_path, 0o600)
        except OSError:
            pass

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
            timeout_message = f"install command timed out after {timeout}s\n"
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

    def _agent_install_failure_message(self, agent_type, result):
        label = _provider_label(agent_type)
        if result.get("timed_out"):
            return "%s 설치/업데이트 시간이 초과되었습니다." % label
        text = (result.get("stderr") or result.get("stdout") or "").strip()
        if not text:
            return "%s 설치/업데이트 명령이 실패했습니다." % label
        lines = [line.strip() for line in text.splitlines() if line.strip()]
        return "%s 설치/업데이트 명령이 실패했습니다: %s" % (label, (lines[-1] if lines else text)[:500])

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
        if not run_env.get("CODEX_HOME"):
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
        negative = any(token in lowered for token in ["not logged", "not authenticated", "not signed in", "no login"])
        positive = any(token in lowered for token in ["logged in", "authenticated", "signed in", "login status: ok"])
        logged_in = result.get("exit_code") == 0 and not negative and (positive or not output)
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
        session_info = self._request_session(provider, request_context)
        mcp_enabled_tools = self._enabled_mcp_tools(request_context)
        prompt_context = self._prompt_context(request_context, mcp_enabled_tools)
        CODEX_RUNTIME_ROOT.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(prefix="run-", dir=str(CODEX_RUNTIME_ROOT)) as runtime_home:
            runtime_home_path = Path(runtime_home)
            mcp_context_path = runtime_home_path / "docker-infra-mcp-context.json"
            mcp_request_context = dict(request_context)
            mcp_request_context["session"] = session_info
            mcp_request_context["mcp_enabled_tools"] = mcp_enabled_tools
            mcp_request_context["ai_request_summary"] = prompt_context
            mcp_context = self._mcp_context(env=env, request_context=mcp_request_context)
            last_message_path = runtime_home_path / "last-message.txt"
            mcp_context_path.write_text(
                json.dumps(mcp_context, ensure_ascii=False),
                encoding="utf-8",
            )
            prompt = self._prompt(system, prompt_context, provider, mcp_enabled_tools)
            if provider["type"] == "codex":
                result = self._run_codex(
                    provider,
                    runtime_home_path,
                    last_message_path,
                    prompt,
                    mcp_context_path,
                    mcp_enabled_tools,
                    session_info,
                )
                engine = "codex"
                cli_mode = provider.get("cli_mode") or "system"
            else:
                result = self._run_agent(
                    provider,
                    runtime_home_path,
                    last_message_path,
                    prompt,
                    mcp_context_path,
                    mcp_enabled_tools,
                    session_info,
                )
                engine = "agent"
                cli_mode = "agent"
            result_session = result.get("session") if isinstance(result.get("session"), dict) else session_info
            metadata = {
                "engine": engine,
                "provider": provider["type"],
                "provider_id": provider["provider_id"],
                "provider_label": _provider_label(provider["type"]),
                "model": provider["model"],
                "reasoning_effort": provider.get("reasoning_effort") or "",
                "cli_mode": cli_mode,
                "executable": result.get("executable") or "",
                "codex_exit_code": result["exit_code"],
                "session": result_session,
                "session_id": result_session.get("session_id") or "",
                "provider_session_id": result_session.get("provider_session_id") or "",
                "session_resumed": bool(result_session.get("resume")),
            }
            return {"text": result["text"], "metadata": metadata}

    def complete_json_stream(self, provider, system, context, env=None):
        provider = self._normalize_provider(provider or {})
        request_context = context if isinstance(context, dict) else {}
        session_info = self._request_session(provider, request_context)
        mcp_enabled_tools = self._enabled_mcp_tools(request_context)
        prompt_context = self._prompt_context(request_context, mcp_enabled_tools)
        CODEX_RUNTIME_ROOT.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(prefix="run-", dir=str(CODEX_RUNTIME_ROOT)) as runtime_home:
            runtime_home_path = Path(runtime_home)
            mcp_context_path = runtime_home_path / "docker-infra-mcp-context.json"
            mcp_request_context = dict(request_context)
            mcp_request_context["session"] = session_info
            mcp_request_context["mcp_enabled_tools"] = mcp_enabled_tools
            mcp_request_context["ai_request_summary"] = prompt_context
            mcp_context = self._mcp_context(env=env, request_context=mcp_request_context)
            last_message_path = runtime_home_path / "last-message.txt"
            mcp_context_path.write_text(
                json.dumps(mcp_context, ensure_ascii=False),
                encoding="utf-8",
            )
            prompt = self._prompt(system, prompt_context, provider, mcp_enabled_tools)
            if provider["type"] == "codex":
                result = yield from self._run_codex_stream(
                    provider,
                    runtime_home_path,
                    last_message_path,
                    prompt,
                    mcp_context_path,
                    mcp_enabled_tools,
                    session_info,
                )
                engine = "codex"
                cli_mode = provider.get("cli_mode") or "system"
            else:
                yield {
                    "type": "runtime_event",
                    "event": {"type": "agent.execution.started", "provider": provider["type"]},
                }
                result = yield from self._run_agent_stream(
                    provider,
                    runtime_home_path,
                    last_message_path,
                    prompt,
                    mcp_context_path,
                    mcp_enabled_tools,
                    session_info,
                )
                yield {
                    "type": "runtime_event",
                    "event": {"type": "agent.execution.completed", "provider": provider["type"]},
                }
                engine = "agent"
                cli_mode = "agent"
            result_session = result.get("session") if isinstance(result.get("session"), dict) else session_info
            metadata = {
                "engine": engine,
                "provider": provider["type"],
                "provider_id": provider["provider_id"],
                "provider_label": _provider_label(provider["type"]),
                "model": provider["model"],
                "reasoning_effort": provider.get("reasoning_effort") or "",
                "cli_mode": cli_mode,
                "executable": result.get("executable") or "",
                "codex_exit_code": result["exit_code"],
                "session": result_session,
                "session_id": result_session.get("session_id") or "",
                "provider_session_id": result_session.get("provider_session_id") or "",
                "session_resumed": bool(result_session.get("resume")),
            }
            yield {"type": "result", "result": {"text": result["text"], "metadata": metadata}}

    def _request_session(self, provider, request_context):
        request_context = request_context if isinstance(request_context, dict) else {}
        session = request_context.get("session") if isinstance(request_context.get("session"), dict) else {}
        session_id = self._normalize_session_id(session.get("session_id") or request_context.get("session_id"))
        provider_session_id = self._normalize_session_id(session.get("provider_session_id"))
        return {
            "session_id": session_id,
            "provider_session_id": provider_session_id,
            "agent_type": provider.get("type") or "",
            "resume": bool(provider_session_id and session.get("resume")),
            "title": self._clean_session_title(session.get("title") or request_context.get("message")),
        }

    def _normalize_session_id(self, value):
        text = str(value or "").strip()[:160]
        if not text:
            return ""
        return re.sub(r"[^A-Za-z0-9_.:-]", "", text)[:160]

    def _clean_session_title(self, value):
        text = re.sub(r"\s+", " ", str(value or "").strip())
        return text[:160] or "AI Agent 세션"

    def _normalize_provider(self, provider):
        provider = dict(provider or {})
        provider_type = self._normalize_agent_type(provider.get("type"))

        model = provider.get("model")
        if not model:
            raise CodexRuntimeError(400, "AI Agent 실행에 사용할 모델이 없습니다.", "AI_AGENT_MODEL_REQUIRED")

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

        config = self._normalize_agent_config(provider_type, provider)
        executable = self._agent_executable(provider_type, config)
        if not executable:
            raise CodexRuntimeError(
                503,
                "%s 실행 파일을 찾을 수 없습니다." % _provider_label(provider_type),
                "AI_AGENT_EXECUTABLE_NOT_FOUND",
                {"agent": provider_type, "env_key": self._agent_env_bin_key(provider_type)},
            )
        provider.update(
            {
                "type": provider_type,
                "provider_id": "%s-agent" % provider_type.replace("_", "-"),
                "provider_name": _provider_label(provider_type),
                "model": config["model"],
                "executable": executable,
                "home": config["home"],
                "command_template": config["command_template"],
                **(
                    {
                        "provider": config.get("provider") or "openrouter",
                        "api_key_env": config.get("api_key_env") or self._default_hermes_api_key_env(config.get("provider")),
                        "terminal_backend": config.get("terminal_backend") or "local",
                        "terminal_cwd": config.get("terminal_cwd") or str(WORKSPACE_ROOT),
                        "terminal_timeout": int(config.get("terminal_timeout") or 180),
                    }
                    if provider_type == "hermes"
                    else {}
                ),
                "env_key": None,
                "env_value": None,
            }
        )
        return provider

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
            requested = AGENT_FULL_CONTROL_MCP_TOOLS

        terminal_actions = request_context.get("terminal_actions") if isinstance(request_context.get("terminal_actions"), dict) else {}
        allow_container_actions = terminal_actions.get("allow_container_actions") is not False
        allow_ssh_command = guidance.get("allow_ssh_command") is not False and permission.get("allow_ssh_command") is not False
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
            "permission_mode": MCP_PERMISSION_MODE,
            "instruction": "Use docker_infra.infra_context for registered servers, DDNS endpoints, runtime values, the detailed MCP contract, and this request summary before making infra claims.",
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

    def _mcp_context(self, env=None, request_context=None):
        request_context = request_context if isinstance(request_context, dict) else {}
        rows = []
        try:
            for item in nodes_model.list(env=env) or []:
                node = nodes_model.detail(item["id"], env=env)
                credential = node.get("credential") or {}
                deployment_mode = "swarm" if str(node.get("swarm_node_id") or "").strip() else "compose"
                rows.append(
                    {
                        "id": node.get("id"),
                        "name": node.get("name"),
                        "host": node.get("host"),
                        "role": node.get("role"),
                        "status": node.get("status"),
                        "swarm_node_id": node.get("swarm_node_id"),
                        "swarm_connected": deployment_mode == "swarm",
                        "deployment_mode": deployment_mode,
                        "network": compose_rules.default_network_name(deployment_mode),
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
            "mcp_permission_mode": MCP_PERMISSION_MODE,
            "allowed_probe_hosts": self._allowed_probe_hosts(request_context, rows),
            "terminal_actions": request_context.get("terminal_actions") or {},
            "runtime_values": {
                "overlay_network": compose_rules.OVERLAY_NETWORK,
                "bridge_network": compose_rules.BRIDGE_NETWORK,
                "network_selection": "Use docker_infra_overlay only for Swarm-connected targets; use docker_infra_bridge for non-Swarm Compose targets.",
                "volume_destruction_policy": "For repair, migration, release, rollback, and redeploy work, never use docker compose down --volumes, docker volume rm/prune, or docker system prune --volumes. Service deletion is the only Docker Infra flow that removes Compose named volumes.",
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
        execution_note = "You are running inside Docker Infra through the %s agent CLI.\n" % _provider_label(provider.get("type"))
        tool_note = (
            "Use the docker_infra MCP tools enabled for this request. "
            f"Enabled docker_infra MCP tools: {enabled_label}.\n"
            "Docker Infra MCP permission mode is agent full control except critical destruction: do not delete Docker Infra itself, stop/remove its control services or containers, shut down/reboot the OS, wipe disks, or recursively delete OS-critical paths.\n"
            "Persistent Docker volumes are protected during agent work: do not run docker compose down --volumes, docker volume rm/prune, or docker system prune --volumes for repair, migration, release, rollback, or redeploy tasks.\n"
            "The request context embedded below is compacted; do not assume omitted runtime logs are unavailable. "
            "Call docker_infra.infra_context for Docker Infra's registered servers, DDNS endpoints, runtime values, detailed MCP contract, and request summary when needed.\n"
            "If another MCP tool is unavailable or not exposed in this session, do not report that as an operator-facing error; "
            "fall back to the enabled tools and provided Docker Infra context.\n\n"
        )
        return (
            execution_note
            + "Return only one JSON object that satisfies the system and context below. "
            "Do not include markdown fences and do not describe the answer outside JSON.\n"
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
            "mcp_servers.docker_infra.env.DOCKER_INFRA_MCP_PERMISSION_MODE": MCP_PERMISSION_MODE,
        }
        args = []
        for key, value in overrides.items():
            if isinstance(value, list):
                encoded = _toml_string_list(value)
            else:
                encoded = _json_string(value)
            args.extend(["-c", f"{key}={encoded}"])
        return args

    def _agent_mcp_config(self, mcp_context_path, enabled_tools):
        return {
            "mcpServers": {
                "docker_infra": {
                    "command": _python_executable(),
                    "args": [str(MCP_SCRIPT)],
                    "env": {
                        "DOCKER_INFRA_ROOT": str(WORKSPACE_ROOT),
                        "DOCKER_INFRA_MCP_CONTEXT_FILE": str(mcp_context_path),
                        "DOCKER_INFRA_MCP_TIMEOUT_SECONDS": "30",
                        "DOCKER_INFRA_MCP_PERMISSION_MODE": MCP_PERMISSION_MODE,
                    },
                    "enabled_tools": enabled_tools,
                }
            }
        }

    def _hermes_mcp_server_config(self, mcp_context_path, enabled_tools):
        return {
            "command": _python_executable(),
            "args": [str(MCP_SCRIPT)],
            "env": {
                "DOCKER_INFRA_ROOT": str(WORKSPACE_ROOT),
                "DOCKER_INFRA_MCP_CONTEXT_FILE": str(mcp_context_path),
                "DOCKER_INFRA_MCP_TIMEOUT_SECONDS": "30",
                "DOCKER_INFRA_MCP_PERMISSION_MODE": MCP_PERMISSION_MODE,
            },
            "tools": {"include": list(enabled_tools or [])},
        }

    def _read_hermes_config_file(self, config_path):
        try:
            data = yaml.safe_load(Path(config_path).read_text(encoding="utf-8"))
            return data if isinstance(data, dict) else {}
        except FileNotFoundError:
            return {}
        except Exception:
            return {}

    def _write_hermes_config_file(self, config_path, data):
        config_path = Path(config_path)
        config_path.parent.mkdir(parents=True, exist_ok=True)
        config_path.write_text(yaml.safe_dump(data, sort_keys=False, allow_unicode=False) + "\n", encoding="utf-8")
        try:
            os.chmod(config_path, 0o600)
        except OSError:
            pass

    def _write_hermes_runtime_mcp_config(self, provider, mcp_context_path, enabled_tools):
        home = Path(provider.get("home") or self._default_agent_home("hermes")).expanduser()
        config_path = home / "config.yaml"
        data = self._read_hermes_config_file(config_path)
        servers = data.setdefault("mcp_servers", {})
        servers["docker_infra"] = self._hermes_mcp_server_config(mcp_context_path, enabled_tools)
        self._write_hermes_config_file(config_path, data)

    def _render_agent_command(self, provider, mcp_config_path, mcp_context_path, last_message_path, prompt="", session_info=None):
        template = provider.get("command_template") or AGENT_DEFAULTS[provider["type"]].get("default_command_template")
        session_args = self._agent_session_args(provider, session_info)
        values = {
            "executable": shlex.quote(provider["executable"]),
            "provider": shlex.quote(str(provider.get("provider") or provider.get("type") or "")),
            "model": shlex.quote(str(provider.get("model") or "")),
            "prompt": shlex.quote(str(prompt or "")),
            "mcp_config": shlex.quote(str(mcp_config_path)),
            "mcp_context": shlex.quote(str(mcp_context_path)),
            "workspace": shlex.quote(str(WORKSPACE_ROOT)),
            "last_message": shlex.quote(str(last_message_path)),
            "session_id": shlex.quote(str((session_info or {}).get("session_id") or "")),
            "provider_session_id": shlex.quote(str((session_info or {}).get("provider_session_id") or "")),
            "session_args": " ".join(shlex.quote(arg) for arg in session_args),
        }
        try:
            rendered = template.format(**values)
        except Exception as exc:
            raise CodexRuntimeError(
                400,
                "Agent 실행 명령 템플릿을 해석할 수 없습니다: %s" % exc,
                "AI_AGENT_COMMAND_TEMPLATE_INVALID",
                {"agent": provider.get("type")},
            )
        return shlex.split(rendered)

    def _agent_session_args(self, provider, session_info=None):
        session_info = session_info if isinstance(session_info, dict) else {}
        if (provider or {}).get("type") != "claude_code":
            return []
        provider_session_id = self._normalize_session_id(session_info.get("provider_session_id"))
        session_id = self._normalize_session_id(session_info.get("session_id"))
        if provider_session_id and session_info.get("resume"):
            return ["--resume", provider_session_id]
        if session_id and self._is_uuid(session_id):
            return ["--session-id", session_id]
        return []

    def _is_uuid(self, value):
        try:
            uuid.UUID(str(value or ""))
            return True
        except Exception:
            return False

    def _agent_env(self, provider):
        run_env = _subprocess_env()
        home = str(provider.get("home") or "").strip()
        if home:
            try:
                Path(home).expanduser().mkdir(parents=True, exist_ok=True)
            except Exception:
                pass
        if provider.get("type") == "claude_code" and home:
            run_env["CLAUDE_CONFIG_DIR"] = str(Path(home).expanduser())
        if provider.get("type") == "hermes" and home:
            hermes_home = Path(home).expanduser()
            run_env["HERMES_HOME"] = str(hermes_home)
            run_env.update(self._read_env_file_values(hermes_home / ".env"))
            run_env["HERMES_INFERENCE_PROVIDER"] = str(provider.get("provider") or "openrouter")
            run_env["HERMES_INFERENCE_MODEL"] = str(provider.get("model") or "")
            run_env["TERMINAL_ENV"] = str(provider.get("terminal_backend") or "local")
            run_env["TERMINAL_CWD"] = str(provider.get("terminal_cwd") or WORKSPACE_ROOT)
            run_env["TERMINAL_TIMEOUT"] = str(int(provider.get("terminal_timeout") or 180))
            if run_env.get("GEMINI_API_KEY") and not run_env.get("GOOGLE_API_KEY"):
                run_env["GOOGLE_API_KEY"] = run_env["GEMINI_API_KEY"]
            if run_env.get("GOOGLE_API_KEY") and not run_env.get("GEMINI_API_KEY"):
                run_env["GEMINI_API_KEY"] = run_env["GOOGLE_API_KEY"]
        run_env["NO_COLOR"] = "1"
        return run_env

    def _read_env_file_values(self, env_path):
        values = {}
        try:
            lines = Path(env_path).read_text(encoding="utf-8").splitlines()
        except FileNotFoundError:
            return values
        except Exception:
            return values
        for line in lines:
            text = line.strip()
            if not text or text.startswith("#") or "=" not in text:
                continue
            key, value = text.split("=", 1)
            key = key.strip()
            if not key:
                continue
            try:
                parsed = shlex.split(value, posix=True)
                values[key] = parsed[0] if parsed else ""
            except Exception:
                values[key] = value.strip().strip("\"'")
        return values

    def _agent_output_text(self, stdout, last_message_path):
        text = last_message_path.read_text(encoding="utf-8").strip() if last_message_path.exists() else ""
        if text:
            return text
        event_text = self._last_json_event_output(stdout)
        if event_text:
            return event_text
        raw = str(stdout or "").strip()
        try:
            parsed = json.loads(raw)
        except Exception:
            return raw
        if isinstance(parsed, dict):
            for key in ["text", "message", "result", "response", "content"]:
                value = parsed.get(key)
                if isinstance(value, str) and value.strip():
                    return value.strip()
            if isinstance(parsed.get("content"), list):
                chunks = []
                for item in parsed.get("content") or []:
                    if isinstance(item, dict):
                        chunks.append(str(item.get("text") or item.get("content") or ""))
                    elif item:
                        chunks.append(str(item))
                return "".join(chunks).strip()
        return raw

    def _run_codex_stream(self, provider, runtime_home, last_message_path, prompt, mcp_context_path, enabled_tools, session_info=None):
        executable = self._codex_login_executable(provider)
        config_args = self._codex_login_config_args(provider, mcp_context_path, enabled_tools)
        session_info = session_info if isinstance(session_info, dict) else {}
        provider_session_id = self._normalize_session_id(session_info.get("provider_session_id"))
        resume_session = bool(provider_session_id and session_info.get("resume"))
        global_args = [
            "--sandbox",
            "danger-full-access",
            "-C",
            str(WORKSPACE_ROOT),
        ]
        exec_args = [
            "--json",
            "--skip-git-repo-check",
            "--ignore-user-config",
            *config_args,
            "-m",
            provider["model"],
            "--output-last-message",
            str(last_message_path),
        ]
        if resume_session:
            command = [executable, *global_args, "exec", "resume", *exec_args, provider_session_id, "-"]
        else:
            command = [executable, *global_args, "exec", *exec_args, "-"]
        run_env = self._codex_env(provider)
        run_env["NO_COLOR"] = "1"
        timeout_seconds = int(provider.get("timeout_seconds") or CODEX_TIMEOUT_SECONDS)
        try:
            process = subprocess.Popen(
                command,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                bufsize=1,
                env=run_env,
            )
        except OSError as exc:
            raise CodexRuntimeError(
                502,
                "Codex 실행을 시작할 수 없습니다.",
                "CODEX_EXEC_START_FAILED",
                {"stderr": str(exc), "command": command},
            )

        stream_queue = queue.Queue()
        stdout_chunks = []
        stderr_chunks = []

        def consume_stdout():
            try:
                for line in process.stdout or []:
                    stream_queue.put(("stdout", line))
            finally:
                stream_queue.put(("stdout_done", None))

        def consume_stderr():
            try:
                for line in process.stderr or []:
                    stream_queue.put(("stderr", line))
            finally:
                stream_queue.put(("stderr_done", None))

        def write_stdin():
            try:
                if process.stdin:
                    process.stdin.write(prompt)
                    process.stdin.close()
            except BrokenPipeError:
                pass
            except OSError:
                pass

        threading.Thread(target=consume_stdout, daemon=True).start()
        threading.Thread(target=consume_stderr, daemon=True).start()
        threading.Thread(target=write_stdin, daemon=True).start()

        stdout_done = False
        stderr_done = False
        started_at = time.time()
        last_progress_phase = ""
        last_progress_at = 0
        deadline = time.time() + timeout_seconds
        while not (stdout_done and stderr_done):
            remaining = deadline - time.time()
            if remaining <= 0:
                process.kill()
                raise CodexRuntimeError(
                    504,
                    "Codex 실행 시간이 초과되었습니다.",
                    "CODEX_EXEC_TIMEOUT",
                    {"stdout": _trim("".join(stdout_chunks)), "stderr": _trim("".join(stderr_chunks)), "command": command},
                )
            try:
                kind, payload = stream_queue.get(timeout=min(1.0, max(0.1, remaining)))
            except queue.Empty:
                now = time.time()
                if now - last_progress_at >= 6:
                    elapsed_seconds = max(1, int(now - started_at))
                    phases = [
                        ("context", "Agent가 Docker Infra 화면과 대화 맥락을 실행 컨텍스트로 정리하고 있습니다."),
                        ("tool_match", "Agent가 MCP/API 후보와 요청 의도를 대조하고 있습니다."),
                        ("runtime_lookup", "Agent가 필요한 런타임 조회 결과를 기다리고 있습니다."),
                        ("answer_shape", "Agent가 조회 결과를 최종 답변 구조로 정리하고 있습니다."),
                    ]
                    phase, message = phases[min(len(phases) - 1, elapsed_seconds // 18)]
                    if phase != last_progress_phase or now - last_progress_at >= 12:
                        last_progress_phase = phase
                        last_progress_at = now
                        yield {
                            "type": "runtime_event",
                            "event": {
                                "type": "agent.progress",
                                "phase": phase,
                                "message": message,
                                "elapsed_seconds": elapsed_seconds,
                            },
                        }
                continue
            if kind == "stdout_done":
                stdout_done = True
                continue
            if kind == "stderr_done":
                stderr_done = True
                continue
            if kind == "stderr":
                stderr_chunks.append(payload)
                continue
            if kind != "stdout":
                continue
            stdout_chunks.append(payload)
            line = str(payload or "").strip()
            if not line:
                continue
            try:
                event = json.loads(line)
            except Exception:
                yield {"type": "runtime_output", "stream": "stdout", "text": _trim(line, 1000)}
                continue
            if isinstance(event, dict):
                yield {"type": "runtime_event", "event": event}

        try:
            return_code = process.wait(timeout=3)
        except subprocess.TimeoutExpired:
            process.kill()
            raise CodexRuntimeError(
                504,
                "Codex 실행 종료를 확인할 수 없습니다.",
                "CODEX_EXEC_TIMEOUT",
                {"stdout": _trim("".join(stdout_chunks)), "stderr": _trim("".join(stderr_chunks)), "command": command},
            )
        stdout = "".join(stdout_chunks)
        stderr = "".join(stderr_chunks)
        text = last_message_path.read_text(encoding="utf-8").strip() if last_message_path.exists() else ""
        if return_code != 0:
            raise CodexRuntimeError(
                502,
                "Codex 실행이 실패했습니다.",
                "CODEX_EXEC_FAILED",
                {
                    "exit_code": return_code,
                    "stdout": _trim(stdout),
                    "stderr": _trim(stderr),
                    "command": command,
                },
            )
        if not text:
            text = self._last_json_event_output(stdout)
        if not text:
            raise CodexRuntimeError(
                502,
                "Codex 최종 응답이 비어 있습니다.",
                "CODEX_EMPTY_RESPONSE",
                {"stdout": _trim(stdout), "stderr": _trim(stderr), "command": command},
            )
        result_session = dict(session_info or {})
        extracted_session_id = self._json_event_session_id(stdout)
        result_session["provider_session_id"] = extracted_session_id or provider_session_id
        result_session["resume"] = resume_session
        return {"text": text, "exit_code": return_code, "executable": executable, "session": result_session}

    def _run_agent(self, provider, runtime_home, last_message_path, prompt, mcp_context_path, enabled_tools, session_info=None):
        mcp_config_path = runtime_home / "docker-infra-agent-mcp.json"
        mcp_config_path.write_text(
            json.dumps(self._agent_mcp_config(mcp_context_path, enabled_tools), ensure_ascii=False),
            encoding="utf-8",
        )
        if provider.get("type") == "hermes":
            self._write_hermes_runtime_mcp_config(provider, mcp_context_path, enabled_tools)
        command = self._render_agent_command(
            provider,
            mcp_config_path,
            mcp_context_path,
            last_message_path,
            prompt=prompt,
            session_info=session_info,
        )
        template = provider.get("command_template") or AGENT_DEFAULTS[provider["type"]].get("default_command_template")
        session_args = self._agent_session_args(provider, session_info)
        if session_args and "{session_args}" not in template and "--session-id" not in command and "--resume" not in command:
            command.extend(session_args)
        try:
            completed = subprocess.run(
                command,
                input=prompt,
                capture_output=True,
                text=True,
                timeout=int(provider.get("timeout_seconds") or CODEX_TIMEOUT_SECONDS),
                check=False,
                cwd=str(WORKSPACE_ROOT),
                env=self._agent_env(provider),
            )
        except subprocess.TimeoutExpired as exc:
            raise CodexRuntimeError(
                504,
                "%s 실행 시간이 초과되었습니다." % _provider_label(provider["type"]),
                "AI_AGENT_EXEC_TIMEOUT",
                {"stdout": _trim(exc.stdout), "stderr": _trim(exc.stderr), "command": command},
            )

        text = self._agent_output_text(completed.stdout, last_message_path)
        if completed.returncode != 0:
            raise CodexRuntimeError(
                502,
                "%s 실행이 실패했습니다." % _provider_label(provider["type"]),
                "AI_AGENT_EXEC_FAILED",
                {
                    "exit_code": completed.returncode,
                    "stdout": _trim(completed.stdout),
                    "stderr": _trim(completed.stderr),
                    "command": command,
                },
            )
        if not text:
            raise CodexRuntimeError(
                502,
                "%s 최종 응답이 비어 있습니다." % _provider_label(provider["type"]),
                "AI_AGENT_EMPTY_RESPONSE",
                {"stdout": _trim(completed.stdout), "stderr": _trim(completed.stderr), "command": command},
            )
        result_session = dict(session_info or {})
        if provider.get("type") == "claude_code":
            result_session["provider_session_id"] = (
                result_session.get("provider_session_id")
                or (result_session.get("session_id") if self._is_uuid(result_session.get("session_id")) else "")
            )
        return {"text": text, "exit_code": completed.returncode, "executable": provider["executable"], "session": result_session}

    def _run_agent_stream(self, provider, runtime_home, last_message_path, prompt, mcp_context_path, enabled_tools, session_info=None):
        mcp_config_path = runtime_home / "docker-infra-agent-mcp.json"
        mcp_config_path.write_text(
            json.dumps(self._agent_mcp_config(mcp_context_path, enabled_tools), ensure_ascii=False),
            encoding="utf-8",
        )
        if provider.get("type") == "hermes":
            self._write_hermes_runtime_mcp_config(provider, mcp_context_path, enabled_tools)
        command = self._agent_stream_command(provider, mcp_config_path, mcp_context_path, last_message_path, prompt, session_info)
        timeout_seconds = int(provider.get("timeout_seconds") or CODEX_TIMEOUT_SECONDS)
        try:
            process = subprocess.Popen(
                command,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                bufsize=1,
                cwd=str(WORKSPACE_ROOT),
                env=self._agent_env(provider),
            )
        except OSError as exc:
            raise CodexRuntimeError(
                502,
                "%s 실행을 시작할 수 없습니다." % _provider_label(provider["type"]),
                "AI_AGENT_EXEC_START_FAILED",
                {"stderr": str(exc), "command": command},
            )

        stream_queue = queue.Queue()
        stdout_chunks = []
        stderr_chunks = []

        def consume_stdout():
            try:
                for line in process.stdout or []:
                    stream_queue.put(("stdout", line))
            finally:
                stream_queue.put(("stdout_done", None))

        def consume_stderr():
            try:
                for line in process.stderr or []:
                    stream_queue.put(("stderr", line))
            finally:
                stream_queue.put(("stderr_done", None))

        def write_stdin():
            try:
                if process.stdin:
                    process.stdin.write(prompt)
                    process.stdin.close()
            except BrokenPipeError:
                pass
            except OSError:
                pass

        threading.Thread(target=consume_stdout, daemon=True).start()
        threading.Thread(target=consume_stderr, daemon=True).start()
        threading.Thread(target=write_stdin, daemon=True).start()

        stdout_done = False
        stderr_done = False
        deadline = time.time() + timeout_seconds
        while not (stdout_done and stderr_done):
            remaining = deadline - time.time()
            if remaining <= 0:
                process.kill()
                raise CodexRuntimeError(
                    504,
                    "%s 실행 시간이 초과되었습니다." % _provider_label(provider["type"]),
                    "AI_AGENT_EXEC_TIMEOUT",
                    {"stdout": _trim("".join(stdout_chunks)), "stderr": _trim("".join(stderr_chunks)), "command": command},
                )
            try:
                kind, payload = stream_queue.get(timeout=min(1.0, max(0.1, remaining)))
            except queue.Empty:
                continue
            if kind == "stdout_done":
                stdout_done = True
                continue
            if kind == "stderr_done":
                stderr_done = True
                continue
            if kind == "stderr":
                stderr_chunks.append(payload)
                continue
            if kind != "stdout":
                continue
            stdout_chunks.append(payload)
            line = str(payload or "").strip()
            if not line:
                continue
            try:
                event = json.loads(line)
            except Exception:
                yield {"type": "runtime_output", "stream": "stdout", "text": _trim(line, 1000)}
                continue
            if isinstance(event, dict):
                yield {"type": "runtime_event", "event": event}

        try:
            return_code = process.wait(timeout=3)
        except subprocess.TimeoutExpired:
            process.kill()
            raise CodexRuntimeError(
                504,
                "%s 실행 종료를 확인할 수 없습니다." % _provider_label(provider["type"]),
                "AI_AGENT_EXEC_TIMEOUT",
                {"stdout": _trim("".join(stdout_chunks)), "stderr": _trim("".join(stderr_chunks)), "command": command},
            )
        stdout = "".join(stdout_chunks)
        stderr = "".join(stderr_chunks)
        text = self._agent_output_text(stdout, last_message_path)
        if return_code != 0:
            raise CodexRuntimeError(
                502,
                "%s 실행이 실패했습니다." % _provider_label(provider["type"]),
                "AI_AGENT_EXEC_FAILED",
                {
                    "exit_code": return_code,
                    "stdout": _trim(stdout),
                    "stderr": _trim(stderr),
                    "command": command,
                },
            )
        if not text:
            raise CodexRuntimeError(
                502,
                "%s 최종 응답이 비어 있습니다." % _provider_label(provider["type"]),
                "AI_AGENT_EMPTY_RESPONSE",
                {"stdout": _trim(stdout), "stderr": _trim(stderr), "command": command},
            )
        result_session = dict(session_info or {})
        if provider.get("type") == "claude_code":
            result_session["provider_session_id"] = (
                result_session.get("provider_session_id")
                or self._json_event_session_id(stdout)
                or (result_session.get("session_id") if self._is_uuid(result_session.get("session_id")) else "")
            )
        return {"text": text, "exit_code": return_code, "executable": provider["executable"], "session": result_session}

    def _agent_stream_command(self, provider, mcp_config_path, mcp_context_path, last_message_path, prompt="", session_info=None):
        if provider.get("type") == "claude_code":
            command = [
                provider["executable"],
                "--print",
                "--output-format",
                "stream-json",
                "--verbose",
                "--include-partial-messages",
                "--mcp-config",
                str(mcp_config_path),
                "--model",
                str(provider.get("model") or ""),
                *self._agent_session_args(provider, session_info),
                "--dangerously-skip-permissions",
            ]
            return [arg for arg in command if arg != ""]
        return self._render_agent_command(provider, mcp_config_path, mcp_context_path, last_message_path, prompt=prompt, session_info=session_info)

    def _run_codex(self, provider, runtime_home, last_message_path, prompt, mcp_context_path, enabled_tools, session_info=None):
        executable = self._codex_login_executable(provider)
        config_args = self._codex_login_config_args(provider, mcp_context_path, enabled_tools)
        session_info = session_info if isinstance(session_info, dict) else {}
        provider_session_id = self._normalize_session_id(session_info.get("provider_session_id"))
        resume_session = bool(provider_session_id and session_info.get("resume"))
        global_args = [
            "--sandbox",
            "danger-full-access",
            "-C",
            str(WORKSPACE_ROOT),
        ]
        exec_args = [
            "--json",
            "--skip-git-repo-check",
            "--ignore-user-config",
            *config_args,
            "-m",
            provider["model"],
            "--output-last-message",
            str(last_message_path),
        ]
        if resume_session:
            command = [executable, *global_args, "exec", "resume", *exec_args, provider_session_id, "-"]
        else:
            command = [executable, *global_args, "exec", *exec_args, "-"]
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
        result_session = dict(session_info or {})
        extracted_session_id = self._json_event_session_id(completed.stdout)
        result_session["provider_session_id"] = extracted_session_id or provider_session_id
        result_session["resume"] = resume_session
        return {"text": text, "exit_code": completed.returncode, "executable": executable, "session": result_session}

    def _json_event_session_id(self, stdout):
        result = ""
        for line in (stdout or "").splitlines():
            try:
                event = json.loads(line)
            except Exception:
                continue
            candidate = self._session_id_from_event(event)
            if candidate:
                result = candidate
        return result

    def _session_id_from_event(self, value):
        if isinstance(value, dict):
            for key in ["session_id", "sessionId", "conversation_id", "conversationId", "thread_id", "threadId"]:
                candidate = self._normalize_session_id(value.get(key))
                if candidate:
                    return candidate
            for key in ["session", "conversation", "thread"]:
                nested = value.get(key)
                if isinstance(nested, dict):
                    candidate = self._normalize_session_id(nested.get("id") or nested.get("session_id"))
                    if candidate:
                        return candidate
            event_type = str(value.get("type") or "")
            if event_type.startswith(("session.", "conversation.", "thread.")):
                candidate = self._normalize_session_id(value.get("id"))
                if candidate:
                    return candidate
            for nested in value.values():
                candidate = self._session_id_from_event(nested)
                if candidate:
                    return candidate
        if isinstance(value, list):
            for item in value:
                candidate = self._session_id_from_event(item)
                if candidate:
                    return candidate
        return ""

    def _last_json_event_output(self, stdout):
        result = ""
        for line in (stdout or "").splitlines():
            try:
                event = json.loads(line)
            except Exception:
                continue
            if event.get("type") == "result":
                value = event.get("result") or event.get("message") or event.get("text")
                if isinstance(value, str) and value.strip():
                    result = value
                structured = event.get("structured_output")
                if not result and isinstance(structured, (dict, list)):
                    result = json.dumps(structured, ensure_ascii=False)
            if event.get("type") == "assistant":
                message = event.get("message") if isinstance(event.get("message"), dict) else {}
                text = self._json_event_content_text(message.get("content"))
                if text:
                    result = text
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

    def _json_event_content_text(self, value):
        if isinstance(value, str):
            return value.strip()
        if not isinstance(value, list):
            return ""
        chunks = []
        for item in value:
            if isinstance(item, dict):
                if item.get("type") in {"text", "output_text"}:
                    chunks.append(str(item.get("text") or ""))
                elif isinstance(item.get("content"), str):
                    chunks.append(str(item.get("content")))
            elif item:
                chunks.append(str(item))
        return "".join(chunks).strip()


Model = CodexRuntime()
