import datetime
import json
import urllib.error
import urllib.parse
import urllib.request

from psycopg.types.json import Jsonb


connect = wiz.model("db/postgres").connect
settings = wiz.model("struct/settings")

AI_CONFIG_KEY = "ai.config"
AI_MODEL_CACHE_KEY = "ai.models_cache"
OPENAI_TOKEN_KEY = "ai.openai.api_token"
GEMINI_TOKEN_KEY = "ai.gemini.api_token"
MASKED_SECRET = settings.MASKED_SECRET

SOURCES = {
    "openai_models_api": "https://developers.openai.com/api/reference/resources/models/methods/list",
    "openai_models_docs": "https://developers.openai.com/api/docs/models",
    "openai_deprecations": "https://developers.openai.com/api/docs/deprecations",
    "openai_pricing": "https://openai.com/api/pricing/",
    "gemini_models_api": "https://ai.google.dev/api/models",
    "gemini_models_docs": "https://ai.google.dev/gemini-api/docs/models",
    "gemini_pricing": "https://ai.google.dev/gemini-api/docs/pricing",
    "ollama_tags_api": "https://docs.ollama.com/api/tags",
}

KNOWN_OPENAI_DEPRECATIONS = {
    "gpt-4.5-preview": {"shutdown_date": "2025-07-14", "replacement": "gpt-4.1"},
    "gpt-4-32k": {"shutdown_date": "2025-06-06", "replacement": "gpt-4o"},
    "gpt-4-32k-0613": {"shutdown_date": "2025-06-06", "replacement": "gpt-4o"},
    "gpt-4-32k-0314": {"shutdown_date": "2025-06-06", "replacement": "gpt-4o"},
    "gpt-4-vision-preview": {"shutdown_date": "2024-12-06", "replacement": "gpt-4o"},
    "gpt-4-1106-vision-preview": {"shutdown_date": "2024-12-06", "replacement": "gpt-4o"},
    "gpt-3.5-turbo-0125": {"shutdown_date": "2026-10-23", "replacement": "gpt-4.1-mini"},
    "gpt-4-0613": {"shutdown_date": "2026-10-23", "replacement": "gpt-4.1"},
    "gpt-4-1106-preview": {"shutdown_date": "2026-10-23", "replacement": "gpt-4.1"},
    "gpt-4-turbo": {"shutdown_date": "2026-10-23", "replacement": "gpt-4.1"},
    "gpt-4-turbo-2024-04-09": {"shutdown_date": "2026-10-23", "replacement": "gpt-4.1"},
    "gpt-4.1-nano": {"shutdown_date": "2026-10-23", "replacement": "gpt-5-nano"},
    "gpt-4o-2024-05-13": {"shutdown_date": "2026-10-23", "replacement": "gpt-4.1"},
    "gpt-image-1": {"shutdown_date": "2026-10-23", "replacement": "gpt-image-1.5"},
    "o1-2024-12-17": {"shutdown_date": "2026-10-23", "replacement": "o3"},
    "o1-pro-2025-03-19": {"shutdown_date": "2026-10-23", "replacement": "gpt-5.4-pro"},
    "o3-mini-2025-01-31": {"shutdown_date": "2026-10-23", "replacement": "o3"},
    "o4-mini-2025-04-16": {"shutdown_date": "2026-10-23", "replacement": "gpt-5-mini"},
}

KNOWN_GEMINI_DEPRECATIONS = {
    "gemini-3-pro-preview": {"shutdown_date": "2026-03-09", "replacement": "gemini-3.1-pro-preview"},
}

OPENAI_PRICING_HINTS = [
    ("gpt-5.5", "입력 $5.00 / 출력 $30.00 per 1M tokens"),
    ("gpt-5.4-mini", "입력 $0.75 / 출력 $4.50 per 1M tokens"),
    ("gpt-5.4", "입력 $2.50 / 출력 $15.00 per 1M tokens"),
    ("gpt-realtime-2", "텍스트 입력 $4.00 / 텍스트 출력 $24.00 per 1M tokens"),
    ("gpt-image-2", "텍스트 입력 $5.00 / 이미지 입력 $8.00 / 이미지 출력 $30.00 per 1M tokens"),
]

GEMINI_PRICING_HINTS = [
    ("gemini-2.5-pro", "입력 $1.25 / 출력 $10.00 per 1M tokens"),
    ("gemini-2.5-flash-lite", "입력 $0.10 / 출력 $0.40 per 1M tokens"),
    ("gemini-2.5-flash", "입력 $0.30 / 출력 $2.50 per 1M tokens"),
    ("gemini-embedding", "입력 $0.15 per 1M tokens"),
    ("imagen", "이미지 1장당 과금"),
    ("veo-3-fast", "동영상 $0.10/sec"),
    ("veo-3", "동영상 $0.40/sec"),
    ("veo-2", "동영상 $0.35/sec"),
]

DEFAULT_CONFIG = {
    "codex": {
        "enabled": False,
        "cli_mode": "system",
        "model": "gpt-5.5",
        "reasoning_effort": "xhigh",
        "codex_home": "",
    },
    "openai": {
        "enabled": False,
        "base_url": "https://api.openai.com/v1",
        "selected_model": "",
        "model_sort": "name_asc",
    },
    "gemini": {
        "enabled": False,
        "api_version": "v1beta",
        "selected_model": "",
        "model_sort": "name_asc",
    },
    "ollama": {
        "enabled": False,
        "scheme": "http",
        "host": "127.0.0.1",
        "port": 11434,
        "selected_model": "",
        "model_sort": "name_asc",
    },
    "runtime": {
        "enabled": False,
        "mode": "cloud_api",
        "target_node_id": "",
        "node_ollama_port": 11434,
        "prefer_gpu": True,
        "selected_model": "",
        "model_sort": "name_asc",
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


def _nodes_model():
    return wiz.model("struct/nodes")


def _scripts_model():
    return wiz.model("struct/local_command_scripts")


def today():
    return datetime.date.today().isoformat()


def _as_bool(value, default=False):
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"1", "true", "yes", "on"}


def _as_port(value, default):
    try:
        port = int(value)
    except (TypeError, ValueError):
        port = default
    return max(1, min(port, 65535))


def _str(value, default=""):
    if value is None:
        return default
    return str(value).strip()


def _reasoning_effort(value):
    effort = _str(value, DEFAULT_CONFIG["codex"]["reasoning_effort"]).lower()
    if effort not in {"low", "medium", "high", "xhigh"}:
        return DEFAULT_CONFIG["codex"]["reasoning_effort"]
    return effort


def _model_sort(value):
    value = _str(value, "name_asc")
    if value not in {"name_asc", "name_desc", "latest", "oldest", "recommended"}:
        return "name_asc"
    return value


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


def _normalize_host(scheme, host):
    host = _str(host, DEFAULT_CONFIG["ollama"]["host"])
    if host.startswith("http://"):
        return "http", host.replace("http://", "", 1).strip("/")
    if host.startswith("https://"):
        return "https", host.replace("https://", "", 1).strip("/")
    return scheme, host.strip("/")


def _token_from_payload(payload, key, saved_key, env=None):
    value = payload.get(key)
    if isinstance(value, str) and value.strip() and value.strip() != MASKED_SECRET:
        return value.strip()
    return settings.get_secret_value(saved_key, env=env)


def _json_from_stdout(result):
    try:
        return json.loads(result.get("stdout") or "{}")
    except Exception:
        return None


def _capability_payload(text=True, image_input=False, image_output=False, video_input=False, video_output=False):
    labels = []
    if text:
        labels.append("텍스트")
    if image_output:
        labels.append("이미지 생성")
    elif image_input:
        labels.append("이미지 입력")
    if video_output:
        labels.append("동영상 생성")
    elif video_input:
        labels.append("동영상 입력")
    return {
        "text": bool(text),
        "image": bool(image_input or image_output),
        "video": bool(video_input or video_output),
        "image_input": bool(image_input),
        "image_output": bool(image_output),
        "video_input": bool(video_input),
        "video_output": bool(video_output),
        "labels": labels,
    }


def _efficiency_profile(model_id):
    value = (model_id or "").lower()
    if any(term in value for term in ["nano", "mini", "flash-lite", "fast"]):
        return {"level": "efficient", "label": "고효율/저비용", "note": "모델명 기준 추정"}
    if "flash" in value:
        return {"level": "balanced", "label": "균형/저지연", "note": "모델명 기준 추정"}
    if any(term in value for term in ["pro", "ultra", "thinking", "o1", "o3", "o4"]):
        return {"level": "performance", "label": "고성능/고비용", "note": "모델명 기준 추정"}
    if any(term in value for term in ["embedding", "tts", "transcribe", "whisper"]):
        return {"level": "specialized", "label": "전용 모델", "note": "모델명 기준 추정"}
    return {"level": "standard", "label": "표준", "note": "공식 가격표 확인 필요"}


def _pricing_profile(provider, model_id):
    if provider == "ollama":
        return {
            "status": "local",
            "label": "로컬/노드 실행 비용",
            "source": SOURCES["ollama_tags_api"],
            "note": "API 토큰 과금이 아닌 서버 자원 사용량 기준입니다.",
        }

    value = (model_id or "").lower()
    hints = OPENAI_PRICING_HINTS if provider == "openai" else GEMINI_PRICING_HINTS
    source = SOURCES["openai_pricing"] if provider == "openai" else SOURCES["gemini_pricing"]
    for prefix, label in hints:
        if value.startswith(prefix):
            return {
                "status": "hint",
                "label": label,
                "source": source,
                "note": "공식 가격표 기준 요약입니다. 세부 과금 단위와 배치/캐시 할인은 공식 가격표를 확인하세요.",
            }
    return {
        "status": "reference",
        "label": "공식 가격표 확인",
        "source": source,
        "note": "모델 목록 API 응답에는 요금표가 포함되지 않습니다.",
    }


def _token_profile(provider, item=None, details=None):
    item = item or {}
    details = details or {}
    if provider == "gemini":
        input_limit = item.get("inputTokenLimit")
        output_limit = item.get("outputTokenLimit")
        return {
            "input_limit": input_limit,
            "output_limit": output_limit,
            "label": "모델 API 제공" if input_limit or output_limit else "토큰 한도 미제공",
            "source": SOURCES["gemini_models_api"],
        }
    if provider == "ollama":
        bits = []
        if details.get("parameter_size"):
            bits.append(f"파라미터 {details['parameter_size']}")
        if details.get("quantization_level"):
            bits.append(f"양자화 {details['quantization_level']}")
        return {
            "input_limit": None,
            "output_limit": None,
            "label": " · ".join(bits) or "컨텍스트 한도 미제공",
            "source": SOURCES["ollama_tags_api"],
        }
    return {
        "input_limit": None,
        "output_limit": None,
        "label": "모델 목록 API 미제공",
        "source": SOURCES["openai_models_api"],
    }


def _openai_capabilities(model_id):
    value = (model_id or "").lower()
    if "sora" in value:
        return _capability_payload(text=True, video_output=True)
    if value.startswith("gpt-image") or "image" in value:
        return _capability_payload(text=True, image_output=True)
    if any(term in value for term in ["embedding", "tts", "transcribe", "whisper"]):
        return _capability_payload(text=True)
    if any(term in value for term in ["gpt-4o", "gpt-4.1", "gpt-5", "o3", "o4"]):
        return _capability_payload(text=True, image_input=True)
    return _capability_payload(text=True)


def _gemini_capabilities(model_id, item):
    value = (model_id or "").lower()
    methods = item.get("supportedGenerationMethods") or []
    if "veo" in value:
        return _capability_payload(text=True, video_output=True)
    if "imagen" in value:
        return _capability_payload(text=True, image_output=True)
    if "embedding" in value or "embedContent" in methods:
        return _capability_payload(text=True)
    if "gemini" in value:
        return _capability_payload(text=True, image_input=True, video_input=True)
    return _capability_payload(text=True)


def _ollama_capabilities(model_id, details):
    value = (model_id or "").lower()
    detail_text = json.dumps(details or {}, ensure_ascii=False).lower()
    vision_terms = ["vision", "llava", "bakllava", "moondream", "minicpm-v", "gemma3", "qwen2-vl", "qwen2.5-vl"]
    return _capability_payload(text=True, image_input=any(term in value or term in detail_text for term in vision_terms))


class AISettings:
    AISettingsError = AISettingsError

    def _saved_config(self, env=None):
        row = settings.get(AI_CONFIG_KEY, env=env)
        value = (row or {}).get("value")
        return _deep_merge(DEFAULT_CONFIG, value if isinstance(value, dict) else {})

    def _normalize_config(self, value):
        config = _deep_merge(DEFAULT_CONFIG, value if isinstance(value, dict) else {})
        cli_mode = DEFAULT_CONFIG["codex"]["cli_mode"]
        config["codex"] = {
            "enabled": _as_bool(config["codex"].get("enabled")),
            "cli_mode": cli_mode,
            "model": _str(config["codex"].get("model"), DEFAULT_CONFIG["codex"]["model"]) or DEFAULT_CONFIG["codex"]["model"],
            "reasoning_effort": _reasoning_effort(config["codex"].get("reasoning_effort")),
            "codex_home": _str(config["codex"].get("codex_home")),
        }
        config["openai"] = {
            "enabled": _as_bool(config["openai"].get("enabled")),
            "base_url": _str(config["openai"].get("base_url"), DEFAULT_CONFIG["openai"]["base_url"]).rstrip("/") or DEFAULT_CONFIG["openai"]["base_url"],
            "selected_model": _str(config["openai"].get("selected_model")),
            "model_sort": _model_sort(config["openai"].get("model_sort")),
        }
        api_version = _str(config["gemini"].get("api_version"), "v1beta")
        if api_version not in {"v1", "v1beta"}:
            api_version = "v1beta"
        config["gemini"] = {
            "enabled": _as_bool(config["gemini"].get("enabled")),
            "api_version": api_version,
            "selected_model": _str(config["gemini"].get("selected_model")).replace("models/", "", 1),
            "model_sort": _model_sort(config["gemini"].get("model_sort")),
        }
        scheme = "https" if _str(config["ollama"].get("scheme"), "http") == "https" else "http"
        scheme, host = _normalize_host(scheme, config["ollama"].get("host"))
        config["ollama"] = {
            "enabled": _as_bool(config["ollama"].get("enabled")),
            "scheme": scheme,
            "host": host or DEFAULT_CONFIG["ollama"]["host"],
            "port": _as_port(config["ollama"].get("port"), DEFAULT_CONFIG["ollama"]["port"]),
            "selected_model": _str(config["ollama"].get("selected_model")),
            "model_sort": _model_sort(config["ollama"].get("model_sort")),
        }
        mode = _str(config["runtime"].get("mode"), "cloud_api")
        if mode not in {"cloud_api", "external_ollama", "local_server", "registered_node"}:
            mode = "cloud_api"
        config["runtime"] = {
            "enabled": _as_bool(config["runtime"].get("enabled")),
            "mode": mode,
            "target_node_id": _str(config["runtime"].get("target_node_id")),
            "node_ollama_port": _as_port(config["runtime"].get("node_ollama_port"), DEFAULT_CONFIG["runtime"]["node_ollama_port"]),
            "prefer_gpu": _as_bool(config["runtime"].get("prefer_gpu"), default=True),
            "selected_model": _str(config["runtime"].get("selected_model")),
            "model_sort": _model_sort(config["runtime"].get("model_sort")),
        }
        return {
            "codex": config["codex"],
            "openai": config["openai"],
            "gemini": config["gemini"],
            "ollama": config["ollama"],
            "runtime": config["runtime"],
        }

    def _model_cache(self, env=None):
        row = settings.get(AI_MODEL_CACHE_KEY, env=env)
        value = (row or {}).get("value")
        cache = value if isinstance(value, dict) else {}
        for provider in ["openai", "gemini", "ollama"]:
            cache.setdefault(provider, {"status": "not_checked", "models": [], "checked_at": None, "message": ""})
        return cache

    def _save_model_cache(self, provider, result, env=None):
        cache = self._model_cache(env=env)
        cache[provider] = result
        settings.upsert(
            AI_MODEL_CACHE_KEY,
            value=cache,
            value_type="json",
            description="AI provider model list cache",
            metadata={"group": "ai", "kind": "model_cache"},
            env=env,
        )

    def _token_status(self, key, env=None):
        row = settings.get(key, env=env)
        secret = (row or {}).get("secret") or {}
        return {
            "configured": bool(secret.get("is_configured")),
            "masked_value": secret.get("masked_value") or "",
            "last_updated_at": secret.get("last_updated_at"),
        }

    def _node_options(self, env=None):
        try:
            rows = _nodes_model().list(env=env)
        except Exception:
            return []
        return [
            {
                "id": row.get("id"),
                "name": row.get("name"),
                "host": row.get("host"),
                "role": row.get("role"),
                "is_local_master": row.get("is_local_master"),
                "status": row.get("status"),
            }
            for row in rows
        ]

    def _normalize_model_for_provider(self, provider, model_id):
        model_id = _str(model_id)
        if provider == "gemini":
            model_id = model_id.replace("models/", "", 1)
        return model_id

    def _cached_model(self, cache, provider, model_id):
        provider_cache = cache.get(provider) or {}
        models = provider_cache.get("models") or []
        normalized = self._normalize_model_for_provider(provider, model_id)
        for model in models:
            for candidate in [model.get("id"), model.get("model"), model.get("full_name")]:
                if self._normalize_model_for_provider(provider, candidate) == normalized:
                    return model
        return None

    def _provider_label(self, provider):
        labels = {
            "codex": "Codex",
            "openai": "OpenAI",
            "gemini": "Gemini",
            "ollama": "Ollama",
        }
        return labels.get(provider, provider or "AI")

    def _provider_badge_class(self, provider, state_level=None):
        if state_level == "error":
            return "border-rose-200 bg-rose-50 text-rose-700 dark:border-rose-900/70 dark:bg-rose-950/40 dark:text-rose-300"
        if state_level == "warning":
            return "border-amber-200 bg-amber-50 text-amber-700 dark:border-amber-900/70 dark:bg-amber-950/40 dark:text-amber-300"
        if provider == "openai":
            return "border-emerald-200 bg-emerald-50 text-emerald-700 dark:border-emerald-900/70 dark:bg-emerald-950/40 dark:text-emerald-300"
        if provider == "codex":
            return "border-fuchsia-200 bg-fuchsia-50 text-fuchsia-700 dark:border-fuchsia-900/70 dark:bg-fuchsia-950/40 dark:text-fuchsia-300"
        if provider == "gemini":
            return "border-sky-200 bg-sky-50 text-sky-700 dark:border-sky-900/70 dark:bg-sky-950/40 dark:text-sky-300"
        if provider == "ollama":
            return "border-violet-200 bg-violet-50 text-violet-700 dark:border-violet-900/70 dark:bg-violet-950/40 dark:text-violet-300"
        return "border-zinc-200 bg-zinc-50 text-zinc-600 dark:border-zinc-700 dark:bg-zinc-950 dark:text-zinc-300"

    def _selected_model_candidates(self, config, cache):
        result = []
        seen = set()

        def add(provider, model_id):
            model_id = self._normalize_model_for_provider(provider, model_id)
            if not model_id:
                return
            key = "%s::%s" % (provider, model_id)
            if key in seen:
                return
            seen.add(key)
            cached = self._cached_model(cache, provider, model_id)
            if provider == "codex":
                codex = config.get("codex") or {}
                effort = _str(codex.get("reasoning_effort") or "xhigh").upper()
                cached = {
                    "id": model_id,
                    "label": "%s · %s" % (model_id, effort),
                    "capabilities": {"labels": ["텍스트", "MCP"]},
                    "pricing": {"label": "Codex 로그인 세션 사용"},
                    "state": {
                        "level": "ok",
                        "message": "Codex 로그인 세션으로 실행합니다.",
                    },
                }
            result.append(
                {
                    "provider": provider,
                    "model_id": model_id,
                    "model": cached or {"id": model_id, "label": model_id},
                }
            )

        openai = config.get("openai") or {}
        if openai.get("enabled") and openai.get("selected_model"):
            add("openai", openai.get("selected_model"))

        gemini = config.get("gemini") or {}
        if gemini.get("enabled") and gemini.get("selected_model"):
            add("gemini", gemini.get("selected_model"))

        ollama = config.get("ollama") or {}
        runtime = config.get("runtime") or {}
        runtime_mode = runtime.get("mode") or "cloud_api"
        runtime_enabled = bool(runtime.get("enabled"))
        if runtime_enabled and runtime_mode in {"external_ollama", "local_server", "registered_node"} and runtime.get("selected_model"):
            add("ollama", runtime.get("selected_model"))
        if ollama.get("enabled") and ollama.get("selected_model"):
            add("ollama", ollama.get("selected_model"))
        if runtime_enabled and runtime_mode in {"external_ollama", "local_server", "registered_node"} and not runtime.get("selected_model"):
            add("ollama", ollama.get("selected_model"))
        return result

    def _default_model_ref(self, config):
        codex = config.get("codex") or {}
        if codex.get("enabled") and codex.get("model"):
            return "codex"
        openai = config.get("openai") or {}
        if openai.get("enabled") and openai.get("selected_model"):
            return "openai::%s" % self._normalize_model_for_provider("openai", openai.get("selected_model"))
        gemini = config.get("gemini") or {}
        if gemini.get("enabled") and gemini.get("selected_model"):
            return "gemini::%s" % self._normalize_model_for_provider("gemini", gemini.get("selected_model"))
        runtime = config.get("runtime") or {}
        runtime_mode = runtime.get("mode") or "cloud_api"
        if runtime.get("enabled") and runtime_mode in {"external_ollama", "local_server", "registered_node"} and runtime.get("selected_model"):
            return "ollama::%s" % self._normalize_model_for_provider("ollama", runtime.get("selected_model"))
        ollama = config.get("ollama") or {}
        if ollama.get("enabled") and ollama.get("selected_model"):
            return "ollama::%s" % self._normalize_model_for_provider("ollama", ollama.get("selected_model"))
        return ""

    def model_options(self, env=None):
        config = self._normalize_config(self._saved_config(env=env))
        cache = self._model_cache(env=env)
        options = []
        seen = set()
        codex = config.get("codex") or {}
        if codex.get("enabled") and codex.get("model"):
            options.append(
                {
                    "value": "codex",
                    "label": "Codex",
                    "description": "Codex CLI 로그인 세션으로 실행합니다.",
                    "badge": "로그인",
                    "badgeClass": "border-fuchsia-200 bg-fuchsia-50 text-fuchsia-700 dark:border-fuchsia-900/70 dark:bg-fuchsia-950/40 dark:text-fuchsia-300",
                    "cli_mode": "system",
                }
            )
            seen.add("codex")
        for item in self._selected_model_candidates(config, cache):
            provider = item["provider"]
            if provider == "codex":
                continue
            model_id = item["model_id"]
            model = item["model"]
            value = "%s::%s" % (provider, model_id)
            if value in seen:
                continue
            seen.add(value)
            state = model.get("state") or {}
            capabilities = model.get("capabilities") or {}
            pricing = model.get("pricing") or {}
            labels = capabilities.get("labels") or ["텍스트"]
            description_bits = [
                self._provider_label(provider),
                " / ".join(labels),
            ]
            if pricing.get("label"):
                description_bits.append(pricing.get("label"))
            if state.get("message"):
                description_bits.append(state.get("message"))
            options.append(
                {
                    "value": value,
                    "label": model.get("label") or model_id,
                    "description": " · ".join([bit for bit in description_bits if bit]),
                    "badge": self._provider_label(provider),
                    "badgeClass": self._provider_badge_class(provider, state.get("level")),
                    "state": state,
                    "cli_mode": "api",
                }
            )
        default_ref = self._default_model_ref(config)
        if default_ref not in seen:
            default_ref = options[0]["value"] if options else ""
        return {
            "options": options,
            "default_model_ref": default_ref,
            "selected": default_ref,
            "has_enabled_models": bool(options),
            "message": "" if options else "시스템 설정에서 사용 중인 AI 모델이 없습니다.",
        }

    def public_payload(self, env=None):
        return {
            "config": self._normalize_config(self._saved_config(env=env)),
            "tokens": {
                "openai": self._token_status(OPENAI_TOKEN_KEY, env=env),
                "gemini": self._token_status(GEMINI_TOKEN_KEY, env=env),
            },
            "model_cache": self._model_cache(env=env),
            "resources": self.resources({"probe": False}, env=env),
            "sources": SOURCES,
        }

    def _persist_config(self, config, env=None):
        settings.upsert(
            AI_CONFIG_KEY,
            value=config,
            value_type="json",
            description="AI generation settings",
            metadata={"group": "ai", "kind": "config"},
            env=env,
        )

    def _save_provider_secret(self, provider, body, env=None):
        if provider == "openai":
            token_key = OPENAI_TOKEN_KEY
            token_field = "openai_api_token"
            clear_field = "clear_openai_api_token"
            description = "OpenAI API token"
        elif provider == "gemini":
            token_key = GEMINI_TOKEN_KEY
            token_field = "gemini_api_token"
            clear_field = "clear_gemini_api_token"
            description = "Gemini API token"
        else:
            return

        if body.get(clear_field):
            settings.delete(token_key, env=env)
        elif _str(body.get(token_field)) and _str(body.get(token_field)) != MASKED_SECRET:
            settings.upsert(
                token_key,
                value=_str(body.get(token_field)),
                value_type="string",
                is_secret=True,
                description=description,
                metadata={"group": "ai", "provider": provider},
                env=env,
            )

    def save(self, payload=None, env=None):
        body = dict(payload or {})
        current = self._normalize_config(self._saved_config(env=env))
        config = self._normalize_config(_deep_merge(current, body))
        self._save_provider_secret("openai", body, env=env)
        self._save_provider_secret("gemini", body, env=env)

        self._persist_config(config, env=env)
        return self.public_payload(env=env)

    def save_section(self, payload=None, env=None):
        body = dict(payload or {})
        section = _str(body.get("section")).lower()
        if section not in {"codex", "openai", "gemini", "ollama", "runtime"}:
            raise AISettingsError(400, "지원하지 않는 AI 설정 섹션입니다.", "AI_SETTING_SECTION_NOT_SUPPORTED")

        current = self._normalize_config(self._saved_config(env=env))
        section_payload = body.get(section) if isinstance(body.get(section), dict) else body
        next_config = dict(current)
        next_config[section] = _deep_merge(current.get(section) or {}, section_payload)
        if section == "runtime" and _as_bool(next_config["runtime"].get("enabled")):
            next_config["runtime"]["mode"] = "registered_node"

        config = self._normalize_config(next_config)
        if section in {"openai", "gemini"}:
            self._save_provider_secret(section, body, env=env)

        self._persist_config(config, env=env)
        return self.public_payload(env=env)

    def _http_json(self, url, headers=None, timeout=15):
        request = urllib.request.Request(url, headers=headers or {})
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                text = response.read().decode("utf-8")
                return json.loads(text)
        except urllib.error.HTTPError as exc:
            message = f"모델 목록 요청에 실패했습니다. HTTP {exc.code}"
            try:
                body = exc.read().decode("utf-8")
                parsed = json.loads(body)
                detail = (parsed.get("error") or {}).get("message") or parsed.get("message")
                if detail:
                    message = detail
            except Exception:
                pass
            raise AISettingsError(exc.code, message, "AI_MODEL_LIST_REQUEST_FAILED")
        except Exception as exc:
            raise AISettingsError(502, f"모델 목록 요청에 실패했습니다. {str(exc)}", "AI_MODEL_LIST_REQUEST_FAILED")

    def _openai_state(self, model_id):
        deprecation = KNOWN_OPENAI_DEPRECATIONS.get(model_id)
        if not deprecation:
            if "preview" in model_id or model_id.endswith("-latest"):
                return {"level": "warning", "message": "미리보기/별칭 모델은 동작이나 지원 범위가 바뀔 수 있습니다."}
            return {"level": "ok", "message": ""}
        level = "error" if deprecation["shutdown_date"] <= today() else "warning"
        return {
            "level": level,
            "message": f"{deprecation['shutdown_date']} 지원 종료 예정/완료. 권장 대체 모델: {deprecation['replacement']}",
            "shutdown_date": deprecation["shutdown_date"],
            "replacement": deprecation["replacement"],
            "source": SOURCES["openai_deprecations"],
        }

    def _gemini_state(self, item):
        name = (item.get("name") or "").lower()
        model_id = name.replace("models/", "", 1)
        deprecation = KNOWN_GEMINI_DEPRECATIONS.get(model_id)
        if deprecation:
            level = "error" if deprecation["shutdown_date"] <= today() else "warning"
            return {
                "level": level,
                "message": f"{deprecation['shutdown_date']} 지원 종료 예정/완료. 권장 대체 모델: {deprecation['replacement']}",
                "shutdown_date": deprecation["shutdown_date"],
                "replacement": deprecation["replacement"],
                "source": SOURCES["gemini_models_docs"],
            }
        display = (item.get("displayName") or "").lower()
        methods = item.get("supportedGenerationMethods") or []
        if "generateContent" not in methods:
            return {"level": "warning", "message": "generateContent를 지원하지 않는 모델입니다."}
        if "preview" in name or "preview" in display or "experimental" in name or "-exp" in name:
            return {"level": "warning", "message": "Preview/experimental 모델은 지원 범위가 바뀔 수 있습니다."}
        return {"level": "ok", "message": ""}

    def _validate_selected(self, provider, selected_model, models):
        selected = _str(selected_model).replace("models/", "", 1)
        if not selected:
            return {"level": "info", "message": "선택된 모델이 없습니다.", "available": None}
        by_id = {item.get("id"): item for item in models}
        by_full = {item.get("full_name"): item for item in models if item.get("full_name")}
        model = by_id.get(selected) or by_full.get(selected)
        if model is None:
            return {
                "level": "error",
                "message": "선택한 모델을 현재 공식 모델 목록에서 찾을 수 없습니다. 토큰 권한 또는 모델 지원 종료 여부를 확인하세요.",
                "available": False,
            }
        state = model.get("state") or {}
        return {
            "level": state.get("level") or "ok",
            "message": state.get("message") or "사용 가능한 모델입니다.",
            "available": True,
            "model": model.get("id"),
        }

    def _fetch_openai_models(self, payload, env=None):
        token = _token_from_payload(payload, "api_token", OPENAI_TOKEN_KEY, env=env)
        if not token:
            raise AISettingsError(400, "OpenAI API Token이 필요합니다.", "OPENAI_TOKEN_REQUIRED")
        base_url = _str(payload.get("base_url"), DEFAULT_CONFIG["openai"]["base_url"]).rstrip("/")
        data = self._http_json(f"{base_url}/models", headers={"Authorization": f"Bearer {token}"})
        models = []
        for item in data.get("data") or []:
            model_id = _str(item.get("id"))
            if not model_id:
                continue
            models.append(
                {
                    "id": model_id,
                    "label": model_id,
                    "owned_by": item.get("owned_by"),
                    "created": item.get("created"),
                    "capabilities": _openai_capabilities(model_id),
                    "token_profile": _token_profile("openai", item=item),
                    "efficiency": _efficiency_profile(model_id),
                    "pricing": _pricing_profile("openai", model_id),
                    "state": self._openai_state(model_id),
                }
            )
        models.sort(key=lambda item: item["id"].lower())
        return models

    def _fetch_gemini_models(self, payload, env=None):
        token = _token_from_payload(payload, "api_token", GEMINI_TOKEN_KEY, env=env)
        if not token:
            raise AISettingsError(400, "Gemini API Token이 필요합니다.", "GEMINI_TOKEN_REQUIRED")
        api_version = _str(payload.get("api_version"), DEFAULT_CONFIG["gemini"]["api_version"])
        if api_version not in {"v1", "v1beta"}:
            api_version = "v1beta"
        models = []
        page_token = ""
        for _ in range(5):
            params = {"key": token, "pageSize": "1000"}
            if page_token:
                params["pageToken"] = page_token
            url = f"https://generativelanguage.googleapis.com/{api_version}/models?{urllib.parse.urlencode(params)}"
            data = self._http_json(url)
            for item in data.get("models") or []:
                full_name = _str(item.get("name"))
                model_id = full_name.replace("models/", "", 1)
                if not model_id:
                    continue
                methods = item.get("supportedGenerationMethods") or []
                models.append(
                    {
                        "id": model_id,
                        "full_name": full_name,
                        "label": item.get("displayName") or model_id,
                        "version": item.get("version"),
                        "description": item.get("description"),
                        "input_token_limit": item.get("inputTokenLimit"),
                        "output_token_limit": item.get("outputTokenLimit"),
                        "supported_generation_methods": methods,
                        "capabilities": _gemini_capabilities(model_id, item),
                        "token_profile": _token_profile("gemini", item=item),
                        "efficiency": _efficiency_profile(model_id),
                        "pricing": _pricing_profile("gemini", model_id),
                        "state": self._gemini_state(item),
                    }
                )
            page_token = _str(data.get("nextPageToken"))
            if not page_token:
                break
        models.sort(key=lambda item: item["id"].lower())
        return models

    def _ollama_model_payload(self, item):
        model_id = _str(item.get("model") or item.get("name"))
        if not model_id:
            return None
        details = item.get("details") or {}
        label_bits = [model_id]
        if details.get("parameter_size"):
            label_bits.append(details["parameter_size"])
        if details.get("quantization_level"):
            label_bits.append(details["quantization_level"])
        return {
            "id": model_id,
            "label": " · ".join(label_bits),
            "name": item.get("name"),
            "modified_at": item.get("modified_at"),
            "size": item.get("size"),
            "digest": item.get("digest"),
            "details": details,
            "capabilities": _ollama_capabilities(model_id, details),
            "token_profile": _token_profile("ollama", details=details),
            "efficiency": _efficiency_profile(model_id),
            "pricing": _pricing_profile("ollama", model_id),
            "state": {"level": "ok", "message": "Ollama에 설치된 모델입니다."},
        }

    def _ollama_models_from_tags(self, models):
        items = []
        for item in models or []:
            if not isinstance(item, dict):
                continue
            model = self._ollama_model_payload(item)
            if model:
                items.append(model)
        items.sort(key=lambda item: item["id"].lower())
        return items

    def _fetch_ollama_models(self, payload):
        scheme = "https" if _str(payload.get("scheme"), "http") == "https" else "http"
        scheme, host = _normalize_host(scheme, payload.get("host") or DEFAULT_CONFIG["ollama"]["host"])
        port = _as_port(payload.get("port"), DEFAULT_CONFIG["ollama"]["port"])
        url = f"{scheme}://{host}:{port}/api/tags"
        data = self._http_json(url, timeout=8)
        return self._ollama_models_from_tags(data.get("models") or [])

    def list_models(self, payload=None, env=None):
        body = dict(payload or {})
        provider = _str(body.get("provider")).lower()
        config = self._normalize_config(self._saved_config(env=env))
        if provider == "openai":
            provider_payload = {**config["openai"], **body}
            models = self._fetch_openai_models(provider_payload, env=env)
            selected = provider_payload.get("selected_model") or config["openai"].get("selected_model")
            source = SOURCES["openai_models_api"]
        elif provider == "gemini":
            provider_payload = {**config["gemini"], **body}
            models = self._fetch_gemini_models(provider_payload, env=env)
            selected = provider_payload.get("selected_model") or config["gemini"].get("selected_model")
            source = SOURCES["gemini_models_api"]
        elif provider == "ollama":
            provider_payload = {**config["ollama"], **body}
            models = self._fetch_ollama_models(provider_payload)
            selected = provider_payload.get("selected_model") or config["ollama"].get("selected_model")
            source = SOURCES["ollama_tags_api"]
        else:
            raise AISettingsError(400, "지원하지 않는 AI provider입니다.", "AI_PROVIDER_NOT_SUPPORTED")

        result = {
            "provider": provider,
            "status": "ok",
            "models": models,
            "checked_at": utcnow(),
            "message": f"{len(models)}개 모델을 불러왔습니다.",
            "source": source,
            "validation": self._validate_selected(provider, selected, models),
        }
        self._save_model_cache(provider, result, env=env)
        return result

    def _cached_resource(self, node):
        metadata = node.get("metadata") or {}
        resource = metadata.get("ai_resource") or {}
        return resource if isinstance(resource, dict) else {}

    def _cached_ollama(self, node):
        metadata = node.get("metadata") or {}
        ollama = metadata.get("ai_ollama") or {}
        return ollama if isinstance(ollama, dict) else {}

    def _node_ref(self, node):
        return {
            "id": node.get("id"),
            "name": node.get("name"),
            "host": node.get("host"),
            "role": node.get("role"),
            "is_local_master": node.get("is_local_master"),
            "status": node.get("status"),
        }

    def _probe_node_resource(self, node, env=None):
        nodes = _nodes_model()
        if node.get("is_local_master") or node.get("role") == "local_master" or node.get("name") == "local-master":
            result = nodes.local_executor.run("ai.resources", timeout_seconds=12, env=env)
        else:
            result = nodes._run_ssh_command(node, ["sh", "-lc", _scripts_model().AI_RESOURCE_SCRIPT], timeout_seconds=15, env=env)
        payload = _json_from_stdout(result)
        status = "ok" if result.get("status") == "ok" and isinstance(payload, dict) else "error"
        return {
            "status": status,
            "checked_at": utcnow(),
            "payload": payload or {},
            "check": {
                "status": result.get("status"),
                "exit_code": result.get("exit_code"),
                "stderr": result.get("stderr"),
                "stdout": "" if payload else result.get("stdout"),
            },
        }

    def _probe_node_ollama(self, node, port, env=None):
        nodes = _nodes_model()
        port = _as_port(port, DEFAULT_CONFIG["runtime"]["node_ollama_port"])
        if node.get("is_local_master") or node.get("role") == "local_master" or node.get("name") == "local-master":
            result = nodes.local_executor.run("ai.ollama_scan", params={"port": port}, timeout_seconds=12, env=env)
        else:
            command = "export OLLAMA_PORT=%s\n%s" % (port, _scripts_model().AI_OLLAMA_SCAN_SCRIPT)
            result = nodes._run_ssh_command(node, ["sh", "-lc", command], timeout_seconds=15, env=env)
        payload = _json_from_stdout(result)
        payload = payload if isinstance(payload, dict) else {}
        installed = _as_bool(payload.get("installed"))
        api_reachable = _as_bool(payload.get("api_reachable"))
        running = _as_bool(payload.get("running"))
        if result.get("status") != "ok" or not payload:
            status = "error"
            message = "Ollama 상태를 확인할 수 없습니다."
        elif api_reachable:
            status = "ok"
            message = "Ollama API가 응답했습니다."
        elif installed or running:
            status = "warning"
            message = "Ollama는 확인되었지만 API가 응답하지 않습니다."
        else:
            status = "missing"
            message = "Ollama가 설치되어 있지 않거나 확인되지 않았습니다."
        models = self._ollama_models_from_tags(payload.get("models") or [])
        return {
            "status": status,
            "checked_at": utcnow(),
            "port": port,
            "installed": installed,
            "running": running,
            "api_reachable": api_reachable,
            "model_count": len(models),
            "models": models,
            "message": message if not payload.get("api_error") else f"{message} ({payload.get('api_error')})",
            "payload": payload,
            "check": {
                "status": result.get("status"),
                "exit_code": result.get("exit_code"),
                "stderr": result.get("stderr"),
                "stdout": "" if payload else result.get("stdout"),
            },
        }

    def _remember_node_metadata(self, node_id, key, value, env=None):
        try:
            with connect(env=env) as connection:
                with connection.cursor() as cursor:
                    cursor.execute("SELECT metadata FROM nodes WHERE id = %s", (node_id,))
                    row = cursor.fetchone()
                    metadata = dict((row or {}).get("metadata") or {})
                    metadata[key] = value
                    cursor.execute("UPDATE nodes SET metadata = %s, updated_at = now() WHERE id = %s", (Jsonb(metadata), node_id))
        except Exception:
            pass

    def _remember_node_resource(self, node_id, resource, env=None):
        self._remember_node_metadata(node_id, "ai_resource", resource, env=env)

    def _remember_node_ollama(self, node_id, ollama, env=None):
        self._remember_node_metadata(node_id, "ai_ollama", ollama, env=env)

    def resources(self, payload=None, env=None):
        body = dict(payload or {})
        probe = _as_bool(body.get("probe"), default=False)
        target_node_id = _str(body.get("node_id"))
        port = _as_port(body.get("port") or body.get("node_ollama_port"), DEFAULT_CONFIG["runtime"]["node_ollama_port"])
        nodes = _nodes_model()
        rows = nodes.list(env=env)
        if target_node_id:
            rows = [row for row in rows if row.get("id") == target_node_id]
            if not rows:
                raise AISettingsError(404, "서버를 찾을 수 없습니다.", "NODE_NOT_FOUND")
        items = []
        for row in rows:
            node = nodes.detail(row["id"], env=env) if probe else row
            resource = self._probe_node_resource(node, env=env) if probe else self._cached_resource(node)
            ollama = self._probe_node_ollama(node, port, env=env) if probe else self._cached_ollama(node)
            if probe:
                self._remember_node_resource(node["id"], resource, env=env)
                self._remember_node_ollama(node["id"], ollama, env=env)
            items.append({"node": self._node_ref(node), "resource": resource, "ollama": ollama})
        return {"nodes": items, "checked_at": utcnow() if probe else None, "probe": probe, "port": port}


Model = AISettings()
