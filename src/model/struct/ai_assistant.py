import datetime
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
ai_history = wiz.model("struct/ai_history")
ai_agent_actions = wiz.model("struct/ai_agent_actions")
codex_runtime = wiz.model("struct/codex_runtime")
connect = wiz.model("db/postgres").connect
nodes_model = wiz.model("struct/nodes")
services_model = wiz.model("struct/services")
services_wizard = wiz.model("struct/services_wizard")
domains_model = wiz.model("struct/domains")
ddns_model = wiz.model("struct/domains_ddns")
compose_rules = wiz.model("struct/compose_rules")
compose_validator = wiz.model("struct/compose_validator")
services_preflight = wiz.model("struct/services_preflight")
placement_selector = wiz.model("struct/services_placement")
operations = wiz.model("struct/operations")


MAX_AI_REPAIR_ATTEMPTS = 20
AI_STREAM_HEARTBEAT_SECONDS = 15
AI_STREAM_PROVIDER_TIMEOUT_SECONDS = 900
AI_VERIFY_MAX_ATTEMPTS = 3
AI_VERIFY_RUNTIME_WAIT_ATTEMPTS = 12
AI_VERIFY_RUNTIME_WAIT_SECONDS = 10
AI_VERIFY_UNCHANGED_BLOCKED_ATTEMPTS = 3
AI_VERIFY_DEPLOY_WAIT_SECONDS = 300
SENSITIVE_ENV_PATTERN = re.compile(r"(PASSWORD|SECRET|TOKEN|KEY|AUTH|CREDENTIAL)", re.IGNORECASE)
FILE_ENV_PATTERN = re.compile(r"_FILE$", re.IGNORECASE)


def _utc_now():
    return datetime.datetime.now(datetime.timezone.utc)


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
    AIAssistantError = AIAssistantError

    def contracts(self):
        return {
            "service": self.service_contract(),
            "template": self.template_contract(),
            "compose_validation": self.compose_validation_contract(),
        }

    def _mcp_tools(self, scope, allow_container_actions=True, allow_ssh_command=True):
        return codex_runtime.mcp_tools_for_scope(
            scope,
            allow_container_actions=allow_container_actions,
            allow_ssh_command=allow_ssh_command,
        )

    def model_options(self, env=None):
        return ai_settings.model_options(env=env)

    def chat_status(self, env=None):
        options = ai_settings.model_options(env=env)
        selected = self._normalize_agent_key(options.get("default_agent") or options.get("selected"))
        enabled = bool(options.get("has_enabled_models") and selected)
        capabilities = self.openapi_capabilities(compact=True)
        return {
            "enabled": enabled,
            "default_agent": selected,
            "agent_label": "AI Agent" if selected else "",
            "options": options.get("options") or [],
            "message": "" if enabled else (options.get("message") or "시스템 설정에서 AI Agent를 먼저 사용 설정하세요."),
            "capabilities": capabilities,
        }

    def openapi_capabilities(self, compact=False, env=None, include_action_catalog=True):
        document = self._openapi_document()
        extension = document.get("x-ai-agent") if isinstance(document, dict) else {}
        operations = extension.get("operations") if isinstance(extension, dict) else []
        normalized = []
        for item in operations or []:
            if not isinstance(item, dict):
                continue
            operation_id = self._clean_text(item.get("operationId") or item.get("operation_id"))
            path = self._clean_text(item.get("path"))
            method = self._clean_text(item.get("method") or "POST").upper()
            if not operation_id or not path:
                continue
            normalized.append(
                {
                    "operation_id": operation_id,
                    "menu": self._clean_text(item.get("menu")),
                    "method": method,
                    "path": path,
                    "safety": self._clean_text(item.get("safety") or "read"),
                    "summary": self._clean_text(item.get("summary")),
                    "required": self._string_list(item.get("required")),
                }
            )
        payload = {
            "swagger_url": self._clean_text(extension.get("swaggerUrl") if isinstance(extension, dict) else "") or "/swagger",
            "openapi_url": self._clean_text(extension.get("openapiUrl") if isinstance(extension, dict) else "") or "/openapi.json",
            "operation_count": len(normalized),
            "menus": sorted({item.get("menu") for item in normalized if item.get("menu")}),
        }
        if compact:
            payload["operations"] = normalized[:20]
        else:
            payload["operations"] = normalized
            if include_action_catalog:
                payload["action_catalog"] = ai_agent_actions.catalog(normalized, compact=False)
        return payload

    def chat(self, payload=None, env=None):
        payload = payload if isinstance(payload, dict) else {}
        message = self._clean_text(payload.get("message"))
        if not message:
            raise AIAssistantError(400, "질문이나 요청 내용을 입력하세요.", "AI_AGENT_MESSAGE_REQUIRED")

        started_at = _utc_now()
        provider = None
        try:
            builtin = self._builtin_chat_response(payload, message)
            if builtin:
                provider = self._builtin_provider()
                builtin["duration_ms"] = self._duration_ms(started_at)
                self._attach_chat_session(builtin, payload, provider, env=env)
                self._record_chat_history(payload, provider, builtin, status="succeeded", started_at=started_at, env=env)
                return builtin
            selection = payload.get("selection") if isinstance(payload.get("selection"), dict) else {}
            provider = self._select_provider(env=env, selection=selection)
            result = codex_runtime.complete_json(
                provider,
                self._ui_chat_system_prompt(),
                self._chat_context_for_provider(payload, message, provider, env=env),
                env=env,
            )
            response = self._chat_response_payload(result, provider)
            response["duration_ms"] = self._duration_ms(started_at)
            self._record_chat_history(payload, provider, response, status="succeeded", started_at=started_at, env=env)
            return response
        except Exception as exc:
            self._record_chat_history(payload, provider, None, status="failed", error=exc, started_at=started_at, env=env)
            raise

    def plan_chat(self, payload=None, env=None):
        payload = payload if isinstance(payload, dict) else {}
        message = self._clean_text(payload.get("message"))
        if not message:
            raise AIAssistantError(400, "질문이나 요청 내용을 입력하세요.", "AI_AGENT_MESSAGE_REQUIRED")

        builtin = self._builtin_chat_todos(message)
        if builtin:
            return {
                "summary": "요청을 실행 가능한 TODO로 정리했습니다.",
                "todos": builtin,
                "provider": self._provider_public(self._builtin_provider()),
            }

        return {
            "summary": "요청을 하나의 Agent 실행 TODO로 정리했습니다.",
            "todos": self._normalize_chat_todos([], message),
            "provider": self._provider_public(self._builtin_provider()),
        }

    def stream_chat(self, payload=None, env=None):
        payload = payload if isinstance(payload, dict) else {}
        message = self._clean_text(payload.get("message"))
        started_at = _utc_now() if message else None
        provider = None
        try:
            if not message:
                yield {"type": "error", "message": "질문이나 요청 내용을 입력하세요.", "error_code": "AI_AGENT_MESSAGE_REQUIRED"}
                return

            builtin = self._builtin_chat_response(payload, message)
            if builtin:
                provider = self._builtin_provider()
                public_provider = self._provider_public(provider)
                builtin["duration_ms"] = self._duration_ms(started_at)
                self._attach_chat_session(builtin, payload, provider, env=env)
                self._record_chat_history(payload, provider, builtin, status="succeeded", started_at=started_at, env=env)
                yield {"type": "provider", "provider": public_provider}
                yield {"type": "status", "message": "요청한 화면 조작을 준비합니다."}
                for chunk in self._text_chunks(builtin.get("answer") or ""):
                    yield {"type": "delta", "text": chunk}
                    time.sleep(0.01)
                yield {"type": "complete", "data": builtin, "provider": public_provider}
                yield {"type": "done", "data": builtin}
                return

            selection = payload.get("selection") if isinstance(payload.get("selection"), dict) else {}
            provider = self._select_provider(env=env, selection=selection)
            public_provider = self._provider_public(provider)
            yield {"type": "provider", "provider": public_provider}
            yield {"type": "status", "message": "현재 화면 컨텍스트를 Agent 요청으로 정리합니다."}
            yield {"type": "status", "message": "Docker Infra MCP 액션 카탈로그에서 요청 의도를 매칭합니다."}
            yield {
                "type": "thinking",
                "message": "요청 문장, 현재 화면, 사용 가능한 MCP/API 작업을 함께 대조합니다.",
                "phase": "intent_mapping",
            }
            matches = ai_agent_actions.intent_matches(
                message,
                self.openapi_capabilities(compact=False, include_action_catalog=False).get("operations") or [],
            )
            if matches:
                top = matches[0]
                yield {
                    "type": "status",
                    "message": "후보 MCP 액션: %s (%s)" % (top.get("tool"), top.get("operation_id")),
                }
                yield {
                    "type": "thinking",
                    "message": "가장 가까운 실행 후보를 %s / %s로 잡고 필요한 입력값을 확인합니다." % (
                        top.get("tool"),
                        top.get("operation_id"),
                    ),
                    "phase": "action_candidate",
                }
            else:
                yield {
                    "type": "thinking",
                    "message": "직접 매칭되는 MCP 액션이 없어 화면 컨텍스트와 대화 이력을 기준으로 응답 전략을 정리합니다.",
                    "phase": "action_candidate",
                }

            result = None

            def run_agent():
                yield {
                    "type": "agent_result",
                    "result": codex_runtime.complete_json(
                        provider,
                        self._ui_chat_system_prompt(),
                        self._chat_context_for_provider(payload, message, provider, env=env),
                        env=env,
                    ),
                }

            yield {
                "type": "thinking",
                "message": "선택한 Agent CLI가 Docker Infra MCP 컨텍스트를 읽고 최종 응답 JSON을 생성합니다.",
                "phase": "agent_execution",
            }
            yield {"type": "status", "message": "AI Agent 응답을 기다리는 중입니다."}
            for event in self._iter_with_heartbeat(run_agent()):
                if event.get("type") == "heartbeat":
                    yield self._agent_chat_heartbeat_event(event)
                    continue
                if event.get("type") == "agent_result":
                    result = event.get("result")

            yield {
                "type": "thinking",
                "message": "Agent 응답을 수신해 사용자에게 보여줄 최종 답변과 실행 액션으로 정리합니다.",
                "phase": "response_normalization",
            }
            response = self._chat_response_payload(result or {}, provider)
            response["duration_ms"] = self._duration_ms(started_at)
            self._record_chat_history(payload, provider, response, status="succeeded", started_at=started_at, env=env)
            yield {"type": "status", "message": "응답을 표시하는 중입니다."}
            for chunk in self._text_chunks(response.get("answer") or ""):
                yield {"type": "delta", "text": chunk}
                time.sleep(0.01)
            yield {"type": "complete", "data": response, "provider": response.get("provider") or public_provider}
            yield {"type": "done", "data": response}
        except Exception as exc:
            if message:
                self._record_chat_history(payload, provider, None, status="failed", error=exc, started_at=started_at, env=env)
            yield self._error_event(exc)

    def _agent_chat_heartbeat_event(self, event):
        elapsed = int((event or {}).get("elapsed_seconds") or 0)
        if elapsed >= 60:
            label = "Agent가 MCP 조회와 응답 생성을 계속 진행 중입니다. (%s분 %s초 경과)" % (elapsed // 60, elapsed % 60)
        else:
            label = "Agent가 MCP 조회와 응답 생성을 계속 진행 중입니다. (%s초 경과)" % elapsed
        return {
            "type": "thinking",
            "label": "처리 중",
            "message": label,
            "phase": "agent_execution_wait",
            "elapsed_seconds": elapsed,
            "heartbeat_count": (event or {}).get("heartbeat_count") or 0,
            "progress_message": "Agent가 MCP 조회와 응답 생성을 계속 진행 중입니다.",
        }

    def _chat_context_for_provider(self, payload, message, provider, env=None):
        context = self._chat_context(payload, message)
        context["session"] = self._chat_session(payload, provider, env=env)
        return context

    def _chat_session(self, payload, provider, env=None):
        payload = payload if isinstance(payload, dict) else {}
        provider = provider if isinstance(provider, dict) else {}
        session_id = self._normalize_session_id(
            payload.get("session_id") or payload.get("client_session_id") or payload.get("conversation_id")
        )
        agent_type = self._normalize_agent_key(provider.get("type"))
        provider_session_id = ""
        if session_id and agent_type in self._agent_keys():
            try:
                provider_session_id = ai_history.provider_session_id(agent_type, session_id, env=env)
            except Exception:
                provider_session_id = ""
        return {
            "session_id": session_id,
            "provider_session_id": self._normalize_session_id(provider_session_id),
            "agent_type": agent_type,
            "resume": bool(provider_session_id),
            "title": self._session_title(payload.get("session_title") or payload.get("message")),
        }

    def _chat_context(self, payload, message):
        screen = self._chat_json_value(payload.get("screen"), depth=0)
        screen_context_summary = ""
        if isinstance(screen, dict):
            screen_context_summary = self._clean_text(screen.get("context_summary"))
        openapi_guidance = self.openapi_capabilities(compact=False, include_action_catalog=False)
        openapi_guidance["mcp_action_catalog"] = ai_agent_actions.prompt_catalog(
            openapi_guidance.get("operations") or [],
            message,
            screen,
        )
        return {
            "message": message,
            "session_id": self._normalize_session_id((payload or {}).get("session_id") or (payload or {}).get("client_session_id")),
            "history": self._compact_chat_history(payload.get("history")),
            "screen": screen,
            "screen_context_summary": screen_context_summary,
            "recent_events": self._chat_json_value(payload.get("events"), depth=0),
            "output_format": {
                "answer": "Korean answer shown to the user.",
                "summary": "Short Korean execution summary.",
                "needs_confirmation": "Boolean. true for destructive or irreversible requests before action.",
                "client_actions": [
                    {
                        "type": "navigate|click|fill|focus|close_modal|refresh|wait|app_event|api_request|noop",
                        "ref": "Visible element ref from screen.interactive_elements when relevant.",
                        "target": "Route path for navigate, semantic label for click/fill/focus, page command key for app_event, or operation_id for api_request.",
                        "operation_id": "OpenAPI x-ai-agent operation_id for api_request.",
                        "params": "Path/query params for api_request.",
                        "body": "Form body for api_request.",
                        "save_as": "Optional ASCII alias for api_request response data that later actions can reference.",
                        "value": "Input value for fill.",
                        "payload": "Structured payload for app_event actions.",
                        "reason": "Korean reason for the action.",
                    }
                ],
                "follow_up": "Optional Korean follow-up question.",
                "suggested_actions": [
                    {
                        "label": "Short Korean button label for a useful next action.",
                        "prompt": "Self-contained Korean chat message to send when the user runs this suggestion.",
                        "reason": "Optional Korean reason shown as helper text.",
                    }
                ],
                "confidence": "low|medium|high",
            },
            "ai_permission_scope": {
                "mode": "agent_full_control_except_critical_destruction",
                "mcp_enabled_tools": self._mcp_tools(
                    "runtime_inspection",
                    allow_container_actions=True,
                    allow_ssh_command=True,
                ),
            },
            "mcp_guidance": {
                "enabled_tools": self._mcp_tools(
                    "runtime_inspection",
                    allow_container_actions=True,
                    allow_ssh_command=True,
                ),
                "purpose": "Answer user questions and perform Docker Infra actions that match the visible UI context.",
            },
            "openapi_guidance": openapi_guidance,
        }

    def _todo_plan_context(self, payload, message, provider, env=None):
        return {
            "message": message,
            "session": self._chat_session(payload, provider, env=env),
            "history": self._compact_chat_history(payload.get("history")),
            "screen": self._chat_json_value(payload.get("screen"), depth=0),
            "recent_events": self._chat_json_value(payload.get("events"), depth=0),
            "output_format": {
                "summary": "Short Korean planning summary.",
                "todos": [
                    {
                        "title": "Conceptual Korean TODO title. Do not split by navigation, click, API, or app_event steps.",
                        "prompt": "Self-contained Korean prompt for executing this TODO in one later AI Agent request.",
                        "reason": "Optional Korean reason.",
                    }
                ],
            },
        }

    def _chat_response_payload(self, result, provider):
        metadata = (result or {}).get("metadata") or {}
        public_provider = self._provider_public(provider, metadata)
        text = self._clean_text((result or {}).get("text"))
        try:
            data = self._extract_json(text)
        except AIAssistantError:
            if not text:
                raise
            data = {"answer": text, "summary": "", "needs_confirmation": False, "client_actions": []}
        answer = self._clean_text(data.get("answer") or data.get("message") or data.get("summary") or text)
        if not answer:
            raise AIAssistantError(502, "AI Agent 응답 내용이 비어 있습니다.", "AI_AGENT_EMPTY_RESPONSE")
        payload = {
            "answer": answer,
            "summary": self._clean_text(data.get("summary")),
            "needs_confirmation": bool(data.get("needs_confirmation")),
            "client_actions": self._normalize_client_actions(data.get("client_actions")),
            "follow_up": self._clean_text(data.get("follow_up")),
            "suggested_actions": self._normalize_suggested_actions(
                data.get("suggested_actions") or data.get("next_actions") or data.get("recommended_actions"),
                fallback=data.get("follow_up"),
            ),
            "confidence": self._clean_text(data.get("confidence") or "medium"),
            "provider": public_provider,
        }
        session = metadata.get("session") if isinstance(metadata.get("session"), dict) else {}
        session_id = self._normalize_session_id(session.get("session_id") or metadata.get("session_id"))
        provider_session_id = self._normalize_session_id(
            session.get("provider_session_id") or metadata.get("provider_session_id")
        )
        if session_id:
            payload["session_id"] = session_id
        if provider_session_id:
            payload["provider_session_id"] = provider_session_id
        return payload

    def _builtin_provider(self):
        return {"type": "builtin", "label": "Docker Infra Agent", "model": "ui-control"}

    def _builtin_chat_response(self, payload, message):
        delete_target = self._service_delete_target(message)
        if delete_target:
            return self._service_delete_response(delete_target)
        if self._looks_like_server_status_macro_run_request(message):
            return self._server_status_macro_run_response()
        if not self._looks_like_server_status_macro_request(message):
            return None

        macro = self._server_status_macro_payload()
        return {
            "answer": (
                "- 전역 매크로 관리 화면으로 이동해 `서버 상태 한눈에 보기` 매크로를 추가합니다.\n"
                "- 매크로는 CPU, 메모리, 디스크, Docker 데몬, 컨테이너, Swarm 서비스/노드 상태를 한 번에 출력합니다.\n"
                "- 같은 이름의 매크로가 이미 있으면 최신 스크립트로 갱신합니다."
            ),
            "summary": "서버 상태 요약 전역 매크로 생성 액션을 준비했습니다.",
            "needs_confirmation": False,
            "client_actions": [
                {
                    "type": "navigate",
                    "target": "/macros",
                    "reason": "전역 매크로 관리 화면으로 이동",
                },
                {
                    "type": "app_event",
                    "target": "macro.create_global",
                    "payload": macro,
                    "reason": "서버 상태를 한눈에 확인하는 전역 매크로 생성",
                },
            ],
            "follow_up": "",
            "suggested_actions": [
                {
                    "label": "서버에서 실행",
                    "prompt": "방금 만든 서버 상태 한눈에 보기 매크로를 선택한 서버에서 실행해줘",
                    "reason": "매크로 생성 후 실제 출력 확인",
                },
                {
                    "label": "서버 화면 열기",
                    "prompt": "서버 관리 화면으로 이동해서 매크로 실행 위치를 보여줘",
                    "reason": "서버 상세의 매크로 탭으로 이어서 이동",
                },
            ],
            "confidence": "high",
            "provider": self._provider_public(self._builtin_provider()),
        }

    def _server_status_macro_run_response(self):
        macro = self._server_status_macro_payload()
        return {
            "answer": (
                "- 마스터 노드에서 `서버 상태 한눈에 보기` 매크로 실행을 시작합니다.\n"
                "- 전역 매크로가 없으면 생성하고, 있으면 최신 스크립트로 갱신한 뒤 실행합니다.\n"
                "- 실행 로그는 서버 관리 화면의 매크로 탭에서 확인할 수 있습니다."
            ),
            "summary": "마스터 노드에서 서버 상태 요약 매크로를 실행하는 순차 액션을 준비했습니다.",
            "needs_confirmation": False,
            "client_actions": [
                {
                    "type": "navigate",
                    "target": "/servers",
                    "reason": "서버 관리 화면으로 이동",
                },
                {
                    "type": "app_event",
                    "target": "server.run_macro",
                    "payload": {
                        "node_selector": "local_master",
                        "macro_name": macro["name"],
                        "macro": macro,
                        "args": "",
                    },
                    "reason": "마스터 노드에서 서버 상태 한눈에 보기 매크로 실행",
                },
            ],
            "follow_up": "",
            "suggested_actions": [
                {
                    "label": "작업 로그 확인",
                    "prompt": "방금 실행한 서버 상태 한눈에 보기 매크로 작업 로그를 요약해줘",
                    "reason": "실행 결과 해석",
                },
                {
                    "label": "컨테이너 점검",
                    "prompt": "마스터 노드의 컨테이너 상태를 새로고침해서 이상 항목을 알려줘",
                    "reason": "상태 확인 후 후속 점검",
                },
            ],
            "confidence": "high",
            "provider": self._provider_public(self._builtin_provider()),
        }

    def _builtin_chat_todos(self, message):
        delete_target = self._service_delete_target(message)
        if delete_target:
            return [
                {
                    "title": "%s 서비스 삭제" % delete_target,
                    "prompt": self._clean_text(message),
                    "reason": "서비스 이름을 service_id로 해석한 뒤 삭제 API를 실행합니다.",
                }
            ]
        if self._looks_like_server_status_macro_run_request(message):
            return [
                {
                    "title": "마스터 노드에서 서버 상태 한눈에 보기 매크로 실행",
                    "prompt": self._clean_text(message),
                    "reason": "서버 화면 이동, 매크로 보장, 실행을 하나의 작업으로 처리합니다.",
                }
            ]
        if self._looks_like_server_status_macro_request(message):
            return [
                {
                    "title": "서버 상태 한눈에 보기 전역 매크로 생성",
                    "prompt": self._clean_text(message),
                    "reason": "전역 매크로 생성과 갱신을 하나의 작업으로 처리합니다.",
                }
            ]
        return []

    def _service_delete_response(self, service_name):
        return {
            "answer": (
                "- `%s` 서비스를 삭제하는 Docker Infra MCP 액션을 준비했습니다.\n"
                "- 브라우저가 서비스 이름을 정확한 `service_id`로 해석한 뒤 삭제 API를 실행합니다.\n"
                "- 삭제 작업 로그는 작업 로그 화면에서 확인할 수 있습니다."
            ) % service_name,
            "summary": "%s 서비스 삭제 액션을 준비했습니다." % service_name,
            "needs_confirmation": False,
            "client_actions": [
                {
                    "type": "api_request",
                    "operation_id": "services.delete",
                    "body": {"service_name": service_name},
                    "reason": "%s 서비스 삭제" % service_name,
                }
            ],
            "follow_up": "",
            "suggested_actions": [
                {
                    "label": "작업 로그 확인",
                    "prompt": "%s 서비스 삭제 작업 로그를 확인해줘" % service_name,
                    "reason": "삭제가 정상 완료됐는지 확인",
                }
            ],
            "confidence": "high",
            "provider": self._provider_public(self._builtin_provider()),
        }

    def _service_delete_target(self, message):
        text = self._clean_text(message)
        if not re.search(r"(삭제|제거|지워|delete|remove)", text, re.IGNORECASE):
            return ""
        if not re.search(r"(서비스|service)", text, re.IGNORECASE):
            return ""
        quoted = re.search(r"[\"'`“”‘’]([^\"'`“”‘’]{2,160})[\"'`“”‘’]", text)
        if quoted:
            return self._clean_text(quoted.group(1))[:160]
        patterns = [
            r"(.{2,160}?)\s+서비스(?:를|을)?\s*(?:삭제|제거|지워|delete|remove)",
            r"(?:서비스\s+)?(.{2,160}?)\s*(?:삭제|제거|지워|delete|remove)(?:\s*해줘|\s*해주세요|\s*해|$)",
        ]
        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if not match:
                continue
            target = self._clean_text(match.group(1)).strip(" .,")
            target = re.sub(r"^(방금|아까|저|그)\s+", "", target).strip()
            if target and target not in {"서비스", "service"}:
                return target[:160]
        return ""

    def _looks_like_server_status_macro_run_request(self, message):
        text = self._clean_text(message).lower()
        compact = re.sub(r"\s+", "", text)
        if "매크로" not in text:
            return False
        if not re.search(r"(실행|돌려|run|execute)", text, re.IGNORECASE):
            return False
        status_macro = (
            ("서버" in compact and "상태" in compact and "한눈" in compact)
            or ("server" in text and "status" in text)
        )
        if not status_macro:
            return False
        return bool(
            "마스터" in compact
            or "master" in text
            or "중심" in compact
            or "local_master" in text
        )

    def _looks_like_server_status_macro_request(self, message):
        text = self._clean_text(message).lower()
        compact = re.sub(r"\s+", "", text)
        if "매크로" not in text:
            return False
        if not re.search(r"(추가|만들|생성|등록|create|add)", text, re.IGNORECASE):
            return False
        return bool(
            ("서버" in compact and "상태" in compact and "한눈" in compact)
            or ("server" in text and "status" in text)
        )

    def _server_status_macro_payload(self):
        script = """#!/usr/bin/env bash
set -euo pipefail

section() {
  printf '\\n===== %s =====\\n' "$1"
}

section "host"
hostnamectl 2>/dev/null || hostname
date -Is
uptime || true

section "resource"
printf 'CPU cores: '
nproc 2>/dev/null || echo unknown
free -h 2>/dev/null || true
df -h / 2>/dev/null || true

section "docker"
if ! command -v docker >/dev/null 2>&1; then
  echo "docker command not found"
  exit 0
fi
docker version --format 'Client {{.Client.Version}} / Server {{.Server.Version}}' 2>/dev/null || docker version || true
docker info --format 'Swarm={{.Swarm.LocalNodeState}} Containers={{.Containers}} Running={{.ContainersRunning}} Images={{.Images}}' 2>/dev/null || true

section "containers"
docker ps --format 'table {{.Names}}\\t{{.Status}}\\t{{.Image}}\\t{{.Ports}}' 2>/dev/null || true

section "container stats"
docker stats --no-stream --format 'table {{.Name}}\\t{{.CPUPerc}}\\t{{.MemUsage}}\\t{{.NetIO}}' 2>/dev/null || true

section "swarm services"
docker service ls --format 'table {{.Name}}\\t{{.Replicas}}\\t{{.Image}}' 2>/dev/null || echo "swarm service list unavailable"

section "swarm nodes"
docker node ls --format 'table {{.Hostname}}\\t{{.Status}}\\t{{.Availability}}\\t{{.ManagerStatus}}' 2>/dev/null || echo "swarm node list unavailable"
"""
        return {
            "name": "서버 상태 한눈에 보기",
            "description": "CPU, 메모리, 디스크, Docker, 컨테이너, Swarm 상태를 한 번에 출력합니다.",
            "script": script,
            "enabled": True,
            "update_existing": True,
        }

    def _record_chat_history(self, payload, provider, response, status="succeeded", error=None, started_at=None, env=None):
        try:
            public_provider = self._provider_public(provider) if isinstance(provider, dict) else {}
            ai_history.record(
                payload=payload if isinstance(payload, dict) else {},
                response=response if isinstance(response, dict) else {},
                provider=public_provider,
                request_meta=(payload or {}).get("request_meta") if isinstance(payload, dict) else {},
                status=status,
                error=error,
                started_at=started_at,
                env=env,
            )
        except Exception:
            return None

    def _attach_chat_session(self, response, payload, provider, metadata=None, env=None):
        if not isinstance(response, dict):
            return response
        metadata = metadata if isinstance(metadata, dict) else {}
        session = metadata.get("session") if isinstance(metadata.get("session"), dict) else {}
        if not session:
            session = self._chat_session(payload, provider, env=env)
        session_id = self._normalize_session_id(session.get("session_id") or (payload or {}).get("session_id"))
        provider_session_id = self._normalize_session_id(
            session.get("provider_session_id") or metadata.get("provider_session_id")
        )
        if session_id:
            response["session_id"] = session_id
        if provider_session_id:
            response["provider_session_id"] = provider_session_id
        provider_payload = response.get("provider") if isinstance(response.get("provider"), dict) else {}
        if provider_payload:
            if session_id:
                provider_payload["session_id"] = session_id
            if provider_session_id:
                provider_payload["provider_session_id"] = provider_session_id
            provider_payload["session_resumed"] = bool(session.get("resume") or metadata.get("session_resumed"))
            response["provider"] = provider_payload
        return response

    def _duration_ms(self, started_at):
        if not isinstance(started_at, datetime.datetime):
            return 0
        started = started_at
        if started.tzinfo is None:
            started = started.replace(tzinfo=datetime.timezone.utc)
        elapsed = (_utc_now() - started.astimezone(datetime.timezone.utc)).total_seconds()
        return max(1, int(round(elapsed * 1000)))

    def _text_chunks(self, text, size=48):
        text = str(text or "")
        for index in range(0, len(text), size):
            yield text[index:index + size]

    def _ui_chat_system_prompt(self):
        return "\n".join(
            [
                "You are the persistent AI Agent inside Docker Infra's web UI.",
                "Return only one JSON object. Do not wrap it in markdown.",
                "The user sees your answer in a floating chat window that survives route changes.",
                "Use the supplied screen context to understand the current route, page title, recent user actions, focused fields, open modals, visible controls, and important visible text.",
                "Use Docker Infra MCP tools when the request needs current server, service, domain, image, container, port, or runtime state.",
                "You may return client_actions to operate the current browser UI. Use refs from screen.interactive_elements when visible, or semantic targets such as button text, label text, placeholder, route path, or app_event command keys when an action must happen after navigation.",
                "The browser executes client_actions in order and waits after navigation, so multi-step workflows can navigate first and then click, fill, focus, or dispatch an app_event on the destination screen.",
                "The browser already shows the current TODO item above the input. Do not repeat the planning TODO list in the answer; explain the result of the current TODO instead.",
                "Use app_event for first-class Docker Infra page commands that are safer than brittle field automation. Supported app_event commands: target='macro.create_global' with payload {name, description, script, enabled, update_existing}; target='server.run_macro' with payload {node_selector, node_id, macro_name, macro, args}.",
                "Use api_request when the user asks you to operate a Docker Infra menu through the Swagger/OpenAPI catalog. Prefer api_request over brittle click/fill automation whenever openapi_guidance.operations contains the needed page command. Choose operation_id only from openapi_guidance.operations and provide body/params with required fields.",
                "Treat openapi_guidance.mcp_action_catalog as the Docker Infra MCP tool catalog. Pick the matching docker_infra.* tool first, then emit the corresponding api_request operation_id.",
                "For service MCP tools that require service_id, if the user names a service but the id is not visible, put body.service_name with the exact name. The browser resolves service_name to service_id before calling the API.",
                "For chained api_request workflows, set save_as on the action whose response is needed, then reference it in later params/body strings as {{alias.path.to.value}}. The browser resolves references from the API response data object before sending the later request. Example: services_create.create with save_as='created_service', then services_create.deploy_background body {'service_id': '{{created_service.result.service.id}}'}, then services.refresh_status body {'service_id': '{{created_service.result.service.id}}'}.",
                "Read safety api_request actions may run directly for explicit inspection/refresh requests. Write safety actions require explicit user intent in the current message. Destructive safety actions require needs_confirmation=true unless the current message explicitly confirms the exact destructive operation.",
                "When the user asks to add a macro that checks server status at a glance, navigate to /macros and dispatch app_event macro.create_global with a safe read-only shell script.",
                "When the user asks to run the server status macro on the master node, navigate to /servers and dispatch app_event server.run_macro with node_selector='local_master' and the server status macro payload.",
                "Return client_actions only when the current user message explicitly asks you to navigate, click, fill, save, run, refresh, close, or otherwise operate a visible UI element. For informational questions, analysis, summaries, inspections, and recommendations, leave client_actions empty and use suggested_actions instead.",
                "Do not return client_actions for destructive or irreversible operations unless the user has explicitly confirmed the exact action in the current message. For those cases set needs_confirmation=true and explain what confirmation is needed.",
                "Never delete Docker Infra itself, stop/remove its control services or containers, shut down/reboot the OS, wipe disks, or recursively delete OS-critical paths.",
                "If the requested UI element is not visible in context, explain the next step or return a navigate action to the relevant page instead of inventing a selector.",
                "Write user-facing fields in Korean. Keep routes, ids, selectors, command names, image names, keys, and JSON fields in ASCII.",
                "The answer field must be a final user-facing result, not a progress placeholder. Never answer only that you are checking, analyzing, or asking the user to wait.",
                "If you cannot complete the requested analysis, put the concrete failure reason in answer and summary instead of returning an empty answer.",
                "When referring to the visible page, use screen_context_summary or a specific title from screen.headings. Do not say only '현재 화면'; name the exact page such as '서비스 관리 . notion 서비스 상세' or '이미지 관리 . 서버 로컬 저장소 . local-master'.",
                "Format answer as concise Markdown bullets, numbered lists, or tables whenever possible. Avoid long unstructured paragraphs.",
                "Always include 2 to 4 suggested_actions that are useful next chat requests based on your answer. Each suggested action must have a concise Korean label and a self-contained Korean prompt.",
                "Suggested actions are not direct browser actions. Do not put dangerous or irreversible operations as a direct suggested prompt; suggest a confirmation, impact check, or preview first.",
                "The output object must include answer, summary, needs_confirmation, client_actions, follow_up, suggested_actions, and confidence.",
            ]
        )

    def _ui_todo_plan_system_prompt(self):
        return "\n".join(
            [
                "You create the user-visible TODO list for Docker Infra's AI Agent.",
                "Return only one JSON object. Do not wrap it in markdown.",
                "Split the user's request into conceptual work items, not browser events.",
                "Do not create separate TODOs for navigation, clicking, selecting tabs, waiting, api_request, or app_event details.",
                "A single TODO may require many client_actions during execution.",
                "For a request like '마스터 노드에서 서버 상태 한눈에 보기 매크로를 실행해줘', return exactly one TODO for running that macro on the master node.",
                "Use Korean user-facing text. Keep route names, ids, and command keys in ASCII.",
                "Each todo.prompt must be self-contained so a later AI Agent request can execute that single TODO without reading hidden planning state.",
                "Limit todos to 1 to 5 items. Prefer fewer TODOs when actions belong to one user goal.",
                "The output object must include summary and todos.",
            ]
        )

    def _normalize_chat_todos(self, value, fallback_message):
        source = value if isinstance(value, list) else []
        result = []
        for index, item in enumerate(source[:5]):
            if isinstance(item, str):
                title = item
                prompt = item
                reason = ""
            elif isinstance(item, dict):
                title = item.get("title") or item.get("label") or item.get("name") or item.get("summary") or ""
                prompt = item.get("prompt") or item.get("message") or item.get("instruction") or title
                reason = item.get("reason") or item.get("description") or ""
            else:
                continue
            title = self._clean_text(title or prompt)[:140]
            prompt = self._clean_text(prompt or title)[:800]
            reason = self._clean_text(reason)[:240]
            if not title and not prompt:
                continue
            result.append({"id": "todo-%s" % (index + 1), "title": title or prompt, "prompt": prompt or title, "reason": reason})
        if not result:
            message = self._clean_text(fallback_message)
            result.append({"id": "todo-1", "title": message[:140] or "요청 처리", "prompt": message, "reason": ""})
        return result

    def _compact_chat_history(self, value):
        if not isinstance(value, list):
            return []
        rows = []
        for item in value[-12:]:
            if not isinstance(item, dict):
                continue
            role = self._clean_text(item.get("role"))
            if role not in {"user", "assistant", "status", "error"}:
                role = "assistant"
            content = self._clean_text(item.get("content"))
            if not content:
                continue
            rows.append(
                {
                    "role": role,
                    "content": content[:1200],
                    "at": self._clean_text(item.get("at"))[:64],
                }
            )
        return rows

    def _chat_json_value(self, value, depth=0):
        if depth > 4:
            return self._clean_text(value)[:240]
        if value is None or isinstance(value, (bool, int, float)):
            return value
        if isinstance(value, str):
            return value[:1600]
        if isinstance(value, list):
            return [self._chat_json_value(item, depth + 1) for item in value[:40]]
        if isinstance(value, dict):
            result = {}
            for index, key in enumerate(value.keys()):
                if index >= 80:
                    result["_truncated"] = True
                    break
                result[self._clean_text(key)[:80]] = self._chat_json_value(value.get(key), depth + 1)
            return result
        return self._clean_text(value)[:400]

    def _normalize_client_actions(self, value):
        if not isinstance(value, list):
            return []
        allowed = {"navigate", "click", "fill", "focus", "close_modal", "refresh", "wait", "app_event", "api_request", "noop"}
        result = []
        for item in value[:6]:
            if not isinstance(item, dict):
                continue
            action_type = self._clean_text(item.get("type")).lower()
            if action_type not in allowed:
                continue
            result.append(
                {
                    "type": action_type,
                    "ref": self._clean_text(item.get("ref"))[:120],
                    "target": self._clean_text(item.get("target"))[:400],
                    "operation_id": self._clean_text(item.get("operation_id") or item.get("operationId"))[:160],
                    "params": self._chat_json_value(item.get("params"), depth=0),
                    "body": self._chat_json_value(item.get("body"), depth=0),
                    "value": self._clean_text(item.get("value"))[:1200],
                    "payload": self._chat_json_value(item.get("payload"), depth=0),
                    "reason": self._clean_text(item.get("reason"))[:400],
                    "requires_confirmation": bool(item.get("requires_confirmation")),
                }
            )
        return result

    def _normalize_suggested_actions(self, value, fallback=None):
        source = value if isinstance(value, list) else []
        result = []
        for item in source[:4]:
            if isinstance(item, str):
                label = prompt = item
                reason = ""
            elif isinstance(item, dict):
                label = item.get("label") or item.get("title") or item.get("name") or ""
                prompt = item.get("prompt") or item.get("message") or item.get("query") or item.get("instruction") or label
                reason = item.get("reason") or item.get("description") or ""
            else:
                continue
            prompt = self._clean_text(prompt)[:500]
            label = self._clean_text(label or prompt)[:80]
            reason = self._clean_text(reason)[:240]
            if not prompt:
                continue
            result.append({"label": label or prompt[:40], "prompt": prompt, "reason": reason})
        follow_up = self._clean_text(fallback)
        if not result and follow_up:
            result.append({"label": follow_up[:80], "prompt": follow_up[:500], "reason": ""})
        return result

    def _agent_keys(self):
        return ["codex", "claude_code", "hermes"]

    def _normalize_agent_key(self, value):
        key = self._clean_text(value).lower().replace("-", "_")
        aliases = {
            "claude": "claude_code",
            "claudecode": "claude_code",
            "claude_code": "claude_code",
            "hermes_agent": "hermes",
            "hermes": "hermes",
            "codex": "codex",
        }
        return aliases.get(key, key)

    def _agent_enabled(self, config, agent):
        return bool((config.get(agent) or {}).get("enabled"))

    def _agent_configured_model(self, config, agent, model):
        configured = self._clean_text((config.get(agent) or {}).get("model"))
        requested = self._clean_text(model)
        return not requested or requested == "__default__" or requested == configured

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
                    "description": "등록 가능한 Cloudflare DNS 존 또는 DDNS 관리 서버 엔드포인트 목록",
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
                "healthchecks are recommended when practical, but not required",
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

    def template_contract(self):
        return {
            "input": [
                {"key": "intent", "required": True, "description": "만들거나 보정할 Compose 템플릿 요구사항"},
                {"key": "mode", "required": True, "values": ["template_create", "template_update"]},
                {"key": "current_template", "required": False, "description": "현재 템플릿 이름, 태그, README, Compose, values schema"},
            ],
            "output": [
                "name",
                "namespace",
                "tags[]",
                "files.docker-compose.yaml",
                "files.values.default.yaml",
                "files.values.schema.json",
                "files.README.md",
                "summary",
                "warnings[]",
            ],
            "output_format": self.output_format_contract("template"),
            "policy": self.template_ai_policy(),
        }

    def template_ai_policy(self):
        enabled_tools = self._mcp_tools("compose_template")
        required_files = ["docker-compose.yaml", "values.default.yaml", "values.schema.json", "README.md"]
        return {
            "scope": "compose_template",
            "purpose": "Reusable Compose template draft only; service deployment and runtime repair are outside this scope.",
            "mcp": {
                "server": "docker_infra",
                "enabled_tools": enabled_tools,
                "allowed_use": [
                    "infra_context: Docker Infra compose/network/template constraints and full MCP contract",
                    "docker_search/docker_image_check: candidate image discovery and exact tag verification",
                    "server_list/server_collect/ssh_command: registered server inspection when the template depends on runtime facts",
                    "container_logs/container_action/service_stack_status/probe tools: runtime confirmation when helpful, within the critical guard",
                ],
                "permission_mode": "agent_full_control_except_critical_destruction",
                "blocked_action_families": [
                    "delete Docker Infra itself",
                    "stop/remove Docker Infra control services, containers, or stacks",
                    "shutdown/reboot/wipe/format the OS",
                    "recursive deletion of OS critical paths",
                ],
                "tool_unavailable_policy": "Do not mention unavailable MCP tools in user-facing text; use the provided contract and context.",
            },
            "standard": {
                "required_files": required_files,
                "placeholder_format": "{{ variable_name }}",
                "namespace_pattern": "^[a-z0-9_]+$",
                "readme_required": True,
                "readme_visibility": "service_create_required",
                "classification": "metadata.tags string array; category is not used",
                "description_field": "removed; use README.md instead",
                "schema_rules": [
                    "values.schema.json must be a JSON Schema object for the same placeholders as docker-compose.yaml",
                    "every placeholder must have a default in values.default.yaml and a property in values.schema.json",
                    "secret-like properties must include secret=true and a safe change_me-style default",
                    "service_name/namespace should be the only mandatory identity input unless the image truly requires more",
                ],
                "compose_rules": self.compose_validation_contract(),
                "forbidden_fields": [
                    "description",
                    "primary_image",
                    "category",
                    "deploy_target",
                    "node_id",
                    "domain",
                    "runtime_actions",
                ],
            },
            "permissions": {
                "can_edit_project_files": True,
                "can_save_template": False,
                "can_deploy": False,
                "can_change_runtime": True,
                "can_read_runtime_logs": True,
                "can_run_container_actions": True,
                "can_run_ssh_command": True,
                "can_run_safe_ssh_diagnostics": True,
                "can_probe_network": True,
                "can_select_deploy_target": False,
                "cannot_delete_docker_infra": True,
                "cannot_run_os_critical_commands": True,
                "result_application": "draft_only_user_review_required",
            },
        }

    def output_format_contract(self, target):
        if target == "template":
            return {
                "root": {
                    "type": "object",
                    "required": ["name", "namespace", "tags", "files", "summary", "warnings"],
                    "namespace_pattern": "^[a-z0-9_]+$",
                    "forbidden": [
                        "markdown fences",
                        "partial patches",
                        "free-form text outside JSON",
                        "description",
                        "primary_image",
                        "category",
                        "deploy_target",
                        "node_id",
                        "domain",
                        "runtime_actions",
                    ],
                },
                "files": {
                    "type": "object",
                    "required": ["docker-compose.yaml", "values.default.yaml", "values.schema.json", "README.md"],
                    "rules": [
                        "docker-compose.yaml is a complete Compose template using {{ variable_name }} placeholders only where users should provide values",
                        "values.default.yaml contains defaults for every placeholder",
                        "values.schema.json is a JSON Schema object for the same placeholders",
                        "README.md is Korean user-facing usage notes shown in the service creation screen",
                        "the placeholder set must match across docker-compose.yaml, values.default.yaml, and values.schema.json",
                        "do not include a deployment target, concrete domain, concrete registered server, host-specific path, container_name, or hostname",
                    ],
                },
                "schema": {
                    "type": "object",
                    "required": ["$schema", "title", "type", "properties", "required"],
                    "rules": [
                        "$schema should be https://json-schema.org/draft/2020-12/schema",
                        "properties keys must match placeholders",
                        "secret-like properties include secret=true",
                    ],
                },
                "metadata": {
                    "type": "object",
                    "required": ["tags"],
                    "optional": ["components", "public_endpoint", "component_labels", "generated_secrets"],
                    "forbidden": ["category", "primary_image", "description", "deploy_target", "node_id", "domain"],
                },
            }
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
                    "each domain includes domain, zone_id when known, provider or dns_provider when known, domain_target_key, domain_target_port, compose_service, target_port, and ssl_mode when known",
                    "for DDNS zones, zone_id is the DDNS endpoint id and the full domain must be under that endpoint wildcard_suffix",
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
        zones = self._service_zones_for_ai(payload, env=env)
        context = {
            "contract": self.service_contract(),
            "output_format": self.output_format_contract("service"),
            "docker_infra_context": self._service_create_context({**payload, "zones": zones}),
            "mode": payload.get("mode") or "service_create",
            "intent": intent,
            "operator_comment": self._clean_text(payload.get("operator_comment")),
            "form": form,
            "components": components,
            "base_content": payload.get("base_content") or "",
            "zones": zones,
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
            "warnings": self._service_warnings(data, draft, context),
            "ai_pipeline": pipeline,
        }

    def stream_service(self, payload, env=None):
        payload = payload or {}
        intent = self._clean_text(payload.get("intent"))
        if not intent:
            yield {"type": "error", "message": "AI 요청 내용을 입력하세요.", "error_code": "MISSING_INTENT"}
            return
        zones = self._service_zones_for_ai(payload, env=env)
        context = {
            "contract": self.service_contract(),
            "output_format": self.output_format_contract("service"),
            "docker_infra_context": self._service_create_context({**payload, "zones": zones}),
            "mode": payload.get("mode") or "service_create",
            "intent": intent,
            "operator_comment": self._clean_text(payload.get("operator_comment")),
            "form": payload.get("form") or {},
            "components": payload.get("components") or [],
            "base_content": payload.get("base_content") or "",
            "zones": zones,
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
                        "warnings": self._service_warnings(data, draft, context),
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

    def stream_template(self, payload, env=None):
        payload = payload or {}
        intent = self._clean_text(payload.get("intent"))
        if not intent:
            yield {"type": "error", "message": "AI 요청 내용을 입력하세요.", "error_code": "MISSING_INTENT"}
            return
        context = self._template_context(payload)
        try:
            provider = self._select_provider(env=env, selection=payload)
        except Exception as exc:
            yield self._error_event(exc)
            return
        yield {"type": "provider", "provider": self._provider_public(provider)}
        yield {"type": "status", "message": "요구사항과 현재 템플릿을 AI 실행 컨텍스트로 정리합니다."}
        system = self._template_system_prompt()
        data = None
        for attempt in range(MAX_AI_REPAIR_ATTEMPTS + 1):
            if attempt > 0:
                yield {"type": "status", "message": "검증 실패 내용을 반영해 템플릿 output을 보정합니다. (%s/%s)" % (attempt, MAX_AI_REPAIR_ATTEMPTS)}
            try:
                data = yield from self._stream_codex_json(system, context, provider, env=env, emit_delta=True)
                if data is None:
                    raise AIAssistantError(502, "AI 응답 JSON 객체가 비어 있습니다.", "AI_EMPTY_RESPONSE")
                template = self._normalize_template_draft(data, context)
                validation = self._validate_template_draft(template)
                yield {
                    "type": "done",
                    "data": {
                        "provider": self._provider_public(provider),
                        "contract": self.template_contract(),
                        "template": template,
                        "validation": validation,
                        "summary": self._clean_text(data.get("summary")) or "AI 템플릿 초안을 적용했습니다.",
                        "warnings": self._string_list(data.get("warnings")),
                    },
                }
                return
            except Exception as exc:
                if not self._is_output_repairable_error(exc):
                    yield self._error_event(exc)
                    return
                if attempt >= MAX_AI_REPAIR_ATTEMPTS:
                    yield self._error_event(self._as_output_validation_error(exc, "template"))
                    return
                context = self._repair_context("template", context, data, exc, attempt + 1)
                system = self._repair_system_prompt("template")

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

        context = self._runtime_repair_context(detail, diagnostics, payload, env=env)
        data = self._ddns_direct_repair_data(context)
        if data is None:
            try:
                data, _ = self._complete_json(self._runtime_repair_system_prompt(), context, provider=provider, env=env)
            except Exception as exc:
                data = self._ddns_repair_fallback_data(context, exc)
                if data is None:
                    raise
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

            context = self._runtime_repair_context(detail, diagnostics, payload, env=env)
            yield {"type": "status", "message": "AI가 현재 설정, 로그, 추가 메시지를 바탕으로 수정안을 작성합니다."}
            data = self._ddns_direct_repair_data(context)
            if data is not None:
                yield {"type": "status", "message": "등록된 DDNS 관리 서버 정보로 도메인 연결을 자동 보정합니다."}
            else:
                try:
                    data = yield from self._stream_codex_json(
                        self._runtime_repair_system_prompt(),
                        context,
                        provider,
                        env=env,
                        emit_delta=True,
                    )
                except Exception as exc:
                    data = self._ddns_repair_fallback_data(context, exc)
                    if data is None:
                        raise
                    yield {"type": "status", "message": "AI 수정 호출이 실패해 DDNS 추천값으로 자동 보정합니다."}
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
        last_status = None
        suppressed_count = 0

        def append_status(status, operation=None, suppressed=False):
            if suppressed:
                operations.append_output(
                    parent_operation_id,
                    "동일한 재배포 상태 로그 %s회를 생략했습니다." % suppressed_count,
                    stream="system",
                    metadata={"step": "deploy wait", "deploy_operation_id": operation_id, "status": status, "suppressed": suppressed_count},
                    env=env,
                )
                return
            operations.append_output(
                parent_operation_id,
                "재배포 작업 상태: %s" % (status or "unknown"),
                stream="system" if status in {"pending", "running", "succeeded"} else "stderr",
                metadata={"step": "deploy wait", "deploy_operation_id": operation_id, "status": status},
                env=env,
            )

        while time.monotonic() < deadline:
            operation = operations.detail(operation_id, env=env)
            status = self._clean_text(operation.get("status")).lower()
            if status == last_status and status in {"pending", "running"}:
                suppressed_count += 1
            else:
                if suppressed_count:
                    append_status(last_status, suppressed=True)
                    suppressed_count = 0
                append_status(status, operation=operation)
            last_status = status
            if status not in {"pending", "running"}:
                return {"status": status, "operation": operation}
            time.sleep(5)
        if suppressed_count:
            append_status(last_status, suppressed=True)
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
        context = self._runtime_verification_context(detail, diagnostics, payload, env=env)
        data = self._ddns_direct_verification_data(context)
        if data is None:
            try:
                data, _ = self._complete_json(self._runtime_verification_system_prompt(), context, provider=provider, env=env)
            except Exception as exc:
                data = self._ddns_verification_fallback_data(context, exc)
                if data is None:
                    raise
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
                "MCP permissions are broad; avoid unnecessary mutation during verification, and never cross the Docker Infra self-destruction or OS-critical guard.",
                "If a desired MCP tool is unavailable or not exposed, do not report that as a service issue; use the enabled tools and supplied runtime context instead.",
                "If a fix is needed, do not return a service draft here. Return a Korean repair_intent that the repair step can use.",
                "When DDNS is requested or ddns_repair_suggestion.enabled is true, include the suggested DDNS endpoint and suggested_domain in repair_intent instead of saying DDNS values are missing.",
                "Return only one JSON object with keys: ok, summary, issues, warnings, checks, repair_required, repair_intent.",
                "issues must be an array of objects with key, severity, message, evidence.",
                "checks should include stack, containers, domains, network, http, user_function when known.",
                "Write summary, issues[].message, warnings, and repair_intent in Korean.",
            ]
        )

    def _runtime_verification_context(self, detail, diagnostics, payload, env=None):
        service = detail.get("service") or {}
        domains = detail.get("domains") or []
        allow_ssh_command = payload.get("allow_ssh_command") is not False
        enabled_tools = self._mcp_tools("post_deploy_verification", allow_ssh_command=allow_ssh_command)
        zones = self._service_zones_for_ai(payload, env=env)
        ddns_endpoints = self._ddns_zones(zones)
        ddns_repair_suggestion = self._ddns_repair_suggestion(detail, payload, zones)
        return {
            "mode": "post_deploy_verification",
            "service": service,
            "domains": domains,
            "zones": zones,
            "ddns_endpoints": ddns_endpoints,
            "ddns_repair_suggestion": ddns_repair_suggestion,
            "form": {
                "name": service.get("name") or service.get("namespace"),
                "description": (service.get("metadata") or {}).get("description") or "",
                "domains": self._domain_rows_for_context(domains),
            },
            "components": detail.get("components") or [],
            "base_content": detail.get("compose_content") or "",
            "runtime_status": self._compact_runtime_status(detail.get("runtime_status") or {}),
            "recent_operations": self._compact_recent_operations(detail.get("operations") or []),
            "runtime_diagnostics": diagnostics,
            "runtime_wait": payload.get("runtime_wait") or {},
            "user_intent": self._clean_text(payload.get("intent")),
            "client_runtime_issues": self._compact_client_runtime_issues(payload.get("client_runtime_issues")),
            "ai_permission_scope": {
                "scope": "post_deploy_verification",
                "can_edit_project_files": True,
                "can_deploy": payload.get("deploy") is not False,
                "can_change_runtime": True,
                "can_run_safe_ssh_diagnostics": allow_ssh_command,
                "can_run_container_actions": True,
                "can_inspect_ddns_domains": True,
                "can_mutate_ddns_records": True,
                "cannot_delete_docker_infra": True,
                "cannot_run_os_critical_commands": True,
                "allow_ssh_command": allow_ssh_command,
                "mcp_enabled_tools": enabled_tools,
            },
            "mcp_guidance": {
                "server": "docker_infra",
                "enabled_tools": enabled_tools,
                "preferred_tools": enabled_tools,
                "allow_ssh_command": allow_ssh_command,
                "tool_unavailable_policy": "Do not mention unavailable or unexposed MCP tools in operator-facing summary, issues, or warnings; use enabled_tools and provided context as fallback.",
            },
        }

    def _finish_runtime_repair(self, provider, detail, diagnostics, payload, data, context, env=None):
        service_id = self._clean_text(payload.get("service_id"))
        draft = self._normalize_service_draft(data, fallback=context)
        self._apply_ddns_repair_fallback(draft, context)
        rendered = self._validate_service_draft(draft, context, env=env)
        result = {
            "provider": self._provider_public(provider),
            "diagnostics": diagnostics,
            "draft": draft,
            "rendered": rendered,
            "summary": self._clean_text(data.get("summary")),
            "warnings": self._service_warnings(data, draft, context),
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
        ddns_register_result = self._register_ddns_after_ai_update(service_id, draft, context, env=env)
        if ddns_register_result:
            result["ddns_register_result"] = ddns_register_result
            if ddns_register_result.get("status") == "error":
                result["warnings"].append("DDNS 등록 API 호출 실패: %s" % (ddns_register_result.get("message") or ddns_register_result.get("error_code") or "unknown"))
                result["summary"] = (result.get("summary") or "AI 수정 결과를 적용했습니다.") + " DDNS 등록 API 호출은 실패했습니다."
            else:
                result["summary"] = (result.get("summary") or "AI 수정 결과를 적용했습니다.") + " " + self._ddns_register_summary_text(ddns_register_result)
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
                "Avoid removing persistent volumes unless the user explicitly asks or the runtime evidence proves they are disposable. Do not invent secret values; use generated_secret_keys.",
                "When logs say a password or secret must be set, set the exact environment variable the image reads with a non-empty stack-local generated value; do not blindly convert it to *_FILE or Docker secrets.",
                "If a deployment rolled back after startup, check healthcheck commands and update_config failure_action. Avoid fragile healthchecks that depend on tools not present in the image.",
                "If terminal_actions.allow_container_actions is not false, you may use docker_infra.container_action to stop, restart, or remove relevant non-Docker-Infra containers.",
                "If SSH diagnostics are enabled, you may use docker_infra.ssh_command for operator-level commands on registered servers within the critical guard.",
                "When a container terminal action is needed, also return runtime_actions as an array of objects: {action, container_id, node_id, reason}. Use action stop, restart, or remove only.",
                "If you already executed an action through MCP, set executed=true on that runtime_actions item so Docker Infra will record it without running it twice.",
                "If a desired MCP tool is unavailable or not exposed, do not report that as a service issue; use the enabled tools and supplied runtime context instead.",
                "Never delete Docker Infra itself, stop/remove its control services or containers, shut down/reboot the OS, wipe disks, or recursively delete OS-critical paths. Summarize any terminal action you executed in Korean warnings or summary.",
                "If the safest action is operational rather than Compose editing, keep Compose stable and return Korean warnings with the manual action.",
                "When ddns_repair_suggestion.enabled is true, use its domain_row to keep or create form.domains; never remove all public domains just because the DDNS record is not registered yet.",
                "If the user asks to convert an existing domain to DDNS and no exact subdomain is specified, use ddns_repair_suggestion.suggested_domain.",
            ]
        )

    def _runtime_repair_context(self, detail, diagnostics, payload, env=None):
        service = detail.get("service") or {}
        domains = detail.get("domains") or []
        client_runtime_issues = payload.get("client_runtime_issues") if isinstance(payload.get("client_runtime_issues"), dict) else {}
        allow_container_actions = payload.get("allow_container_terminal_actions") is not False
        allow_ssh_command = payload.get("allow_ssh_command") is not False
        enabled_tools = self._mcp_tools(
            "runtime_repair" if allow_container_actions else "runtime_inspection",
            allow_container_actions=allow_container_actions,
            allow_ssh_command=allow_ssh_command,
        )
        zones = self._service_zones_for_ai(payload, env=env)
        ddns_endpoints = self._ddns_zones(zones)
        ddns_repair_suggestion = self._ddns_repair_suggestion(detail, payload, zones)
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
                "can_edit_project_files": True,
                "can_deploy": payload.get("deploy") is not False,
                "can_change_runtime": allow_container_actions,
                "can_run_container_actions": allow_container_actions,
                "can_run_safe_ssh_diagnostics": allow_ssh_command,
                "can_select_ddns_domains": True,
                "can_register_ddns_records_via_deploy": payload.get("deploy") is not False,
                "can_inspect_ddns_domains": True,
                "can_mutate_ddns_records": payload.get("deploy") is not False,
                "cannot_delete_docker_infra": True,
                "cannot_run_os_critical_commands": True,
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
            "zones": zones,
            "ddns_endpoints": ddns_endpoints,
            "ddns_repair_suggestion": ddns_repair_suggestion,
            "runtime_status": self._compact_runtime_status(detail.get("runtime_status") or {}),
            "recent_operations": self._compact_recent_operations(detail.get("operations") or []),
            "runtime_diagnostics": diagnostics,
            "client_runtime_issues": self._compact_client_runtime_issues(client_runtime_issues),
            "terminal_actions": {
                "allow_container_actions": allow_container_actions,
                "allowed_actions": ["stop", "restart", "remove"] if allow_container_actions else [],
                "scope": "problem containers from runtime_diagnostics.problem_containers and client_runtime_issues.problem_containers only",
                "return_field": "runtime_actions",
                "schema": {"action": "stop|restart|remove", "container_id": "container id or name", "node_id": "registered node id", "reason": "Korean reason", "executed": "true only if MCP already executed it"},
            },
            "docker_infra_context": {
                **self._service_create_context({"mode": "service_update", "zones": zones}),
                "repair_flow": "refresh runtime status, collect container logs and stack errors, ask the selected AI Agent for a corrected service draft, save the corrected compose, then redeploy when requested",
                "ddns_repair_suggestion": ddns_repair_suggestion,
            },
            "mcp_guidance": {
                "server": "docker_infra",
                "enabled_tools": enabled_tools,
                "preferred_tools": enabled_tools,
                "allow_ssh_command": allow_ssh_command,
                "tool_unavailable_policy": "Do not mention unavailable or unexposed MCP tools in operator-facing summary, issues, or warnings; use enabled_tools and provided context as fallback.",
            },
        }

    def _ddns_verification_fallback_data(self, context, exc):
        suggestion = (context or {}).get("ddns_repair_suggestion") if isinstance(context, dict) else {}
        if not isinstance(suggestion, dict) or suggestion.get("enabled") is not True:
            return None
        error = self._exception_payload(exc)
        domain = suggestion.get("suggested_domain")
        endpoint = suggestion.get("endpoint") or {}
        return {
            "ok": False,
            "summary": "Codex 검증 호출이 실패해 등록된 DDNS 서버 정보를 기준으로 자동 수정 단계로 전환합니다.",
            "issues": [
                {
                    "key": "ddns.runtime_repair_fallback",
                    "severity": "warning",
                    "message": "DDNS 도메인 연결이 비어 있어 Docker Infra가 추천 DDNS 도메인으로 수정안을 생성해야 합니다.",
                    "evidence": {
                        "suggested_domain": domain,
                        "endpoint_id": suggestion.get("domain_row", {}).get("ddns_endpoint_id"),
                        "wildcard_suffix": endpoint.get("wildcard_suffix") or endpoint.get("domain"),
                        "codex_error_code": error.get("error_code"),
                    },
                }
            ],
            "warnings": ["Codex 검증 호출 실패로 DDNS deterministic fallback을 사용합니다."],
            "checks": {
                "domains": {
                    "status": "repair_required",
                    "suggested_domain": domain,
                    "ddns_endpoint_id": suggestion.get("domain_row", {}).get("ddns_endpoint_id"),
                }
            },
            "repair_required": True,
            "repair_intent": "DDNS endpoint %s의 wildcard suffix %s에 %s 도메인을 등록하고 현재 서비스의 공개 포트로 연결해 주세요." % (
                suggestion.get("domain_row", {}).get("ddns_endpoint_id") or "",
                endpoint.get("wildcard_suffix") or endpoint.get("domain") or "",
                domain or "",
            ),
        }

    def _ddns_direct_verification_data(self, context):
        suggestion = (context or {}).get("ddns_repair_suggestion") if isinstance(context, dict) else {}
        if not isinstance(suggestion, dict) or suggestion.get("enabled") is not True:
            return None
        domain = suggestion.get("suggested_domain")
        endpoint = suggestion.get("endpoint") or {}
        domains = (context or {}).get("domains") if isinstance((context or {}).get("domains"), list) else []
        already_configured = any(self._clean_text((row or {}).get("domain")).lower().strip(".") == domain for row in domains if isinstance(row, dict))
        if already_configured:
            return None
        return {
            "ok": False,
            "summary": "등록된 DDNS 관리 서버 정보로 서비스 도메인 연결을 보정해야 합니다.",
            "issues": [
                {
                    "key": "ddns.domain_not_attached",
                    "severity": "warning",
                    "message": "서비스에 DDNS 하위 도메인이 아직 연결되어 있지 않습니다.",
                    "evidence": {
                        "suggested_domain": domain,
                        "endpoint_id": suggestion.get("domain_row", {}).get("ddns_endpoint_id"),
                        "wildcard_suffix": endpoint.get("wildcard_suffix") or endpoint.get("domain"),
                    },
                }
            ],
            "warnings": [],
            "checks": {"domains": {"status": "repair_required", "suggested_domain": domain}},
            "repair_required": True,
            "repair_intent": "등록된 DDNS endpoint에 %s 도메인을 연결하고 DDNS 등록 API를 호출해 주세요." % (domain or ""),
        }

    def _ddns_direct_repair_data(self, context):
        suggestion = (context or {}).get("ddns_repair_suggestion") if isinstance(context, dict) else {}
        if not isinstance(suggestion, dict) or suggestion.get("enabled") is not True:
            return None
        row = dict(suggestion.get("domain_row") or {})
        if not row.get("domain"):
            return None
        form = dict((context or {}).get("form") or {})
        form.update(
            {
                "domain_mode": "registered",
                "domain": row.get("domain"),
                "zone_id": row.get("zone_id"),
                "domain_prefix": row.get("domain_prefix"),
                "domain_target_key": row.get("domain_target_key"),
                "domain_target_port": row.get("domain_target_port"),
                "domains": [row],
            }
        )
        return {
            "form": form,
            "base_content": (context or {}).get("base_content") or "",
            "components": (context or {}).get("components") or [],
            "generated_secret_keys": [],
            "summary": "등록된 DDNS 관리 서버 정보로 서비스 도메인을 %s로 보정했습니다." % row.get("domain"),
            "warnings": [],
            "thinking_summary": "Applied deterministic DDNS domain repair without Codex because the requested change is a registered DDNS domain mapping.",
            "notes": "",
        }

    def _ddns_repair_fallback_data(self, context, exc):
        suggestion = (context or {}).get("ddns_repair_suggestion") if isinstance(context, dict) else {}
        if not isinstance(suggestion, dict) or suggestion.get("enabled") is not True:
            return None
        form = dict((context or {}).get("form") or {})
        row = dict(suggestion.get("domain_row") or {})
        form.update(
            {
                "domain_mode": "registered",
                "domain": row.get("domain"),
                "zone_id": row.get("zone_id"),
                "domain_prefix": row.get("domain_prefix"),
                "domain_target_key": row.get("domain_target_key"),
                "domain_target_port": row.get("domain_target_port"),
                "domains": [row],
            }
        )
        return {
            "form": form,
            "base_content": (context or {}).get("base_content") or "",
            "components": (context or {}).get("components") or [],
            "generated_secret_keys": [],
            "summary": "AI 수정 호출이 실패해 등록된 DDNS 서버와 추천 도메인으로 서비스 도메인을 보정했습니다.",
            "warnings": [
                "AI 수정 호출 실패로 DDNS deterministic fallback을 사용했습니다.",
                "추천 도메인이 의도와 다르면 도메인 설정에서 prefix를 수정한 뒤 다시 배포하세요.",
            ],
            "thinking_summary": "Used deterministic DDNS repair fallback after AI runtime failure.",
            "notes": "",
        }

    def _register_ddns_after_ai_update(self, service_id, draft, context=None, env=None):
        if not self._draft_has_ddns_domain(draft, context):
            return None
        try:
            return ddns_model.register_service_domains(service_id, env=env)
        except Exception as exc:
            if hasattr(exc, "message"):
                return {
                    "status": "error",
                    "message": getattr(exc, "message", str(exc)),
                    "error_code": getattr(exc, "error_code", "DDNS_REGISTER_FAILED"),
                    **getattr(exc, "extra", {}),
                }
            return {"status": "error", "message": str(exc), "error_code": "DDNS_REGISTER_FAILED"}

    def _ddns_register_summary_text(self, result):
        registered = result.get("registered") if isinstance(result.get("registered"), list) else []
        skipped = result.get("skipped") if isinstance(result.get("skipped"), list) else []
        if registered:
            return "DDNS 등록 API를 %s개 도메인에 호출했습니다." % len(registered)
        unchanged = [item for item in skipped if isinstance(item, dict) and item.get("reason") == "public_ip_unchanged"]
        if unchanged:
            return "기존 DDNS 등록 정보와 공인 IP가 같아 DDNS API 호출은 생략되었습니다."
        if skipped:
            return "DDNS 등록 대상이 없어 DDNS API 호출은 생략되었습니다."
        return "DDNS 등록 API 호출 결과를 확인했습니다."

    def _ddns_zones(self, zones):
        return [
            zone
            for zone in zones or []
            if isinstance(zone, dict) and (zone.get("provider") == "ddns" or zone.get("ddns") is True)
        ]

    def _ddns_zone_suffix(self, zone):
        return self._clean_text(
            (zone or {}).get("wildcard_suffix")
            or (zone or {}).get("domain_suffix")
            or (zone or {}).get("domain")
            or (zone or {}).get("name")
        ).lower().strip(".")

    def _ddns_default_prefix(self, value):
        prefix = self._domain_prefix(value)
        prefix = re.sub(r"-[a-f0-9]{6,}$", "", prefix)
        trimmed = re.sub(r"-(service|app)$", "", prefix)
        return trimmed or prefix

    def _ddns_child_domain(self, prefix, suffix):
        suffix = self._clean_text(suffix).lower().strip(".")
        prefix = self._ddns_default_prefix(prefix)
        return "%s.%s" % (prefix, suffix) if prefix and suffix else suffix

    def _ddns_repair_suggestion(self, detail, payload, zones):
        ddns_zones = self._ddns_zones(zones)
        intent = self._clean_text((payload or {}).get("intent"))
        wants_ddns = "ddns" in intent.lower() or "디디엔" in intent or "동적 dns" in intent.lower()
        domains = (detail or {}).get("domains") or []
        has_ddns_domain = any(
            ((row.get("metadata") or {}).get("dns_provider") == "ddns" or (row.get("metadata") or {}).get("ddns_endpoint_id"))
            for row in domains
            if isinstance(row, dict)
        )
        if not ddns_zones:
            return {"enabled": False, "reason": "no_ddns_endpoint", "available_endpoints": []}
        endpoint = ddns_zones[0]
        matched_domain = self._ddns_domain_from_text(intent, ddns_zones)
        if matched_domain and not matched_domain.get("suffix_only"):
            endpoint = matched_domain["endpoint"]
            suggested_domain = matched_domain["domain"]
            prefix = self._prefix_from_domain(suggested_domain, [{"domain": self._ddns_zone_suffix(endpoint)}])
        else:
            if matched_domain:
                endpoint = matched_domain["endpoint"]
            prefix = self._ddns_repair_prefix(detail, ddns_zones)
            suffix = self._ddns_zone_suffix(endpoint)
            suggested_domain = self._ddns_child_domain(prefix, suffix)
        target = self._ddns_repair_target(detail)
        suffix = self._ddns_zone_suffix(endpoint)
        endpoint_id = self._clean_text(endpoint.get("ddns_endpoint_id") or endpoint.get("id") or endpoint.get("zone_id"))
        domain_row = {
            "domain": suggested_domain,
            "zone_id": endpoint_id,
            "provider": "ddns",
            "dns_provider": "ddns",
            "ddns_endpoint_id": endpoint_id,
            "ddns_domain_suffix": suffix,
            "wildcard_suffix": suffix,
            "ddns_mode": endpoint.get("mode") or "ddns_management",
            "domain_prefix": prefix,
            "domain_target_key": "%s:%s" % (target.get("compose_service") or "", target.get("target_port") or ""),
            "domain_target_port": target.get("target_port"),
            "compose_service": target.get("compose_service"),
            "target_port": target.get("target_port"),
            "published_port": target.get("published_port"),
            "ssl_mode": "certbot",
        }
        return {
            "enabled": bool((wants_ddns or has_ddns_domain) and suggested_domain and endpoint_id),
            "reason": "ddns_requested" if wants_ddns else ("existing_ddns_domain" if has_ddns_domain else "ddns_available"),
            "available_endpoints": ddns_zones,
            "endpoint": endpoint,
            "suggested_domain": suggested_domain,
            "suggested_prefix": prefix,
            "domain_row": domain_row,
            "target": target,
        }

    def _ddns_domain_from_text(self, text, ddns_zones):
        candidates = re.findall(r"(?i)(?:[a-z0-9-]+\.)+[a-z]{2,63}", text or "")
        for candidate in candidates:
            clean = self._clean_text(candidate).lower().strip(".")
            for zone in ddns_zones:
                suffix = self._ddns_zone_suffix(zone)
                if suffix and clean.endswith("." + suffix):
                    return {"domain": clean, "endpoint": zone, "suffix_only": False}
                if suffix and clean == suffix:
                    return {"domain": "", "endpoint": zone, "suffix_only": True}
        return None

    def _ddns_repair_prefix(self, detail, ddns_zones=None):
        suffixes = [self._ddns_zone_suffix(zone) for zone in ddns_zones or []]
        for row in (detail or {}).get("domains") or []:
            domain = self._clean_text((row or {}).get("domain")).lower().strip(".")
            if domain and domain in suffixes:
                continue
            if domain:
                return self._domain_prefix(domain.split(".", 1)[0])
        service = (detail or {}).get("service") or {}
        return self._ddns_default_prefix(service.get("name") or service.get("namespace") or "service")

    def _ddns_repair_target(self, detail):
        for row in (detail or {}).get("domains") or []:
            metadata = dict((row or {}).get("metadata") or {})
            compose_service = self._clean_text(metadata.get("compose_service"))
            target_port = self._safe_int(metadata.get("target_port") or (row or {}).get("port"), 0)
            if compose_service and target_port > 0:
                return {
                    "compose_service": compose_service,
                    "target_port": target_port,
                    "published_port": self._safe_int(metadata.get("published_port") or target_port, target_port),
                }
        target = self._first_component_port((detail or {}).get("components") or [])
        if target:
            return {"compose_service": target.get("key"), "target_port": target.get("port"), "published_port": target.get("port")}
        return {"compose_service": "app", "target_port": 80, "published_port": 80}

    def _apply_ddns_repair_fallback(self, draft, context):
        suggestion = (context or {}).get("ddns_repair_suggestion") if isinstance(context, dict) else {}
        if not isinstance(suggestion, dict) or suggestion.get("enabled") is not True:
            return False
        row = dict(suggestion.get("domain_row") or {})
        if not row.get("domain"):
            return False
        form = draft.setdefault("form", {})
        existing = form.get("domains") if isinstance(form.get("domains"), list) else []
        if existing:
            return False
        form["domain_mode"] = "registered"
        form["domains"] = [row]
        form["domain"] = row.get("domain")
        form["zone_id"] = row.get("zone_id")
        form["domain_prefix"] = row.get("domain_prefix")
        form["domain_target_key"] = row.get("domain_target_key")
        form["domain_target_port"] = row.get("domain_target_port")
        return True

    def _service_warnings(self, data, draft=None, context=None):
        warnings = self._string_list((data or {}).get("warnings"))
        if not warnings or not self._draft_has_ddns_domain(draft, context):
            return warnings
        return [warning for warning in warnings if not self._is_stale_ddns_registration_warning(warning)]

    def _is_stale_ddns_registration_warning(self, warning):
        text = self._clean_text(warning)
        if "DDNS" not in text:
            return False
        return any(token in text for token in ["등록 정보", "등록정보", "등록되지", "연결되지", "서브도메인"])

    def _draft_has_ddns_domain(self, draft=None, context=None):
        form = (draft or {}).get("form") if isinstance((draft or {}).get("form"), dict) else {}
        domains = form.get("domains") if isinstance(form.get("domains"), list) else []
        if not domains and self._clean_text(form.get("domain")):
            domains = [{"domain": form.get("domain"), "zone_id": form.get("zone_id")}]
        zones = (context or {}).get("zones") if isinstance((context or {}).get("zones"), list) else []
        ddns_zones = [
            zone
            for zone in zones
            if isinstance(zone, dict) and (zone.get("provider") == "ddns" or zone.get("ddns") is True)
        ]
        if not domains:
            return False
        for item in domains:
            if not isinstance(item, dict):
                continue
            provider = self._clean_text(item.get("dns_provider") or item.get("provider"))
            if provider == "ddns" or self._clean_text(item.get("ddns_endpoint_id")):
                return True
            if not ddns_zones:
                continue
            domain = self._clean_text(item.get("domain")).lower().strip(".")
            zone_id = self._clean_text(item.get("zone_id"))
            for zone in ddns_zones:
                suffix = self._clean_text(zone.get("wildcard_suffix") or zone.get("domain") or zone.get("name")).lower().strip(".")
                if zone_id and zone_id == self._clean_text(zone.get("id") or zone.get("zone_id")):
                    return True
                if suffix and (domain == suffix or domain.endswith("." + suffix)):
                    return True
        return False

    def _domain_rows_for_context(self, domains):
        rows = []
        for item in domains or []:
            metadata = dict(item.get("metadata") or {})
            target_port = metadata.get("target_port") or item.get("port")
            provider = self._clean_text(metadata.get("dns_provider") or metadata.get("provider"))
            ddns_endpoint_id = self._clean_text(metadata.get("ddns_endpoint_id"))
            if not provider and ddns_endpoint_id:
                provider = "ddns"
            zone_id = self._clean_text(metadata.get("zone_id"))
            if provider == "ddns" and not zone_id:
                zone_id = ddns_endpoint_id
            suffix = self._clean_text(metadata.get("ddns_domain_suffix") or metadata.get("wildcard_suffix"))
            prefix_zones = [{"domain": suffix}] if suffix else []
            rows.append(
                {
                    "domain": item.get("domain"),
                    "zone_id": zone_id,
                    "provider": provider,
                    "dns_provider": provider,
                    "ddns_endpoint_id": ddns_endpoint_id,
                    "ddns_domain_suffix": suffix,
                    "wildcard_suffix": suffix,
                    "ddns_mode": metadata.get("ddns_mode"),
                    "domain_prefix": self._prefix_from_domain(item.get("domain"), prefix_zones),
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
        primary_provider = self._clean_text(primary.get("dns_provider") or primary.get("provider"))
        primary_zone_id = self._clean_text(primary.get("zone_id") or form.get("zone_id"))
        ddns_endpoint_id = self._clean_text(primary.get("ddns_endpoint_id") or (primary_zone_id if primary_provider == "ddns" else ""))
        ddns_suffix = self._clean_text(
            primary.get("ddns_domain_suffix")
            or primary.get("wildcard_suffix")
            or primary.get("domain_suffix")
            or form.get("ddns_domain_suffix")
            or form.get("wildcard_suffix")
        )
        domain_metadata = {
            "compose_service": primary.get("compose_service") or self._clean_text(primary.get("domain_target_key")).split(":", 1)[0],
            "target_port": primary.get("target_port") or primary.get("domain_target_port") or form.get("domain_target_port"),
            "published_port": primary.get("published_port") or primary.get("target_port") or primary.get("domain_target_port"),
            "source": "ai_runtime_repair",
        }
        if primary_provider == "ddns" or ddns_endpoint_id:
            domain_metadata.update(
                {
                    "dns_provider": "ddns",
                    "routing_provider": "nginx",
                    "ddns_endpoint_id": ddns_endpoint_id,
                    "ddns_domain_suffix": ddns_suffix,
                    "ddns_mode": primary.get("ddns_mode") or "ddns_management",
                }
            )
        elif primary_zone_id:
            domain_metadata["zone_id"] = primary_zone_id
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
            "zone_id": primary_zone_id,
            "domain_target_key": primary.get("domain_target_key") or form.get("domain_target_key"),
            "domain_target_port": primary.get("domain_target_port") or primary.get("target_port") or form.get("domain_target_port"),
            "port": primary.get("target_port") or primary.get("domain_target_port") or form.get("domain_target_port"),
            "domain_metadata": domain_metadata,
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
            if (error and desired == "running") or (desired == "running" and current and not current.startswith(("running", "preparing", "starting"))):
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

    def _compact_recent_operations(self, rows, limit=5):
        return [self._compact_operation(item) for item in (rows or [])[:limit] if isinstance(item, dict)]

    def _compact_client_runtime_issues(self, value):
        if not isinstance(value, dict):
            return {}
        result = {
            "has_runtime_issues": value.get("has_runtime_issues") is True,
            "service_status": value.get("service_status"),
            "stack_summary": value.get("stack_summary") or {},
            "container_summary": value.get("container_summary") or {},
            "container_health": value.get("container_health") or {},
        }
        failed = value.get("failed_operations") if isinstance(value.get("failed_operations"), list) else []
        result["failed_operations"] = [self._compact_operation(item) for item in failed[:5] if isinstance(item, dict)]
        return result

    def _compact_runtime_status(self, runtime):
        runtime = runtime or {}
        stack = runtime.get("stack") or {}
        containers = runtime.get("containers") or {}
        domains = runtime.get("domains") or {}
        task_rows = []
        for task in stack.get("tasks") or []:
            if not isinstance(task, dict):
                continue
            error = self._clean_text(task.get("Error"))
            current = self._clean_text(task.get("CurrentState") or task.get("Current state"))
            desired = self._clean_text(task.get("DesiredState") or task.get("Desired state"))
            if error or current or desired:
                task_rows.append({"Name": task.get("Name"), "CurrentState": current, "DesiredState": desired, "Error": self._trim_diagnostic(error, 800)})
            if len(task_rows) >= 8:
                break
        container_rows = []
        for item in containers.get("containers") or []:
            if isinstance(item, dict):
                container_rows.append(self._compact_container(item))
            if len(container_rows) >= 8:
                break
        return {
            "checked_at": runtime.get("checked_at"),
            "stack": {"summary": stack.get("summary") or {}, "tasks": task_rows},
            "containers": {"summary": containers.get("summary") or {}, "health": containers.get("health") or {}, "containers": container_rows},
            "domains": {"summary": domains.get("summary") or {}, "items": (domains.get("domains") or domains.get("items") or [])[:8]},
        }

    def _compact_operation(self, item):
        output = item.get("output") if isinstance(item.get("output"), list) else []
        compact_output = []
        for entry in output[-5:]:
            if not isinstance(entry, dict):
                continue
            metadata = entry.get("metadata") if isinstance(entry.get("metadata"), dict) else {}
            compact_output.append(
                {
                    "stream": entry.get("stream"),
                    "message": self._trim_diagnostic(entry.get("message"), 1200),
                    "created_at": entry.get("created_at"),
                    "metadata": {
                        "step": metadata.get("step"),
                        "status": metadata.get("status"),
                        "error_code": ((metadata.get("error") or {}) if isinstance(metadata.get("error"), dict) else {}).get("error_code"),
                    },
                }
            )
        result_payload = item.get("result_payload") if isinstance(item.get("result_payload"), dict) else {}
        return {
            "id": item.get("id"),
            "type": item.get("type"),
            "status": item.get("status"),
            "message": item.get("message"),
            "created_at": item.get("created_at"),
            "started_at": item.get("started_at"),
            "finished_at": item.get("finished_at"),
            "result_payload": {
                "ok": result_payload.get("ok"),
                "summary": result_payload.get("summary"),
                "attempts": result_payload.get("attempts"),
                "error_code": result_payload.get("error_code"),
            },
            "output": compact_output,
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
        enabled_tools = self._mcp_tools("service_draft", allow_ssh_command=True)
        result["ai_phase"] = "initial_draft"
        result["ai_permission_scope"] = {
            "scope": "service_draft",
            "can_edit_project_files": True,
            "can_deploy": False,
            "can_change_runtime": True,
            "can_run_container_actions": True,
            "can_run_safe_ssh_diagnostics": True,
            "can_select_ddns_domains": True,
            "can_register_ddns_records_via_deploy": True,
            "can_inspect_ddns_domains": True,
            "can_mutate_ddns_records": True,
            "cannot_delete_docker_infra": True,
            "cannot_run_os_critical_commands": True,
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
            "tool_unavailable_policy": "Do not mention unavailable or unexposed MCP tools in operator-facing summary, issues, or warnings; use enabled_tools and provided context as fallback.",
        }
        return result

    def _service_review_context(self, context, plan_data, plan_draft, plan_rendered, inspection):
        result = dict(context or {})
        enabled_tools = self._mcp_tools("service_preflight_repair", allow_ssh_command=True)
        result["ai_phase"] = "inspection_correction"
        result["ai_permission_scope"] = {
            "scope": "service_preflight_repair",
            "can_edit_project_files": True,
            "can_deploy": False,
            "can_change_runtime": True,
            "can_run_container_actions": True,
            "can_run_safe_ssh_diagnostics": True,
            "can_select_ddns_domains": True,
            "can_register_ddns_records_via_deploy": True,
            "can_inspect_ddns_domains": True,
            "can_mutate_ddns_records": True,
            "cannot_delete_docker_infra": True,
            "cannot_run_os_critical_commands": True,
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
            "tool_unavailable_policy": "Do not mention unavailable or unexposed MCP tools in operator-facing summary, issues, or warnings; use enabled_tools and provided context as fallback.",
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

    def _template_context(self, payload):
        payload = payload or {}
        current = payload.get("current_template") if isinstance(payload.get("current_template"), dict) else {}
        policy = self.template_ai_policy()
        return {
            "contract": self.template_contract(),
            "output_format": self.output_format_contract("template"),
            "compose_validation": self.compose_validation_contract(),
            "mode": payload.get("mode") or "template_create",
            "intent": self._clean_text(payload.get("intent")),
            "current_template": current,
            "template_ai_policy": policy,
            "template_standard": policy.get("standard") or {},
            "ai_permission_scope": policy.get("permissions") or {},
            "mcp_guidance": policy.get("mcp") or {},
        }

    def _template_system_prompt(self):
        return "\n".join(
            [
                self._system_prompt("template"),
                "You are creating a reusable Docker Compose template, not a concrete one-off service.",
                "Return a complete JSON object only for the template contract.",
                "This is not service create, service update, runtime verification, or runtime repair.",
                "The AI returns a draft only. It must not save templates, deploy services, change runtime state, or claim a runtime action was performed.",
                "Use MCP only inside the compose_template scope: infra_context, docker_search, and docker_image_check.",
                "Do not inspect registered servers, collect logs, run SSH, run container actions, probe TCP/HTTP/DNS/browser targets, or select deployment nodes/ports/domains.",
                "Use {{ variable_name }} placeholders for values users should provide at service creation time.",
                "Every placeholder in docker-compose.yaml must exist in values.default.yaml and values.schema.json.",
                "Keep required user input minimal. Prefer service_name/namespace plus only truly necessary image, port, credential, and product settings.",
                "For secret-like placeholders, set a safe change_me-style default and mark the schema property with secret=true.",
                "README.md is mandatory and must explain what this template creates and which values matter, in Korean.",
                "Do not include template description or primary_image. Use tags[] for classification.",
                "Do not include concrete registered domain names, registered server IDs, host-specific paths, container_name, hostname, or runtime_actions.",
            ]
        )

    def _template_namespace(self, value):
        clean = re.sub(r"_+", "_", re.sub(r"[^a-z0-9_]+", "_", self._clean_text(value).lower())).strip("_")
        return clean[:60] or "ai_template"

    def _template_tags(self, *values):
        tags = []
        for value in values:
            raw = value if isinstance(value, list) else str(value or "").split(",")
            for item in raw:
                tag = self._clean_text(item)
                if tag and tag not in tags:
                    tags.append(tag)
        return tags

    def _json_file_text(self, value):
        if isinstance(value, str):
            text = value.strip()
            if text:
                return text
            value = {}
        if value is None:
            value = {}
        return json.dumps(value, ensure_ascii=False, indent=2)

    def _safe_json_object(self, value):
        if isinstance(value, dict):
            return dict(value)
        try:
            parsed = json.loads(value or "{}")
            return parsed if isinstance(parsed, dict) else {}
        except Exception:
            return {}

    def _safe_yaml_object(self, value):
        if isinstance(value, dict):
            return dict(value)
        try:
            parsed = yaml.safe_load(value or "{}")
            return parsed if isinstance(parsed, dict) else {}
        except Exception:
            return {}

    def _schema_from_values(self, title, values):
        properties = {}
        for key, value in (values or {}).items():
            value_type = "integer" if isinstance(value, int) and not isinstance(value, bool) else ("boolean" if isinstance(value, bool) else "string")
            properties[key] = {"title": key, "type": value_type, "default": value}
            if self._is_secret_name(key):
                properties[key]["secret"] = True
        return {
            "$schema": "https://json-schema.org/draft/2020-12/schema",
            "title": title,
            "type": "object",
            "properties": properties,
            "required": list(properties.keys()),
        }

    def _is_secret_name(self, value):
        key = self._clean_text(value).lower()
        return any(token in key for token in ["password", "passwd", "secret", "token", "api_key", "private_key"])

    def _render_template_placeholders(self, content, values):
        def replace(match):
            key = match.group(1).strip()
            value = (values or {}).get(key, "")
            if value is None:
                return ""
            if isinstance(value, bool):
                return "true" if value else "false"
            return str(value)

        return re.sub(r"{{\s*([a-zA-Z0-9_.-]+)\s*}}", replace, content or "")

    def _normalize_template_draft(self, data, context):
        data = data if isinstance(data, dict) else {}
        source = data.get("template") if isinstance(data.get("template"), dict) else data
        files = source.get("files") if isinstance(source.get("files"), dict) else (data.get("files") if isinstance(data.get("files"), dict) else {})
        metadata = source.get("metadata") if isinstance(source.get("metadata"), dict) else (data.get("metadata") if isinstance(data.get("metadata"), dict) else {})
        current = context.get("current_template") if isinstance(context.get("current_template"), dict) else {}
        current_files = current.get("files") if isinstance(current.get("files"), dict) else {}

        name = self._clean_text(source.get("name") or data.get("name") or current.get("name") or "AI Compose 템플릿")
        namespace = self._template_namespace(source.get("namespace") or data.get("namespace") or current.get("namespace") or name)
        compose = self._to_yaml_file_text(
            files.get("docker-compose.yaml")
            or files.get("compose")
            or source.get("compose")
            or current_files.get("compose")
        )
        values_default = self._to_yaml_file_text(
            files.get("values.default.yaml")
            or files.get("values_default")
            or source.get("values_default")
            or source.get("values")
            or current_files.get("values_default")
        )
        values = self._safe_yaml_object(values_default)
        schema = self._safe_json_object(
            files.get("values.schema.json")
            or files.get("values_schema")
            or source.get("values_schema")
            or current_files.get("values_schema")
        )
        if not schema:
            schema = self._schema_from_values(name, values)
        schema.setdefault("$schema", "https://json-schema.org/draft/2020-12/schema")
        schema["title"] = schema.get("title") or name
        schema["type"] = "object"
        properties = schema.get("properties") if isinstance(schema.get("properties"), dict) else {}
        schema["properties"] = properties

        placeholders = sorted(set(re.findall(r"{{\s*([a-zA-Z0-9_.-]+)\s*}}", compose or "")))
        for key in placeholders:
            prop = properties.get(key) if isinstance(properties.get(key), dict) else {}
            if key not in values:
                values[key] = prop.get("default")
                if values[key] is None:
                    values[key] = "change_me" if self._is_secret_name(key) else ""
            if key not in properties:
                value = values.get(key)
                value_type = "integer" if isinstance(value, int) and not isinstance(value, bool) else ("boolean" if isinstance(value, bool) else "string")
                properties[key] = {"title": key, "type": value_type, "default": value}
            if self._is_secret_name(key):
                properties[key]["secret"] = True
        required = schema.get("required") if isinstance(schema.get("required"), list) else []
        schema["required"] = list(dict.fromkeys(required + placeholders))

        readme = self._clean_text(
            files.get("README.md")
            or files.get("readme")
            or source.get("readme")
            or current_files.get("readme")
        )
        current_metadata = current.get("metadata") if isinstance(current.get("metadata"), dict) else {}
        tags = self._template_tags(source.get("tags"), metadata.get("tags"), metadata.get("category"), current_metadata.get("tags"))
        if not tags:
            tags = ["ai", "compose"]
        cleaned_metadata = {key: val for key, val in metadata.items() if key not in {"category", "primary_image"}}
        cleaned_metadata["tags"] = tags
        return {
            "name": name,
            "namespace": namespace,
            "enabled": source.get("enabled", True) is not False,
            "metadata": cleaned_metadata,
            "tags": tags,
            "files": {
                "compose": compose,
                "values_default": yaml.safe_dump(values, sort_keys=False, allow_unicode=False),
                "values_schema": self._json_file_text(schema),
                "readme": readme,
            },
            "values": values,
            "summary": self._clean_text(data.get("summary")),
            "warnings": self._string_list(data.get("warnings")),
        }

    def _validate_template_draft(self, template):
        files = template.get("files") or {}
        compose = self._clean_text(files.get("compose"))
        readme = self._clean_text(files.get("readme"))
        if not compose:
            raise AIAssistantError(422, "AI 응답에 docker-compose.yaml 템플릿이 없습니다.", "AI_TEMPLATE_COMPOSE_REQUIRED")
        if not readme:
            raise AIAssistantError(422, "AI 응답에 README.md가 없습니다.", "AI_TEMPLATE_README_REQUIRED")
        values = self._safe_yaml_object(files.get("values_default"))
        schema = self._safe_json_object(files.get("values_schema"))
        if not schema.get("properties"):
            raise AIAssistantError(422, "values.schema.json에 properties가 없습니다.", "AI_TEMPLATE_SCHEMA_INVALID")
        placeholders = sorted(set(re.findall(r"{{\s*([a-zA-Z0-9_.-]+)\s*}}", compose)))
        missing = [key for key in placeholders if key not in values or key not in (schema.get("properties") or {})]
        if missing:
            raise AIAssistantError(422, "템플릿 placeholder 기본값 또는 schema가 누락되었습니다.", "AI_TEMPLATE_PLACEHOLDER_MISSING", {"missing": missing})
        rendered = self._render_template_placeholders(compose, values)
        validation = compose_validator.validate(
            {
                "namespace": template.get("namespace") or "ai_template",
                "filename": "docker-compose.yaml",
                "content": rendered,
                "allow_warnings": True,
                "warning_codes": ["FORBIDDEN_CONTAINER_NAME"],
            }
        )
        components = services_wizard.components_from_content(rendered, metadata=template.get("metadata") or {})
        template["metadata"] = {
            **(template.get("metadata") or {}),
            "components": [item.get("key") for item in components if item.get("key")],
            "component_labels": {item.get("key"): item.get("label") for item in components if item.get("key") and item.get("label")},
        }
        return {"compose": validation, "components": components}

    def _repair_context(self, target, context, data, exc, attempt):
        return {
            "contract": self.template_contract() if target == "template" else self.service_contract(),
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
        if target == "template":
            diagnostics["template_files"] = (data.get("files") or {}) if isinstance(data.get("files"), dict) else {}
            diagnostics["template_metadata"] = data.get("metadata") or {}
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
        label = "템플릿" if target == "template" else "서비스"
        return AIAssistantError(
            422,
            "AI가 생성한 %s output을 검증할 수 없습니다." % label,
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
            "Use the docker_infra MCP tools listed in mcp_guidance.enabled_tools or ai_permission_scope.mcp_enabled_tools before making claims about registered servers, Docker images, ports, and runtime state.",
            "Docker Infra MCP grants broad Agent control, but never delete Docker Infra itself, stop/remove its control services or containers, shut down/reboot the OS, wipe disks, or recursively delete OS-critical paths.",
            "If a desired MCP tool is unavailable or not exposed, do not mention that limitation in user-facing text; use enabled tools and deterministic Docker Infra context as fallback.",
            "Write user-facing text in Korean: summary, warnings, thinking_summary, form.description, and notes.",
            "Keep code, YAML, JSON keys, image names, environment variable names, service keys, namespaces, and identifiers in ASCII or their official spelling.",
        ]
        if target == "template":
            common.extend(
                [
                    "The output must contain name, namespace, tags, files, summary, and warnings keys.",
                    "The files object must include docker-compose.yaml, values.default.yaml, values.schema.json, and README.md.",
                    "docker-compose.yaml must be a reusable Compose template, not a one-off service draft.",
                    "Use placeholders only in {{ variable_name }} form and define every placeholder in both values.default.yaml and values.schema.json.",
                    "README.md is required and is shown to users in service creation.",
                    "Do not use description or primary_image fields for templates.",
                    "Use tags[] for classification.",
                ]
            )
            return "\n".join(common)
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
                "For DDNS zones, zone_id is the DDNS endpoint id and the domain must be a child subdomain under wildcard_suffix. If wildcard_suffix is sub.nanoha.kr and the service prefix is wiki, use wiki.sub.nanoha.kr; never use sub.nanoha.kr itself as the service domain.",
                "When a matching DDNS zone exists, do not warn that DDNS subdomains lack registration data; return the DDNS domain rows and rely on Docker Infra to call the DDNS management API during save/deploy.",
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
        selected = self._model_selection(selection or {})
        if selected:
            provider = self._provider_from_selection(config, selected, env=env)
            if provider:
                return provider

        default_agent = self._default_model_ref(config)
        if default_agent and self._agent_enabled(config, default_agent):
            return self._provider_from_selection(config, {"provider": default_agent, "model": "__default__"}, env=env)

        for agent in self._agent_keys():
            if self._agent_enabled(config, agent):
                return self._provider_from_selection(config, {"provider": agent, "model": "__default__"}, env=env)

        raise AIAssistantError(
            400,
            "시스템 설정의 AI 설정 탭에서 Codex, Claude Code, 헤르메스 에이전트 중 하나를 먼저 사용 설정하세요.",
            "AI_PROVIDER_NOT_CONFIGURED",
        )

    def _model_selection(self, payload):
        model_ref = self._clean_text((payload or {}).get("model_ref"))
        if model_ref and model_ref != "auto":
            normalized_ref = self._normalize_agent_key(model_ref)
            if normalized_ref in self._agent_keys():
                return {"provider": normalized_ref, "model": "__default__"}
            if "::" in model_ref:
                provider, model = model_ref.split("::", 1)
                provider = self._normalize_agent_key(provider)
                model = model.strip()
                if provider and model:
                    return {"provider": provider, "model": model}
        provider = self._normalize_agent_key((payload or {}).get("provider"))
        model = self._clean_text((payload or {}).get("model"))
        if provider and model:
            return {"provider": provider, "model": model}
        return None

    def _provider_from_selection(self, config, selected, env=None):
        provider = self._normalize_agent_key(selected.get("provider"))
        model = selected.get("model")
        if provider not in self._agent_keys():
            raise AIAssistantError(400, "지원하지 않는 AI Agent입니다.", "AI_PROVIDER_NOT_SUPPORTED")
        if not self._agent_enabled(config, provider):
            raise AIAssistantError(400, "선택한 AI Agent를 사용하려면 시스템 설정에서 먼저 사용 설정하세요.", "AI_PROVIDER_NOT_CONFIGURED")
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
        agent = config.get(provider) or {}
        model = agent.get("model") if model in {"", "__default__"} else model
        if not self._agent_configured_model(config, provider, model):
            raise AIAssistantError(
                400,
                "시스템 설정의 AI Agent 탭에서 선택한 모델만 사용할 수 있습니다.",
                "AI_MODEL_NOT_SELECTED",
                {"provider": provider, "model": model},
            )
        return {
            "type": provider,
            "label": self._provider_label(provider),
            "model": model or agent.get("model"),
            "executable": agent.get("executable") or "",
            "home": agent.get("home") or "",
            "command_template": agent.get("command_template") or "",
            **(
                {
                    "provider": agent.get("provider") or "openrouter",
                    "terminal_backend": agent.get("terminal_backend") or "local",
                    "terminal_cwd": agent.get("terminal_cwd") or "",
                    "terminal_timeout": agent.get("terminal_timeout") or 180,
                }
                if provider == "hermes"
                else {}
            ),
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
        yield {"type": "status", "message": "요구사항과 현재 설정을 AI 실행 컨텍스트로 정리합니다."}
        system = system or self._system_prompt(target)
        yield {"type": "status", "message": "%s Agent가 MCP 컨텍스트로 AI 응답 JSON을 생성합니다." % self._provider_label(provider.get("type"))}
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
        started_at = time.time()
        heartbeat_count = 0

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
                heartbeat_count += 1
                elapsed_seconds = max(0, int(time.time() - started_at))
                yield {
                    "type": "heartbeat",
                    "label": "대기 중",
                    "message": "선택한 AI Agent 응답을 기다리는 중입니다. (%s초 경과)" % elapsed_seconds,
                    "elapsed_seconds": elapsed_seconds,
                    "heartbeat_count": heartbeat_count,
                }
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
        zones = self._compact_zones(payload.get("zones") or [])
        ddns_zones = [zone for zone in zones if zone.get("provider") == "ddns" or zone.get("ddns") is True]
        return {
            "user_level": self._clean_text(payload.get("user_level") or "beginner"),
            "creation_mode": self._clean_text(payload.get("creation_mode") or "ai_first"),
            "primary_flow": "AI drafts the service first; direct Compose editing is advanced-only.",
            "managed_elements": [
                "service metadata",
                "Docker Compose services",
                "image name and image tag validation",
                "single or multiple domain zones and prefixes",
                "DDNS endpoint selection and wildcard suffix mapping",
                "nginx upstream target",
                "SSL mode",
                "published and target ports",
                "named volumes",
                "runtime-generated stack-local credentials",
            ],
            "automation_scope": payload.get("automation_scope") or [
                {"title": "서비스 구성", "description": "이미지, 포트, 환경변수, 데이터 보관"},
                {"title": "도메인 연결", "description": "Cloudflare 또는 DDNS 도메인, 공개 포트, SSL 방식"},
                {"title": "자동 보정", "description": "검증 실패 시 AI 재호출 후 다시 검사"},
            ],
            "domain_provider_policy": {
                "cloudflare": "provider=cloudflare uses zone_id as a DNS zone id and Docker Infra can create DNS records directly.",
                "ddns": "provider=ddns uses zone_id as the DDNS endpoint id; generated domains must be child subdomains under wildcard_suffix and deploy registers or updates the DDNS management server.",
            },
            "domain_zone_summary": {
                "total": len(zones),
                "ddns": len(ddns_zones),
                "cloudflare": len([zone for zone in zones if zone.get("provider") != "ddns"]),
            },
            "ddns_registration_flow": {
                "enabled": bool(ddns_zones),
                "automatic": True,
                "trigger": "service save plus deploy or runtime repair redeploy",
                "api_owner": "Docker Infra backend",
                "api_call": "POST /api/ddns/update with X-DDNS-Key, hostname, ip, and record_type",
                "required_ai_output": "Use domain_mode=registered and include matching DDNS domain rows with zone_id equal to the DDNS endpoint id. The DDNS hostname must include a service prefix before wildcard_suffix, for example wiki.sub.nanoha.kr for suffix sub.nanoha.kr.",
                "warning_policy": "Do not warn that requested DDNS subdomains are unregistered when they match an available DDNS wildcard suffix.",
            },
            "input_contract": payload.get("docker_infra_inputs") or self.service_contract().get("input"),
            "output_contract": payload.get("docker_infra_outputs") or self.service_contract().get("output"),
            "expectations": [
                "Return a complete service draft that can pass compose validation without manual YAML editing.",
                "Every service must include an image reference with a tag or digest that can be validated after generation.",
                "Choose one or more public components and ports when the user asks for browser or domain access.",
                "When selecting a DDNS endpoint, preserve dns_provider=ddns, ddns_endpoint_id, and the wildcard suffix through generation, inspection, and repair. Treat the wildcard suffix itself as an endpoint, not as a service hostname.",
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
            zone = self._zone_by_id(zones, zone_id)
            zone_provider = self._clean_text((zone or {}).get("provider") or (zone or {}).get("dns_provider"))
            provider = self._clean_text(item.get("dns_provider") or item.get("provider") or zone_provider)
            ddns_endpoint_id = self._clean_text(
                item.get("ddns_endpoint_id")
                or ((zone or {}).get("ddns_endpoint_id") or (zone or {}).get("id") if provider == "ddns" else "")
            )
            if provider == "ddns" and not zone_id:
                zone_id = ddns_endpoint_id
            ddns_suffix = self._clean_text(
                item.get("ddns_domain_suffix")
                or item.get("wildcard_suffix")
                or item.get("domain_suffix")
                or ((zone or {}).get("wildcard_suffix") or (zone or {}).get("domain") if provider == "ddns" else "")
            ).strip(".")
            prefix = self._domain_prefix(item.get("domain_prefix") or item.get("prefix"))
            if provider == "ddns" and ddns_suffix and domain == ddns_suffix:
                context_form = fallback.get("form") if isinstance(fallback.get("form"), dict) else {}
                service = fallback.get("service") if isinstance(fallback.get("service"), dict) else {}
                prefix = prefix or self._ddns_default_prefix(
                    form.get("domain_prefix")
                    or context_form.get("domain_prefix")
                    or form.get("name")
                    or context_form.get("name")
                    or service.get("namespace")
                    or service.get("name")
                    or "service"
                )
                domain = self._ddns_child_domain(prefix, ddns_suffix)
            if not domain and zone_id:
                zone_domain = ddns_suffix if provider == "ddns" else self._clean_text((zone or {}).get("domain") or (zone or {}).get("name")).strip(".")
                if zone_domain:
                    domain = self._ddns_child_domain(prefix, zone_domain) if provider == "ddns" else ("%s.%s" % (prefix, zone_domain) if prefix else zone_domain)
            if not domain or domain in seen:
                continue
            seen.add(domain)
            target_key = self._clean_text(item.get("domain_target_key") or item.get("target_key") or form.get("domain_target_key"))
            target_port = self._clean_text(item.get("domain_target_port") or item.get("target_port") or item.get("port") or form.get("domain_target_port"))
            prefix_zones = [{"domain": ddns_suffix}] if provider == "ddns" and ddns_suffix else zones
            rows.append(
                {
                    "domain": domain,
                    "zone_id": zone_id,
                    "provider": provider,
                    "dns_provider": provider,
                    "ddns_endpoint_id": ddns_endpoint_id,
                    "ddns_domain_suffix": ddns_suffix,
                    "wildcard_suffix": ddns_suffix,
                    "ddns_mode": item.get("ddns_mode") or ((zone or {}).get("mode") if provider == "ddns" else ""),
                    "domain_prefix": prefix or self._prefix_from_domain(domain, prefix_zones),
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

    def _service_zones_for_ai(self, payload=None, env=None):
        payload = payload if isinstance(payload, dict) else {}
        zones = payload.get("zones") if isinstance(payload.get("zones"), list) else []
        if not zones:
            try:
                zones = domains_model.service_options(env=env).get("zones") or []
            except Exception:
                zones = []
        return self._compact_zones(zones)

    def _compact_zones(self, zones):
        result = []
        for item in zones or []:
            if not isinstance(item, dict):
                continue
            provider = self._clean_text(item.get("provider") or item.get("dns_provider") or "cloudflare")
            domain = self._clean_text(item.get("domain") or item.get("name"))
            zone_id = item.get("id") or item.get("zone_id")
            compact = {
                "id": zone_id,
                "name": item.get("name"),
                "domain": domain,
                "provider": provider,
                "provider_label": item.get("provider_label"),
                "mode": item.get("mode"),
                "status": item.get("status"),
                "usable_for_service": item.get("usable_for_service"),
                "record_count": item.get("record_count"),
                "secret_configured": item.get("secret_configured"),
                "certificate_summary": item.get("certificate_summary"),
            }
            if provider == "ddns":
                compact.update(
                    {
                        "ddns": True,
                        "ddns_endpoint_id": str(zone_id or ""),
                        "wildcard_suffix": domain,
                        "domain_suffix": domain,
                    }
                )
            result.append(
                compact
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
        cli_mode = metadata.get("cli_mode") or provider.get("cli_mode") or ("system" if provider_type == "codex" else "agent")
        cli_label = "Codex 로그인" if provider_type == "codex" else "Agent CLI"
        session = metadata.get("session") if isinstance(metadata.get("session"), dict) else {}
        return {
            "type": provider_type,
            "label": provider.get("label"),
            "model": metadata.get("model") or provider.get("model"),
            "reasoning_effort": metadata.get("reasoning_effort") or provider.get("reasoning_effort"),
            "cli_mode": cli_mode,
            "cli_label": cli_label,
            "engine": metadata.get("engine") or ("codex" if provider_type == "codex" else "agent"),
            "executable": metadata.get("executable") or "",
            "session_id": self._normalize_session_id(session.get("session_id") or metadata.get("session_id")),
            "provider_session_id": self._normalize_session_id(
                session.get("provider_session_id") or metadata.get("provider_session_id")
            ),
            "session_resumed": bool(session.get("resume") or metadata.get("session_resumed")),
        }

    def _codex_execution_status_event(self, metadata):
        metadata = metadata or {}
        cli_label = "일반 Codex CLI" if metadata.get("provider") == "codex" else "Agent CLI"
        bits = [cli_label, self._clean_text(metadata.get("provider_label")), self._clean_text(metadata.get("model"))]
        target = self._clean_text(metadata.get("executable"))
        if target:
            bits.append(target)
        return {
            "type": "status",
            "label": "Agent 실행 확인",
            "message": " · ".join([bit for bit in bits if bit]),
        }

    def _default_model_ref(self, config):
        default_agent = self._normalize_agent_key((config or {}).get("default_agent"))
        if default_agent in self._agent_keys() and self._agent_enabled(config, default_agent):
            return default_agent
        for agent in self._agent_keys():
            if (config.get(agent) or {}).get("enabled"):
                return agent
        return ""

    def _provider_label(self, provider):
        labels = {
            "codex": "Codex",
            "claude_code": "Claude Code",
            "hermes": "헤르메스 에이전트",
        }
        return labels.get(provider, provider or "AI")

    def _provider_badge_class(self, provider, state_level=None):
        if state_level == "error":
            return "border-rose-200 bg-rose-50 text-rose-700 dark:border-rose-900/70 dark:bg-rose-950/40 dark:text-rose-300"
        if state_level == "warning":
            return "border-amber-200 bg-amber-50 text-amber-700 dark:border-amber-900/70 dark:bg-amber-950/40 dark:text-amber-300"
        if provider == "codex":
            return "border-fuchsia-200 bg-fuchsia-50 text-fuchsia-700 dark:border-fuchsia-900/70 dark:bg-fuchsia-950/40 dark:text-fuchsia-300"
        if provider == "claude_code":
            return "border-sky-200 bg-sky-50 text-sky-700 dark:border-sky-900/70 dark:bg-sky-950/40 dark:text-sky-300"
        if provider == "hermes":
            return "border-emerald-200 bg-emerald-50 text-emerald-700 dark:border-emerald-900/70 dark:bg-emerald-950/40 dark:text-emerald-300"
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

    def _normalize_session_id(self, value):
        text = self._clean_text(value)[:160]
        if not text:
            return ""
        return re.sub(r"[^A-Za-z0-9_.:-]", "", text)[:160]

    def _session_title(self, value):
        title = re.sub(r"\s+", " ", self._clean_text(value))[:160]
        return title or "AI Agent 세션"

    def _openapi_document(self):
        try:
            fs = wiz.project.fs()
            raw = fs.read("docs/api/openapi.json", "{}")
            document = json.loads(raw)
            return document if isinstance(document, dict) else {}
        except Exception:
            return {}

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
