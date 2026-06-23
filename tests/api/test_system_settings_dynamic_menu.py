import json
import unittest
from pathlib import Path

from tests.fixtures.api_client import DockerInfraApiClient, password_only_login


ROOT = Path(__file__).resolve().parents[2]
SETTINGS_ROUTE = ROOT / "src" / "route" / "api-system-settings" / "controller.py"
APPEARANCE_ROUTE = ROOT / "src" / "route" / "api-system-appearance" / "controller.py"
SIDEBAR_TS = ROOT / "src" / "app" / "component.nav.sidebar" / "view.ts"
ASSET_ROUTE = ROOT / "src" / "route" / "api-system-assets" / "controller.py"
AUTH_ROUTE = ROOT / "src" / "portal" / "season" / "route" / "auth" / "controller.py"
DOMAINS_API = ROOT / "src" / "app" / "page.domains" / "api.py"
SYSTEM_API = ROOT / "src" / "app" / "page.system" / "api.py"
SYSTEM_VIEW = ROOT / "src" / "app" / "page.system" / "view.pug"
SYSTEM_TS = ROOT / "src" / "app" / "page.system" / "view.ts"
CODEX_RUNTIME_MODEL = ROOT / "src" / "model" / "struct" / "codex_runtime.py"
AI_SETTINGS_MODEL = ROOT / "src" / "model" / "struct" / "ai_settings.py"
AUTH_MODEL = ROOT / "src" / "model" / "struct" / "auth.py"
SETUP_MODEL = ROOT / "src" / "model" / "struct" / "setup.py"
DASHBOARD_VIEW = ROOT / "src" / "app" / "page.dashboard" / "view.pug"
APP_MODULE = ROOT / "src" / "angular" / "app" / "app.module.ts"
APP_INITIALIZER = ROOT / "src" / "angular" / "app" / "appearance.initializer.ts"
APPEARANCE_RUNTIME = ROOT / "src" / "portal" / "season" / "libs" / "appearance.ts"


class SystemSettingsStaticContractTest(unittest.TestCase):
    def test_settings_routes_and_domains_contract_are_declared(self):
        controller = SETTINGS_ROUTE.read_text(encoding="utf-8")
        appearance_route = APPEARANCE_ROUTE.read_text(encoding="utf-8")
        sidebar = SIDEBAR_TS.read_text(encoding="utf-8")
        assets = ASSET_ROUTE.read_text(encoding="utf-8")
        auth_route = AUTH_ROUTE.read_text(encoding="utf-8")
        domains_api = DOMAINS_API.read_text(encoding="utf-8")
        system_api = SYSTEM_API.read_text(encoding="utf-8")
        system_view = SYSTEM_VIEW.read_text(encoding="utf-8")
        system_ts = SYSTEM_TS.read_text(encoding="utf-8")
        codex_runtime = CODEX_RUNTIME_MODEL.read_text(encoding="utf-8")
        ai_settings_model = AI_SETTINGS_MODEL.read_text(encoding="utf-8")
        auth_model = AUTH_MODEL.read_text(encoding="utf-8")
        setup_model = SETUP_MODEL.read_text(encoding="utf-8")
        dashboard_view = DASHBOARD_VIEW.read_text(encoding="utf-8")
        app_module = APP_MODULE.read_text(encoding="utf-8")
        app_initializer = APP_INITIALIZER.read_text(encoding="utf-8")
        appearance_runtime = APPEARANCE_RUNTIME.read_text(encoding="utf-8")

        self.assertIn("settings.upsert", controller)
        self.assertIn("def as_bool(value):", controller)
        self.assertIn("AppearanceRuntime.read()", sidebar)
        self.assertIn("appearance.store_asset", assets)
        self.assertNotIn("appearance.public_payload()", auth_route)
        self.assertIn("appearance.public_payload()", appearance_route)
        self.assertIn("APPEARANCE_INITIALIZER_PROVIDER", app_module)
        self.assertIn("APP_INITIALIZER", app_initializer)
        self.assertIn("/api/system/appearance", appearance_runtime)
        self.assertIn("def save_ddns_endpoint():", domains_api)
        self.assertIn("def force_update_ddns_endpoint():", domains_api)
        self.assertIn("def ensure_ddns_dispatcher():", domains_api)
        self.assertIn("def change_admin_password():", system_api)
        self.assertIn("auth.change_password", system_api)
        self.assertIn("def change_password(", auth_model)
        self.assertIn("INVALID_CURRENT_PASSWORD", auth_model)
        self.assertIn("system-admin-current-password", system_view)
        self.assertIn("system-admin-new-password", system_view)
        self.assertIn("system-admin-password-save", system_view)
        self.assertIn("changeAdminPassword()", system_ts)
        for token in ["session_settings", "save_session_policy"]:
            self.assertIn(token, system_api)
        for token in ["auth.extend_session", "auth.remember_session_cookie"]:
            self.assertIn(token, system_api)
        for token in ["docker-infra:session-updated", "handleSessionUpdated"]:
            self.assertIn(token, system_ts + sidebar)
        for token in ["세션 지속시간", "system-session-ttl-hours", "sessionDurationLabel()", "sessionDurationRangeLabel()"]:
            self.assertIn(token, system_view + system_ts)
        for token in ["def ai_codex_device_login_start():", "def ai_codex_device_login_status():", "def ai_codex_device_login_cancel():"]:
            self.assertIn(token, system_api)
        for token in ["def ai_claude_code_login_start():", "def ai_claude_code_login_status():", "def ai_claude_code_login_submit():", "def ai_claude_code_login_cancel():", "def ai_hermes_apply_settings():"]:
            self.assertIn(token, system_api)
        for token in ["def ai_agent_status():", "def ai_agent_model_catalog():", "def ai_agent_update_check():", "def ai_agent_test():", "def ai_agent_install():", "def ai_agent_install_status():", "agent_statuses", "claude_code", "hermes"]:
            self.assertIn(token, system_api + system_ts)
        for token in ["OpenAI GPT", "Google Gemini", "Ollama", "API Token", "등록 노드 Ollama", "ai_models", "ai_resources"]:
            self.assertNotIn(token, system_api + system_view + system_ts)
        for token in ["Claude Code", "헤르메스", "AI Agent", "refreshAgentStatus", "installAiAgent", "checkAgentUpdate", "설치 스크립트 실행"]:
            self.assertIn(token, system_view + system_ts)
        for token in ["네이티브", "native", "npm global"]:
            self.assertNotIn(token, system_view + system_ts)
        for token in ["AI_UPDATE_STATUS_KEY", "save_agent_update", "agent_updates"]:
            self.assertIn(token, system_api + system_ts + ai_settings_model)
        for token in ["def save_ai_default_agent():", "save_default_agent", "default_agent", "기본 AI Agent", "defaultAgentOptions", "saveAiDefaultAgent()", "defaultAiAgentVisible()"]:
            self.assertIn(token, system_api + system_view + system_ts + ai_settings_model)
        for token in ["agent_update_status", "CLAUDE_CODE_INSTALL_URL", "HERMES_AGENT_INSTALL_URL"]:
            self.assertIn(token, codex_runtime)
        for token in ["closeCodexUpdateOperation()", "closeAgentInstallOperation()", "Agent 설치/업데이트 진행"]:
            self.assertIn(token, system_view + system_ts)
        for token in ["CODEX_HOME", "활성 CLI", "실행 파일", "Agent HOME", "명령 템플릿", "확인 명령", "현재 모델"]:
            self.assertNotIn(token, system_view)
        self.assertNotIn("Codex 저장", system_view)
        self.assertNotIn("agentStatusRows(activeAiTab())", system_view)
        self.assertGreaterEqual(system_view.count("ml-auto inline-flex h-10"), 2)
        for token in ["codex_home", "executable", "command_template"]:
            self.assertNotIn(token, system_ts)
        for token in ["Agent 기반 실행과 Codex 로그인 세션만 제어합니다.", "실행 테스트", "testAiCodexLogin()", "testAiAgent(activeAiTab())"]:
            self.assertNotIn(token, system_view)
        for token in ["install_agent_async", "agent_install_script", "DOCKER_INFRA_CLAUDE_CODE_INSTALL_SCRIPT", "DOCKER_INFRA_CLAUDE_CODE_INSTALL_CHANNEL", "DOCKER_INFRA_HERMES_AGENT_INSTALL_SCRIPT", "DOCKER_INFRA_HERMES_AGENT_INSTALL_URL"]:
            self.assertIn(token, codex_runtime)
        self.assertNotIn(" doctor", codex_runtime)
        for token in ["AGENT_RUNTIME_HOME_ROOT", "DOCKER_INFRA_CLAUDE_CODE_HOME", "DOCKER_INFRA_HERMES_AGENT_HOME", "CODEX_DEVICE_LOGIN_START_TIMEOUT_SECONDS = 10"]:
            self.assertIn(token, codex_runtime)
        self.assertIn("[\"bash\", \"-lc\", self.agent_install_script(\"codex\", env=env)]", codex_runtime)
        self.assertIn("[\"bash\", \"-lc\", script]", codex_runtime)
        for token in ["startCodexDeviceLogin()", "codexDeviceLogin()", "copyCodexDeviceCode()", "브라우저 로그인", "One-time code"]:
            self.assertIn(token, system_view + system_ts)
        for token in ["startClaudeLogin()", "claudeLogin()", "submitClaudeLoginCode()", "agentInstallActionVisible", "agentUpdateCheckVisible", "hermesProviderOptions", "hermesConfigStatusLabel"]:
            self.assertIn(token, system_view + system_ts)
        for token in ["wiz-component-search-select([items]=\"agentModelItems('codex')\"", "wiz-component-search-select([items]=\"agentModelItems(activeAiTab())\"", "refreshAgentModels", "agentModelCatalogLabel"]:
            self.assertIn(token, system_view + system_ts)
        for token in ["API Key Env", "OPENROUTER_API_KEY", "Working Directory", "hermesProviderApiKeyEnv", "헤르메스 에이전트는 필요할 때 업그레이드를 직접 실행하는 방식입니다."]:
            self.assertNotIn(token, system_view + system_ts)
        for token in ["def start_device_login", "codex login --device-auth", "verification_uri", "user_code", "cancel_device_login", "pty.openpty", "_read_device_login_pty"]:
            self.assertIn(token, codex_runtime)
        for token in ["def start_claude_login", "claude auth login", "submit_claude_login_code", "apply_hermes_settings", "upgrade_policy", "hermes update", "agent_model_catalog", "MODEL_CATALOG_SOURCES", "openrouter.ai/api/v1/models"]:
            self.assertIn(token, codex_runtime)
        self.assertNotIn("public_url", setup_model)
        self.assertNotIn("public_url", dashboard_view)


class SystemSettingsLiveFlowTest(unittest.TestCase):
    def setUp(self):
        self.client = DockerInfraApiClient.from_env(self)
        password_only_login(self.client, testcase=self)

    def test_setting_create_read_and_delete_flow_masks_secret_values(self):
        key = f"integration.test.secret.{self.client.test_run_id}"
        upsert = self.client.post(
            "/api/system/settings",
            json={
                "key": key,
                "value": "plain-secret-value",
                "value_type": "secret",
                "is_secret": True,
                "test_run_id": self.client.test_run_id,
            },
            validate=False,
        )
        read = self.client.get(f"/api/system/settings?key={key}", validate=False)
        delete = self.client.request("DELETE", "/api/system/settings", json={"key": key}, validate=False)

        for response in [upsert, read, delete]:
            self.assertEqual(response.status_code, 200, response.text[:500])
            self.assertNotIn("plain-secret-value", json.dumps(response.json(), ensure_ascii=False))
        self.assertEqual(upsert.json()["data"]["setting"]["secret"]["masked_value"], "********")
        self.assertTrue(delete.json()["data"]["deleted"])

    def test_public_appearance_endpoint_returns_general_branding(self):
        response = self.client.get("/api/system/appearance", validate=False)
        self.assertEqual(response.status_code, 200, response.text[:500])
        appearance = response.json()["data"]["appearance"]
        self.assertIn("browser_title", appearance)
        self.assertIn("favicon_url", appearance)
        self.assertIn("logo_url", appearance)

if __name__ == "__main__":
    unittest.main()
