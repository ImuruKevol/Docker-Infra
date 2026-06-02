import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


class AIAgentHistoryStaticContractTest(unittest.TestCase):
    def read(self, relative):
        return (ROOT / relative).read_text(encoding="utf-8")

    def test_history_repository_contract(self):
        model = self.read("src/model/struct/ai_history.py")

        for token in [
            "CREATE TABLE IF NOT EXISTS ai_agent_histories",
            "request_id TEXT NOT NULL DEFAULT ''",
            "session_id TEXT NOT NULL DEFAULT ''",
            "provider_session_id TEXT NOT NULL DEFAULT ''",
            "turn_index INTEGER NOT NULL DEFAULT 1",
            "ai_agent_histories_request_idx",
            "FOR UPDATE",
            "def record(",
            "def list(",
            "def sessions(",
            "def session(",
            "def detail(",
            "def delete(",
            "def delete_session(",
            "def delete_range(",
            "def export(",
            "def provider_session_id(",
            "_browser_from_user_agent",
            "\"ip\"",
            "\"browser\"",
            "\"duration_ms\"",
            "duration_ms =",
        ]:
            self.assertIn(token, model)

    def test_ai_agent_route_wires_history_management(self):
        route = self.read("src/route/api-ai-agent/controller.py")

        for token in [
            "request_metadata()",
            "\"request_meta\"",
            "\"request_id\"",
            "\"session_id\"",
            "history.list",
            "history.sessions",
            "history.session",
            "history.detail",
            "history.delete(",
            "history.delete_session",
            "history.delete_range",
            "history.export",
            "history/sessions",
            "history/session",
            "history/download",
            "history/delete-range",
            "openapi_capabilities",
            "capabilities",
            "assistant.plan_chat",
            "path == \"plan\"",
            "Content-Disposition",
            "X-Forwarded-For",
            "User-Agent",
        ]:
            self.assertIn(token, route)

    def test_assistant_records_chat_history_automatically(self):
        assistant = self.read("src/model/struct/ai_assistant.py")

        for token in [
            "ai_history = wiz.model(\"struct/ai_history\")",
            "def _record_chat_history",
            "ai_history.record",
            "status=\"succeeded\"",
            "status=\"failed\"",
            "request_meta",
            "_chat_context_for_provider",
            "_chat_session",
            "session_id",
            "provider_session_id",
            "duration_ms",
            "def _duration_ms",
        ]:
            self.assertIn(token, assistant)

    def test_agent_runtime_uses_provider_sessions(self):
        runtime = self.read("src/model/struct/codex_runtime.py")

        for token in [
            "def _request_session",
            "def _agent_session_args",
            "def _json_event_session_id",
            "\"exec\", \"resume\"",
            "\"--session-id\"",
            "\"--resume\"",
            "provider_session_id",
            "session_resumed",
        ]:
            self.assertIn(token, runtime)

    def test_global_agent_ui_exposes_history_controls(self):
        view_ts = self.read("src/angular/app/app.component.ts")
        template = self.read("src/angular/app/app.component.pug")
        style = self.read("src/angular/app/app.component.scss")

        for token in [
            "agentPanelMode",
            "agentSessionId",
            "createAgentRequestId",
            "request_id: requestId",
            "agentSessionLabel()",
            "newAgentSession()",
            "showAgentHistory()",
            "loadAgentHistory()",
            "downloadAgentHistory",
            "continueAgentHistory",
            "loadAgentHistorySession",
            "agentHistoryChatMessages",
            "deleteAgentHistory(",
            "deleteAgentHistoryRange()",
            "history/sessions",
            "history/session/delete",
            "agentHistoryTurns",
            "agentHistoryFilters",
            "agentMessageDurationLabel",
            "agentHistoryDurationLabel",
            "agentHistoryResponseHtml",
            "agentHistoryActions",
            "DomSanitizer",
            "bypassSecurityTrustHtml",
            "isAgentCodeLine",
            "agentHistoryTitle",
            "copyAgentHistoryAction",
            "agentHistoryActionCopied",
            "agentHistoryDetailDockVisible",
            "agentHistoryPageSize",
            "agentHistoryOffset",
            "agentHistoryRangeLabel",
            "agentHistoryHasNext",
            "moveAgentHistoryPage",
            "agentContextSignature",
            "shouldIgnoreAgentContextMutations",
            "handleAgentCodeCopy",
            "data-ai-agent-copy-code",
            "renderAgentView",
            "agentTextSelectionActive",
            "scheduleAgentRenderAfterSelection",
            "agentSelectionRenderTimer",
        ]:
            self.assertIn(token, view_ts)

        for token in [
            "fa-clock-rotate-left",
            "새 세션",
            "agentSessionLabel()",
            "agentPanelMode === 'history'",
            "downloadAgentHistory('json')",
            "downloadAgentHistory('csv')",
            "deleteAgentHistoryRange()",
            "deleteAgentHistory(item, $event)",
            "loadAgentHistory(true)",
            "ai-agent-history-pagination",
            "agentHistoryRangeLabel()",
            "moveAgentHistoryPage(-1)",
            "moveAgentHistoryPage(1)",
            "agentMessageDurationLabel(message)",
            "agentHistoryResponseHtml(turn)",
            "agentHistoryActions(history)",
            "agentHistoryTitle(item)",
            "agentHistoryTurns(history)",
            "continueAgentHistory(history, $event)",
            "continueAgentHistory(item, $event)",
            "ai-agent-history-continue",
            "ai-agent-history-continue-icon",
            "이어서 대화",
            "ai-agent-history-copy-actions",
            "ai-agent-history-detail-dock",
            "agentHistoryDetailDockVisible()",
            "copyAgentHistoryAction(action, index, $event)",
            "fa-solid fa-check",
            "fa-solid fa-copy",
        ]:
            self.assertIn(token, template)
        self.assertNotIn("agentHistoryPreview(item)", template)
        self.assertNotIn("small(*ngIf=\"action.reason\")", template)

        for token in [
            ".ai-agent-history-panel",
            ".ai-agent-history-toolbar",
            ".ai-agent-history-item",
            ".ai-agent-history-detail",
            ".ai-agent-history-detail-dock",
            ".ai-agent-history-pagination",
            ".ai-agent-session-pill",
            ".ai-agent-history-turn",
            ".ai-agent-history-status.failed",
            ".ai-agent-message-meta",
            ".ai-agent-code-block",
            ".ai-agent-code-toolbar",
            ".ai-agent-code-copy",
            ":host ::ng-deep .ai-agent-markdown .ai-agent-code-block",
            ".ai-agent-shell-history-detail-open",
            ".ai-agent-history-copy-actions",
            ".ai-agent-history-copy-button",
            ".ai-agent-history-continue",
            ".ai-agent-history-continue-icon",
            "grid-template-columns: minmax(0, 1fr) 32px 32px",
        ]:
            self.assertIn(token, style)
        self.assertNotIn(".ai-agent-history-copy-text small", style)
        self.assertNotIn("box-shadow: inset 3px 0 0 #f97316", style)

    def test_agent_toggle_is_visible_while_status_loads(self):
        view_ts = self.read("src/angular/app/app.component.ts")
        template = self.read("src/angular/app/app.component.pug")
        style = self.read("src/angular/app/app.component.scss")

        for token in [
            "public agentVisible()",
            "return true;",
            "public agentReady()",
            "public agentStatusLoading()",
            "public agentUnavailable()",
            "agentStateTitle()",
            "agentStateMessage()",
        ]:
            self.assertIn(token, view_ts)

        for token in [
            "agentHeaderStatusLabel()",
            "!agentReady()",
            "agentStatusLoading()",
            "ai-agent-state",
            "ai-agent-toggle-loading",
            "ai-agent-toggle-unavailable",
        ]:
            self.assertIn(token, template)

        for token in [
            ".ai-agent-state",
            ".ai-agent-toggle-loading",
            ".ai-agent-toggle-unavailable",
        ]:
            self.assertIn(token, style)

    def test_agent_can_dispatch_page_control_actions(self):
        assistant = self.read("src/model/struct/ai_assistant.py")
        app = self.read("src/angular/app/app.component.ts")
        template = self.read("src/angular/app/app.component.pug")
        style = self.read("src/angular/app/app.component.scss")
        macros = self.read("src/app/page.macros/view.ts")
        servers = self.read("src/app/page.servers/view.ts")

        for token in [
            "macro.create_global",
            "server.run_macro",
            "_looks_like_server_status_macro_request",
            "_looks_like_server_status_macro_run_request",
            "_server_status_macro_payload",
            "app_event",
            "api_request",
            "openapi_capabilities",
            "openapi_guidance",
            "plan_chat",
            "_ui_todo_plan_system_prompt",
            "_normalize_chat_todos",
        ]:
            self.assertIn(token, assistant)

        for token in [
            "agentTodos",
            "planAgentTodos",
            "runAgentTodo",
            "updateAgentTodo",
            "dispatchAgentAppEvent",
            "executeAgentApiRequest",
            "agentApiOperations",
            "loadAgentCapabilities",
            "docker-infra-agent-action",
            "docker-infra-agent-action-result",
            "waitForAgentRoute",
            "findAgentElementByLabel",
            "buildAgentActionTodoList",
        ]:
            self.assertIn(token, app)
        for token in [
            "const timeoutLimitMs = 10 * 60 * 1000",
            "const idleLimitMs = timeoutLimitMs",
            "const maxDurationMs = timeoutLimitMs",
            "AI Agent 응답이 10분 이상 갱신되지 않았습니다.",
        ]:
            self.assertIn(token, app)
        self.assertNotIn("AI Agent 응답이 30초 이상 갱신되지 않았습니다.", app)

        for token in ["agentTodoVisible()", "agentTodoStatusLabel(todo)", "ai-agent-todo-panel"]:
            self.assertIn(token, template)
        self.assertNotIn("agentTodoSummary", template)
        self.assertNotIn("agentTodoDetail(todo)", template)

        for token in [
            ".ai-agent-todo-panel",
            ".ai-agent-todo-item.state-running",
            ".ai-agent-todo-item.state-succeeded",
            "grid-template-columns: 22px minmax(0, 1fr) max-content",
            "justify-self: end",
            "box-sizing: border-box",
        ]:
            self.assertIn(token, style)
        self.assertNotIn(".ai-agent-todo-item p", style)

        for token in [
            "startAgentCommandListener",
            "handleAgentCommand",
            "createGlobalMacroFromAgent",
            "publishAgentCommandResult",
            "macro.create_global",
        ]:
            self.assertIn(token, macros)

        for token in [
            "startAgentCommandListener",
            "handleAgentCommand",
            "runMacroFromAgent",
            "saveAgentGlobalMacro",
            "server.run_macro",
        ]:
            self.assertIn(token, servers)


if __name__ == "__main__":
    unittest.main()
