import json
import queue
import re
import threading
import urllib.error
import urllib.parse
import urllib.request

import yaml


settings = wiz.model("struct/settings")
ai_settings = wiz.model("struct/ai_settings")
nodes_model = wiz.model("struct/nodes")
services_wizard = wiz.model("struct/services_wizard")
compose_rules = wiz.model("struct/compose_rules")
compose_validator = wiz.model("struct/compose_validator")


OPENAI_TOKEN_KEY = "ai.openai.api_token"
GEMINI_TOKEN_KEY = "ai.gemini.api_token"
MAX_AI_REPAIR_ATTEMPTS = 20
AI_STREAM_HEARTBEAT_SECONDS = 15
AI_STREAM_PROVIDER_TIMEOUT_SECONDS = 900
AI_OLLAMA_REQUEST_TIMEOUT_SECONDS = 900


class AIAssistantError(Exception):
    def __init__(self, status_code, message, code="AI_ASSISTANT_ERROR", details=None):
        super().__init__(message)
        self.status_code = status_code
        self.message = message
        self.code = code
        self.details = details or {}

    def to_response(self):
        return {
            "code": self.status_code,
            "error": self.message,
            "reason": self.code,
            "details": self.details,
        }


class AIAssistant:
    def contracts(self):
        return {
            "service": self.service_contract(),
            "compose_validation": self.compose_validation_contract(),
        }

    def model_options(self, env=None):
        payload = ai_settings.public_payload(env=env)
        config = payload.get("config") or {}
        cache = payload.get("model_cache") or {}
        options = [
            {
                "value": "auto",
                "label": "시스템 설정 기본 모델",
                "description": "AI 설정 탭의 런타임 우선순위를 사용합니다.",
                "badge": "auto",
                "badgeClass": "border-zinc-200 bg-zinc-50 text-zinc-600 dark:border-zinc-700 dark:bg-zinc-950 dark:text-zinc-300",
            }
        ]
        seen = {"auto"}
        for item in self._selected_model_candidates(config, cache):
            provider = item["provider"]
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
                }
            )
        default_ref = self._default_model_ref(config)
        if default_ref not in seen:
            default_ref = "auto"
        return {
            "options": options,
            "default_model_ref": default_ref,
            "selected": default_ref,
        }

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

    def _cached_model(self, cache, provider, model_id):
        provider_cache = cache.get(provider) or {}
        models = provider_cache.get("models") or []
        normalized = self._normalize_model_for_provider(provider, model_id)
        for model in models:
            candidate_ids = [
                model.get("id"),
                model.get("model"),
                model.get("full_name"),
            ]
            for candidate in candidate_ids:
                if self._normalize_model_for_provider(provider, candidate) == normalized:
                    return model
        return None

    def _normalize_model_for_provider(self, provider, model_id):
        model_id = self._clean_text(model_id)
        if provider == "gemini":
            model_id = model_id.replace("models/", "", 1)
        return model_id

    def _configured_model_ids(self, config, runtime, provider):
        result = set()
        if provider == "openai":
            openai = config.get("openai") or {}
            if openai.get("enabled"):
                result.add(self._normalize_model_for_provider(provider, openai.get("selected_model")))
        elif provider == "gemini":
            gemini = config.get("gemini") or {}
            if gemini.get("enabled"):
                result.add(self._normalize_model_for_provider(provider, gemini.get("selected_model")))
        elif provider == "ollama":
            ollama = config.get("ollama") or {}
            runtime_mode = runtime.get("mode") or "cloud_api"
            if ollama.get("enabled"):
                result.add(self._normalize_model_for_provider(provider, ollama.get("selected_model")))
            if runtime.get("enabled") and runtime_mode in {"external_ollama", "local_server", "registered_node"}:
                result.add(self._normalize_model_for_provider(provider, runtime.get("selected_model")))
                result.add(self._normalize_model_for_provider(provider, ollama.get("selected_model")))
        return {item for item in result if item}

    def _assert_configured_model(self, config, runtime, provider, model):
        normalized = self._normalize_model_for_provider(provider, model)
        if normalized in self._configured_model_ids(config, runtime, provider):
            return
        raise AIAssistantError(
            400,
            "시스템 설정의 AI 설정 탭에서 선택한 모델만 사용할 수 있습니다.",
            "AI_MODEL_NOT_SELECTED",
            {"provider": provider, "model": model},
        )

    def service_contract(self):
        return {
            "input": [
                {
                    "key": "intent",
                    "required": True,
                    "description": "사용자가 배포하거나 수정하려는 서비스 요구사항",
                },
                {
                    "key": "mode",
                    "required": True,
                    "values": ["service_create", "service_update"],
                },
                {
                    "key": "form",
                    "required": True,
                    "description": "서비스 이름, 설명, 도메인 설정",
                },
                {
                    "key": "components",
                    "required": True,
                    "description": "컴포넌트별 이미지, 포트, 환경변수, 볼륨",
                },
                {
                    "key": "base_content",
                    "required": False,
                    "description": "현재 서비스 compose 원본 또는 AI가 이어서 수정할 Compose 초안",
                },
                {
                    "key": "zones",
                    "required": False,
                    "description": "등록 가능한 DNS 존 목록",
                },
            ],
            "output": [
                "base_content",
                "form.name",
                "form.description",
                "form.domain_mode",
                "form.zone_id",
                "form.domain_prefix",
                "form.domain_target_key",
                "form.domain_target_port",
                "components[].key",
                "components[].image_name",
                "components[].image_tag",
                "components[].ports[]",
                "components[].env_vars[]",
                "components[].volumes[]",
                "generated_secret_keys[]",
                "notes",
                "summary",
                "warnings",
            ],
            "output_format": self.output_format_contract("service"),
        }

    def compose_validation_contract(self):
        return {
            "namespace_pattern": "^[a-z0-9_]+$",
            "filename": "docker-compose.yaml",
            "required": [
                "root object",
                "services object with at least one service",
                "each service has a healthcheck unless an external health_check override exists",
            ],
            "forbidden": [
                "services.*.container_name",
                "services.*.hostname",
                "root networks other than %s" % compose_rules.OVERLAY_NETWORK,
                "service networks other than %s" % compose_rules.OVERLAY_NETWORK,
            ],
            "network": {
                "name": compose_rules.OVERLAY_NETWORK,
                "root": {"external": True},
                "service_usage": "omit networks or use only %s" % compose_rules.OVERLAY_NETWORK,
            },
            "deploy_defaults": {
                "replicas": 1,
                "update_config": compose_rules.DEFAULT_UPDATE_CONFIG,
                "rollback_config": compose_rules.DEFAULT_ROLLBACK_CONFIG,
                "restart_policy": compose_rules.DEFAULT_RESTART_POLICY,
            },
        }

    def output_format_contract(self, target):
        return {
            "root": {
                "type": "object",
                "required": ["form", "base_content", "components", "summary", "warnings"],
                "forbidden": ["markdown fences", "partial patches", "free-form text outside JSON"],
            },
            "form": {
                "type": "object",
                "required": ["name", "description", "domain_mode"],
            },
            "components": {
                "type": "array",
                "rules": [
                    "component keys must match service keys in base_content",
                    "ports include target, published, protocol, and mode when known",
                    "env_vars include key, value, and secret",
                    "volumes include source, target, type, and readonly",
                ],
            },
            "base_content": {
                "preferred_type": "object",
                "allowed_type": "object or valid YAML string",
                "rules": [
                    "complete Docker Compose document, not a patch",
                    "no placeholder syntax",
                    "healthcheck.test, interval, timeout, retries, and start_period are sibling keys under healthcheck",
                    "no container_name, no hostname, no unsupported networks",
                    "only docker_infra_overlay network when networks are declared",
                ],
            },
        }

    def generate_service(self, payload, env=None):
        payload = payload or {}
        intent = self._clean_text(payload.get("intent"))
        if not intent:
            raise AIAssistantError(400, "AI 요청 내용을 입력하세요.", "MISSING_INTENT")

        form = payload.get("form") or {}
        components = payload.get("components") or []
        context = {
            "contract": self.service_contract(),
            "output_format": self.output_format_contract("service"),
            "docker_infra_context": self._service_create_context(payload),
            "mode": payload.get("mode") or "service_create",
            "intent": intent,
            "form": form,
            "components": components,
            "base_content": payload.get("base_content") or "",
            "zones": self._compact_zones(payload.get("zones") or []),
            "service": payload.get("service") or {},
            "compose_validation": self.compose_validation_contract(),
        }
        system = self._system_prompt("service")
        provider = self._select_provider(env=env, selection=payload)
        provider_public = self._provider_public(provider)
        draft, rendered, data = self._complete_service_until_valid(system, context, provider, env=env)

        return {
            "provider": provider_public,
            "contract": self.service_contract(),
            "draft": draft,
            "rendered": rendered,
            "summary": self._clean_text(data.get("summary")),
            "warnings": self._string_list(data.get("warnings")),
        }

    def stream_service(self, payload, env=None):
        payload = payload or {}
        intent = self._clean_text(payload.get("intent"))
        if not intent:
            yield {"type": "error", "message": "AI 요청 내용을 입력하세요.", "error_code": "MISSING_INTENT"}
            return
        context = {
            "contract": self.service_contract(),
            "output_format": self.output_format_contract("service"),
            "docker_infra_context": self._service_create_context(payload),
            "mode": payload.get("mode") or "service_create",
            "intent": intent,
            "form": payload.get("form") or {},
            "components": payload.get("components") or [],
            "base_content": payload.get("base_content") or "",
            "zones": self._compact_zones(payload.get("zones") or []),
            "service": payload.get("service") or {},
            "compose_validation": self.compose_validation_contract(),
        }
        try:
            provider = self._select_provider(env=env, selection=payload)
        except Exception as exc:
            yield self._error_event(exc)
            return
        stream_context = context
        system = self._system_prompt("service")
        for attempt in range(MAX_AI_REPAIR_ATTEMPTS + 1):
            data = None
            if attempt > 0:
                yield {
                    "type": "status",
                    "message": "검증 실패 내용을 AI에 다시 전달해 output을 보정합니다. (%s/%s)" % (
                        attempt,
                        MAX_AI_REPAIR_ATTEMPTS,
                    ),
                }
            try:
                for event in self._stream_json_with_provider("service", stream_context, provider, system=system):
                    if event.get("type") != "complete":
                        yield event
                        continue
                    data = event.get("data") or {}
                if data is None:
                    raise AIAssistantError(502, "AI 응답 JSON 객체가 비어 있습니다.", "AI_EMPTY_RESPONSE")
                draft = self._normalize_service_draft(data, fallback=context)
                rendered = self._validate_service_draft(draft, context, env=env)
                yield {
                    "type": "done",
                    "data": {
                        "provider": self._provider_public(provider),
                        "contract": self.service_contract(),
                        "draft": draft,
                        "rendered": rendered,
                        "summary": self._clean_text(data.get("summary")),
                        "warnings": self._string_list(data.get("warnings")),
                    },
                }
                return
            except Exception as exc:
                if not self._is_output_repairable_error(exc):
                    yield self._error_event(exc)
                    return
                if attempt >= MAX_AI_REPAIR_ATTEMPTS:
                    yield self._error_event(self._as_output_validation_error(exc, "service"))
                    return
                stream_context = self._repair_context("service", context, data, exc, attempt + 1)
                system = self._repair_system_prompt("service")

    def _complete_service_until_valid(self, system, context, provider, env=None):
        data = None
        last_error = None
        request_context = context
        request_system = system
        for attempt in range(MAX_AI_REPAIR_ATTEMPTS + 1):
            try:
                data, _ = self._complete_json(request_system, request_context, provider=provider)
                if not isinstance(data, dict):
                    raise AIAssistantError(502, "AI 응답 JSON 객체가 비어 있습니다.", "AI_EMPTY_RESPONSE")
                draft = self._normalize_service_draft(data, fallback=context)
                rendered = self._validate_service_draft(draft, context, env=env)
                return draft, rendered, data
            except Exception as exc:
                last_error = exc
                if not self._is_output_repairable_error(exc):
                    raise
                if attempt >= MAX_AI_REPAIR_ATTEMPTS:
                    raise self._as_output_validation_error(exc, "service")
                request_context = self._repair_context("service", context, data, exc, attempt + 1)
                request_system = self._repair_system_prompt("service")
        raise self._as_output_validation_error(last_error, "service")

    def _validate_service_draft(self, draft, context, env=None):
        content = draft.get("base_content") or context.get("base_content") or ""
        try:
            self._resolve_component_images(draft)
            self._assert_component_images(draft)
            if content and draft.get("components"):
                rendered = services_wizard.render(
                    {
                        "base_content": content,
                        "components": draft.get("components") or [],
                    }
                )
            else:
                rendered = content
            if not str(rendered or "").strip():
                raise AIAssistantError(422, "AI 응답에 Compose 초안이 없습니다.", "AI_OUTPUT_MISSING_FIELD")
            namespace = self._namespace((draft.get("form") or {}).get("name") or (context.get("form") or {}).get("name") or "ai_service")
            validation = compose_validator.validate(
                {
                    "namespace": namespace,
                    "filename": "docker-compose.yaml",
                    "content": rendered,
                }
            )
            self._assert_service_images(validation)
            return rendered
        except Exception as exc:
            raise self._as_output_validation_error(exc, "service")

    def _assert_component_images(self, draft):
        errors = []
        for index, component in enumerate(draft.get("components") or []):
            if not isinstance(component, dict):
                continue
            image_name = self._clean_text(component.get("image_name") or component.get("image"))
            image_tag = self._clean_text(component.get("image_tag") or component.get("tag") or "latest")
            if not image_name:
                errors.append(
                    {
                        "path": "components[%s].image_name" % index,
                        "error_code": "IMAGE_NAME_REQUIRED",
                        "message": "서비스 구성의 이미지 이름이 비어 있습니다.",
                        "component": self._clean_text(component.get("key") or component.get("label")),
                    }
                )
            if not image_tag:
                errors.append(
                    {
                        "path": "components[%s].image_tag" % index,
                        "error_code": "IMAGE_TAG_REQUIRED",
                        "message": "서비스 구성의 이미지 버전이 비어 있습니다.",
                        "component": self._clean_text(component.get("key") or component.get("label")),
                    }
                )
        if errors:
            raise AIAssistantError(
                422,
                "AI가 생성한 서비스 구성의 이미지 이름 또는 버전이 비어 있습니다.",
                "AI_OUTPUT_IMAGE_VALIDATION_FAILED",
                {"details": errors},
            )

    def _assert_service_images(self, validation):
        errors = []
        checked = {}
        services = ((validation.get("normalized") or {}).get("services") or {})
        for service_name, service in services.items():
            ref = self._clean_text((service or {}).get("image"))
            path = "services.%s.image" % service_name
            if not ref:
                errors.append(
                    {
                        "path": path,
                        "error_code": "IMAGE_REF_REQUIRED",
                        "message": "Compose 서비스에 image가 없습니다.",
                        "service": service_name,
                    }
                )
                continue
            if ref not in checked:
                checked[ref] = services_wizard.check_image(ref)
            status = checked[ref]
            if status.get("exists") is False:
                errors.append(
                    {
                        "path": path,
                        "error_code": "IMAGE_VERSION_NOT_FOUND",
                        "message": "이미지 이름과 버전을 확인할 수 없습니다.",
                        "service": service_name,
                        "image": ref,
                        "check": status,
                    }
                )
        if errors:
            raise AIAssistantError(
                422,
                "AI가 생성한 서비스 초안의 이미지 이름 또는 버전을 확인할 수 없습니다.",
                "AI_OUTPUT_IMAGE_VALIDATION_FAILED",
                {"details": errors},
            )

    def _resolve_component_images(self, draft):
        resolutions = []
        for component in draft.get("components") or []:
            if not isinstance(component, dict):
                continue
            image_name = self._clean_text(component.get("image_name") or component.get("image"))
            raw_image_tag = self._clean_text(component.get("image_tag") or component.get("tag"))
            image_tag = raw_image_tag or "latest"
            if not image_name or image_tag.startswith("sha256:"):
                continue
            ref = "%s:%s" % (image_name, image_tag)
            query = image_name.rsplit("/", 1)[-1]
            resolution = services_wizard.resolve_image_ref(ref, search_query=query)
            if not raw_image_tag and resolution.get("status", {}).get("exists") is not False:
                component["image_tag"] = image_tag
            if not resolution.get("resolved"):
                continue
            component["image_name"] = resolution.get("image_name") or image_name
            component["image_tag"] = resolution.get("image_tag") or image_tag
            resolutions.append(
                {
                    "component": self._clean_text(component.get("key") or component.get("label")),
                    "original": resolution.get("original") or ref,
                    "image_ref": resolution.get("image_ref"),
                    "source": resolution.get("source") or "docker_search",
                }
            )
        if resolutions:
            draft["image_resolution"] = resolutions

    def _repair_context(self, target, context, data, exc, attempt):
        return {
            "contract": self.service_contract(),
            "output_format": self.output_format_contract(target),
            "compose_validation": self.compose_validation_contract(),
            "mode": context.get("mode"),
            "intent": context.get("intent"),
            "original_context": context,
            "previous_output": data or {},
            "validation_error": self._exception_payload(exc),
            "repair_diagnostics": self._repair_diagnostics(target, data, exc),
            "repair_attempt": attempt,
            "repair_instruction": (
                "The previous output failed validation or could not be saved. "
                "Return a complete corrected JSON object for the same contract. "
                "Do not describe the fix outside JSON. Do not omit unchanged required fields."
            ),
        }

    def _repair_system_prompt(self, target):
        lines = [
            self._system_prompt(target),
            "You are repairing a previous AI output that failed validation.",
            "Use output_format, validation_error, repair_diagnostics, and previous_output to return a complete corrected JSON object only.",
            "When repair_diagnostics contains docker_search image candidates, choose one of those exact image_name and image_tag values.",
            "If the error is INVALID_YAML or a YAML parser error, rebuild the failed YAML file as an object field when output_format allows it; otherwise rebuild the full YAML text instead of patching only the reported line.",
            "Do not include markdown, explanations, or partial patches.",
        ]
        return "\n".join(lines)

    def _repair_diagnostics(self, target, data, exc):
        diagnostics = {
            "error": self._exception_payload(exc),
            "note": "Line-numbered excerpts are for repairing the next AI output. They are not patches.",
        }
        if not isinstance(data, dict):
            return diagnostics
        diagnostics["service_components"] = data.get("components") or []
        diagnostics["service_form"] = data.get("form") or {}
        diagnostics["docker_search"] = self._image_search_diagnostics(data)
        return diagnostics

    def _image_search_diagnostics(self, data):
        rows = []
        seen = set()
        components = data.get("components") if isinstance(data.get("components"), list) else []
        for component in components[:5]:
            if not isinstance(component, dict):
                continue
            image_name = self._clean_text(component.get("image_name") or component.get("image"))
            image_tag = self._clean_text(component.get("image_tag") or component.get("tag") or "latest") or "latest"
            if not image_name:
                continue
            ref = "%s:%s" % (image_name, image_tag)
            if ref in seen:
                continue
            seen.add(ref)
            resolution = services_wizard.resolve_image_ref(ref, search_query=image_name.rsplit("/", 1)[-1])
            if resolution.get("resolved") or resolution.get("candidates"):
                rows.append(
                    {
                        "component": self._clean_text(component.get("key") or component.get("label")),
                        "original": ref,
                        "resolved": resolution.get("resolved"),
                        "image_ref": resolution.get("image_ref"),
                        "image_name": resolution.get("image_name"),
                        "image_tag": resolution.get("image_tag"),
                        "candidates": [
                            {
                                "image_ref": item.get("image_ref"),
                                "image_name": item.get("image_name"),
                                "image_tag": item.get("image_tag"),
                            }
                            for item in (resolution.get("candidates") or [])[:5]
                        ],
                    }
                )
        return rows

    def _exception_payload(self, exc):
        details = getattr(exc, "details", None) or getattr(exc, "extra", None) or {}
        return {
            "message": getattr(exc, "message", str(exc)),
            "error_code": getattr(exc, "code", None) or getattr(exc, "error_code", "AI_OUTPUT_VALIDATION_FAILED"),
            "details": details,
            "summary": self._detail_summary(details),
        }

    def _is_output_repairable_error(self, exc):
        code = getattr(exc, "code", None) or getattr(exc, "error_code", None)
        return code not in {
            "AI_PROVIDER_NOT_CONFIGURED",
            "AI_PROVIDER_REQUEST_FAILED",
            "AI_PROVIDER_UNREACHABLE",
            "AI_PROVIDER_BAD_RESPONSE",
        }

    def _as_output_validation_error(self, exc, target):
        if isinstance(exc, AIAssistantError) and exc.code == "AI_OUTPUT_VALIDATION_FAILED":
            return exc
        details = self._exception_payload(exc)
        return AIAssistantError(
            422,
            "AI가 생성한 서비스 output을 검증할 수 없습니다.",
            "AI_OUTPUT_VALIDATION_FAILED",
            details,
        )

    def _system_prompt(self, target):
        common = [
            "You are an assistant inside Docker Infra.",
            "Return only one JSON object. Do not wrap it in markdown.",
            "Optimize for Docker Compose services managed by this application.",
            "Avoid container_name and avoid host paths unless the user explicitly asks for them.",
            "Use named volumes for persistence, healthchecks when practical, and stable image tags.",
            "Do not put plaintext production secrets in the output. Use generated secret keys instead.",
            "Use ASCII for generated ids, keys, and namespaces.",
            "If a requested image, feature, or option is risky or unsupported, include a warning.",
            "Do not invent exact current image versions. If the user asks for the latest version and no exact current version is provided in context, use the image's official latest tag only for that explicitly requested image and add a Korean warning that floating tags should be pinned after verification.",
            "Every generated Compose service must include an image reference whose image name and tag or digest can pass the application's image validation.",
            "Include a short thinking_summary field that summarizes the decision path without exposing raw chain-of-thought.",
            "Use the compose_validation object in the user context as a hard contract. Fix violations before returning JSON.",
            "Use the output_format object in the user context as the exact output contract.",
            "Write user-facing text in Korean: summary, warnings, thinking_summary, form.description, and notes.",
            "Keep code, YAML, JSON keys, image names, environment variable names, service keys, namespaces, and identifiers in ASCII or their official spelling.",
        ]
        common.extend(
            [
                "The output must contain form, base_content, and components keys.",
                "For service_create, assume the user is a beginner. Convert plain-language requirements into a complete Docker Infra service draft.",
                "Use docker_infra_context to align service metadata, domain selection, public endpoint, ports, volumes, secrets, and validation expectations.",
                "base_content must be a complete Docker Compose document that can be saved directly as docker-compose.yaml.",
                "Do not use placeholder syntax in base_content.",
                "components must match services in base_content.",
                "Each port must include target, published, protocol, and mode when known.",
                "Each env var must include key, value, and secret when known.",
                "Each volume must include source, target, type, and readonly when known.",
                "When a public endpoint is requested, choose one valid component port as the domain target.",
                "If zones are provided and the intent asks for public access or a domain, use domain_mode=registered, a valid zone_id, and a short domain_prefix. Otherwise use domain_mode=none.",
                "Respect the existing Compose validation constraints when choosing images, ports, env, volumes, and domain target.",
            ]
        )
        return "\n".join(common)

    def _complete_json(self, system, context, env=None, selection=None, provider=None):
        provider = provider or self._select_provider(env=env, selection=selection)
        text = None
        if provider["type"] == "openai":
            text = self._call_openai(provider, system, context)
        elif provider["type"] == "gemini":
            text = self._call_gemini(provider, system, context)
        elif provider["type"] == "ollama":
            text = self._call_ollama(provider, system, context)
        else:
            raise AIAssistantError(400, "사용 가능한 AI 공급자가 없습니다.", "AI_PROVIDER_NOT_CONFIGURED")

        data = self._extract_json(text)
        return data, {
            "type": provider["type"],
            "label": provider["label"],
            "model": provider["model"],
        }

    def _select_provider(self, env=None, selection=None):
        config = (ai_settings.public_payload(env=env).get("config") or {})
        runtime = config.get("runtime") or {}
        runtime_mode = runtime.get("mode") or "cloud_api"
        runtime_enabled = bool(runtime.get("enabled"))
        selected = self._model_selection(selection or {})
        if selected:
            provider = self._provider_from_selection(config, runtime, selected, env=env)
            if provider:
                return provider

        if runtime_mode == "cloud_api":
            openai = config.get("openai") or {}
            openai_token = settings.get_secret_value(OPENAI_TOKEN_KEY, env=env)
            if openai.get("enabled") and openai.get("selected_model") and openai_token:
                return {
                    "type": "openai",
                    "label": "OpenAI",
                    "model": openai.get("selected_model"),
                    "base_url": openai.get("base_url") or "https://api.openai.com/v1",
                    "token": openai_token,
                }

            gemini = config.get("gemini") or {}
            gemini_token = settings.get_secret_value(GEMINI_TOKEN_KEY, env=env)
            if gemini.get("enabled") and gemini.get("selected_model") and gemini_token:
                return {
                    "type": "gemini",
                    "label": "Gemini",
                    "model": gemini.get("selected_model"),
                    "api_version": gemini.get("api_version") or "v1beta",
                    "token": gemini_token,
                }

        if runtime_enabled and runtime_mode == "registered_node":
            provider = self._registered_node_provider(config, runtime, env=env)
            if provider:
                return provider

        if runtime_enabled and runtime_mode == "local_server":
            model = runtime.get("selected_model") or (config.get("ollama") or {}).get("selected_model")
            port = self._safe_int(runtime.get("node_ollama_port"), 11434)
            if model:
                return {
                    "type": "ollama",
                    "label": "Local Ollama",
                    "model": model,
                    "base_url": "http://127.0.0.1:%s" % port,
                }

        ollama = config.get("ollama") or {}
        model = ollama.get("selected_model")
        if ollama.get("enabled") and model:
            scheme = ollama.get("scheme") or "http"
            host = ollama.get("host") or "127.0.0.1"
            port = self._safe_int(ollama.get("port"), 11434)
            return {
                "type": "ollama",
                "label": "Ollama",
                "model": model,
                "base_url": "%s://%s:%s" % (scheme, host, port),
            }

        raise AIAssistantError(
            400,
            "시스템 설정의 AI 설정 탭에서 공급자, 모델, API 토큰 또는 Ollama 접속 정보를 먼저 설정하세요.",
            "AI_PROVIDER_NOT_CONFIGURED",
        )

    def _model_selection(self, payload):
        model_ref = self._clean_text((payload or {}).get("model_ref"))
        if model_ref and model_ref != "auto":
            if "::" in model_ref:
                provider, model = model_ref.split("::", 1)
                provider = provider.strip().lower()
                model = model.strip()
                if provider and model:
                    return {"provider": provider, "model": model}
        provider = self._clean_text((payload or {}).get("provider")).lower()
        model = self._clean_text((payload or {}).get("model"))
        if provider and model:
            return {"provider": provider, "model": model}
        return None

    def _provider_from_selection(self, config, runtime, selected, env=None):
        provider = selected.get("provider")
        model = selected.get("model")
        if provider not in {"openai", "gemini", "ollama"}:
            raise AIAssistantError(400, "지원하지 않는 AI 모델 공급자입니다.", "AI_PROVIDER_NOT_SUPPORTED")
        self._assert_configured_model(config, runtime, provider, model)
        if provider == "openai":
            openai = config.get("openai") or {}
            token = settings.get_secret_value(OPENAI_TOKEN_KEY, env=env)
            if not openai.get("enabled") or not token:
                raise AIAssistantError(400, "선택한 OpenAI 모델을 사용하려면 OpenAI 공급자와 API Token을 설정하세요.", "AI_PROVIDER_NOT_CONFIGURED")
            return {
                "type": "openai",
                "label": "OpenAI",
                "model": model,
                "base_url": openai.get("base_url") or "https://api.openai.com/v1",
                "token": token,
            }
        if provider == "gemini":
            gemini = config.get("gemini") or {}
            token = settings.get_secret_value(GEMINI_TOKEN_KEY, env=env)
            if not gemini.get("enabled") or not token:
                raise AIAssistantError(400, "선택한 Gemini 모델을 사용하려면 Gemini 공급자와 API Token을 설정하세요.", "AI_PROVIDER_NOT_CONFIGURED")
            return {
                "type": "gemini",
                "label": "Gemini",
                "model": model.replace("models/", "", 1),
                "api_version": gemini.get("api_version") or "v1beta",
                "token": token,
            }
        if provider == "ollama":
            runtime_mode = runtime.get("mode") or "cloud_api"
            runtime_enabled = bool(runtime.get("enabled"))
            if runtime_enabled and runtime_mode == "registered_node":
                node_runtime = dict(runtime)
                node_runtime["selected_model"] = model
                return self._registered_node_provider(config, node_runtime, env=env)
            if runtime_enabled and runtime_mode == "local_server":
                port = self._safe_int(runtime.get("node_ollama_port"), 11434)
                return {
                    "type": "ollama",
                    "label": "Local Ollama",
                    "model": model,
                    "base_url": "http://127.0.0.1:%s" % port,
                }
            ollama = config.get("ollama") or {}
            if not ollama.get("enabled"):
                raise AIAssistantError(400, "선택한 Ollama 모델을 사용하려면 Ollama 접속 정보를 설정하세요.", "AI_PROVIDER_NOT_CONFIGURED")
            scheme = ollama.get("scheme") or "http"
            host = ollama.get("host") or "127.0.0.1"
            port = self._safe_int(ollama.get("port"), 11434)
            return {
                "type": "ollama",
                "label": "Ollama",
                "model": model,
                "base_url": "%s://%s:%s" % (scheme, host, port),
            }
        raise AIAssistantError(400, "지원하지 않는 AI 모델 공급자입니다.", "AI_PROVIDER_NOT_SUPPORTED")

    def _registered_node_provider(self, config, runtime, env=None):
        model = runtime.get("selected_model") or (config.get("ollama") or {}).get("selected_model")
        target_node_id = self._clean_text(runtime.get("target_node_id"))
        if not model or not target_node_id:
            return None
        try:
            nodes = nodes_model.list(env=env) or []
        except Exception:
            nodes = []
        target = None
        for node in nodes:
            if str(node.get("id") or "") == target_node_id:
                target = node
                break
        if not target:
            raise AIAssistantError(
                400,
                "선택한 AI 실행 노드를 찾을 수 없습니다.",
                "AI_NODE_NOT_FOUND",
                {"node_id": target_node_id},
            )
        host = (
            target.get("host")
            or target.get("hostname")
            or target.get("ip")
            or target.get("address")
            or target.get("name")
        )
        if not host:
            raise AIAssistantError(
                400,
                "선택한 AI 실행 노드의 접속 주소를 확인할 수 없습니다.",
                "AI_NODE_HOST_MISSING",
                {"node_id": target_node_id},
            )
        port = self._safe_int(runtime.get("node_ollama_port"), 11434)
        return {
            "type": "ollama",
            "label": "Node Ollama",
            "model": model,
            "base_url": "http://%s:%s" % (host, port),
        }

    def _call_openai(self, provider, system, context):
        base_url = provider["base_url"].rstrip("/")
        headers = {
            "Authorization": "Bearer %s" % provider["token"],
            "Content-Type": "application/json",
        }
        body = {
            "model": provider["model"],
            "messages": [
                {"role": "system", "content": system},
                {
                    "role": "user",
                    "content": json.dumps(context, ensure_ascii=False, sort_keys=True),
                },
            ],
            "temperature": 0.2,
            "max_completion_tokens": 4000,
            "response_format": {"type": "json_object"},
        }
        try:
            data = self._post_json("%s/chat/completions" % base_url, body, headers=headers)
        except AIAssistantError as exc:
            if exc.status_code not in (400, 404, 422):
                raise
            fallback = dict(body)
            fallback.pop("response_format", None)
            fallback.pop("max_completion_tokens", None)
            fallback["max_tokens"] = 4000
            data = self._post_json("%s/chat/completions" % base_url, fallback, headers=headers)

        choices = data.get("choices") or []
        if not choices:
            raise AIAssistantError(502, "OpenAI 응답에 choices가 없습니다.", "AI_EMPTY_RESPONSE")
        message = choices[0].get("message") or {}
        content = message.get("content")
        if isinstance(content, list):
            content = "\n".join(
                [str(part.get("text") or part.get("content") or "") for part in content if isinstance(part, dict)]
            )
        return self._clean_text(content)

    def _call_gemini(self, provider, system, context):
        api_version = provider.get("api_version") or "v1beta"
        model = provider["model"]
        if not model.startswith("models/"):
            model = "models/%s" % model
        path = "%s/%s:generateContent" % (api_version.strip("/"), model)
        url = "https://generativelanguage.googleapis.com/%s?%s" % (
            path,
            urllib.parse.urlencode({"key": provider["token"]}),
        )
        body = {
            "systemInstruction": {"parts": [{"text": system}]},
            "contents": [
                {
                    "role": "user",
                    "parts": [
                        {
                            "text": json.dumps(context, ensure_ascii=False, sort_keys=True),
                        }
                    ],
                }
            ],
            "generationConfig": {
                "temperature": 0.2,
                "responseMimeType": "application/json",
                "maxOutputTokens": 4000,
            },
        }
        data = self._post_json(url, body)
        candidates = data.get("candidates") or []
        if not candidates:
            raise AIAssistantError(502, "Gemini 응답에 candidates가 없습니다.", "AI_EMPTY_RESPONSE")
        parts = (((candidates[0].get("content") or {}).get("parts")) or [])
        return "\n".join([self._clean_text(part.get("text")) for part in parts if isinstance(part, dict)])

    def _call_ollama(self, provider, system, context):
        body = {
            "model": provider["model"],
            "stream": False,
            "format": "json",
            "messages": [
                {"role": "system", "content": system},
                {
                    "role": "user",
                    "content": json.dumps(context, ensure_ascii=False, sort_keys=True),
                },
            ],
            "options": {"temperature": 0.2},
        }
        data = self._post_json(
            "%s/api/chat" % provider["base_url"].rstrip("/"),
            body,
            timeout=AI_OLLAMA_REQUEST_TIMEOUT_SECONDS,
        )
        message = data.get("message") or {}
        return self._clean_text(message.get("content") or data.get("response"))

    def _stream_json(self, target, context, selection, env=None):
        try:
            provider = self._select_provider(env=env, selection=selection)
            for event in self._stream_json_with_provider(target, context, provider):
                yield event
        except Exception as exc:
            yield self._error_event(exc)

    def _stream_json_with_provider(self, target, context, provider, system=None):
        public_provider = self._provider_public(provider)
        yield {"type": "provider", "provider": public_provider}
        yield {"type": "status", "message": "요구사항과 현재 설정을 정리합니다."}
        system = system or self._system_prompt(target)
        chunks = []
        if provider["type"] == "openai":
            stream = self._call_openai_stream(provider, system, context)
        elif provider["type"] == "gemini":
            stream = self._call_gemini_stream(provider, system, context)
        elif provider["type"] == "ollama":
            stream = self._call_ollama_stream(provider, system, context)
        else:
            raise AIAssistantError(400, "사용 가능한 AI 공급자가 없습니다.", "AI_PROVIDER_NOT_CONFIGURED")
        yield {"type": "status", "message": "AI 응답 JSON을 생성하는 중입니다."}
        for event in self._iter_with_heartbeat(stream):
            if event.get("type") == "heartbeat":
                yield event
                continue
            if event.get("type") == "delta":
                chunks.append(event.get("text") or "")
                yield event
        text = "".join(chunks)
        data = self._extract_json(text)
        thinking_summary = self._clean_text(data.get("thinking_summary"))
        if thinking_summary:
            yield {"type": "thinking", "text": thinking_summary}
        yield {"type": "status", "message": "AI 응답을 Docker Infra 설정으로 검증합니다."}
        yield {"type": "complete", "data": data, "provider": public_provider}

    def _call_openai_stream(self, provider, system, context):
        base_url = provider["base_url"].rstrip("/")
        headers = {
            "Authorization": "Bearer %s" % provider["token"],
            "Content-Type": "application/json",
        }
        body = {
            "model": provider["model"],
            "messages": [
                {"role": "system", "content": system},
                {
                    "role": "user",
                    "content": json.dumps(context, ensure_ascii=False, sort_keys=True),
                },
            ],
            "temperature": 0.2,
            "max_completion_tokens": 4000,
            "response_format": {"type": "json_object"},
            "stream": True,
        }
        try:
            for data in self._iter_sse_json("%s/chat/completions" % base_url, body, headers=headers):
                choices = data.get("choices") or []
                if not choices:
                    continue
                delta = choices[0].get("delta") or {}
                content = delta.get("content")
                if isinstance(content, list):
                    content = "\n".join(
                        [str(part.get("text") or part.get("content") or "") for part in content if isinstance(part, dict)]
                    )
                if content:
                    yield {"type": "delta", "text": content}
        except AIAssistantError as exc:
            if exc.status_code not in (400, 404, 422):
                raise
            fallback = dict(body)
            fallback.pop("response_format", None)
            fallback.pop("max_completion_tokens", None)
            fallback["max_tokens"] = 4000
            for data in self._iter_sse_json("%s/chat/completions" % base_url, fallback, headers=headers):
                choices = data.get("choices") or []
                if not choices:
                    continue
                content = ((choices[0].get("delta") or {}).get("content"))
                if content:
                    yield {"type": "delta", "text": content}

    def _call_gemini_stream(self, provider, system, context):
        api_version = provider.get("api_version") or "v1beta"
        model = provider["model"]
        if not model.startswith("models/"):
            model = "models/%s" % model
        path = "%s/%s:streamGenerateContent" % (api_version.strip("/"), model)
        url = "https://generativelanguage.googleapis.com/%s?%s" % (
            path,
            urllib.parse.urlencode({"key": provider["token"], "alt": "sse"}),
        )
        body = {
            "systemInstruction": {"parts": [{"text": system}]},
            "contents": [
                {
                    "role": "user",
                    "parts": [
                        {
                            "text": json.dumps(context, ensure_ascii=False, sort_keys=True),
                        }
                    ],
                }
            ],
            "generationConfig": {
                "temperature": 0.2,
                "responseMimeType": "application/json",
                "maxOutputTokens": 4000,
            },
        }
        for data in self._iter_sse_json(url, body):
            candidates = data.get("candidates") or []
            if not candidates:
                continue
            parts = (((candidates[0].get("content") or {}).get("parts")) or [])
            for part in parts:
                if not isinstance(part, dict):
                    continue
                text = self._clean_text(part.get("text"))
                if not text:
                    continue
                if part.get("thought"):
                    continue
                else:
                    yield {"type": "delta", "text": text}

    def _call_ollama_stream(self, provider, system, context):
        body = {
            "model": provider["model"],
            "stream": True,
            "format": "json",
            "messages": [
                {"role": "system", "content": system},
                {
                    "role": "user",
                    "content": json.dumps(context, ensure_ascii=False, sort_keys=True),
                },
            ],
            "options": {"temperature": 0.2},
        }
        for data in self._iter_ndjson(
            "%s/api/chat" % provider["base_url"].rstrip("/"),
            body,
            timeout=AI_OLLAMA_REQUEST_TIMEOUT_SECONDS,
        ):
            message = data.get("message") or {}
            content = message.get("content") or data.get("response")
            if content:
                yield {"type": "delta", "text": content}

    def _iter_with_heartbeat(self, iterator, interval=AI_STREAM_HEARTBEAT_SECONDS):
        events = queue.Queue()
        done = object()

        def consume():
            try:
                for event in iterator:
                    events.put(("event", event))
            except Exception as exc:
                events.put(("error", exc))
            finally:
                events.put(("done", done))

        threading.Thread(target=consume, daemon=True).start()
        while True:
            try:
                kind, payload = events.get(timeout=interval)
            except queue.Empty:
                yield {"type": "heartbeat"}
                continue
            if kind == "event":
                yield payload
                continue
            if kind == "error":
                raise payload
            return

    def _iter_sse_json(self, url, body, headers=None, timeout=AI_STREAM_PROVIDER_TIMEOUT_SECONDS):
        for payload in self._iter_sse_data(url, body, headers=headers, timeout=timeout):
            if payload == "[DONE]":
                break
            try:
                yield json.loads(payload)
            except Exception:
                continue

    def _iter_sse_data(self, url, body, headers=None, timeout=AI_STREAM_PROVIDER_TIMEOUT_SECONDS):
        with self._open_stream(url, body, headers=headers, timeout=timeout) as response:
            event_lines = []
            for raw in response:
                line = raw.decode("utf-8", "replace").rstrip("\r\n")
                if not line:
                    if event_lines:
                        yield "\n".join(event_lines)
                        event_lines = []
                    continue
                if line.startswith("data:"):
                    event_lines.append(line[5:].strip())
            if event_lines:
                yield "\n".join(event_lines)

    def _iter_ndjson(self, url, body, headers=None, timeout=AI_STREAM_PROVIDER_TIMEOUT_SECONDS):
        with self._open_stream(url, body, headers=headers, timeout=timeout) as response:
            for raw in response:
                line = raw.decode("utf-8", "replace").strip()
                if not line:
                    continue
                try:
                    yield json.loads(line)
                except Exception:
                    continue

    def _open_stream(self, url, body, headers=None, timeout=AI_STREAM_PROVIDER_TIMEOUT_SECONDS):
        request_headers = {"Content-Type": "application/json"}
        request_headers.update(headers or {})
        data = json.dumps(body, ensure_ascii=False).encode("utf-8")
        req = urllib.request.Request(url, data=data, headers=request_headers)
        try:
            return urllib.request.urlopen(req, timeout=timeout)
        except urllib.error.HTTPError as exc:
            raw = exc.read().decode("utf-8", "replace")
            message = self._extract_error_message(raw) or str(exc)
            raise AIAssistantError(exc.code, message, "AI_PROVIDER_REQUEST_FAILED", {"url": url})
        except urllib.error.URLError as exc:
            raise AIAssistantError(
                502,
                "AI 공급자에 연결할 수 없습니다: %s" % exc.reason,
                "AI_PROVIDER_UNREACHABLE",
                {"url": url},
            )

    def _post_json(self, url, body, headers=None, timeout=45):
        request_headers = {"Content-Type": "application/json"}
        request_headers.update(headers or {})
        data = json.dumps(body, ensure_ascii=False).encode("utf-8")
        req = urllib.request.Request(url, data=data, headers=request_headers)
        try:
            with urllib.request.urlopen(req, timeout=timeout) as response:
                raw = response.read().decode("utf-8", "replace")
        except urllib.error.HTTPError as exc:
            raw = exc.read().decode("utf-8", "replace")
            message = self._extract_error_message(raw) or str(exc)
            raise AIAssistantError(exc.code, message, "AI_PROVIDER_REQUEST_FAILED", {"url": url})
        except urllib.error.URLError as exc:
            raise AIAssistantError(
                502,
                "AI 공급자에 연결할 수 없습니다: %s" % exc.reason,
                "AI_PROVIDER_UNREACHABLE",
                {"url": url},
            )
        except Exception as exc:
            raise AIAssistantError(
                502,
                "AI 공급자 호출 중 오류가 발생했습니다: %s" % exc,
                "AI_PROVIDER_REQUEST_FAILED",
                {"url": url},
            )
        try:
            return json.loads(raw or "{}")
        except Exception:
            raise AIAssistantError(502, "AI 공급자가 JSON이 아닌 응답을 반환했습니다.", "AI_PROVIDER_BAD_RESPONSE")

    def _extract_error_message(self, raw):
        try:
            data = json.loads(raw or "{}")
        except Exception:
            return self._clean_text(raw)[:500]
        error = data.get("error")
        if isinstance(error, dict):
            return self._clean_text(error.get("message") or error.get("status"))
        if error:
            return self._clean_text(error)
        return self._clean_text(data.get("message"))

    def _extract_json(self, text):
        text = self._clean_text(text)
        if not text:
            raise AIAssistantError(502, "AI 응답이 비어 있습니다.", "AI_EMPTY_RESPONSE")
        candidates = [text]
        fenced = re.findall(r"```(?:json)?\s*(\{.*?\})\s*```", text, flags=re.S)
        candidates.extend(fenced)
        if "{" in text and "}" in text:
            candidates.append(text[text.find("{") : text.rfind("}") + 1])
        last_error = None
        for candidate in candidates:
            try:
                data = json.loads(candidate)
                if isinstance(data, dict):
                    return data
            except Exception as exc:
                last_error = exc
        raise AIAssistantError(
            502,
            "AI 응답에서 JSON 객체를 읽을 수 없습니다.",
            "AI_RESPONSE_JSON_PARSE_FAILED",
            {"message": str(last_error) if last_error else ""},
        )

    def _service_create_context(self, payload):
        payload = payload or {}
        return {
            "user_level": self._clean_text(payload.get("user_level") or "beginner"),
            "creation_mode": self._clean_text(payload.get("creation_mode") or "ai_first"),
            "primary_flow": "AI drafts the service first; direct Compose editing is advanced-only.",
            "managed_elements": [
                "service metadata",
                "Docker Compose services",
                "image name and image tag validation",
                "domain zone and prefix",
                "nginx upstream target",
                "SSL mode",
                "published and target ports",
                "named volumes",
                "runtime-generated secrets",
            ],
            "automation_scope": payload.get("automation_scope") or [
                {"title": "서비스 구성", "description": "이미지, 포트, 환경변수, 데이터 보관"},
                {"title": "도메인 연결", "description": "등록 도메인, 공개 포트, SSL 방식"},
                {"title": "자동 보정", "description": "검증 실패 시 AI 재호출 후 다시 검사"},
            ],
            "input_contract": payload.get("docker_infra_inputs") or self.service_contract().get("input"),
            "output_contract": payload.get("docker_infra_outputs") or self.service_contract().get("output"),
            "expectations": [
                "Return a complete service draft that can pass compose validation without manual YAML editing.",
                "Every service must include an image reference with a tag or digest that can be validated after generation.",
                "Choose one public component and port when the user asks for browser or domain access.",
                "Prefer named volumes over host paths for beginner-created persistent data.",
                "Mark sensitive values as secret and list generated_secret_keys instead of returning real production secrets.",
                "Include Korean warnings for assumptions, floating tags, unsupported requests, or manual follow-up.",
            ],
        }

    def _normalize_service_draft(self, data, fallback):
        files = data.get("files") if isinstance(data.get("files"), dict) else {}
        base_content = self._to_yaml_file_text(
            data.get("base_content")
            or data.get("compose")
            or files.get("docker-compose.yaml")
            or files.get("compose")
            or fallback.get("base_content")
        )
        if base_content == "{}\n":
            base_content = ""

        form = data.get("form") if isinstance(data.get("form"), dict) else {}
        fallback_form = fallback.get("form") if isinstance(fallback.get("form"), dict) else {}
        merged_form = dict(fallback_form)
        for key in [
            "name",
            "description",
            "domain_mode",
            "zone_id",
            "domain_prefix",
            "domain_target_key",
            "domain_target_port",
        ]:
            if key in form:
                merged_form[key] = form.get(key)

        merged_form["name"] = self._clean_text(merged_form.get("name"))
        if not merged_form["name"]:
            merged_form["name"] = self._service_name_from_intent(fallback.get("intent"))
        merged_form["description"] = self._clean_text(merged_form.get("description"))
        if merged_form.get("domain_mode") not in ("none", "registered"):
            merged_form["domain_mode"] = "none"
        merged_form["domain_prefix"] = self._domain_prefix(merged_form.get("domain_prefix") or merged_form["name"])
        merged_form["domain_target_port"] = self._clean_text(merged_form.get("domain_target_port"))
        merged_form["domain_target_key"] = self._clean_text(merged_form.get("domain_target_key"))
        merged_form["zone_id"] = self._clean_text(merged_form.get("zone_id"))

        components = data.get("components") if isinstance(data.get("components"), list) else []
        if not components:
            if base_content:
                components = services_wizard.components_from_content(base_content)
            else:
                components = fallback.get("components") or []
        normalized_components = self._normalize_components(components, fallback_components=fallback.get("components") or [])
        if not normalized_components:
            raise AIAssistantError(422, "AI 응답에 서비스 컴포넌트가 없습니다.", "AI_OUTPUT_MISSING_FIELD")

        if not merged_form.get("domain_target_key") or not merged_form.get("domain_target_port"):
            target = self._first_component_port(normalized_components)
            if target:
                merged_form["domain_target_key"] = merged_form.get("domain_target_key") or target["key"]
                merged_form["domain_target_port"] = merged_form.get("domain_target_port") or str(target["port"])

        return {
            "base_content": base_content,
            "form": merged_form,
            "components": normalized_components,
            "generated_secret_keys": self._string_list(data.get("generated_secret_keys")),
            "notes": self._clean_text(data.get("notes") or data.get("readme")),
        }

    def _normalize_components(self, components, fallback_components=None):
        normalized = []
        fallback_components = fallback_components or []
        for index, component in enumerate(components or []):
            if not isinstance(component, dict):
                continue
            fallback = fallback_components[index] if index < len(fallback_components) and isinstance(fallback_components[index], dict) else {}
            key = self._key(fallback.get("key") or component.get("key") or component.get("name") or "app%s" % (index + 1))
            image_name = self._clean_text(component.get("image_name") or component.get("image") or fallback.get("image_name") or "")
            image_tag = self._clean_text(component.get("image_tag") or component.get("tag") or fallback.get("image_tag") or "")
            if ":" in image_name and not image_tag:
                image_name, image_tag = image_name.rsplit(":", 1)
            ports = []
            source_ports = component.get("ports")
            if source_ports is None:
                source_ports = fallback.get("ports") or []
            for port in source_ports or []:
                if not isinstance(port, dict):
                    continue
                target = self._safe_int(port.get("target") or port.get("container"), 0)
                published = self._safe_int(port.get("published") or port.get("host") or target, 0)
                if target <= 0:
                    continue
                ports.append(
                    {
                        "target": target,
                        "published": published or target,
                        "protocol": self._clean_text(port.get("protocol") or "tcp") or "tcp",
                        "mode": self._clean_text(port.get("mode") or "host") or "host",
                    }
                )
            env_vars = []
            source_env = component.get("env_vars")
            if source_env is None:
                source_env = component.get("environment")
            if source_env is None:
                source_env = fallback.get("env_vars") or []
            for item in source_env or []:
                if not isinstance(item, dict):
                    continue
                env_key = self._env_key(item.get("key") or item.get("name"))
                if not env_key:
                    continue
                env_vars.append(
                    {
                        "key": env_key,
                        "value": self._clean_text(item.get("value")),
                        "secret": bool(item.get("secret")),
                    }
                )
            volumes = []
            source_volumes = component.get("volumes")
            if source_volumes is None:
                source_volumes = fallback.get("volumes") or []
            for item in source_volumes or []:
                if not isinstance(item, dict):
                    continue
                target = self._clean_text(item.get("target") or item.get("path"))
                if not target:
                    continue
                source = self._key(item.get("source") or ("%s-data" % key))
                volumes.append(
                    {
                        "source": source,
                        "target": target,
                        "type": self._clean_text(item.get("type") or "volume") or "volume",
                        "readonly": bool(item.get("readonly")),
                    }
                )
            normalized.append(
                {
                    "key": key,
                    "label": self._clean_text(component.get("label") or fallback.get("label") or key),
                    "role": self._clean_text(component.get("role") or fallback.get("role") or "app"),
                    "image_name": image_name,
                    "image_tag": image_tag,
                    "ports": ports,
                    "env_vars": env_vars,
                    "volumes": volumes,
                }
            )
        return normalized

    def _to_yaml_file_text(self, value):
        if isinstance(value, str):
            text = value.strip()
            return text if text else "{}\n"
        if value is None:
            value = {}
        return yaml.safe_dump(value, sort_keys=False, allow_unicode=False)

    def _diagnostic_file_text(self, value):
        if isinstance(value, (dict, list)):
            return yaml.safe_dump(value, sort_keys=False, allow_unicode=False)
        return self._clean_text(value)

    def _compact_zones(self, zones):
        result = []
        for item in zones or []:
            if not isinstance(item, dict):
                continue
            result.append(
                {
                    "id": item.get("id") or item.get("zone_id"),
                    "name": item.get("name"),
                    "domain": item.get("domain") or item.get("name"),
                }
            )
        return result[:50]

    def _first_image(self, compose):
        match = re.search(r"(?m)^\s*image:\s*['\"]?([^'\"\n]+)", compose or "")
        return match.group(1).strip() if match else ""

    def _first_component_port(self, components):
        for component in components:
            ports = component.get("ports") or []
            if ports:
                return {"key": component.get("key"), "port": ports[0].get("target")}
        return None

    def _provider_public(self, provider):
        return {
            "type": provider.get("type"),
            "label": provider.get("label"),
            "model": provider.get("model"),
        }

    def _default_model_ref(self, config):
        runtime = config.get("runtime") or {}
        runtime_model = self._clean_text(runtime.get("selected_model"))
        mode = runtime.get("mode") or "cloud_api"
        if runtime.get("enabled") and mode in {"external_ollama", "local_server", "registered_node"}:
            model = runtime_model or self._clean_text((config.get("ollama") or {}).get("selected_model"))
            return "ollama::%s" % model if model else "auto"
        openai = config.get("openai") or {}
        if openai.get("enabled") and openai.get("selected_model"):
            return "openai::%s" % openai.get("selected_model")
        gemini = config.get("gemini") or {}
        if gemini.get("enabled") and gemini.get("selected_model"):
            return "gemini::%s" % gemini.get("selected_model")
        ollama = config.get("ollama") or {}
        if ollama.get("enabled") and ollama.get("selected_model"):
            return "ollama::%s" % ollama.get("selected_model")
        return "auto"

    def _provider_label(self, provider):
        labels = {
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
        if provider == "gemini":
            return "border-sky-200 bg-sky-50 text-sky-700 dark:border-sky-900/70 dark:bg-sky-950/40 dark:text-sky-300"
        if provider == "ollama":
            return "border-violet-200 bg-violet-50 text-violet-700 dark:border-violet-900/70 dark:bg-violet-950/40 dark:text-violet-300"
        return "border-zinc-200 bg-zinc-50 text-zinc-600 dark:border-zinc-700 dark:bg-zinc-950 dark:text-zinc-300"

    def _detail_summary(self, details):
        if isinstance(details, dict):
            if isinstance(details.get("details"), list):
                details = details.get("details")
            elif details.get("message"):
                return self._clean_text(details.get("message"))
            else:
                return ""
        if not isinstance(details, list):
            return ""
        rows = []
        for item in details[:5]:
            if not isinstance(item, dict):
                continue
            path = self._clean_text(item.get("path"))
            message = self._clean_text(item.get("message") or item.get("error_code"))
            reason = self._clean_text(item.get("reason"))
            if reason:
                message = "%s (%s)" % (message, reason) if message else reason
            if not message:
                continue
            rows.append("%s: %s" % (path, message) if path else message)
        if len(details) > 5:
            rows.append("외 %s건" % (len(details) - 5))
        return "\n".join(rows)

    def _error_event(self, exc):
        details = getattr(exc, "details", None) or getattr(exc, "extra", {})
        message = getattr(exc, "message", str(exc))
        detail_summary = self._detail_summary(details)
        if detail_summary and detail_summary not in message:
            message = "%s\n%s" % (message, detail_summary)
        return {
            "type": "error",
            "message": message,
            "error_code": getattr(exc, "code", None) or getattr(exc, "error_code", "AI_ASSISTANT_ERROR"),
            "details": details,
        }

    def _service_name_from_intent(self, intent):
        text = self._domain_prefix(intent or "ai-service")
        return text[:32] or "ai-service"

    def _namespace(self, value):
        value = self._key(value)
        if not value:
            return "ai-service"
        return value[:60]

    def _domain_prefix(self, value):
        value = re.sub(r"[^a-z0-9-]+", "-", self._clean_text(value).lower())
        value = re.sub(r"-+", "-", value).strip("-")
        return value[:50]

    def _key(self, value):
        value = re.sub(r"[^a-z0-9_./-]+", "-", self._clean_text(value).lower())
        value = re.sub(r"-+", "-", value).strip("-._/")
        return value

    def _env_key(self, value):
        value = re.sub(r"[^A-Za-z0-9_]+", "_", self._clean_text(value).upper()).strip("_")
        return value

    def _line_numbered_text(self, value, max_lines=220, max_chars=16000):
        text = self._clean_text(value)
        if not text:
            return ""
        rows = []
        for index, line in enumerate(text.splitlines()[:max_lines], start=1):
            rows.append("%04d: %s" % (index, line))
        result = "\n".join(rows)
        if len(result) > max_chars:
            result = result[:max_chars].rstrip() + "\n... truncated ..."
        return result

    def _clean_text(self, value):
        if value is None:
            return ""
        return str(value).strip()

    def _string_list(self, value):
        if not isinstance(value, list):
            return []
        return [self._clean_text(item) for item in value if self._clean_text(item)]

    def _safe_int(self, value, default=0):
        try:
            return int(value)
        except Exception:
            return default


Model = AIAssistant()
