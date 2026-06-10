import ast
import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
WIZ_ROOT = ROOT.parents[1]


def is_wiz_response_call(node):
    if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Attribute):
        return False
    value = node.func.value
    return (
        isinstance(value, ast.Attribute)
        and value.attr == "response"
        and isinstance(value.value, ast.Name)
        and value.value.id == "wiz"
    )


class WizStructureContractTest(unittest.TestCase):
    def test_model_files_declare_model_and_stay_small(self):
        for path in sorted((ROOT / "src" / "model").rglob("*.py")):
            with self.subTest(path=path.relative_to(ROOT)):
                text = path.read_text(encoding="utf-8")
                self.assertLessEqual(len(text.splitlines()), 300)
                tree = ast.parse(text, filename=str(path))
                self.assertTrue(
                    any(isinstance(node, ast.Assign) and any(getattr(target, "id", None) == "Model" for target in node.targets) for node in tree.body),
                    "WIZ model files must expose Model",
                )

    def test_wiz_response_is_not_called_inside_try_except_blocks(self):
        scan_roots = [ROOT / "src" / "app", ROOT / "src" / "route", ROOT / "src" / "controller"]
        failures = []
        for scan_root in scan_roots:
            for path in sorted(scan_root.rglob("*.py")):
                if "src/portal/" in path.as_posix():
                    continue
                tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
                for try_node in [node for node in ast.walk(tree) if isinstance(node, ast.Try)]:
                    blocks = [try_node.body, try_node.orelse, try_node.finalbody]
                    blocks.extend(handler.body for handler in try_node.handlers)
                    for block in blocks:
                        for child in block:
                            for nested in ast.walk(child):
                                if is_wiz_response_call(nested):
                                    failures.append(f"{path.relative_to(ROOT)}:{nested.lineno}")
        self.assertEqual(failures, [])

    def test_boot_base_user_and_route_controller_boundaries(self):
        boot = (WIZ_ROOT / "config" / "boot.py").read_text(encoding="utf-8")
        base = (ROOT / "src" / "controller" / "base.py").read_text(encoding="utf-8")
        user = (ROOT / "src" / "controller" / "user.py").read_text(encoding="utf-8")

        for token in ["def bootstrap(app, config):", "def before_request(wiz):", "def after_request(wiz, response):", "SESSION_COOKIE_NAME"]:
            self.assertIn(token, boot)
        self.assertNotIn("SESSION_COOKIE", base)
        self.assertNotIn("enforce_access", base)
        self.assertIn("AUTHENTICATION_REQUIRED", user)

        protected_routes = [
            "api-compose-validate",
            "api-nodes",
            "api-nodes-path",
            "api-system-local-command-check",
            "api-system-local-master-ensure",
            "api-system-settings",
        ]
        for route in protected_routes:
            app_json = ROOT / "src" / "route" / route / "app.json"
            with self.subTest(route=route):
                self.assertEqual(json.loads(app_json.read_text(encoding="utf-8"))["controller"], "user")

    def test_runtime_config_owns_database_and_daemon_env_loading(self):
        runtime_config = ROOT / "config" / "docker_infra.py"
        self.assertTrue(runtime_config.is_file())
        config_text = runtime_config.read_text(encoding="utf-8")
        self.assertIn("config.env", config_text)
        self.assertIn("def database_url(env=None):", config_text)

        model_paths = [
            ROOT / "src" / "model" / "db" / "postgres.py",
            ROOT / "src" / "model" / "struct" / "settings.py",
            ROOT / "src" / "model" / "struct" / "local_executor.py",
            ROOT / "src" / "model" / "struct" / "setup_environment.py",
        ]
        for path in model_paths:
            with self.subTest(path=path.relative_to(ROOT)):
                text = path.read_text(encoding="utf-8")
                self.assertNotIn("os.environ", text)
                self.assertIn('wiz.config("docker_infra")', text)

        service_file = Path("/etc/systemd/system/wiz.docker-infra.service")
        if service_file.is_file():
            self.assertIn("EnvironmentFile=-/root/docker-infra/config.env", service_file.read_text(encoding="utf-8"))

    def test_frontend_detail_routes_are_explicit(self):
        routing = (ROOT / "src" / "angular" / "app" / "app-routing.module.ts").read_text(encoding="utf-8")
        service_lib = (ROOT / "src" / "portal" / "season" / "libs" / "service.ts").read_text(encoding="utf-8")

        for token in [
            '"page.services": ["services/:service_id", "services/:service_id/:detail_tab"]',
            '"page.servers": ["servers/:node_id", "servers/:node_id/:detail_tab"]',
            '"page.domains": ["domains/:zone_id"]',
            '"page.images": ["images/local", "images/local/:node_id", "images/harbor", "images/harbor/:project_name", "images/harbor/:project_name/:repository_name"]',
            '"page.operations": ["operations/:operation_id"]',
            '"page.system": ["system/:section", "system/:section/:subsection"]',
        ]:
            self.assertIn(token, routing)

        for token in ["routeSegment(name: string)", "routeTo(url: any", "encodeRouteSegment(value: any)"]:
            self.assertIn(token, service_lib)
        self.assertEqual(routing.count("router.children.push({"), 1)
        self.assertIn("let patterns = childPatterns(child);", routing)
        self.assertIn("otherChildPathMatches(layout_childs, child, url)", routing)
        self.assertIn("patternMatcher(child.path, url, false)", routing)
        self.assertNotIn("let matcher = patternMatcher(alias, url);", routing)

        route_aware_views = {
            "page.services": ["routeServiceId", "syncServiceRoute", "serviceDetailRoute"],
            "page.servers": ["routeNodeId", "syncNodeRoute", "nodeDetailRoute"],
            "page.domains": ["routeZoneId", "syncZoneRoute", "zoneDetailRoute"],
            "page.images": ["routeImageTarget", "syncImageRoute", "imageRoute"],
            "page.macros": ["routeMacroId", "syncMacroRoute", "macroDetailRoute"],
            "page.operations": ["routeOperationId", "syncOperationRoute", "operationDetailRoute"],
            "page.system": ["applyRouteSelection", "syncSystemRoute", "systemRoute"],
        }
        for app, tokens in route_aware_views.items():
            view = (ROOT / "src" / "app" / app / "view.ts").read_text(encoding="utf-8")
            with self.subTest(app=app):
                for token in tokens:
                    self.assertIn(token, view)

        for app in ["page.services", "page.servers", "page.operations", "page.system"]:
            view = (ROOT / "src" / "app" / app / "view.ts").read_text(encoding="utf-8")
            with self.subTest(app=app):
                self.assertIn("NavigationEnd", view)
                self.assertIn("handleRouteNavigation", view)

    def test_servers_layout_uses_container_width_for_agent_dock(self):
        view = (ROOT / "src" / "app" / "page.servers" / "view.pug").read_text(encoding="utf-8")
        style = (ROOT / "src" / "app" / "page.servers" / "view.scss").read_text(encoding="utf-8")

        self.assertIn("servers-page", view)
        self.assertIn("servers-detail-grid", view)
        self.assertNotIn("xl:grid-cols-[360px_1fr]", view)
        self.assertIn("container-type: inline-size", style)
        self.assertIn("@container (min-width: 1120px)", style)
        self.assertIn("minmax(280px, 360px) minmax(0, 1fr)", style)

    def test_ai_agent_destructive_actions_can_run_after_explicit_confirmation(self):
        view = (ROOT / "src" / "angular" / "app" / "app.component.ts").read_text(encoding="utf-8")

        self.assertIn("isBlockedAgentAction(action, requestMessage)", view)
        self.assertIn("hasExplicitDestructiveConfirmation", view)
        self.assertIn("operation?.safety === 'destructive'", view)
        self.assertNotIn("if (operation?.safety === 'destructive') return true;", view)

    def test_ai_agent_api_requests_can_chain_json_results(self):
        view = (ROOT / "src" / "angular" / "app" / "app.component.ts").read_text(encoding="utf-8")
        assistant = (ROOT / "src" / "model" / "struct" / "ai_assistant.py").read_text(encoding="utf-8")
        actions = (ROOT / "src" / "model" / "struct" / "ai_agent_actions.py").read_text(encoding="utf-8")

        self.assertIn("resolveAgentActionReferences(item.action, actionContext)", view)
        self.assertIn("storeAgentActionResult(action, result, actionContext)", view)
        self.assertIn("resolveAgentApiEntityPayload", view)
        self.assertIn("resolveAgentServiceIdByName", view)
        self.assertIn("appendAgentProgressLine", view)
        self.assertIn("JSON.stringify(payload || {})", view)
        self.assertIn("if (resolved === undefined) return _match", view)
        self.assertIn("return data?.data || data || {}", view)
        self.assertIn("mcp_action_catalog", assistant)
        self.assertIn("Docker Infra MCP 액션 카탈로그에서 요청 의도를 매칭합니다.", assistant)
        self.assertIn("save_as", assistant)
        self.assertIn("{{created_service.result.service.id}}", assistant)
        self.assertIn("docker_infra.services.delete", actions)
        self.assertIn("service_name_to_service_id", actions)

    def test_ai_agent_progress_lines_do_not_hide_missing_answer(self):
        view = (ROOT / "src" / "angular" / "app" / "app.component.ts").read_text(encoding="utf-8")
        assistant = (ROOT / "src" / "model" / "struct" / "ai_assistant.py").read_text(encoding="utf-8")
        runtime = (ROOT / "src" / "model" / "struct" / "codex_runtime.py").read_text(encoding="utf-8")

        self.assertIn("agentMessageHasAnswerContent(assistantMessage)", view)
        self.assertIn("!this.agentMessageHasAnswerContent(assistantMessage) && !done?.answer && !done?.stream_incomplete", view)
        self.assertIn("completeAgentChatFallback(payload, assistantMessage, requestStartedAt)", view)
        self.assertIn("setAgentErrorContent(assistantMessage", view)
        self.assertIn("__agentAnswerText", view)
        self.assertIn("Boolean(this.normalizeText(state.__agentAnswerText || ''))", view)
        self.assertIn("assistantMessage.role = 'error'", view)
        self.assertIn("missing_terminal_event", view)
        self.assertIn("event.type === 'thinking'", view)
        self.assertIn("let readPromise = reader.read().then((result) => ({ result }))", view)
        self.assertIn("if (!next.tick)", view)
        self.assertIn("runAgentRequest(message, sessionId)", view)
        self.assertIn("event.type === 'todo_update'", view)
        self.assertIn("applyAgentTodoUpdate", view)
        self.assertIn("agentSyntheticProgressMessage", view)
        self.assertIn("assistantMessage.content = ''", view)
        self.assertIn("Agent 응답을 수신해 사용자에게 보여줄 최종 답변과 실행 액션으로 정리합니다.", assistant)
        self.assertIn("_stream_complete_json_result", assistant)
        self.assertIn("_codex_runtime_todo_event", assistant)
        self.assertIn("_claude_runtime_todo_event", assistant)
        self.assertIn("TaskCreate", assistant)
        self.assertIn("TaskUpdate", assistant)
        self.assertIn("TodoWrite", assistant)
        self.assertIn("hermes.tool.progress", assistant)
        self.assertIn("Codex's built-in TODO/plan update mechanism", assistant)
        self.assertIn("Do not include runtime progress", assistant)
        self.assertIn("complete_json_stream", runtime)
        self.assertIn("_run_agent_stream", runtime)
        self.assertIn("_agent_stream_command", runtime)
        self.assertIn("--include-partial-messages", runtime)
        self.assertIn("stream-json", runtime)
        self.assertIn("agent.progress", runtime)
        self.assertIn("Do not copy the user's raw sentence as the TODO title.", assistant)
        self.assertIn("fallbackAgentTodos", view)
        self.assertNotIn("fastQuestionAgentTodos", view)
        self.assertNotIn("_fast_chat_todos", assistant)
        self.assertNotIn("응답을 기다리는 중입니다. (${elapsedSeconds}초 경과)", view)
        self.assertNotIn("Agent가 MCP 조회와 응답 생성을 계속 진행 중입니다.", assistant)


if __name__ == "__main__":
    unittest.main()
