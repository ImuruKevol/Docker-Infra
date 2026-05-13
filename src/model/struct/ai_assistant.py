import json
import queue
import re
import shlex
import subprocess
import threading
import time
import yaml


settings = wiz.model("struct/settings")
ai_settings = wiz.model("struct/ai_settings")
codex_runtime = wiz.model("struct/codex_runtime")
connect = wiz.model("db/postgres").connect
nodes_model = wiz.model("struct/nodes")
services_model = wiz.model("struct/services")
services_wizard = wiz.model("struct/services_wizard")
compose_rules = wiz.model("struct/compose_rules")
compose_validator = wiz.model("struct/compose_validator")
services_preflight = wiz.model("struct/services_preflight")
placement_selector = wiz.model("struct/services_placement")
operations = wiz.model("struct/operations")


OPENAI_TOKEN_KEY = "ai.openai.api_token"
GEMINI_TOKEN_KEY = "ai.gemini.api_token"
MAX_AI_REPAIR_ATTEMPTS = 20
AI_STREAM_HEARTBEAT_SECONDS = 15
AI_STREAM_PROVIDER_TIMEOUT_SECONDS = 900
AI_OLLAMA_REQUEST_TIMEOUT_SECONDS = 900
AI_VERIFY_MAX_ATTEMPTS = 3
AI_VERIFY_RUNTIME_WAIT_ATTEMPTS = 12
AI_VERIFY_RUNTIME_WAIT_SECONDS = 10
AI_VERIFY_UNCHANGED_BLOCKED_ATTEMPTS = 3
AI_VERIFY_DEPLOY_WAIT_SECONDS = 300
SENSITIVE_ENV_PATTERN = re.compile(r"(PASSWORD|SECRET|TOKEN|KEY|AUTH|CREDENTIAL)", re.IGNORECASE)
FILE_ENV_PATTERN = re.compile(r"_FILE$", re.IGNORECASE)


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
                "value": "codex",
                "label": "Codex",
                "description": "Codex CLI 로그인 세션으로 실행합니다.",
                "badge": "로그인",
                "badgeClass": "border-fuchsia-200 bg-fuchsia-50 text-fuchsia-700 dark:border-fuchsia-900/70 dark:bg-fuchsia-950/40 dark:text-fuchsia-300",
                "cli_mode": "system",
            }
        ]
        seen = {"codex"}
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
                    "cli_mode": "custom",
                }
            )
        default_ref = self._default_model_ref(config)
        if default_ref not in seen:
            default_ref = "codex"
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
            if provider == "codex":
                codex = config.get("codex") or {}
                effort = self._clean_text(codex.get("reasoning_effort") or "xhigh").upper()
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
        if provider == "codex":
            codex = config.get("codex") or {}
            if codex.get("enabled"):
                result.add(self._normalize_model_for_provider(provider, codex.get("model")))
        elif provider == "openai":
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
                "form.domains[]",
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
                "optional": ["domains"],
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
            "domains": {
                "type": "array",
                "rules": [
                    "use form.domains when one service needs multiple public domains",
                    "each domain includes domain, zone_id when known, domain_target_key, domain_target_port, compose_service, target_port, and ssl_mode when known",
                    "keep legacy form.domain_* fields aligned with the first public domain for backward compatibility",
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
                    "no *_FILE env var or top-level Docker secret unless explicitly supported by both Docker Infra and the image",
                    "secret-like env values must be non-empty when the selected image requires them",
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
            "operator_comment": self._clean_text(payload.get("operator_comment")),
            "form": form,
            "components": components,
            "base_content": payload.get("base_content") or "",
            "zones": self._compact_zones(payload.get("zones") or []),
            "service": payload.get("service") or {},
            "compose_validation": self.compose_validation_contract(),
        }
        provider = self._select_provider(env=env, selection=payload)
        provider_public = self._provider_public(provider)
        draft, rendered, data, pipeline = self._complete_service_multiphase(context, provider, env=env)

        return {
            "provider": provider_public,
            "contract": self.service_contract(),
            "draft": draft,
            "rendered": rendered,
            "summary": self._clean_text(data.get("summary")),
            "warnings": self._string_list(data.get("warnings")),
            "ai_pipeline": pipeline,
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
            "operator_comment": self._clean_text(payload.get("operator_comment")),
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
        yield {"type": "provider", "provider": self._provider_public(provider)}
        yield {"type": "status", "message": "1차 AI 호출로 이미지, 버전, 컨테이너 포트 초안을 작성합니다."}
        plan_data = {}
        plan_error = None
        try:
            plan_data = yield from self._stream_codex_json(
                self._service_plan_system_prompt(),
                self._service_plan_context(context),
                provider,
                env=env,
                emit_delta=False,
            )
        except Exception as exc:
            if not self._is_output_repairable_error(exc):
                yield self._error_event(exc)
                return
            plan_error = self._exception_payload(exc)
            yield {"type": "status", "message": "1차 초안 JSON을 바로 사용할 수 없어 원 요청과 오류 정보를 기준으로 검증 단계를 진행합니다."}

        yield {"type": "status", "message": "Docker Infra 서버 배치, 포트 사용, 이미지 존재 여부를 확인합니다."}
        plan_draft, plan_rendered, inspection = self._inspect_service_plan(
            plan_data,
            context,
            env=env,
            plan_error=plan_error,
        )
        stream_context = self._service_review_context(context, plan_data, plan_draft, plan_rendered, inspection)
        system = self._service_review_system_prompt()
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
                if attempt == 0:
                    yield {"type": "status", "message": "검증 결과를 반영해 2차 AI 호출로 최종 서비스 구성을 보정합니다."}
                data = yield from self._stream_codex_json(
                    system,
                    stream_context,
                    provider,
                    env=env,
                    emit_delta=True,
                )
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
                        "ai_pipeline": self._service_pipeline_metadata(plan_data, inspection),
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
                stream_context["initial_draft"] = plan_data or {}
                stream_context["docker_infra_inspection"] = inspection
                system = self._repair_system_prompt("service")

    def repair_runtime(self, payload, env=None):
        payload = payload or {}
        service_id = self._clean_text(payload.get("service_id"))
        if not service_id:
            raise AIAssistantError(400, "service_id는 필수입니다.", "SERVICE_ID_REQUIRED")
        provider = self._select_provider(env=env, selection=payload)
        detail = self._service_detail_for_ai(service_id, env=env)
        diagnostics = self._runtime_diagnostics(detail, payload=payload, env=env)
        if diagnostics.get("needs_repair") is not True and payload.get("force") is not True:
            return {
                "provider": self._provider_public(provider),
                "diagnostics": diagnostics,
                "applied": False,
                "summary": "현재 런타임 상태에서 AI 수정이 필요한 문제를 찾지 못했습니다.",
                "warnings": [],
            }

        context = self._runtime_repair_context(detail, diagnostics, payload)
        data, _ = self._complete_json(self._runtime_repair_system_prompt(), context, provider=provider, env=env)
        return self._finish_runtime_repair(provider, detail, diagnostics, payload, data, context, env=env)

    def stream_runtime_repair(self, payload, env=None):
        payload = payload or {}
        service_id = self._clean_text(payload.get("service_id"))
        if not service_id:
            yield {"type": "error", "message": "service_id는 필수입니다.", "error_code": "SERVICE_ID_REQUIRED"}
            return
        try:
            provider = self._select_provider(env=env, selection=payload)
        except Exception as exc:
            yield self._error_event(exc)
            return
        yield {"type": "provider", "provider": self._provider_public(provider)}
        try:
            yield {"type": "status", "message": "서비스 상세와 최근 배포 상태를 다시 조회합니다."}
            detail = self._service_detail_for_ai(service_id, env=env)
            yield {"type": "status", "message": "처리 로그, Docker 작업, 컨테이너 상태를 런타임 진단으로 정리합니다."}
            diagnostics = self._runtime_diagnostics(detail, payload=payload, env=env)
            if diagnostics.get("needs_repair") is not True and payload.get("force") is not True:
                yield {
                    "type": "done",
                    "data": {
                        "result": {
                            "provider": self._provider_public(provider),
                            "diagnostics": diagnostics,
                            "applied": False,
                            "summary": "현재 런타임 상태에서 AI 수정이 필요한 문제를 찾지 못했습니다.",
                            "warnings": [],
                        }
                    },
                }
                return

            context = self._runtime_repair_context(detail, diagnostics, payload)
            yield {"type": "status", "message": "AI가 현재 설정, 로그, 추가 메시지를 바탕으로 수정안을 작성합니다."}
            data = yield from self._stream_codex_json(
                self._runtime_repair_system_prompt(),
                context,
                provider,
                env=env,
                emit_delta=True,
            )
            if data is None:
                raise AIAssistantError(502, "AI 응답 JSON 객체가 비어 있습니다.", "AI_EMPTY_RESPONSE")
            yield {"type": "status", "message": "AI 수정안을 검증하고 허용된 터미널 조치를 실행합니다."}
            result = self._finish_runtime_repair(provider, detail, diagnostics, payload, data, context, env=env)
            if result.get("applied"):
                yield {"type": "status", "message": "수정된 설정을 저장했고 재배포 요청을 반영했습니다."}
            yield {"type": "done", "data": {"result": result}}
        except Exception as exc:
            yield self._error_event(exc)

    def start_runtime_verification(self, payload, env=None):
        payload = dict(payload or {})
        service_id = self._clean_text(payload.get("service_id"))
        if not service_id:
            raise AIAssistantError(400, "service_id는 필수입니다.", "SERVICE_ID_REQUIRED")

        active = self._active_runtime_verification_operation(service_id, env=env)
        if active and payload.get("force_new_operation") is not True:
            return {"accepted": True, "operation": active, "deduplicated": True}

        service = (services_model.detail(service_id, env=env).get("service") or {})
        request_payload = {
            "service_id": service_id,
            "model_ref": payload.get("model_ref") or "auto",
            "intent": self._clean_text(payload.get("intent")),
            "source_operation_id": payload.get("source_operation_id"),
            "client_runtime_issues": payload.get("client_runtime_issues") if isinstance(payload.get("client_runtime_issues"), dict) else {},
            "allow_container_terminal_actions": payload.get("allow_container_terminal_actions") is not False,
            "allow_ssh_command": payload.get("allow_ssh_command") is not False,
            "apply": payload.get("apply") is not False,
            "deploy": payload.get("deploy") is not False,
            "verification_only": payload.get("verification_only") is True,
        }
        operation = operations.create(
            "service.ai.verify",
            target_type="service",
            target_id=service_id,
            status="pending",
            message="AI 백그라운드 검증을 준비했습니다.",
            requested_payload=request_payload,
            metadata={
                "service_id": service_id,
                "namespace": service.get("namespace"),
                "background": True,
                "allow_container_terminal_actions": request_payload["allow_container_terminal_actions"],
                "allow_ssh_command": request_payload["allow_ssh_command"],
            },
            env=env,
        )
        thread = threading.Thread(
            target=self._runtime_verification_worker,
            args=(request_payload, operation["id"], env),
            name=f"service-ai-verify-{operation['id']}",
            daemon=True,
        )
        thread.start()
        return {"accepted": True, "operation": operation}

    def _active_runtime_verification_operation(self, service_id, env=None):
        with connect(env=env) as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT id
                    FROM operation_logs
                    WHERE type = 'service.ai.verify'
                      AND status IN ('pending', 'running')
                      AND (
                        target_id = %s
                        OR requested_payload->>'service_id' = %s
                        OR metadata->>'service_id' = %s
                      )
                    ORDER BY created_at DESC
                    LIMIT 1
                    """,
                    (service_id, service_id, service_id),
                )
                row = cursor.fetchone()
        if row is None:
            return None
        return operations.detail(row["id"], env=env)

    def _runtime_verification_worker(self, payload, operation_id, env=None):
        try:
            operations.transition(
                operation_id,
                "running",
                message="AI 백그라운드 검증을 시작했습니다.",
                env=env,
            )
            result = self._run_runtime_verification_loop(payload, operation_id, env=env)
            status = "succeeded" if result.get("ok") else "failed"
            message = result.get("summary") or ("AI 검증을 완료했습니다." if status == "succeeded" else "AI 검증에서 확인이 필요한 문제가 남았습니다.")
            operations.transition(
                operation_id,
                status,
                message=message,
                result_payload=result,
                env=env,
            )
        except Exception as exc:
            try:
                operations.append_output(
                    operation_id,
                    getattr(exc, "message", str(exc)),
                    stream="stderr",
                    metadata={"step": "ai verification", "error_code": getattr(exc, "code", None)},
                    env=env,
                )
                operations.transition(
                    operation_id,
                    "failed",
                    message=getattr(exc, "message", str(exc)),
                    result_payload={"error": str(exc), "error_code": getattr(exc, "code", "AI_RUNTIME_VERIFY_FAILED")},
                    env=env,
                )
            except Exception:
                pass

    def _run_runtime_verification_loop(self, payload, operation_id, env=None):
        payload = dict(payload or {})
        service_id = self._clean_text(payload.get("service_id"))
        history = []
        for attempt in range(1, AI_VERIFY_MAX_ATTEMPTS + 1):
            try:
                operations.append_output(
                    operation_id,
                    "검증 시도 %s/%s를 시작합니다." % (attempt, AI_VERIFY_MAX_ATTEMPTS),
                    stream="system",
                    metadata={"step": "verification attempt", "attempt": attempt},
                    env=env,
                )
                wait_result = self._wait_runtime_ready(service_id, operation_id, env=env)
                verification = self.verify_runtime({**payload, "runtime_wait": wait_result}, env=env)
            except Exception as exc:
                history.append({"attempt": attempt, "error": self._exception_payload(exc)})
                operations.append_output(
                    operation_id,
                    "AI 검증 시도 실패: %s" % getattr(exc, "message", str(exc)),
                    stream="stderr",
                    metadata={"step": "ai verification", "attempt": attempt, "error": self._exception_payload(exc)},
                    env=env,
                )
                if attempt < AI_VERIFY_MAX_ATTEMPTS:
                    continue
                return {
                    "ok": False,
                    "summary": "AI 검증 시도가 모두 실패했습니다.",
                    "attempts": attempt,
                    "history": history,
                }
            history.append({"attempt": attempt, "wait": wait_result, "verification": self._compact_verification_result(verification)})
            operations.append_output(
                operation_id,
                verification.get("summary") or "AI 검증 결과를 받았습니다.",
                stream="system" if verification.get("ok") else "stderr",
                metadata={"step": "ai verification", "attempt": attempt, "verification": self._compact_verification_result(verification)},
                env=env,
            )
            if verification.get("ok") is True:
                return {
                    "ok": True,
                    "summary": verification.get("summary") or "AI 검증을 통과했습니다.",
                    "attempts": attempt,
                    "history": history,
                }
            if payload.get("verification_only") is True:
                return {
                    "ok": False,
                    "summary": verification.get("summary") or "AI 검증에서 확인이 필요한 문제가 있습니다.",
                    "attempts": attempt,
                    "history": history,
                }
            if verification.get("repair_required") is not True:
                return {
                    "ok": False,
                    "summary": verification.get("summary") or "AI 검증에서 자동 수정 없이 확인이 필요한 문제가 있습니다.",
                    "attempts": attempt,
                    "history": history,
                }
            try:
                repair = self._run_runtime_repair_from_verification(payload, verification, operation_id, env=env)
            except Exception as exc:
                history[-1]["repair_error"] = self._exception_payload(exc)
                operations.append_output(
                    operation_id,
                    "AI 수정 시도 실패: %s" % getattr(exc, "message", str(exc)),
                    stream="stderr",
                    metadata={"step": "ai repair", "attempt": attempt, "error": self._exception_payload(exc)},
                    env=env,
                )
                if attempt < AI_VERIFY_MAX_ATTEMPTS:
                    continue
                return {
                    "ok": False,
                    "summary": "AI 수정 시도가 모두 실패했습니다.",
                    "attempts": attempt,
                    "history": history,
                }
            history[-1]["repair"] = self._compact_verification_result(repair)
            deploy_operation = (repair.get("deploy_result") or {}).get("operation") or {}
            if deploy_operation.get("id"):
                deploy_wait = self._wait_operation_finished(deploy_operation["id"], operation_id, env=env)
                history[-1]["deploy_wait"] = deploy_wait
                if deploy_wait.get("status") not in {"succeeded", "deduplicated"}:
                    operations.append_output(
                        operation_id,
                        "AI 수정 후 재배포가 완료되지 않았습니다. 다음 검증 시도로 이어갑니다.",
                        stream="stderr",
                        metadata={"step": "deploy wait", "attempt": attempt, "deploy_wait": deploy_wait},
                        env=env,
                    )
                    if attempt < AI_VERIFY_MAX_ATTEMPTS:
                        continue
                    return {
                        "ok": False,
                        "summary": "AI 수정 후 재배포가 반복해서 완료되지 않았습니다.",
                        "attempts": attempt,
                        "history": history,
                    }
        return {
            "ok": False,
            "summary": "AI 검증과 수정 재시도 후에도 확인이 필요한 문제가 남았습니다.",
            "attempts": AI_VERIFY_MAX_ATTEMPTS,
            "history": history,
        }

    def _run_runtime_repair_from_verification(self, payload, verification, operation_id, env=None):
        service_id = self._clean_text(payload.get("service_id"))
        issues = verification.get("issues") if isinstance(verification.get("issues"), list) else []
        repair_intent = self._clean_text(verification.get("repair_intent"))
        if not repair_intent:
            repair_intent = self._clean_text(payload.get("intent"))
        if not repair_intent:
            repair_intent = "AI 검증에서 발견한 문제를 수정하고 서비스를 다시 정상 동작하게 해주세요."
        operations.append_output(
            operation_id,
            "AI 수정 단계를 실행합니다.",
            stream="system",
            metadata={"step": "ai repair", "issues": issues[:10]},
            env=env,
        )
        result = self.repair_runtime(
            {
                **payload,
                "service_id": service_id,
                "intent": repair_intent,
                "force": True,
                "allow_container_terminal_actions": payload.get("allow_container_terminal_actions") is not False,
                "allow_ssh_command": payload.get("allow_ssh_command") is not False,
                "apply": payload.get("apply") is not False,
                "deploy": payload.get("deploy") is not False,
            },
            env=env,
        )
        operations.append_output(
            operation_id,
            result.get("summary") or "AI 수정 결과를 적용했습니다.",
            stream="system" if result.get("applied") else "stderr",
            metadata={"step": "ai repair", "repair": self._compact_verification_result(result)},
            env=env,
        )
        return result

    def _wait_runtime_ready(self, service_id, operation_id, env=None):
        last = {}
        last_key = None
        unchanged_count = 0
        suppressed_count = 0
        for attempt in range(1, AI_VERIFY_RUNTIME_WAIT_ATTEMPTS + 1):
            try:
                refreshed = services_model.refresh_deploy_status(service_id, operation_id=operation_id, env=env)
                runtime = refreshed.get("runtime_status") or {}
                last = self._runtime_wait_snapshot(runtime)
                key = self._runtime_snapshot_key(last)
                if key == last_key:
                    unchanged_count += 1
                    suppressed_count += 1
                else:
                    unchanged_count = 1
                    if suppressed_count:
                        operations.append_output(
                            operation_id,
                            "동일한 상태 확인 로그 %s회를 생략했습니다." % suppressed_count,
                            stream="system",
                            metadata={"step": "runtime wait", "suppressed": suppressed_count},
                            env=env,
                        )
                        suppressed_count = 0
                    self._append_runtime_wait_snapshot(operation_id, attempt, last, env=env)
                last_key = key
                if self._runtime_snapshot_ready(last):
                    if suppressed_count:
                        operations.append_output(
                            operation_id,
                            "동일한 상태 확인 로그 %s회를 생략했습니다." % suppressed_count,
                            stream="system",
                            metadata={"step": "runtime wait", "suppressed": suppressed_count},
                            env=env,
                        )
                    return {"status": "ready", "attempts": attempt, "snapshot": last}
                if self._runtime_snapshot_blocked(last) and unchanged_count >= AI_VERIFY_UNCHANGED_BLOCKED_ATTEMPTS:
                    if suppressed_count:
                        operations.append_output(
                            operation_id,
                            "동일한 실패 상태 확인 로그 %s회를 생략했습니다." % suppressed_count,
                            stream="system",
                            metadata={"step": "runtime wait", "suppressed": suppressed_count},
                            env=env,
                        )
                    operations.append_output(
                        operation_id,
                        "런타임 상태가 %s회 연속 같은 실패 상태라 AI 분석 단계로 넘어갑니다." % unchanged_count,
                        stream="stderr",
                        metadata={"step": "runtime wait", "attempt": attempt, "snapshot": last, "unchanged_count": unchanged_count},
                        env=env,
                    )
                    return {"status": "blocked", "attempts": attempt, "snapshot": last, "unchanged_count": unchanged_count}
            except Exception as exc:
                last = {"error": str(exc)}
                operations.append_output(
                    operation_id,
                    "상태 확인 실패: %s" % exc,
                    stream="stderr",
                    metadata={"step": "runtime wait", "attempt": attempt},
                    env=env,
                )
            if attempt < AI_VERIFY_RUNTIME_WAIT_ATTEMPTS:
                time.sleep(AI_VERIFY_RUNTIME_WAIT_SECONDS)
        if suppressed_count:
            operations.append_output(
                operation_id,
                "동일한 상태 확인 로그 %s회를 생략했습니다." % suppressed_count,
                stream="system",
                metadata={"step": "runtime wait", "suppressed": suppressed_count},
                env=env,
            )
        return {"status": "timeout", "attempts": AI_VERIFY_RUNTIME_WAIT_ATTEMPTS, "snapshot": last}

    def _append_runtime_wait_snapshot(self, operation_id, attempt, snapshot, env=None):
        operations.append_output(
            operation_id,
            "상태 확인: stack %s, containers %s, domains %s" % (
                snapshot.get("stack"),
                snapshot.get("containers"),
                snapshot.get("domains"),
            ),
            stream="system",
            metadata={"step": "runtime wait", "attempt": attempt, "snapshot": snapshot},
            env=env,
        )

    def _runtime_wait_snapshot(self, runtime):
        runtime = runtime or {}
        return {
            "checked_at": runtime.get("checked_at"),
            "stack": (runtime.get("stack") or {}).get("summary") or {},
            "containers": (runtime.get("containers") or {}).get("summary") or {},
            "health": (runtime.get("containers") or {}).get("health") or {},
            "domains": (runtime.get("domains") or {}).get("summary") or {},
        }

    def _runtime_snapshot_ready(self, snapshot):
        stack = snapshot.get("stack") or {}
        containers = snapshot.get("containers") or {}
        health = snapshot.get("health") or {}
        desired = self._safe_int(stack.get("desired"), 0)
        running = self._safe_int(stack.get("running"), 0)
        task_errors = self._safe_int(stack.get("task_errors"), 0)
        stopped = self._safe_int(containers.get("stopped"), 0)
        unhealthy = self._safe_int(health.get("unhealthy"), 0)
        starting = self._safe_int(health.get("starting"), 0)
        if desired > 0 and running < desired:
            return False
        if task_errors > 0 or stopped > 0 or unhealthy > 0 or starting > 0:
            return False
        return desired > 0 or running > 0

    def _runtime_snapshot_key(self, snapshot):
        try:
            return json.dumps(
                {
                    "stack": snapshot.get("stack") or {},
                    "containers": snapshot.get("containers") or {},
                    "health": snapshot.get("health") or {},
                    "domains": snapshot.get("domains") or {},
                    "error": snapshot.get("error"),
                },
                ensure_ascii=False,
                sort_keys=True,
            )
        except Exception:
            return str(snapshot)

    def _runtime_snapshot_blocked(self, snapshot):
        stack = snapshot.get("stack") or {}
        containers = snapshot.get("containers") or {}
        health = snapshot.get("health") or {}
        desired = self._safe_int(stack.get("desired"), 0)
        running = self._safe_int(stack.get("running"), 0)
        task_errors = self._safe_int(stack.get("task_errors"), 0)
        stopped = self._safe_int(containers.get("stopped"), 0)
        unhealthy = self._safe_int(health.get("unhealthy"), 0)
        return desired > 0 and (running < desired or task_errors > 0 or stopped > 0 or unhealthy > 0)

    def _wait_operation_finished(self, operation_id, parent_operation_id, env=None):
        deadline = time.monotonic() + AI_VERIFY_DEPLOY_WAIT_SECONDS
        while time.monotonic() < deadline:
            operation = operations.detail(operation_id, env=env)
            status = self._clean_text(operation.get("status")).lower()
            operations.append_output(
                parent_operation_id,
                "재배포 작업 상태: %s" % (status or "unknown"),
                stream="system" if status in {"pending", "running", "succeeded"} else "stderr",
                metadata={"step": "deploy wait", "deploy_operation_id": operation_id, "status": status},
                env=env,
            )
            if status not in {"pending", "running"}:
                return {"status": status, "operation": operation}
            time.sleep(5)
        return {"status": "timeout", "operation_id": operation_id}

    def _compact_verification_result(self, result):
        if not isinstance(result, dict):
            return result
        return {
            "ok": result.get("ok"),
            "applied": result.get("applied"),
            "summary": result.get("summary"),
            "issues": result.get("issues") or [],
            "warnings": result.get("warnings") or [],
            "checks": result.get("checks") or {},
            "deploy_operation_id": ((result.get("deploy_result") or {}).get("operation") or {}).get("id"),
            "diagnostics": {
                "needs_repair": (result.get("diagnostics") or {}).get("needs_repair"),
                "signals": (result.get("diagnostics") or {}).get("signals") or [],
            },
        }

    def verify_runtime(self, payload, env=None):
        payload = dict(payload or {})
        service_id = self._clean_text(payload.get("service_id"))
        if not service_id:
            raise AIAssistantError(400, "service_id는 필수입니다.", "SERVICE_ID_REQUIRED")
        provider = self._select_provider(env=env, selection=payload)
        detail = self._service_detail_for_ai(service_id, env=env)
        diagnostics = self._runtime_diagnostics(detail, payload=payload, env=env)
        context = self._runtime_verification_context(detail, diagnostics, payload)
        data, _ = self._complete_json(self._runtime_verification_system_prompt(), context, provider=provider, env=env)
        if not isinstance(data, dict):
            raise AIAssistantError(502, "AI 검증 응답 JSON 객체가 비어 있습니다.", "AI_EMPTY_RESPONSE")
        ok = data.get("ok") is True
        issues = data.get("issues") if isinstance(data.get("issues"), list) else []
        if diagnostics.get("needs_repair") is True and not issues:
            issues = diagnostics.get("signals") or []
        if diagnostics.get("needs_repair") is True:
            ok = False
        return {
            "provider": self._provider_public(provider),
            "ok": ok and not issues,
            "summary": self._clean_text(data.get("summary")) or ("AI 검증을 통과했습니다." if ok else "AI 검증에서 문제를 발견했습니다."),
            "issues": issues,
            "warnings": self._string_list(data.get("warnings")),
            "checks": data.get("checks") if isinstance(data.get("checks"), dict) else {},
            "repair_required": data.get("repair_required") is True or bool(issues) or diagnostics.get("needs_repair") is True,
            "repair_intent": self._clean_text(data.get("repair_intent")),
            "diagnostics": diagnostics,
        }

    def _runtime_verification_system_prompt(self):
        return "\n".join(
            [
                "You are an autonomous Docker Infra post-deploy verifier for non-developer users.",
                "Use the enabled docker_infra MCP tools to inspect the real current state before judging success.",
                "Verify Docker stack tasks, container health, recent logs, DNS resolution, TCP connectivity, HTTP response, and whether the user's requested service purpose appears reachable.",
                "You may use safe SSH diagnostics when enabled, but do not run destructive commands during the verification-only step.",
                "If a fix is needed, do not return a service draft here. Return a Korean repair_intent that the repair step can use.",
                "Return only one JSON object with keys: ok, summary, issues, warnings, checks, repair_required, repair_intent.",
                "issues must be an array of objects with key, severity, message, evidence.",
                "checks should include stack, containers, domains, network, http, user_function when known.",
                "Write summary, issues[].message, warnings, and repair_intent in Korean.",
            ]
        )

    def _runtime_verification_context(self, detail, diagnostics, payload):
        service = detail.get("service") or {}
        domains = detail.get("domains") or []
        enabled_tools = [
            "infra_context",
            "server_list",
            "server_port_check",
            "service_stack_status",
            "container_logs",
            "server_collect",
            "dns_lookup",
            "tcp_connect_check",
            "http_probe",
            "ssh_command",
        ]
        return {
            "mode": "post_deploy_verification",
            "service": service,
            "domains": domains,
            "form": {
                "name": service.get("name") or service.get("namespace"),
                "description": (service.get("metadata") or {}).get("description") or "",
                "domains": self._domain_rows_for_context(domains),
            },
            "components": detail.get("components") or [],
            "base_content": detail.get("compose_content") or "",
            "runtime_status": detail.get("runtime_status") or {},
            "recent_operations": detail.get("operations") or [],
            "runtime_diagnostics": diagnostics,
            "runtime_wait": payload.get("runtime_wait") or {},
            "user_intent": self._clean_text(payload.get("intent")),
            "client_runtime_issues": payload.get("client_runtime_issues") if isinstance(payload.get("client_runtime_issues"), dict) else {},
            "ai_permission_scope": {
                "scope": "post_deploy_verification",
                "can_edit_project_files": False,
                "can_deploy": payload.get("deploy") is not False,
                "can_change_runtime": False,
                "can_run_safe_ssh_diagnostics": payload.get("allow_ssh_command") is not False,
                "can_run_container_actions": False,
                "allow_ssh_command": payload.get("allow_ssh_command") is not False,
                "mcp_enabled_tools": enabled_tools,
            },
            "mcp_guidance": {
                "server": "docker_infra",
                "enabled_tools": enabled_tools,
                "preferred_tools": enabled_tools,
                "allow_ssh_command": payload.get("allow_ssh_command") is not False,
            },
        }

    def _finish_runtime_repair(self, provider, detail, diagnostics, payload, data, context, env=None):
        service_id = self._clean_text(payload.get("service_id"))
        draft = self._normalize_service_draft(data, fallback=context)
        rendered = self._validate_service_draft(draft, context, env=env)
        result = {
            "provider": self._provider_public(provider),
            "diagnostics": diagnostics,
            "draft": draft,
            "rendered": rendered,
            "summary": self._clean_text(data.get("summary")),
            "warnings": self._string_list(data.get("warnings")),
            "applied": False,
        }
        if payload.get("apply") is False:
            return result

        terminal_action_results = self._execute_runtime_actions(data, diagnostics, detail, payload, env=env)
        if terminal_action_results:
            result["terminal_action_results"] = terminal_action_results

        update_result = services_model.update_wizard(
            self._runtime_repair_update_payload(service_id, draft, rendered, detail),
            env=env,
        )
        result["applied"] = True
        result["update_result"] = update_result
        if payload.get("deploy") is not False:
            result["deploy_result"] = services_model.deploy_background({"service_id": service_id, "start_ai_verification": False}, env=env)
        return result

    def _service_detail_for_ai(self, service_id, env=None):
        try:
            services_model.refresh_deploy_status(service_id, env=env)
        except Exception:
            pass
        detail = services_model.detail(service_id, env=env)
        detail["components"] = services_wizard.components_from_content(detail.get("compose_content"))
        return detail

    def _runtime_repair_system_prompt(self):
        return "\n".join(
            [
                self._system_prompt("service"),
                "You are repairing a Docker Infra service after deployment or runtime health failure.",
                "Use runtime_diagnostics, container logs, stack task errors, current Compose, domains, and Docker Infra constraints to return a corrected full service JSON object.",
                "Prefer minimal, deployable changes: fix invalid env vars, healthchecks, commands, ports, dependencies, image tags, volumes, and domain targets.",
                "Do not remove persistent volumes unless the user explicitly asks. Do not invent secret values; use generated_secret_keys.",
                "When logs say a password or secret must be set, set the exact environment variable the image reads with a non-empty stack-local generated value; do not blindly convert it to *_FILE or Docker secrets.",
                "If a deployment rolled back after startup, check healthcheck commands and update_config failure_action. Avoid fragile healthchecks that depend on tools not present in the image.",
                "If terminal_actions.allow_container_actions is true, you may use docker_infra.container_action to stop, restart, or remove only the problem containers listed in runtime_diagnostics or client_runtime_issues.",
                "If safe SSH diagnostics are enabled, you may use docker_infra.ssh_command for read-only inspection commands on registered servers.",
                "When a container terminal action is needed, also return runtime_actions as an array of objects: {action, container_id, node_id, reason}. Use action stop, restart, or remove only.",
                "If you already executed an action through MCP, set executed=true on that runtime_actions item so Docker Infra will record it without running it twice.",
                "Never remove Docker volumes or unrelated containers. Summarize any terminal action you executed in Korean warnings or summary.",
                "If the safest action is operational rather than Compose editing, keep Compose stable and return Korean warnings with the manual action.",
            ]
        )

    def _runtime_repair_context(self, detail, diagnostics, payload):
        service = detail.get("service") or {}
        domains = detail.get("domains") or []
        client_runtime_issues = payload.get("client_runtime_issues") if isinstance(payload.get("client_runtime_issues"), dict) else {}
        allow_container_actions = payload.get("allow_container_terminal_actions") is not False
        allow_ssh_command = payload.get("allow_ssh_command") is not False
        enabled_tools = [
            "service_stack_status",
            "container_logs",
            "server_collect",
            "server_port_check",
            "dns_lookup",
            "tcp_connect_check",
            "http_probe",
            "infra_context",
            "server_list",
        ]
        if allow_container_actions:
            enabled_tools.append("container_action")
        if allow_ssh_command:
            enabled_tools.append("ssh_command")
        form = {
            "name": service.get("name") or service.get("namespace"),
            "description": (service.get("metadata") or {}).get("description") or "",
            "domain_mode": "registered" if domains else "none",
            "domains": self._domain_rows_for_context(domains),
        }
        primary = form["domains"][0] if form["domains"] else {}
        form.update(
            {
                "domain": primary.get("domain", ""),
                "zone_id": primary.get("zone_id", ""),
                "domain_prefix": primary.get("domain_prefix", ""),
                "domain_target_key": primary.get("domain_target_key", ""),
                "domain_target_port": primary.get("domain_target_port", ""),
            }
        )
        return {
            "contract": self.service_contract(),
            "output_format": self.output_format_contract("service"),
            "compose_validation": self.compose_validation_contract(),
            "mode": "service_update",
            "ai_permission_scope": {
                "scope": "runtime_repair" if allow_container_actions else "runtime_inspection",
                "can_edit_project_files": False,
                "can_deploy": payload.get("deploy") is not False,
                "can_change_runtime": allow_container_actions,
                "can_run_container_actions": allow_container_actions,
                "can_run_safe_ssh_diagnostics": allow_ssh_command,
                "allow_ssh_command": allow_ssh_command,
                "mcp_enabled_tools": enabled_tools,
            },
            "intent": self._clean_text(payload.get("intent")) or "배포 후 실패한 서비스 상태와 로그를 분석해 Docker Infra에서 재배포 가능한 수정안을 만들어주세요.",
            "operator_message": self._clean_text(payload.get("intent")),
            "form": form,
            "components": detail.get("components") or [],
            "base_content": detail.get("compose_content") or "",
            "service": service,
            "domains": domains,
            "runtime_status": detail.get("runtime_status") or {},
            "recent_operations": detail.get("operations") or [],
            "runtime_diagnostics": diagnostics,
            "client_runtime_issues": client_runtime_issues,
            "terminal_actions": {
                "allow_container_actions": allow_container_actions,
                "allowed_actions": ["stop", "restart", "remove"] if allow_container_actions else [],
                "scope": "problem containers from runtime_diagnostics.problem_containers and client_runtime_issues.problem_containers only",
                "return_field": "runtime_actions",
                "schema": {"action": "stop|restart|remove", "container_id": "container id or name", "node_id": "registered node id", "reason": "Korean reason", "executed": "true only if MCP already executed it"},
            },
            "docker_infra_context": {
                **self._service_create_context({"mode": "service_update"}),
                "repair_flow": "refresh runtime status, collect container logs and stack errors, ask Codex AI for a corrected service draft, save the corrected compose, then redeploy when requested",
            },
            "mcp_guidance": {
                "server": "docker_infra",
                "enabled_tools": enabled_tools,
                "preferred_tools": enabled_tools,
                "allow_ssh_command": allow_ssh_command,
            },
        }

    def _domain_rows_for_context(self, domains):
        rows = []
        for item in domains or []:
            metadata = dict(item.get("metadata") or {})
            target_port = metadata.get("target_port") or item.get("port")
            rows.append(
                {
                    "domain": item.get("domain"),
                    "zone_id": metadata.get("zone_id"),
                    "domain_prefix": self._prefix_from_domain(item.get("domain"), []),
                    "domain_target_key": "%s:%s" % (metadata.get("compose_service") or "", target_port or ""),
                    "domain_target_port": target_port,
                    "compose_service": metadata.get("compose_service"),
                    "target_port": target_port,
                    "published_port": metadata.get("published_port") or item.get("port"),
                    "ssl_mode": item.get("ssl_mode"),
                }
            )
        return rows

    def _runtime_repair_update_payload(self, service_id, draft, rendered, detail):
        form = draft.get("form") or {}
        domains = form.get("domains") if isinstance(form.get("domains"), list) else []
        primary = domains[0] if domains else {}
        return {
            "service_id": service_id,
            "name": form.get("name") or (detail.get("service") or {}).get("name"),
            "description": form.get("description") or ((detail.get("service") or {}).get("metadata") or {}).get("description"),
            "content": rendered,
            "base_content": rendered,
            "components": draft.get("components") or [],
            "generated_secret_keys": draft.get("generated_secret_keys") or [],
            "domain_mode": form.get("domain_mode") or ("registered" if domains else "none"),
            "domain": primary.get("domain") or form.get("domain") or "",
            "domains": domains,
            "zone_id": primary.get("zone_id") or form.get("zone_id"),
            "domain_target_key": primary.get("domain_target_key") or form.get("domain_target_key"),
            "domain_target_port": primary.get("domain_target_port") or primary.get("target_port") or form.get("domain_target_port"),
            "port": primary.get("target_port") or primary.get("domain_target_port") or form.get("domain_target_port"),
            "domain_metadata": {
                "compose_service": primary.get("compose_service") or self._clean_text(primary.get("domain_target_key")).split(":", 1)[0],
                "target_port": primary.get("target_port") or primary.get("domain_target_port") or form.get("domain_target_port"),
                "published_port": primary.get("published_port") or primary.get("target_port") or primary.get("domain_target_port"),
                "zone_id": primary.get("zone_id") or form.get("zone_id"),
                "source": "ai_runtime_repair",
            },
            "wizard": {"components": draft.get("components") or [], "domain_mode": form.get("domain_mode"), "domains": domains},
            "draft_metadata": {"source": "ai_runtime_repair", "runtime_repair": True},
        }

    def _runtime_diagnostics(self, detail, payload=None, env=None):
        payload = payload or {}
        service = detail.get("service") or {}
        runtime = detail.get("runtime_status") or {}
        containers = ((runtime.get("containers") or {}).get("containers") or [])
        stack = runtime.get("stack") or {}
        stack_summary = stack.get("summary") or {}
        task_errors = []
        for task in stack.get("tasks") or []:
            desired = self._clean_text(task.get("DesiredState") or task.get("Desired state")).lower()
            current = self._clean_text(task.get("CurrentState") or task.get("Current state")).lower()
            error = self._clean_text(task.get("Error"))
            if error or (desired == "running" and current and not current.startswith(("running", "preparing", "starting"))):
                task_errors.append(task)
        problem_containers = [item for item in containers if self._container_needs_repair(item)]
        failed_operations = [
            item for item in (detail.get("operations") or [])
            if self._clean_text(item.get("status")).lower() in {"failed", "canceled"}
        ][:10]
        failed_operations = self._merge_runtime_operations(failed_operations, self._client_failed_operations(payload))
        client_runtime_issues = payload.get("client_runtime_issues") if isinstance(payload.get("client_runtime_issues"), dict) else {}
        signals = self._runtime_issue_signals(service, stack_summary, runtime.get("containers") or {}, failed_operations, client_runtime_issues)
        logs = []
        for item in problem_containers[:5]:
            logs.append(
                {
                    "container": self._compact_container(item),
                    "inspect": self._container_command(item, ["docker", "inspect", item.get("id")], env=env),
                    "logs": self._container_command(item, ["docker", "logs", "--tail", "160", item.get("id")], env=env),
                }
            )
        needs_repair = bool(signals or problem_containers or task_errors)
        return {
            "needs_repair": needs_repair,
            "service_status": service.get("status"),
            "signals": signals,
            "failed_operations": failed_operations,
            "problem_containers": [self._compact_container(item) for item in problem_containers],
            "task_errors": task_errors[:12],
            "stack_summary": stack_summary,
            "container_summary": (runtime.get("containers") or {}).get("summary") or {},
            "container_health": (runtime.get("containers") or {}).get("health") or {},
            "logs": logs,
        }

    def _runtime_issue_signals(self, service, stack_summary, container_status, failed_operations, client_runtime_issues=None):
        client_runtime_issues = client_runtime_issues or {}
        signals = []
        service_status = self._clean_text(service.get("status")).lower()
        client_service_status = self._clean_text(client_runtime_issues.get("service_status")).lower()
        if service_status in {"failed", "canceled"}:
            signals.append({"key": "service_status", "message": "서비스 상태가 실패 또는 취소 상태입니다.", "value": service_status})
        elif client_service_status in {"failed", "canceled"}:
            signals.append({"key": "client_service_status", "message": "화면에 표시된 서비스 상태가 실패 또는 취소 상태입니다.", "value": client_service_status})
        if failed_operations:
            signals.append({"key": "operation_failed", "message": "최근 처리 내역에 실패한 작업이 있습니다.", "count": len(failed_operations)})

        desired = self._safe_int(stack_summary.get("desired"), 0)
        running = self._safe_int(stack_summary.get("running"), 0)
        client_stack = client_runtime_issues.get("stack_summary") if isinstance(client_runtime_issues.get("stack_summary"), dict) else {}
        if desired <= 0 and self._safe_int(client_stack.get("desired"), 0) > 0:
            desired = self._safe_int(client_stack.get("desired"), 0)
            running = self._safe_int(client_stack.get("running"), 0)
        if self._safe_int(stack_summary.get("task_errors"), 0) > 0:
            signals.append({"key": "stack_task_errors", "message": "Docker stack task 오류가 있습니다.", "count": self._safe_int(stack_summary.get("task_errors"), 0)})
        elif self._safe_int(client_stack.get("task_errors"), 0) > 0:
            signals.append({"key": "client_stack_task_errors", "message": "화면에 표시된 Docker stack task 오류가 있습니다.", "count": self._safe_int(client_stack.get("task_errors"), 0)})
        if desired > 0 and running < desired:
            signals.append({"key": "stack_replicas", "message": "Docker stack 실행 수가 목표 수보다 적습니다.", "desired": desired, "running": running})

        summary = (container_status or {}).get("summary") or {}
        health = (container_status or {}).get("health") or {}
        client_summary = client_runtime_issues.get("container_summary") if isinstance(client_runtime_issues.get("container_summary"), dict) else {}
        client_health = client_runtime_issues.get("container_health") if isinstance(client_runtime_issues.get("container_health"), dict) else {}
        stopped = self._safe_int(summary.get("stopped"), 0)
        unhealthy = self._safe_int(health.get("unhealthy"), 0)
        unknown = self._safe_int(summary.get("unknown"), 0)
        if stopped <= 0:
            stopped = self._safe_int(client_summary.get("stopped"), 0)
        if unhealthy <= 0:
            unhealthy = self._safe_int(client_health.get("unhealthy"), 0)
        if unknown <= 0:
            unknown = self._safe_int(client_summary.get("unknown"), 0)
        if stopped > 0:
            signals.append({"key": "containers_stopped", "message": "중지된 컨테이너가 있습니다.", "count": stopped})
        if unhealthy > 0:
            signals.append({"key": "containers_unhealthy", "message": "unhealthy 컨테이너가 있습니다.", "count": unhealthy})
        if unknown > 0:
            signals.append({"key": "containers_unknown", "message": "상태를 확인할 수 없는 컨테이너가 있습니다.", "count": unknown})
        if client_runtime_issues.get("has_runtime_issues") is True and not signals:
            signals.append({"key": "client_runtime_issue", "message": "화면에 표시된 런타임 검사 조건이 문제 상태입니다."})
        return signals

    def _client_failed_operations(self, payload):
        client_runtime_issues = payload.get("client_runtime_issues") if isinstance(payload.get("client_runtime_issues"), dict) else {}
        operations = client_runtime_issues.get("failed_operations") if isinstance(client_runtime_issues.get("failed_operations"), list) else []
        return [
            self._compact_operation(item)
            for item in operations
            if isinstance(item, dict) and self._clean_text(item.get("status")).lower() in {"failed", "canceled"}
        ][:10]

    def _merge_runtime_operations(self, primary, fallback):
        merged = []
        seen = set()
        for item in list(primary or []) + list(fallback or []):
            if not isinstance(item, dict):
                continue
            key = self._clean_text(item.get("id")) or "%s:%s:%s" % (
                self._clean_text(item.get("type")),
                self._clean_text(item.get("status")),
                self._clean_text(item.get("created_at")),
            )
            if key in seen:
                continue
            seen.add(key)
            merged.append(self._compact_operation(item))
            if len(merged) >= 10:
                break
        return merged

    def _compact_operation(self, item):
        output = item.get("output") if isinstance(item.get("output"), list) else []
        return {
            "id": item.get("id"),
            "type": item.get("type"),
            "status": item.get("status"),
            "message": item.get("message"),
            "created_at": item.get("created_at"),
            "started_at": item.get("started_at"),
            "finished_at": item.get("finished_at"),
            "result_payload": item.get("result_payload") or {},
            "output": output[-30:],
        }

    def _container_needs_repair(self, item):
        state = self._clean_text(item.get("state")).lower()
        status = self._clean_text(item.get("status")).lower()
        if "unhealthy" in status or "dead" in state:
            return True
        if state and state not in {"running"}:
            return True
        return False

    def _compact_container(self, item):
        return {
            "id": item.get("id"),
            "name": item.get("name"),
            "image": item.get("image"),
            "state": item.get("state"),
            "status": item.get("status"),
            "node_id": item.get("node_id"),
            "node_name": item.get("node_name"),
            "runtime_service_name": item.get("runtime_service_name"),
            "port_bindings": item.get("port_bindings") or [],
        }

    def _container_command(self, container, command, env=None):
        node_id = self._clean_text(container.get("node_id"))
        container_id = self._clean_text(container.get("id"))
        if not node_id or not container_id:
            return {"status": "skipped", "message": "container node or id is missing"}
        try:
            node = nodes_model.detail(node_id, env=env)
            if node.get("is_local_master"):
                completed = subprocess.run(command, capture_output=True, text=True, timeout=20, check=False)
                return {
                    "status": "ok" if completed.returncode == 0 else "error",
                    "exit_code": completed.returncode,
                    "stdout": self._trim_diagnostic(completed.stdout),
                    "stderr": self._trim_diagnostic(completed.stderr),
                }
            result = nodes_model._run_ssh_command(node, command, timeout_seconds=25, env=env)
            return {
                "status": result.get("status"),
                "exit_code": result.get("exit_code"),
                "stdout": self._trim_diagnostic(result.get("stdout")),
                "stderr": self._trim_diagnostic(result.get("stderr")),
            }
        except Exception as exc:
            return {"status": "error", "message": str(exc)}

    def _runtime_actions_from_ai(self, data):
        raw = data.get("runtime_actions")
        if raw is None:
            raw = data.get("container_actions")
        if not isinstance(raw, list):
            return []
        actions = []
        for item in raw[:8]:
            if not isinstance(item, dict):
                continue
            action = self._clean_text(item.get("action")).lower()
            if action in {"delete", "rm"}:
                action = "remove"
            container_id = self._clean_text(item.get("container_id") or item.get("id") or item.get("name")).lstrip("/")
            node_id = self._clean_text(item.get("node_id"))
            if not action or not container_id:
                continue
            actions.append(
                {
                    "action": action,
                    "container_id": container_id,
                    "node_id": node_id,
                    "reason": self._clean_text(item.get("reason") or item.get("message")),
                    "executed": item.get("executed") is True or self._clean_text(item.get("executed")).lower() == "true",
                }
            )
        return actions

    def _runtime_action_container_index(self, detail, diagnostics, payload):
        client_runtime_issues = payload.get("client_runtime_issues") if isinstance(payload.get("client_runtime_issues"), dict) else {}
        runtime = detail.get("runtime_status") or {}
        groups = [
            ((runtime.get("containers") or {}).get("containers") or []),
            diagnostics.get("problem_containers") or [],
            [item.get("container") for item in diagnostics.get("logs") or [] if isinstance(item, dict)],
            client_runtime_issues.get("problem_containers") if isinstance(client_runtime_issues.get("problem_containers"), list) else [],
            client_runtime_issues.get("containers") if isinstance(client_runtime_issues.get("containers"), list) else [],
        ]
        index = {}
        for group in groups:
            for item in group or []:
                if not isinstance(item, dict):
                    continue
                container = self._compact_container(item)
                if not container.get("id") and item.get("container_id"):
                    container["id"] = item.get("container_id")
                if not container.get("node_id") and item.get("node"):
                    container["node_id"] = item.get("node")
                for value in [container.get("id"), container.get("name")]:
                    key = self._clean_text(value).lstrip("/")
                    if not key:
                        continue
                    index[key] = container
                    index[key.lower()] = container
                    if len(key) > 12:
                        index.setdefault(key[:12], container)
        return index

    def _execute_runtime_actions(self, data, diagnostics, detail, payload, env=None):
        actions = self._runtime_actions_from_ai(data or {})
        if not actions:
            return []
        if payload.get("allow_container_terminal_actions") is not True:
            return [
                {
                    **action,
                    "status": "skipped",
                    "message": "컨테이너 터미널 조치가 허용되지 않았습니다.",
                }
                for action in actions
            ]
        container_index = self._runtime_action_container_index(detail or {}, diagnostics or {}, payload or {})
        results = []
        for action in actions:
            container_key = self._clean_text(action.get("container_id")).lstrip("/")
            container = container_index.get(container_key) or container_index.get(container_key.lower())
            if not container:
                results.append({**action, "status": "skipped", "message": "허용된 문제 컨테이너 목록에서 찾을 수 없습니다."})
                continue
            if action.get("node_id") and self._clean_text(container.get("node_id")) != action.get("node_id"):
                results.append({**action, "status": "skipped", "message": "요청 node_id가 컨테이너 node_id와 다릅니다."})
                continue
            if action.get("executed"):
                results.append({**action, "status": "recorded", "message": "AI MCP 도구에서 이미 실행한 조치로 기록했습니다."})
                continue
            results.append({**action, **self._run_container_terminal_action(container, action.get("action"), env=env)})
        return results

    def _run_container_terminal_action(self, container, action, env=None):
        action = self._clean_text(action).lower()
        if action not in {"stop", "restart", "remove"}:
            return {"status": "skipped", "message": "지원하지 않는 컨테이너 조치입니다."}
        node_id = self._clean_text(container.get("node_id"))
        container_id = self._clean_text(container.get("id") or container.get("name")).lstrip("/")
        if not node_id or not container_id:
            return {"status": "skipped", "message": "컨테이너 node_id 또는 id가 없습니다."}
        if re.match(r"^[A-Za-z0-9_.:-]{3,160}$", container_id) is None:
            return {"status": "skipped", "message": "컨테이너 id 형식이 올바르지 않습니다."}
        quoted = shlex.quote(container_id)
        if action == "stop":
            command = ["docker", "stop", container_id]
        elif action == "restart":
            command = ["docker", "restart", container_id]
        else:
            command = ["sh", "-lc", "docker stop %s >/dev/null 2>&1 || true; docker rm %s" % (quoted, quoted)]
        try:
            node = nodes_model.detail(node_id, env=env)
            if node.get("is_local_master"):
                completed = subprocess.run(command, capture_output=True, text=True, timeout=60, check=False)
                return {
                    "status": "ok" if completed.returncode == 0 else "error",
                    "exit_code": completed.returncode,
                    "command_display": shlex.join(command),
                    "stdout": self._trim_diagnostic(completed.stdout),
                    "stderr": self._trim_diagnostic(completed.stderr),
                }
            result = nodes_model._run_ssh_command(node, command, timeout_seconds=60, env=env)
            return {
                "status": result.get("status"),
                "exit_code": result.get("exit_code"),
                "command_display": result.get("command_display") or shlex.join(command),
                "stdout": self._trim_diagnostic(result.get("stdout")),
                "stderr": self._trim_diagnostic(result.get("stderr")),
            }
        except Exception as exc:
            return {"status": "error", "message": str(exc), "command_display": shlex.join(command)}

    def _complete_service_multiphase(self, context, provider, env=None):
        plan_data = {}
        plan_error = None
        try:
            plan_data, _ = self._complete_json(
                self._service_plan_system_prompt(),
                self._service_plan_context(context),
                provider=provider,
                env=env,
            )
        except Exception as exc:
            if not self._is_output_repairable_error(exc):
                raise
            plan_error = self._exception_payload(exc)

        plan_draft, plan_rendered, inspection = self._inspect_service_plan(
            plan_data,
            context,
            env=env,
            plan_error=plan_error,
        )
        request_context = self._service_review_context(context, plan_data, plan_draft, plan_rendered, inspection)
        request_system = self._service_review_system_prompt()
        data = None
        last_error = None
        for attempt in range(MAX_AI_REPAIR_ATTEMPTS + 1):
            try:
                data, _ = self._complete_json(request_system, request_context, provider=provider, env=env)
                if not isinstance(data, dict):
                    raise AIAssistantError(502, "AI 응답 JSON 객체가 비어 있습니다.", "AI_EMPTY_RESPONSE")
                draft = self._normalize_service_draft(data, fallback=context)
                rendered = self._validate_service_draft(draft, context, env=env)
                return draft, rendered, data, self._service_pipeline_metadata(plan_data, inspection)
            except Exception as exc:
                last_error = exc
                if not self._is_output_repairable_error(exc):
                    raise
                if attempt >= MAX_AI_REPAIR_ATTEMPTS:
                    raise self._as_output_validation_error(exc, "service")
                request_context = self._repair_context("service", context, data, exc, attempt + 1)
                request_context["initial_draft"] = plan_data or {}
                request_context["docker_infra_inspection"] = inspection
                request_system = self._repair_system_prompt("service")
        raise self._as_output_validation_error(last_error, "service")

    def _complete_service_until_valid(self, system, context, provider, env=None):
        data = None
        last_error = None
        request_context = context
        request_system = system
        for attempt in range(MAX_AI_REPAIR_ATTEMPTS + 1):
            try:
                data, _ = self._complete_json(request_system, request_context, provider=provider, env=env)
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

    def _service_plan_system_prompt(self):
        return "\n".join(
            [
                self._system_prompt("service"),
                "This is phase 1 of a multi-call Docker Infra service workflow.",
                "Focus on a practical first draft: exact Docker images, image tags, container ports, published ports, volumes, env vars, and public endpoint target.",
                "Use the docker_infra MCP tools when helpful, especially docker_search, docker_image_check, infra_context, and server_list.",
                "Return a complete service JSON object for the normal service contract, even though the result will be inspected before final use.",
            ]
        )

    def _service_review_system_prompt(self):
        return "\n".join(
            [
                self._system_prompt("service"),
                "This is phase 2 of a multi-call Docker Infra service workflow.",
                "You are validating and correcting the first draft using docker_infra_inspection.",
                "Use inspection blocking items, warnings, placement recommendation, port checks, and image checks as hard feedback.",
                "If an image or tag failed validation, choose a valid replacement image_name and image_tag from inspection or MCP search results.",
                "If published ports are adjusted or already used, keep target ports stable and update published ports or warnings accordingly.",
                "Return the final complete service JSON object only. Do not include the inspection report as prose outside JSON.",
            ]
        )

    def _service_plan_context(self, context):
        result = dict(context or {})
        enabled_tools = ["infra_context", "docker_search", "docker_image_check", "server_list", "server_port_check", "server_collect", "ssh_command"]
        result["ai_phase"] = "initial_draft"
        result["ai_permission_scope"] = {
            "scope": "service_draft",
            "can_edit_project_files": False,
            "can_deploy": False,
            "can_change_runtime": False,
            "can_run_container_actions": False,
            "can_run_safe_ssh_diagnostics": True,
            "allow_ssh_command": True,
            "mcp_enabled_tools": enabled_tools,
        }
        result["phase_goal"] = (
            "First AI call: draft the service shape, image choices, image versions, component ports, "
            "published ports, env vars, volumes, and public endpoint target before Docker Infra inspection."
        )
        result["mcp_guidance"] = {
            "server": "docker_infra",
            "enabled_tools": enabled_tools,
            "preferred_tools": enabled_tools,
            "allow_ssh_command": True,
        }
        return result

    def _service_review_context(self, context, plan_data, plan_draft, plan_rendered, inspection):
        result = dict(context or {})
        enabled_tools = ["infra_context", "docker_search", "docker_image_check", "server_list", "server_port_check", "server_collect", "ssh_command"]
        result["ai_phase"] = "inspection_correction"
        result["ai_permission_scope"] = {
            "scope": "service_preflight_repair",
            "can_edit_project_files": False,
            "can_deploy": False,
            "can_change_runtime": False,
            "can_run_container_actions": False,
            "can_run_safe_ssh_diagnostics": True,
            "allow_ssh_command": True,
            "mcp_enabled_tools": enabled_tools,
        }
        result["phase_goal"] = (
            "Second AI call: correct the first draft using the Docker Infra inspection result, then return "
            "a complete final output that passes this application's compose, image, port, and placement checks."
        )
        result["initial_draft"] = plan_data or {}
        result["normalized_initial_draft"] = plan_draft or {}
        result["initial_rendered_compose"] = self._line_numbered_text(plan_rendered, max_lines=180, max_chars=14000)
        result["docker_infra_inspection"] = inspection or {}
        result["mcp_guidance"] = {
            "server": "docker_infra",
            "enabled_tools": enabled_tools,
            "preferred_tools": enabled_tools,
            "allow_ssh_command": True,
        }
        return result

    def _service_pipeline_metadata(self, plan_data, inspection):
        inspection = inspection or {}
        return {
            "engine": "codex",
            "phases": [
                {
                    "key": "initial_draft",
                    "label": "1차 AI 초안",
                    "summary": self._clean_text((plan_data or {}).get("summary")),
                    "warnings": self._string_list((plan_data or {}).get("warnings")),
                },
                {
                    "key": "docker_infra_inspection",
                    "label": "Docker Infra 상태 검사",
                    "ok": bool(inspection.get("ok")),
                    "summary": inspection.get("summary") or {},
                    "blocking": inspection.get("blocking") or [],
                    "warnings": inspection.get("warnings") or [],
                },
                {
                    "key": "final_correction",
                    "label": "2차 AI 보정",
                },
            ],
        }

    def _inspect_service_plan(self, data, context, env=None, plan_error=None):
        inspection = {
            "ok": False,
            "summary": {"total": 0, "blocking": 0, "warnings": 0, "passed": 0},
            "blocking": [],
            "warnings": [],
            "items": [],
            "component_ports": [],
            "placement": None,
        }
        if plan_error:
            inspection["planning_error"] = plan_error
        draft = None
        rendered = ""
        if not isinstance(data, dict) or not data:
            inspection["blocking"].append(
                {
                    "key": "initial_draft",
                    "title": "1차 AI 초안",
                    "status": "error",
                    "message": "1차 AI 초안이 비어 있어 원 요청 기준으로 2차 보정을 진행합니다.",
                }
            )
            inspection["summary"]["blocking"] = len(inspection["blocking"])
            inspection["summary"]["total"] = len(inspection["blocking"])
            return draft, rendered, inspection

        try:
            draft = self._normalize_service_draft(data, fallback=context)
            self._resolve_component_images(draft)
            inspection["component_ports"] = self._component_port_summary(draft)
        except Exception as exc:
            inspection["normalization_error"] = self._exception_payload(exc)
            inspection["blocking"].append(
                {
                    "key": "initial_draft.normalize",
                    "title": "1차 초안 정규화",
                    "status": "error",
                    "message": getattr(exc, "message", str(exc)),
                    "details": getattr(exc, "details", {}),
                }
            )
            inspection["summary"]["blocking"] = len(inspection["blocking"])
            inspection["summary"]["total"] = len(inspection["blocking"])
            return draft, rendered, inspection

        namespace = self._namespace((draft.get("form") or {}).get("name") or (context.get("form") or {}).get("name") or "ai_service")
        validation = None
        try:
            rendered = self._render_service_draft(draft, context)
            if not str(rendered or "").strip():
                raise AIAssistantError(422, "AI 응답에 Compose 초안이 없습니다.", "AI_OUTPUT_MISSING_FIELD")
            validation = compose_validator.validate(
                {
                    "namespace": namespace,
                    "filename": "docker-compose.yaml",
                    "content": rendered,
                }
            )
            inspection["compose_validation"] = {
                "ok": True,
                "services": list(((validation.get("normalized") or {}).get("services") or {}).keys()),
            }
        except Exception as exc:
            inspection["compose_validation"] = {"ok": False, "error": self._exception_payload(exc)}
            inspection["blocking"].append(
                {
                    "key": "compose",
                    "title": "Compose 검증",
                    "status": "error",
                    "message": getattr(exc, "message", str(exc)),
                    "details": getattr(exc, "details", {}),
                }
            )

        try:
            preflight_payload = self._preflight_payload(draft, context)
            recommendation = placement_selector.recommend(preflight_payload, env=env)
            inspection["placement_recommendation"] = recommendation
            inspection["placement"] = services_preflight._check_placement(
                services_preflight._candidate_nodes(preflight_payload, env=env),
                recommendation=recommendation,
            )
        except Exception as exc:
            inspection["placement_error"] = self._exception_payload(exc)

        if validation is not None and rendered:
            try:
                preflight = services_preflight.check(
                    self._preflight_payload(draft, context),
                    rendered,
                    namespace,
                    validation=validation,
                    env=env,
                )
                inspection["ok"] = bool(preflight.get("ok"))
                inspection["summary"] = preflight.get("summary") or inspection["summary"]
                inspection["items"] = self._compact_preflight_items(preflight.get("items") or [])
                inspection["blocking"] = self._compact_preflight_items((preflight.get("blocking") or []) + inspection["blocking"])
                inspection["warnings"] = self._compact_preflight_items(preflight.get("warnings") or [])
                inspection["preflight"] = {
                    "ok": bool(preflight.get("ok")),
                    "summary": preflight.get("summary") or {},
                }
            except Exception as exc:
                inspection["preflight_error"] = self._exception_payload(exc)
                inspection["blocking"].append(
                    {
                        "key": "preflight",
                        "title": "Docker Infra 상태 검사",
                        "status": "error",
                        "message": getattr(exc, "message", str(exc)),
                        "details": getattr(exc, "details", {}),
                    }
                )

        if inspection["blocking"]:
            inspection["ok"] = False
        inspection["summary"] = {
            **(inspection.get("summary") or {}),
            "blocking": len(inspection.get("blocking") or []),
            "warnings": len(inspection.get("warnings") or []),
            "total": max(
                int((inspection.get("summary") or {}).get("total") or 0),
                len(inspection.get("items") or []) + len(inspection.get("blocking") or []),
            ),
        }
        return draft, rendered, inspection

    def _preflight_payload(self, draft, context):
        form = {}
        if isinstance(context.get("form"), dict):
            form.update(context.get("form") or {})
        if isinstance((draft or {}).get("form"), dict):
            form.update((draft or {}).get("form") or {})
        service = context.get("service") if isinstance(context.get("service"), dict) else {}
        domain = self._clean_text(form.get("domain"))
        if not domain and form.get("domain_mode") == "registered":
            zone = self._zone_by_id(context.get("zones") or [], form.get("zone_id"))
            prefix = self._clean_text(form.get("domain_prefix")).strip(".")
            zone_domain = self._clean_text((zone or {}).get("domain") or (zone or {}).get("name")).strip(".")
            if zone_domain:
                domain = "%s.%s" % (prefix, zone_domain) if prefix else zone_domain
        return {
            "domain": domain,
            "domains": form.get("domains") if isinstance(form.get("domains"), list) else [],
            "zone_id": self._clean_text(form.get("zone_id")),
            "service_id": service.get("id") or service.get("service_id"),
            "node_id": self._clean_text(form.get("node_id") or service.get("node_id") or service.get("target_node_id")),
        }

    def _zone_by_id(self, zones, zone_id):
        zone_id = self._clean_text(zone_id)
        if not zone_id:
            return None
        for zone in zones or []:
            if not isinstance(zone, dict):
                continue
            if self._clean_text(zone.get("id") or zone.get("zone_id")) == zone_id:
                return zone
        return None

    def _compact_preflight_items(self, items):
        rows = []
        for item in items[:20]:
            if not isinstance(item, dict):
                continue
            details = item.get("details")
            if isinstance(details, list):
                details = details[:8]
            rows.append(
                {
                    "key": item.get("key"),
                    "title": item.get("title"),
                    "status": item.get("status"),
                    "message": item.get("message"),
                    "details": details or [],
                }
            )
        return rows

    def _component_port_summary(self, draft):
        rows = []
        for component in (draft or {}).get("components") or []:
            for port in component.get("ports") or []:
                rows.append(
                    {
                        "component": component.get("key"),
                        "target": port.get("target"),
                        "published": port.get("published"),
                        "protocol": port.get("protocol") or "tcp",
                        "mode": port.get("mode") or "host",
                    }
                )
        return rows

    def _render_service_draft(self, draft, context):
        content = draft.get("base_content") or context.get("base_content") or ""
        if content and draft.get("components"):
            return services_wizard.render(
                {
                    "base_content": content,
                    "components": draft.get("components") or [],
                }
            )
        return content

    def _validate_service_draft(self, draft, context, env=None):
        try:
            self._resolve_component_images(draft)
            self._assert_component_images(draft)
            rendered = self._render_service_draft(draft, context)
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
            self._assert_ai_runtime_compose_contract(validation.get("normalized") or {})
            self._assert_service_images(validation)
            return rendered
        except Exception as exc:
            raise self._as_output_validation_error(exc, "service")

    def _compose_env_map(self, environment):
        if isinstance(environment, dict):
            return {str(key): "" if value is None else str(value) for key, value in environment.items()}
        result = {}
        if isinstance(environment, list):
            for item in environment:
                text = str(item or "")
                if "=" in text:
                    key, value = text.split("=", 1)
                    result[str(key)] = value
                elif text:
                    result[text] = ""
        return result

    def _healthcheck_text(self, healthcheck):
        if not isinstance(healthcheck, dict):
            return ""
        test = healthcheck.get("test")
        if isinstance(test, list):
            return " ".join(str(item or "") for item in test)
        return str(test or "")

    def _assert_ai_runtime_compose_contract(self, compose):
        errors = []
        if isinstance(compose.get("secrets"), dict) and compose.get("secrets"):
            errors.append(
                {
                    "path": "secrets",
                    "message": "AI drafts must not rely on Docker secrets because Docker Infra does not provision arbitrary external secrets during draft validation.",
                }
            )
        services = compose.get("services") if isinstance(compose.get("services"), dict) else {}
        for service_key, service in services.items():
            if not isinstance(service, dict):
                continue
            env_map = self._compose_env_map(service.get("environment"))
            for key, value in env_map.items():
                if FILE_ENV_PATTERN.search(key):
                    errors.append(
                        {
                            "path": "services.%s.environment.%s" % (service_key, key),
                            "message": "Use the exact env var the image reads; do not use *_FILE unless support is explicitly verified.",
                        }
                    )
                if SENSITIVE_ENV_PATTERN.search(key) and not str(value or "").strip():
                    errors.append(
                        {
                            "path": "services.%s.environment.%s" % (service_key, key),
                            "message": "Secret-like env values required by images must be non-empty generated stack-local values.",
                        }
                    )
            image = str(service.get("image") or "")
            healthcheck = self._healthcheck_text(service.get("healthcheck"))
            if image.startswith("jitsi/jicofo") and re.search(r"\b(pgrep|ps)\b", healthcheck):
                errors.append(
                    {
                        "path": "services.%s.healthcheck.test" % service_key,
                        "message": "jitsi/jicofo images may not include process-listing tools; use a verified probe or a conservative healthcheck.",
                    }
                )
            if image.startswith("jitsi/prosody") and re.search(r"\b(nc|netcat)\b", healthcheck):
                errors.append(
                    {
                        "path": "services.%s.healthcheck.test" % service_key,
                        "message": "jitsi/prosody images may not include nc; use a verified probe or a conservative healthcheck.",
                    }
                )
        if errors:
            raise AIAssistantError(
                422,
                "AI Compose 초안에 런타임에서 실패할 수 있는 secret/healthcheck 구성이 있습니다.",
                "AI_RUNTIME_COMPOSE_CONTRACT_FAILED",
                {"errors": errors[:20]},
            )

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
            "ai_permission_scope": context.get("ai_permission_scope") or {},
            "mcp_guidance": context.get("mcp_guidance") or {},
            "terminal_actions": context.get("terminal_actions") or {},
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
            "CODEX_PROVIDER_NOT_SUPPORTED",
            "CODEX_PROVIDER_TOKEN_REQUIRED",
            "CODEX_MODEL_REQUIRED",
            "CODEX_EXECUTABLE_NOT_FOUND",
            "CODEX_EXEC_FAILED",
            "CODEX_EXEC_TIMEOUT",
            "CODEX_EMPTY_RESPONSE",
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
            "Do not put plaintext production secrets in the output. For stack-local bootstrap credentials, use non-empty generated-looking values, mark matching component env_vars as secret=true, and list their keys in generated_secret_keys.",
            "Do not use *_FILE environment variables or top-level Docker secrets unless the context explicitly proves that Docker Infra will provision those secrets and the target image supports that exact *_FILE variable.",
            "Use ASCII for generated ids, keys, and namespaces.",
            "If a requested image, feature, or option is risky or unsupported, include a warning.",
            "Do not invent exact current image versions. If the user asks for the latest version and no exact current version is provided in context, use the image's official latest tag only for that explicitly requested image and add a Korean warning that floating tags should be pinned after verification.",
            "Every generated Compose service must include an image reference whose image name and tag or digest can pass the application's image validation.",
            "Include a short thinking_summary field that summarizes the decision path without exposing raw chain-of-thought.",
            "Use the compose_validation object in the user context as a hard contract. Fix violations before returning JSON.",
            "Use the output_format object in the user context as the exact output contract.",
            "Use only the docker_infra MCP tools listed in mcp_guidance.enabled_tools or ai_permission_scope.mcp_enabled_tools before making claims about registered servers, Docker images, ports, and runtime state.",
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
                "When multiple domains or subdomains are useful, return form.domains and keep the first domain mirrored into legacy form.domain_prefix/domain_target_key/domain_target_port.",
                "Autofill service names, domain prefixes, target ports, stack-local generated credentials, volumes, healthchecks, and placement assumptions from Docker Infra context when the user did not specify them.",
                "Healthchecks must use commands that are known to exist in the selected image; if you cannot verify a command, use a conservative HTTP/TCP probe or omit the fragile command instead of guessing pgrep, ps, nc, or bash-specific behavior.",
                "Respect the existing Compose validation constraints when choosing images, ports, env, volumes, and domain target.",
            ]
        )
        return "\n".join(common)

    def _complete_json(self, system, context, env=None, selection=None, provider=None):
        provider = provider or self._select_provider(env=env, selection=selection)
        try:
            result = codex_runtime.complete_json(provider, system, context, env=env)
        except Exception as exc:
            raise AIAssistantError(
                getattr(exc, "status_code", 502),
                getattr(exc, "message", str(exc)),
                getattr(exc, "error_code", "CODEX_RUNTIME_FAILED"),
                getattr(exc, "details", {}),
            )
        text = result.get("text")
        data = self._extract_json(text)
        metadata = result.get("metadata") or {}
        return data, self._provider_public(provider, metadata)

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
            codex = config.get("codex") or {}
            if codex.get("enabled") and codex.get("model"):
                return {
                    "type": "codex",
                    "label": "Codex",
                    "model": codex.get("model"),
                    "reasoning_effort": codex.get("reasoning_effort") or "xhigh",
                    "cli_mode": "system",
                    "codex_home": codex.get("codex_home") or "",
                }

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
            if model_ref == "codex":
                return {"provider": "codex", "model": "__default__"}
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
        if provider not in {"codex", "openai", "gemini", "ollama"}:
            raise AIAssistantError(400, "지원하지 않는 AI 모델 공급자입니다.", "AI_PROVIDER_NOT_SUPPORTED")
        if provider == "codex":
            codex = config.get("codex") or {}
            model = codex.get("model") if model in {"", "__default__"} else model
            model = model or "gpt-5.5"
            return {
                "type": "codex",
                "label": "Codex",
                "model": model,
                "reasoning_effort": codex.get("reasoning_effort") or "xhigh",
                "cli_mode": "system",
                "codex_home": codex.get("codex_home") or "",
            }
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

    def _stream_json(self, target, context, selection, env=None):
        try:
            provider = self._select_provider(env=env, selection=selection)
            for event in self._stream_json_with_provider(target, context, provider, env=env):
                yield event
        except Exception as exc:
            yield self._error_event(exc)

    def _stream_json_with_provider(self, target, context, provider, system=None, env=None):
        public_provider = self._provider_public(provider)
        yield {"type": "provider", "provider": public_provider}
        yield {"type": "status", "message": "요구사항과 현재 설정을 Codex 실행 컨텍스트로 정리합니다."}
        system = system or self._system_prompt(target)
        yield {"type": "status", "message": "Codex를 통해 선택한 모델로 AI 응답 JSON을 생성합니다."}
        result = None
        def run_codex():
            yield {"type": "codex_result", "result": codex_runtime.complete_json(provider, system, context, env=env)}

        for event in self._iter_with_heartbeat(run_codex()):
            if event.get("type") == "heartbeat":
                yield event
                continue
            if event.get("type") == "codex_result":
                result = event.get("result")
        metadata = (result or {}).get("metadata") or {}
        completed_provider = self._provider_public(provider, metadata)
        if metadata:
            yield self._codex_execution_status_event(metadata)
        text = (result or {}).get("text") or ""
        if text:
            yield {"type": "delta", "text": text}
        data = self._extract_json(text)
        thinking_summary = self._clean_text(data.get("thinking_summary"))
        if thinking_summary:
            yield {"type": "thinking", "text": thinking_summary}
        yield {"type": "status", "message": "AI 응답을 Docker Infra 설정으로 검증합니다."}
        yield {"type": "complete", "data": data, "provider": completed_provider}

    def _stream_codex_json(self, system, context, provider, env=None, emit_delta=False):
        result = None

        def run_codex():
            yield {"type": "codex_result", "result": codex_runtime.complete_json(provider, system, context, env=env)}

        try:
            for event in self._iter_with_heartbeat(run_codex()):
                if event.get("type") == "heartbeat":
                    yield event
                    continue
                if event.get("type") == "codex_result":
                    result = event.get("result")
        except Exception as exc:
            raise AIAssistantError(
                getattr(exc, "status_code", 502),
                getattr(exc, "message", str(exc)),
                getattr(exc, "error_code", "CODEX_RUNTIME_FAILED"),
                getattr(exc, "details", {}),
            )

        metadata = (result or {}).get("metadata") or {}
        if metadata:
            yield self._codex_execution_status_event(metadata)
        text = (result or {}).get("text") or ""
        if emit_delta and text:
            yield {"type": "delta", "text": text}
        data = self._extract_json(text)
        thinking_summary = self._clean_text(data.get("thinking_summary"))
        if thinking_summary:
            yield {"type": "thinking", "text": thinking_summary}
        return data

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
                "single or multiple domain zones and prefixes",
                "nginx upstream target",
                "SSL mode",
                "published and target ports",
                "named volumes",
                "runtime-generated stack-local credentials",
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
                "Choose one or more public components and ports when the user asks for browser or domain access.",
                "Prefer named volumes over host paths for beginner-created persistent data.",
                "For stack-local credentials required by images, return non-empty values the image actually reads, mark them as secret in components, and list generated_secret_keys. Do not switch to *_FILE or Docker secrets unless support is explicitly verified.",
                "Autofill missing but necessary Docker Infra values instead of leaving blanks.",
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
            "domain",
            "domain_target_key",
            "domain_target_port",
            "domains",
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

        domains = self._normalize_domains(data, merged_form, fallback)
        if domains:
            merged_form["domains"] = domains
            primary = domains[0]
            merged_form["domain"] = merged_form.get("domain") or primary.get("domain")
            merged_form["zone_id"] = merged_form.get("zone_id") or primary.get("zone_id")
            merged_form["domain_prefix"] = merged_form.get("domain_prefix") or primary.get("domain_prefix") or self._prefix_from_domain(primary.get("domain"), fallback.get("zones") or [])
            merged_form["domain_target_key"] = merged_form.get("domain_target_key") or primary.get("domain_target_key")
            merged_form["domain_target_port"] = merged_form.get("domain_target_port") or self._clean_text(primary.get("domain_target_port") or primary.get("target_port"))

        return {
            "base_content": base_content,
            "form": merged_form,
            "components": normalized_components,
            "generated_secret_keys": self._string_list(data.get("generated_secret_keys")),
            "notes": self._clean_text(data.get("notes") or data.get("readme")),
        }

    def _normalize_domains(self, data, form, fallback):
        raw = []
        for source in (data.get("domains"), form.get("domains"), (fallback.get("form") or {}).get("domains"), fallback.get("domains")):
            if isinstance(source, list):
                raw = source
                break
        if not raw and self._clean_text(form.get("domain")):
            raw = [
                {
                    "domain": form.get("domain"),
                    "zone_id": form.get("zone_id"),
                    "domain_prefix": form.get("domain_prefix"),
                    "domain_target_key": form.get("domain_target_key"),
                    "domain_target_port": form.get("domain_target_port"),
                }
            ]
        rows = []
        seen = set()
        zones = fallback.get("zones") or []
        for item in raw:
            if not isinstance(item, dict):
                continue
            domain = self._clean_text(item.get("domain")).lower()
            zone_id = self._clean_text(item.get("zone_id") or form.get("zone_id"))
            prefix = self._domain_prefix(item.get("domain_prefix") or item.get("prefix"))
            if not domain and zone_id:
                zone = self._zone_by_id(zones, zone_id)
                zone_domain = self._clean_text((zone or {}).get("domain") or (zone or {}).get("name")).strip(".")
                if zone_domain:
                    domain = "%s.%s" % (prefix, zone_domain) if prefix else zone_domain
            if not domain or domain in seen:
                continue
            seen.add(domain)
            target_key = self._clean_text(item.get("domain_target_key") or item.get("target_key") or form.get("domain_target_key"))
            target_port = self._clean_text(item.get("domain_target_port") or item.get("target_port") or item.get("port") or form.get("domain_target_port"))
            rows.append(
                {
                    "domain": domain,
                    "zone_id": zone_id,
                    "domain_prefix": prefix or self._prefix_from_domain(domain, zones),
                    "domain_target_key": target_key,
                    "domain_target_port": target_port,
                    "compose_service": self._clean_text(item.get("compose_service") or item.get("service_key") or target_key.split(":", 1)[0]),
                    "target_port": self._safe_int(target_port, 0),
                    "published_port": self._safe_int(item.get("published_port") or target_port, 0),
                    "ssl_mode": self._clean_text(item.get("ssl_mode")),
                    "dns_proxied": bool(item.get("dns_proxied")),
                }
            )
        return rows

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

    def _provider_public(self, provider, metadata=None):
        metadata = metadata or {}
        provider_type = provider.get("type")
        cli_mode = metadata.get("cli_mode") or provider.get("cli_mode") or ("system" if provider_type == "codex" else "custom")
        uses_custom_cli = bool(metadata.get("uses_custom_cli")) if "uses_custom_cli" in metadata else cli_mode == "custom"
        return {
            "type": provider_type,
            "label": provider.get("label"),
            "model": metadata.get("model") or provider.get("model"),
            "reasoning_effort": metadata.get("reasoning_effort") or provider.get("reasoning_effort"),
            "cli_mode": cli_mode,
            "cli_label": "Codex 로그인" if provider_type == "codex" else "",
            "uses_custom_cli": uses_custom_cli,
            "engine": metadata.get("engine") or "codex",
            "executable": metadata.get("executable") or "",
        }

    def _codex_execution_status_event(self, metadata):
        metadata = metadata or {}
        cli_label = "Codex 실행"
        bits = [cli_label, self._clean_text(metadata.get("model"))]
        executable = self._clean_text(metadata.get("executable"))
        if executable:
            bits.append(executable)
        return {
            "type": "status",
            "label": "Codex 실행 확인",
            "message": " · ".join([bit for bit in bits if bit]),
        }

    def _default_model_ref(self, config):
        return "codex"

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

    def _prefix_from_domain(self, domain, zones):
        clean = self._clean_text(domain).lower().strip(".")
        for zone in sorted([item for item in zones or [] if isinstance(item, dict)], key=lambda item: len(self._clean_text(item.get("domain") or item.get("name"))), reverse=True):
            suffix = self._clean_text(zone.get("domain") or zone.get("name")).lower().strip(".")
            if not suffix:
                continue
            if clean == suffix:
                return ""
            if clean.endswith("." + suffix):
                return clean[: -(len(suffix) + 1)]
        return clean.split(".", 1)[0] if clean else ""

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

    def _trim_diagnostic(self, value, limit=12000):
        text = self._clean_text(value)
        if len(text) <= limit:
            return text
        return text[-limit:]

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
