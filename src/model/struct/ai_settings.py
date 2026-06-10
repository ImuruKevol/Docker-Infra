import datetime


settings = wiz.model("struct/settings")

AI_CONFIG_KEY = "ai.config"
AI_UPDATE_STATUS_KEY = "ai.agent_updates"

AGENT_ORDER = ["codex", "claude_code", "hermes"]
AGENT_LABELS = {
    "codex": "Codex",
    "claude_code": "Claude Code",
    "hermes": "헤르메스 에이전트",
}
AGENT_DESCRIPTIONS = {
    "codex": "Codex 로그인 세션과 Docker Infra MCP로 실행합니다.",
    "claude_code": "Claude Code CLI와 Docker Infra MCP로 실행합니다.",
    "hermes": "헤르메스 에이전트 CLI와 Docker Infra MCP로 실행합니다.",
}
SOURCES = {
    "codex_cli": "https://www.npmjs.com/package/@openai/codex",
    "claude_code": "https://code.claude.com/docs/en/setup",
    "hermes_agent": "local-agent",
}

DEFAULT_CONFIG = {
    "default_agent": "",
    "codex": {
        "enabled": False,
        "cli_mode": "system",
        "model": "gpt-5.5",
        "reasoning_effort": "xhigh",
    },
    "claude_code": {
        "enabled": False,
        "model": "sonnet",
    },
    "hermes": {
        "enabled": False,
        "model": "default",
        "provider": "openrouter",
        "terminal_backend": "local",
        "terminal_cwd": "/root/docker-infra",
        "terminal_timeout": 180,
    },
}


class AISettingsError(Exception):
    def __init__(self, status_code, message, error_code, **extra):
        super().__init__(message)
        self.status_code = status_code
        self.message = message
        self.error_code = error_code
        self.extra = extra


def utcnow():
    return datetime.datetime.now(datetime.timezone.utc).isoformat().replace("+00:00", "Z")


def _as_bool(value, default=False):
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"1", "true", "yes", "on"}


def _str(value, default=""):
    if value is None:
        return default
    return str(value).strip()


def _reasoning_effort(value):
    effort = _str(value, DEFAULT_CONFIG["codex"]["reasoning_effort"]).lower()
    if effort not in {"low", "medium", "high", "xhigh"}:
        return DEFAULT_CONFIG["codex"]["reasoning_effort"]
    return effort


def _safe_int(value, default, minimum=None, maximum=None):
    try:
        number = int(value)
    except Exception:
        number = int(default)
    if minimum is not None:
        number = max(int(minimum), number)
    if maximum is not None:
        number = min(int(maximum), number)
    return number


def _deep_merge(base, value):
    merged = dict(base)
    if isinstance(value, dict) is False:
        return merged
    for key, item in value.items():
        if isinstance(merged.get(key), dict) and isinstance(item, dict):
            merged[key] = _deep_merge(merged[key], item)
        else:
            merged[key] = item
    return merged


def _agent_key(value):
    agent = _str(value).lower().replace("-", "_")
    if agent in {"claude", "claudecode"}:
        return "claude_code"
    if agent == "hermes_agent":
        return "hermes"
    return agent


def _default_agent(value, config):
    agent = _agent_key(value)
    if agent in AGENT_ORDER and (config.get(agent) or {}).get("enabled"):
        return agent
    return next((name for name in AGENT_ORDER if (config.get(name) or {}).get("enabled")), "")


def _agent_badge_class(agent, level="ok"):
    if level == "error":
        return "border-rose-200 bg-rose-50 text-rose-700 dark:border-rose-900/70 dark:bg-rose-950/40 dark:text-rose-300"
    if level == "warning":
        return "border-amber-200 bg-amber-50 text-amber-700 dark:border-amber-900/70 dark:bg-amber-950/40 dark:text-amber-300"
    if agent == "codex":
        return "border-fuchsia-200 bg-fuchsia-50 text-fuchsia-700 dark:border-fuchsia-900/70 dark:bg-fuchsia-950/40 dark:text-fuchsia-300"
    if agent == "claude_code":
        return "border-sky-200 bg-sky-50 text-sky-700 dark:border-sky-900/70 dark:bg-sky-950/40 dark:text-sky-300"
    if agent == "hermes":
        return "border-emerald-200 bg-emerald-50 text-emerald-700 dark:border-emerald-900/70 dark:bg-emerald-950/40 dark:text-emerald-300"
    return "border-zinc-200 bg-zinc-50 text-zinc-600 dark:border-zinc-700 dark:bg-zinc-950 dark:text-zinc-300"


class AISettings:
    AISettingsError = AISettingsError

    def _saved_config(self, env=None):
        row = settings.get(AI_CONFIG_KEY, env=env)
        value = (row or {}).get("value")
        return _deep_merge(DEFAULT_CONFIG, value if isinstance(value, dict) else {})

    def _saved_agent_updates(self, env=None):
        row = settings.get(AI_UPDATE_STATUS_KEY, env=env)
        value = (row or {}).get("value")
        if not isinstance(value, dict):
            return {}
        return {
            agent: dict(value.get(agent) or {})
            for agent in AGENT_ORDER
            if isinstance(value.get(agent), dict)
        }

    def _normalize_config(self, value):
        config = _deep_merge(DEFAULT_CONFIG, value if isinstance(value, dict) else {})
        codex = config.get("codex") or {}
        claude = config.get("claude_code") or {}
        hermes = config.get("hermes") or {}
        hermes_provider = _str(hermes.get("provider"), DEFAULT_CONFIG["hermes"]["provider"]) or DEFAULT_CONFIG["hermes"]["provider"]
        hermes_terminal_backend = _str(hermes.get("terminal_backend"), DEFAULT_CONFIG["hermes"]["terminal_backend"]).lower()
        if hermes_terminal_backend not in {"local", "docker", "ssh", "modal", "daytona", "singularity"}:
            hermes_terminal_backend = DEFAULT_CONFIG["hermes"]["terminal_backend"]
        normalized = {
            "codex": {
                "enabled": _as_bool(codex.get("enabled")),
                "cli_mode": "system",
                "model": _str(codex.get("model"), DEFAULT_CONFIG["codex"]["model"]) or DEFAULT_CONFIG["codex"]["model"],
                "reasoning_effort": _reasoning_effort(codex.get("reasoning_effort")),
            },
            "claude_code": {
                "enabled": _as_bool(claude.get("enabled")),
                "model": _str(claude.get("model"), DEFAULT_CONFIG["claude_code"]["model"]) or DEFAULT_CONFIG["claude_code"]["model"],
            },
            "hermes": {
                "enabled": _as_bool(hermes.get("enabled")),
                "model": _str(hermes.get("model"), DEFAULT_CONFIG["hermes"]["model"]) or DEFAULT_CONFIG["hermes"]["model"],
                "provider": hermes_provider,
                "terminal_backend": hermes_terminal_backend,
                "terminal_cwd": _str(hermes.get("terminal_cwd"), DEFAULT_CONFIG["hermes"]["terminal_cwd"]) or DEFAULT_CONFIG["hermes"]["terminal_cwd"],
                "terminal_timeout": _safe_int(hermes.get("terminal_timeout"), DEFAULT_CONFIG["hermes"]["terminal_timeout"], 10, 7200),
            },
        }
        normalized["default_agent"] = _default_agent(config.get("default_agent"), normalized)
        return normalized

    def _persist_config(self, config, env=None):
        settings.upsert(
            AI_CONFIG_KEY,
            value=config,
            value_type="json",
            description="AI agent settings",
            metadata={"group": "ai", "kind": "agent_config"},
            env=env,
        )

    def _persist_agent_updates(self, updates, env=None):
        settings.upsert(
            AI_UPDATE_STATUS_KEY,
            value=updates,
            value_type="json",
            description="AI agent version update check cache",
            metadata={"group": "ai", "kind": "agent_update_status"},
            env=env,
        )

    def _agent_status(self, agent, config, env=None):
        try:
            runtime = wiz.model("struct/codex_runtime")
            return runtime.agent_status(agent, config.get(agent) or {})
        except Exception as exc:
            return {
                "checked_at": utcnow(),
                "type": agent,
                "label": AGENT_LABELS.get(agent, agent),
                "enabled": bool((config.get(agent) or {}).get("enabled")),
                "model": (config.get(agent) or {}).get("model"),
                "active": {"available": False, "executable": "", "version": ""},
                "login": {"status": "error", "logged_in": False, "message": str(exc)},
            }

    def _agent_model_item(self, agent, config, status=None):
        agent_config = config.get(agent) or {}
        status = status or {}
        active = status.get("active") or {}
        login = status.get("login") or {}
        available = bool(active.get("available") or login.get("logged_in"))
        level = "ok" if available else "warning"
        return {
            "id": agent_config.get("model") or DEFAULT_CONFIG[agent]["model"],
            "label": "%s · %s" % (AGENT_LABELS.get(agent, agent), agent_config.get("model") or DEFAULT_CONFIG[agent]["model"]),
            "agent": agent,
            "capabilities": {"labels": ["MCP", "서버 제어", "Compose 작성"]},
            "pricing": {"label": "Agent CLI 실행"},
            "state": {
                "level": level,
                "message": login.get("message") or ("Agent CLI 사용 가능" if available else "Agent CLI 상태 확인 필요"),
            },
        }

    def public_payload(self, env=None, include_status=True):
        config = self._normalize_config(self._saved_config(env=env))
        statuses = {agent: self._agent_status(agent, config, env=env) for agent in AGENT_ORDER} if include_status else {}
        return {
            "config": config,
            "tokens": {},
            "resources": {"agents": statuses, "checked_at": utcnow()},
            "sources": SOURCES,
            "agent_statuses": statuses,
            "agent_updates": self._saved_agent_updates(env=env),
        }

    def save(self, payload=None, env=None, include_status=True):
        body = dict(payload or {})
        current = self._normalize_config(self._saved_config(env=env))
        config = self._normalize_config(_deep_merge(current, body))
        self._persist_config(config, env=env)
        return self.public_payload(env=env, include_status=include_status)

    def save_section(self, payload=None, env=None, include_status=True):
        body = dict(payload or {})
        section = _str(body.get("section")).lower().replace("-", "_")
        if section in {"claude", "claudecode"}:
            section = "claude_code"
        if section == "hermes_agent":
            section = "hermes"
        if section not in AGENT_ORDER:
            raise AISettingsError(400, "지원하지 않는 AI Agent 설정입니다.", "AI_AGENT_SECTION_NOT_SUPPORTED")

        current = self._normalize_config(self._saved_config(env=env))
        section_payload = body.get(section) if isinstance(body.get(section), dict) else body
        next_config = dict(current)
        next_config[section] = _deep_merge(current.get(section) or {}, section_payload)
        config = self._normalize_config(next_config)
        self._persist_config(config, env=env)
        return self.public_payload(env=env, include_status=include_status)

    def save_default_agent(self, payload=None, env=None, include_status=True):
        body = dict(payload or {})
        current = self._normalize_config(self._saved_config(env=env))
        agent = _agent_key(body.get("default_agent") or body.get("agent") or body.get("provider"))
        if agent not in AGENT_ORDER or not (current.get(agent) or {}).get("enabled"):
            raise AISettingsError(
                400,
                "기본 AI Agent는 사용 중인 Agent 중에서 선택하세요.",
                "AI_DEFAULT_AGENT_INVALID",
            )
        next_config = dict(current)
        next_config["default_agent"] = agent
        config = self._normalize_config(next_config)
        self._persist_config(config, env=env)
        return self.public_payload(env=env, include_status=include_status)

    def save_agent_update(self, agent, update, env=None):
        agent = _agent_key(agent)
        if agent not in AGENT_ORDER:
            raise AISettingsError(400, "지원하지 않는 AI Agent입니다.", "AI_AGENT_NOT_SUPPORTED")
        if not isinstance(update, dict):
            raise AISettingsError(400, "Agent 업데이트 정보가 올바르지 않습니다.", "AI_AGENT_UPDATE_INVALID")
        updates = self._saved_agent_updates(env=env)
        updates[agent] = {**dict(update), "agent": agent}
        self._persist_agent_updates(updates, env=env)
        return updates[agent]

    def model_options(self, env=None):
        config = self._normalize_config(self._saved_config(env=env))
        statuses = {agent: self._agent_status(agent, config, env=env) for agent in AGENT_ORDER}
        options = []
        for agent in AGENT_ORDER:
            agent_config = config.get(agent) or {}
            if not agent_config.get("enabled"):
                continue
            status = statuses.get(agent) or {}
            item = self._agent_model_item(agent, config, status)
            options.append(
                {
                    "value": agent,
                    "label": AGENT_LABELS.get(agent, agent),
                    "description": AGENT_DESCRIPTIONS.get(agent, ""),
                    "badge": "Agent",
                    "badgeClass": _agent_badge_class(agent, (item.get("state") or {}).get("level")),
                    "state": item.get("state") or {},
                    "cli_mode": "agent",
                    "model": agent_config.get("model"),
                }
            )
        default_ref = config.get("default_agent") or next((agent for agent in AGENT_ORDER if (config.get(agent) or {}).get("enabled")), "")
        return {
            "options": options,
            "default_model_ref": default_ref,
            "default_agent": default_ref,
            "enabled_agent_count": len(options),
            "selected": default_ref,
            "has_enabled_models": bool(options),
            "message": "" if options else "시스템 설정에서 사용 중인 AI Agent가 없습니다.",
        }

    def resources(self, payload=None, env=None):
        config = self._normalize_config(self._saved_config(env=env))
        statuses = {agent: self._agent_status(agent, config, env=env) for agent in AGENT_ORDER}
        return {"agents": statuses, "checked_at": utcnow(), "probe": bool((payload or {}).get("probe"))}


Model = AISettings()
