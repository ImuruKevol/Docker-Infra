import re


SCREEN_META = {
    "access": {"route": "/access", "title": "Access", "entities": ["session", "setup"]},
    "dashboard": {"route": "/dashboard", "title": "Dashboard", "entities": ["overview", "service", "domain", "server"]},
    "services_create": {"route": "/services/create", "title": "Service Create", "entities": ["service", "compose_template"]},
    "services": {"route": "/services", "title": "Services", "entities": ["service", "container", "compose", "backup"]},
    "templates": {"route": "/templates", "title": "Compose Templates", "entities": ["compose_template"]},
    "domains": {"route": "/domains", "title": "Domains", "entities": ["domain", "certificate"]},
    "servers": {"route": "/servers", "title": "Servers", "entities": ["server", "node", "macro"]},
    "images": {"route": "/images", "title": "Images", "entities": ["image", "registry"]},
    "macros": {"route": "/macros", "title": "Macros", "entities": ["macro"]},
    "operations": {"route": "/operations", "title": "Operation Logs", "entities": ["operation"]},
    "system": {"route": "/system", "title": "System", "entities": ["setting", "backup", "agent"]},
    "ai_agent": {"route": "/", "title": "AI Agent", "entities": ["agent", "history"]},
    "file_tree": {"route": "", "title": "Files", "entities": ["file"]},
}

CURATED_TOOLS = {
    "services.load": {
        "name": "docker_infra.services.list",
        "description": "서비스 목록과 서비스 ID를 조회합니다.",
        "intent_phrases": ["서비스 목록", "서비스 찾아", "서비스 ID", "list services", "find service"],
        "input_schema": {"type": "object", "properties": {}},
        "result_alias": "services",
    },
    "services.delete": {
        "name": "docker_infra.services.delete",
        "description": "서비스를 삭제하고 연결된 stack/nginx/DNS/파일 정리를 수행합니다.",
        "intent_phrases": ["서비스 삭제", "서비스 제거", "delete service", "remove service"],
        "input_schema": {
            "type": "object",
            "properties": {
                "service_id": {"type": "string", "description": "서비스 UUID. 알 수 없으면 service_name을 사용합니다."},
                "service_name": {"type": "string", "description": "정확한 서비스 이름 또는 namespace."},
            },
        },
        "resolver": "service_name_to_service_id",
    },
    "services.deploy": {
        "name": "docker_infra.services.deploy",
        "description": "서비스를 백그라운드로 배포합니다.",
        "intent_phrases": ["서비스 배포", "재배포", "deploy service"],
        "input_schema": {"type": "object", "properties": {"service_id": {"type": "string"}, "service_name": {"type": "string"}}},
        "resolver": "service_name_to_service_id",
    },
    "services.refresh_status": {
        "name": "docker_infra.services.refresh_status",
        "description": "서비스 배포와 런타임 상태를 새로고침합니다.",
        "intent_phrases": ["서비스 상태", "배포 상태", "runtime status", "refresh service"],
        "input_schema": {"type": "object", "properties": {"service_id": {"type": "string"}, "service_name": {"type": "string"}}},
        "resolver": "service_name_to_service_id",
    },
    "services_create.prepare_template_draft": {
        "name": "docker_infra.services.create_from_template_draft",
        "description": "Compose 템플릿과 입력값으로 서비스 초안을 생성합니다.",
        "intent_phrases": ["템플릿으로 서비스", "compose template service"],
        "result_alias": "draft",
    },
    "services_create.create": {
        "name": "docker_infra.services.create",
        "description": "서비스 초안을 실제 서비스로 생성합니다.",
        "intent_phrases": ["서비스 생성", "create service"],
        "result_alias": "created_service",
    },
    "services_create.deploy_background": {
        "name": "docker_infra.services_create.deploy",
        "description": "생성 화면 컨텍스트에서 서비스를 백그라운드 배포합니다.",
        "intent_phrases": ["생성한 서비스 배포", "deploy created service"],
        "resolver": "service_name_to_service_id",
    },
    "templates.save": {
        "name": "docker_infra.templates.save",
        "description": "Compose 템플릿을 저장합니다.",
        "intent_phrases": ["템플릿 저장", "템플릿 생성", "save template"],
        "result_alias": "template_saved",
    },
    "templates.delete": {
        "name": "docker_infra.templates.delete",
        "description": "Compose 템플릿을 삭제합니다.",
        "intent_phrases": ["템플릿 삭제", "delete template"],
        "resolver": "template_name_to_template_id",
    },
}


def _clean(value):
    return re.sub(r"\s+", " ", str(value or "")).strip()


def _tool_name(operation_id, menu):
    clean = re.sub(r"[^a-z0-9_.]+", "_", str(operation_id or "").lower()).strip("_")
    if clean:
        return "docker_infra.%s" % clean
    return "docker_infra.%s.action" % (menu or "app")


def _input_schema(required):
    properties = {key: {"type": "string"} for key in (required or []) if key}
    return {"type": "object", "properties": properties, "required": list(properties.keys())}


class AIAgentActions:
    def catalog(self, operations, compact=False):
        operations = [item for item in (operations or []) if isinstance(item, dict)]
        tools_by_menu = {}
        for item in operations:
            tool = self._tool(item)
            tools_by_menu.setdefault(tool["screen"], []).append(tool)

        screens = []
        for menu in sorted(tools_by_menu.keys()):
            meta = SCREEN_META.get(menu, {})
            tools = sorted(tools_by_menu[menu], key=lambda item: item["name"])
            screens.append({
                "screen": menu,
                "route": meta.get("route", ""),
                "title": meta.get("title") or menu,
                "entities": meta.get("entities") or [],
                "tool_count": len(tools),
                "tools": tools[:12] if compact else tools,
            })
        return {
            "version": "docker-infra-mcp-actions.v1",
            "tool_naming": "docker_infra.<screen>.<action>",
            "resolver_rules": [
                "If a service operation needs service_id and the user gave only a service name, send service_name; the browser resolves the exact service_id before the API call.",
                "For chained api_request actions, use save_as and {{alias.path}} references.",
                "For destructive tools, execute only when the current user message explicitly names the target and destructive action.",
            ],
            "workflow_examples": [
                {
                    "intent": "서비스 이름으로 삭제",
                    "actions": [
                        {"type": "api_request", "operation_id": "services.delete", "body": {"service_name": "<exact service name>"}},
                    ],
                },
                {
                    "intent": "템플릿 생성 후 서비스 생성/배포",
                    "actions": [
                        {"operation_id": "templates.save", "save_as": "template_saved"},
                        {"operation_id": "services_create.prepare_template_draft", "save_as": "draft"},
                        {"operation_id": "services_create.create", "save_as": "created_service"},
                        {"operation_id": "services_create.deploy_background", "body": {"service_id": "{{created_service.result.service.id}}"}},
                    ],
                },
            ],
            "screens": screens,
        }

    def prompt_catalog(self, operations, message="", screen=None):
        catalog = self.catalog(operations, compact=True)
        matches = self.intent_matches(message, operations)
        catalog["intent_matches"] = matches[:8]
        return catalog

    def intent_matches(self, message, operations):
        text = _clean(message).lower()
        if not text:
            return []
        matches = []
        for item in operations or []:
            tool = self._tool(item)
            haystack = " ".join([tool.get("description", ""), " ".join(tool.get("intent_phrases") or []), tool.get("operation_id", "")]).lower()
            score = sum(1 for token in re.findall(r"[a-z0-9가-힣_]+", text) if len(token) >= 2 and token in haystack)
            if score > 0:
                matches.append({"tool": tool["name"], "operation_id": tool["operation_id"], "score": score, "safety": tool["safety"]})
        return sorted(matches, key=lambda item: item["score"], reverse=True)

    def _tool(self, item):
        operation_id = _clean(item.get("operation_id") or item.get("operationId"))
        menu = _clean(item.get("menu")) or operation_id.split(".", 1)[0]
        curated = CURATED_TOOLS.get(operation_id) or {}
        return {
            "name": curated.get("name") or _tool_name(operation_id, menu),
            "screen": menu,
            "operation_id": operation_id,
            "method": _clean(item.get("method") or "POST").upper(),
            "path": _clean(item.get("path")),
            "safety": _clean(item.get("safety") or "read"),
            "description": curated.get("description") or _clean(item.get("summary")) or operation_id,
            "required": item.get("required") or [],
            "input_schema": curated.get("input_schema") or _input_schema(item.get("required") or []),
            "intent_phrases": curated.get("intent_phrases") or [],
            "resolver": curated.get("resolver", ""),
            "result_alias": curated.get("result_alias", ""),
        }


Model = AIAgentActions()
