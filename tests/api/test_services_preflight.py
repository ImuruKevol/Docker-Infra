import json
import os
import subprocess
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
CREATE_API = ROOT / "src" / "app" / "page.services.create" / "api.py"
CREATE_VIEW = ROOT / "src" / "app" / "page.services.create" / "view.ts"
CREATE_TEMPLATE = ROOT / "src" / "app" / "page.services.create" / "view.pug"
SERVERS_VIEW = ROOT / "src" / "app" / "page.servers" / "view.ts"
SERVERS_TEMPLATE = ROOT / "src" / "app" / "page.servers" / "view.pug"
SERVICES_API = ROOT / "src" / "app" / "page.services" / "api.py"
SERVICES_VIEW = ROOT / "src" / "app" / "page.services" / "view.ts"
SERVICES_TEMPLATE = ROOT / "src" / "app" / "page.services" / "view.pug"
PREFLIGHT_MODEL = ROOT / "src" / "model" / "struct" / "services_preflight.py"
SERVICES_MODEL = ROOT / "src" / "model" / "struct" / "services.py"
UPDATE_MODEL = ROOT / "src" / "model" / "struct" / "services_update.py"
ROLLBACK_MODEL = ROOT / "src" / "model" / "struct" / "services_rollback.py"
STATUS_MODEL = ROOT / "src" / "model" / "struct" / "services_status.py"
FLOW_MODEL = ROOT / "src" / "model" / "struct" / "services_flow.py"
WIZARD_MODEL = ROOT / "src" / "model" / "struct" / "services_wizard.py"
AI_ASSISTANT_MODEL = ROOT / "src" / "model" / "struct" / "ai_assistant.py"
CODEX_RUNTIME_MODEL = ROOT / "src" / "model" / "struct" / "codex_runtime.py"
DOCKER_INFRA_MCP = ROOT / "tools" / "docker_infra_mcp.py"
PORTS_MODEL = ROOT / "src" / "model" / "struct" / "services_ports.py"
DEPLOY_MODEL = ROOT / "src" / "model" / "struct" / "services_deploy.py"
LOCAL_COMMAND_MODEL = ROOT / "src" / "model" / "struct" / "local_command_catalog.py"
OPERATIONS_MODEL = ROOT / "src" / "model" / "struct" / "operations.py"
DEPLOY_TARGETS_MODEL = ROOT / "src" / "model" / "struct" / "services_deploy_targets.py"
PLACEMENT_MODEL = ROOT / "src" / "model" / "struct" / "services_placement.py"
NGINX_MODEL = ROOT / "src" / "model" / "struct" / "service_nginx.py"
NGINX_CERT_MODEL = ROOT / "src" / "model" / "struct" / "service_nginx_certificates.py"
SERVICES_CERTBOT_MODEL = ROOT / "src" / "model" / "struct" / "services_certbot.py"
DOMAINS_MODEL = ROOT / "src" / "model" / "struct" / "domains.py"
DOMAINS_VIEW = ROOT / "src" / "app" / "page.domains" / "view.ts"
DOMAINS_TEMPLATE = ROOT / "src" / "app" / "page.domains" / "view.pug"
DOMAIN_CERT_ROUTE = ROOT / "src" / "route" / "api-domain-certificates" / "controller.py"
WEBSERVER_MODEL = ROOT / "src" / "model" / "struct" / "webserver.py"
RUNTIME_CONFIG = ROOT / "config" / "docker_infra.py"


class ServicesPreflightStaticContractTest(unittest.TestCase):
    def test_docker_infra_mcp_accepts_codex_stdio_json(self):
        context = {
            "workspace_root": str(ROOT.parents[1]),
            "project_root": str(ROOT),
            "mcp_enabled_tools": ["infra_context"],
            "nodes": [],
            "domain_zones": [],
            "ddns_endpoints": [],
            "allowed_probe_hosts": [],
            "runtime_values": {},
            "ai_request_summary": {"mode": "test", "context_delivery": {"prompt": "compacted_summary"}},
            "request_context_keys": ["mode"],
        }
        messages = [
            {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "initialize",
                "params": {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {},
                    "clientInfo": {"name": "codex-test", "version": "1"},
                },
            },
            {"jsonrpc": "2.0", "method": "notifications/initialized", "params": {}},
            {"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}},
            {"jsonrpc": "2.0", "id": 3, "method": "resources/list", "params": {}},
            {"jsonrpc": "2.0", "id": 4, "method": "tools/call", "params": {"name": "infra_context", "arguments": {}}},
        ]
        completed = subprocess.run(
            [sys.executable, str(DOCKER_INFRA_MCP)],
            input="\n".join(json.dumps(item) for item in messages) + "\n",
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
            env={**os.environ, "DOCKER_INFRA_MCP_CONTEXT_JSON": json.dumps(context)},
        )
        self.assertEqual(completed.returncode, 0, completed.stderr)
        responses = [json.loads(line) for line in completed.stdout.splitlines() if line.strip()]
        by_id = {item.get("id"): item for item in responses}
        self.assertEqual(by_id[1]["result"]["serverInfo"]["name"], "docker-infra")
        self.assertEqual([tool["name"] for tool in by_id[2]["result"]["tools"]], ["infra_context"])
        self.assertEqual(by_id[3]["result"]["resources"], [])
        infra_context = json.loads(by_id[4]["result"]["content"][0]["text"])
        self.assertEqual(infra_context["ai_request_summary"]["mode"], "test")
        self.assertEqual(infra_context["request_context_keys"], ["mode"])

    def test_service_create_preflight_contract_is_wired(self):
        api = CREATE_API.read_text(encoding="utf-8")
        view = CREATE_VIEW.read_text(encoding="utf-8")
        template = CREATE_TEMPLATE.read_text(encoding="utf-8")
        preflight = PREFLIGHT_MODEL.read_text(encoding="utf-8")
        wizard = WIZARD_MODEL.read_text(encoding="utf-8")
        ports = PORTS_MODEL.read_text(encoding="utf-8")
        deploy = DEPLOY_MODEL.read_text(encoding="utf-8")
        local_commands = LOCAL_COMMAND_MODEL.read_text(encoding="utf-8")
        deploy_targets = DEPLOY_TARGETS_MODEL.read_text(encoding="utf-8")
        placement = PLACEMENT_MODEL.read_text(encoding="utf-8")
        nginx = NGINX_MODEL.read_text(encoding="utf-8")
        config = RUNTIME_CONFIG.read_text(encoding="utf-8")

        self.assertIn("def preflight():", api)
        self.assertIn("deploy_service_background", api)
        self.assertIn("wizard.preflight", api)
        self.assertIn("public async runPreflight", view)
        self.assertIn("deploy_service_background", view)
        self.assertIn("저장 전 자동 점검", template)
        self.assertIn("services_preflight", wizard)
        self.assertIn("SERVICE_PREFLIGHT_BLOCKED", wizard)
        self.assertIn('"mode": "host"', wizard)
        self.assertIn("_rewrite_internal_service_ref", wizard)
        self.assertIn("{{ namespace }}", wizard)
        for token in ["_check_placement", "_check_images", "_check_volumes", "_check_ports", "_check_domain", "_remote_port_usage"]:
            self.assertIn(token, preflight)
        self.assertIn("def preview_content", ports)
        self.assertIn("_sync_domain_published_ports", deploy)
        self.assertIn("_record_deploy_adjustments", deploy)
        self.assertIn("_apply_stack_placement", deploy)
        self.assertIn("node.id ==", deploy)
        self.assertIn("deploy_adjustments", deploy)
        self.assertIn("placement_selector.recommend", deploy)
        for token in ["least_loaded_resource_score", "cpu_percent", "memory_used_percent", "storage_used_percent", "containers"]:
            self.assertIn(token, placement)
        self.assertIn("sync_domain_proxy_targets", deploy)
        self.assertIn("registered_by_swarm_id", deploy_targets)
        self.assertIn("node_id[:12]", deploy_targets)
        self.assertIn("inspected[key]", deploy_targets)
        self.assertIn("swarm.nodes.inspect", deploy_targets)
        self.assertIn("swarm_addr", deploy_targets)
        self.assertIn("swarm_addr or", deploy_targets)
        self.assertIn("proxy_host", deploy_targets)
        self.assertIn("service_nginx.apply", deploy)
        self.assertIn("deploy_background", deploy)
        self.assertIn("_deploy_background_worker", deploy)
        self.assertIn("threading.Thread", deploy)
        operations_model = OPERATIONS_MODEL.read_text(encoding="utf-8")
        self.assertIn("Jsonb(_serialize(requested_payload", operations_model)
        self.assertIn("Jsonb(_serialize(metadata", operations_model)
        self.assertIn("proxy.nginx.reload", config)
        self.assertIn("certbot.nginx.issue", config)
        nginx_cert = NGINX_CERT_MODEL.read_text(encoding="utf-8")
        for token in ["_render", "_restore_domain", "_issue_certificates", "proxy.nginx.configtest", "proxy.nginx.reload"]:
            self.assertIn(token, nginx)
        self.assertIn("proxy_pass http://{upstream}", nginx)
        for token in ["_letsencrypt_cert", "certbot.nginx.issue"]:
            self.assertIn(token, nginx_cert)

    def test_server_compose_import_uses_service_create_wizard(self):
        api = CREATE_API.read_text(encoding="utf-8")
        view = CREATE_VIEW.read_text(encoding="utf-8")
        template = CREATE_TEMPLATE.read_text(encoding="utf-8")
        servers_view = SERVERS_VIEW.read_text(encoding="utf-8")
        servers_template = SERVERS_TEMPLATE.read_text(encoding="utf-8")
        wizard = WIZARD_MODEL.read_text(encoding="utf-8")

        self.assertIn("def load_import():", api)
        self.assertIn("wizard.prepare_import", api)
        self.assertIn("public async loadImportFromQuery", view)
        self.assertIn("import_source", view)
        self.assertIn("server_compose_import_wizard", wizard)
        self.assertIn("prepare_import", wizard)
        self.assertIn("/services/create?", servers_view)
        self.assertIn("import_node_id", servers_view)
        self.assertIn("생성 화면으로 이동", servers_template)

    def test_service_create_uses_draft_sources_without_templates(self):
        api = CREATE_API.read_text(encoding="utf-8")
        view = CREATE_VIEW.read_text(encoding="utf-8")
        template = CREATE_TEMPLATE.read_text(encoding="utf-8")
        wizard = WIZARD_MODEL.read_text(encoding="utf-8")
        assistant = AI_ASSISTANT_MODEL.read_text(encoding="utf-8")
        codex_runtime = CODEX_RUNTIME_MODEL.read_text(encoding="utf-8")
        mcp = DOCKER_INFRA_MCP.read_text(encoding="utf-8")
        deploy = DEPLOY_MODEL.read_text(encoding="utf-8")
        local_commands = LOCAL_COMMAND_MODEL.read_text(encoding="utf-8")

        self.assertIn("def prepare_compose_draft():", api)
        self.assertIn("prepare_manual", api)
        self.assertIn("public async applyManualCompose", view)
        self.assertIn("applyComposeDraft", view)
        self.assertIn("draft_metadata", view)
        self.assertIn("manual_compose", view)
        self.assertIn("manualComposeEditorOptions", view)
        self.assertIn("const detailRows = Array.isArray(data?.details) ? data.details : []", view)
        self.assertIn("[data?.reason, ...detailRows]", view)
        self.assertIn("manualComposeOpen.set(true)", view)
        self.assertIn("hasAiModels()", view)
        self.assertIn("server_compose_import", view)
        self.assertIn("Compose 직접 작성", template)
        self.assertIn("nu-monaco-editor", template)
        self.assertIn('*ngIf="hasAiModels()"', template)
        self.assertIn('*ngIf="!hasAiModels()"', template)
        self.assertIn("SERVICE_DRAFT_REQUIRED", wizard)
        self.assertIn("def prepare_manual", wizard)
        self.assertIn("draft_metadata", wizard)
        self.assertIn('"draft"', (ROOT / "src" / "model" / "struct" / "services.py").read_text(encoding="utf-8"))
        services_view = SERVICES_VIEW.read_text(encoding="utf-8")
        services_template = SERVICES_TEMPLATE.read_text(encoding="utf-8")
        self.assertIn("versionSourceLabel", services_view)
        self.assertIn("versionDraftText", services_view)
        self.assertIn("versionSourceLabel(version)", services_template)
        self.assertIn("generated_secret_keys", assistant)
        for token in ["_complete_service_multiphase", "_service_plan_system_prompt", "_inspect_service_plan", "_service_review_system_prompt", "docker_infra_inspection", "repair_runtime", "runtime_diagnostics", "form.domains", "_assert_ai_runtime_compose_contract", "AI_RUNTIME_COMPOSE_CONTRACT_FAILED", "Do not use *_FILE", "can_select_ddns_domains", "can_register_ddns_records_via_deploy", "can_inspect_ddns_domains", "ddns_endpoint_id", "wildcard_suffix", "domain_provider_policy", "ddns_registration_flow", "ddns_repair_suggestion", "_service_zones_for_ai", "_ddns_repair_suggestion", "_ddns_verification_fallback_data", "_ddns_repair_fallback_data", "_ddns_direct_verification_data", "_ddns_direct_repair_data", "_compact_runtime_status", "_compact_recent_operations", "_register_ddns_after_ai_update", "_ddns_register_summary_text", "ddns_register_result", "_apply_ddns_repair_fallback", "_service_warnings", "_is_stale_ddns_registration_warning", "_ddns_child_domain", "_ddns_default_prefix", "never use sub.nanoha.kr itself as the service domain"]:
            self.assertIn(token, assistant)
        self.assertIn('"can_register_ddns_records_via_deploy": True', assistant)
        self.assertIn("Do not warn that requested DDNS subdomains are unregistered", assistant)
        self.assertIn("never remove all public domains just because the DDNS record is not registered yet", assistant)
        self.assertIn("Codex 수정 호출 실패로 DDNS deterministic fallback", assistant)
        self.assertIn("기존 DDNS 등록 정보와 공인 IP가 같아 DDNS API 호출은 생략되었습니다.", assistant)
        for token in ["has_enabled_models", "시스템 설정에서 사용 중인 AI 모델이 없습니다.", "선택한 Codex 모델을 사용하려면 Codex 로그인을 사용 설정하세요.", "AI_PROVIDER_NOT_CONFIGURED"]:
            self.assertIn(token, assistant)
        for token in ["_runtime_issue_signals", "_client_failed_operations", "_merge_runtime_operations", "client_runtime_issues", "terminal_actions", "container_action", "operator_message", "service_status", "failed_operations", "stack_replicas", "containers_stopped", "stream_runtime_repair", "runtime_actions", "terminal_action_results", "_execute_runtime_actions", "start_runtime_verification", "_runtime_verification_worker", "_wait_runtime_ready", "_runtime_snapshot_blocked", "_runtime_snapshot_key", "AI_VERIFY_UNCHANGED_BLOCKED_ATTEMPTS", "동일한 상태 확인 로그", "다음 검증 시도", "verify_runtime", "service.ai.verify"]:
            self.assertIn(token, assistant)
        for token in ["runtimeIssueSnapshot", "client_runtime_issues", "runtimeIssueOperations", "runtimeAiIntent", "runtimeAiAllowContainerActions", "runtimeAiAllowSshDiagnostics", "allow_container_terminal_actions", "allow_ssh_command", "submitRuntimeAiRepair", "start_runtime_ai_verification", "activeBackgroundOperation", "service.ai.verify", "editOperatorComment", "operator_comment", "doneSeen", "완료 이벤트 없이 종료", "normalizeMcpToolExposureMessage"]:
            self.assertIn(token, services_view)
        for token in ["infra_context", "docker_image_check", "server_port_check", "container_logs", "container_action", "service_stack_status", "dns_lookup", "tcp_connect_check", "http_probe", "browser_probe", "server_collect", "ssh_command"]:
            self.assertIn(token, codex_runtime)
            self.assertIn(token, mcp)
        for token in ["domain_zones", "ddns_endpoints"]:
            self.assertIn(token, codex_runtime)
            self.assertIn(token, mcp)
        self.assertIn("default_tools_approval_mode", codex_runtime)
        self.assertIn("mcp_tools_for_scope", codex_runtime)
        for token in ["_prompt_context", "_semantic_prompt_context", "PROMPT_CONTEXT_CHAR_BUDGET", "context_delivery", "ai_request_summary", "request_context_keys", "large Docker Infra runtime data is kept out of the prompt"]:
            self.assertIn(token, codex_runtime)
        for token in ["ai_request_summary", "request_context_keys", "compact AI request summary"]:
            self.assertIn(token, mcp)
        self.assertIn("create_session_id", wizard)
        self.assertIn("_existing_create_session", wizard)
        self.assertIn("createSessionId", view)
        self.assertIn("createdServiceId", view)
        for token in ["_active_deploy_operation", "deduplicated"]:
            self.assertIn(token, deploy)
        self.assertIn("--prune", local_commands)
        for token in ["_candidate_codex_binaries", "_build_codex_binary", "_source_newer_than", "CODEX_BUILD_CHECK_INTERVAL_SECONDS", "DOCKER_INFRA_CODEX_AUTO_BUILD", "codex-build.lock"]:
            self.assertIn(token, codex_runtime)
        self.assertIn("domains", wizard)
        services_update = (ROOT / "src" / "model" / "struct" / "services_update.py").read_text(encoding="utf-8")
        self.assertIn("domains", services_update)
        self.assertIn("elif zone_id", services_update)
        self.assertIn("normalize_service_domain", services_update)
        self.assertIn("normalize_service_domain", (ROOT / "src" / "model" / "struct" / "services_wizard.py").read_text(encoding="utf-8"))
        self.assertIn("_task_error_active", STATUS_MODEL.read_text(encoding="utf-8"))
        self.assertIn("ai_runtime_repair", SERVICES_API.read_text(encoding="utf-8"))
        self.assertIn("stream_runtime_ai_repair", SERVICES_API.read_text(encoding="utf-8"))
        self.assertIn("start_runtime_ai_verification", SERVICES_API.read_text(encoding="utf-8"))
        self.assertIn("start_ai_verification", deploy)
        self.assertNotIn("start_ai_verification: true", view)
        self.assertNotIn("start_ai_verification: true", SERVICES_VIEW.read_text(encoding="utf-8"))
        self.assertIn("start_runtime_ai_verification", SERVICES_VIEW.read_text(encoding="utf-8"))
        self.assertIn("runRuntimeAiRepair", SERVICES_VIEW.read_text(encoding="utf-8"))
        self.assertIn("suppressed_duplicate_logs", SERVICES_VIEW.read_text(encoding="utf-8"))
        self.assertNotIn("AI 검증과 수정 작업을 백그라운드에서 시작했습니다.', 'success'", SERVICES_VIEW.read_text(encoding="utf-8"))
        self.assertIn("hasAiModels()", SERVICES_VIEW.read_text(encoding="utf-8"))
        self.assertIn("AI 검사/수정", SERVICES_TEMPLATE.read_text(encoding="utf-8"))
        self.assertIn('*ngIf="hasAiModels()"', SERVICES_TEMPLATE.read_text(encoding="utf-8"))
        self.assertIn("AI 자동 조치 허용", SERVICES_TEMPLATE.read_text(encoding="utf-8"))
        self.assertIn("서버 진단", SERVICES_TEMPLATE.read_text(encoding="utf-8"))
        self.assertIn("브라우저 점검", services_view)
        self.assertIn("백그라운드 작업 진행 중", SERVICES_TEMPLATE.read_text(encoding="utf-8"))
        self.assertIn("추가 코멘트", SERVICES_TEMPLATE.read_text(encoding="utf-8"))
        for token in ["template_detail", "selectedTemplateId", "templateLoading", "templateSelectorItems", "template_id"]:
            self.assertNotIn(token, api)
            self.assertNotIn(token, view)

    def test_service_edit_wizard_contract_is_wired(self):
        api = SERVICES_API.read_text(encoding="utf-8")
        view = SERVICES_VIEW.read_text(encoding="utf-8")
        template = SERVICES_TEMPLATE.read_text(encoding="utf-8")
        services = SERVICES_MODEL.read_text(encoding="utf-8")
        update = UPDATE_MODEL.read_text(encoding="utf-8")

        self.assertIn("def update_service():", api)
        self.assertIn("services_model.update_wizard", api)
        self.assertIn("public openEditModal", view)
        self.assertIn("public async saveEditService", view)
        self.assertIn("editOperatorComment", view)
        self.assertIn("operator_comment", view)
        self.assertIn("operator_comment", update)
        self.assertIn("서비스 수정", template)
        self.assertIn("추가 코멘트", template)
        self.assertIn("ServiceUpdateMixin", services)
        for token in ["def update_wizard", "compose_versions", "service_domains", "SERVICE_PREFLIGHT_BLOCKED"]:
            self.assertIn(token, update)

    def test_service_delete_contract_is_wired(self):
        api = SERVICES_API.read_text(encoding="utf-8")
        view = SERVICES_VIEW.read_text(encoding="utf-8")
        template = SERVICES_TEMPLATE.read_text(encoding="utf-8")
        services = SERVICES_MODEL.read_text(encoding="utf-8")
        delete_model = (ROOT / "src" / "model" / "struct" / "services_delete.py").read_text(encoding="utf-8")
        commands = (ROOT / "src" / "model" / "struct" / "local_command_catalog.py").read_text(encoding="utf-8")
        config = RUNTIME_CONFIG.read_text(encoding="utf-8")

        self.assertIn("def delete_service():", api)
        self.assertIn("services_model.delete", api)
        self.assertIn("public async deleteSelectedService", view)
        self.assertIn("서비스 삭제", template)
        self.assertIn("ServiceDeleteMixin", services)
        for token in ["def delete", "_managed_nginx_delete_path", "_remove_volumes", "_remove_dns_records", "delete_service_dns_records", "SERVICE_DNS_RECORD_REMOVE_FAILED", "service.stack.remove", "service.stack.volumes.remove", "proxy.nginx.configtest", "proxy.nginx.reload"]:
            self.assertIn(token, delete_model)
        self.assertIn("service.stack.remove", commands)
        self.assertIn("service.stack.volumes.remove", commands)
        self.assertIn("service.stack.remove", config)
        self.assertIn("service.stack.volumes.remove", config)

    def test_service_delete_removes_cloudflare_dns_records(self):
        delete_model = (ROOT / "src" / "model" / "struct" / "services_delete.py").read_text(encoding="utf-8")
        domains = DOMAINS_MODEL.read_text(encoding="utf-8")

        self.assertIn("domains_model.delete_service_dns_records", delete_model)
        self.assertIn("def delete_service_dns_records", domains)
        self.assertIn("domain.record.delete_service", domains)
        self.assertIn("SERVICE_DNS_RECORD_DELETE_FAILED", domains)
        self.assertIn("Managed by Docker Infra", domains)

    def test_service_rollback_contract_is_wired(self):
        api = SERVICES_API.read_text(encoding="utf-8")
        view = SERVICES_VIEW.read_text(encoding="utf-8")
        template = SERVICES_TEMPLATE.read_text(encoding="utf-8")
        services = SERVICES_MODEL.read_text(encoding="utf-8")
        rollback = ROLLBACK_MODEL.read_text(encoding="utf-8")

        self.assertIn("def rollback_plan():", api)
        self.assertIn("def rollback_service():", api)
        self.assertIn("services_model.rollback_plan", api)
        self.assertIn("services_model.rollback", api)
        self.assertIn("public async openRollbackModal", view)
        self.assertIn("public async runRollback", view)
        self.assertIn("버전 되돌리기", template)
        self.assertIn("ServiceRollbackMixin", services)
        for token in ["def rollback_plan", "def rollback", "compose_rollback", "compose_versions", "service.compose.rollback"]:
            self.assertIn(token, rollback)

    def test_service_operation_output_polling_is_wired(self):
        api = SERVICES_API.read_text(encoding="utf-8")
        view = SERVICES_VIEW.read_text(encoding="utf-8")
        template = SERVICES_TEMPLATE.read_text(encoding="utf-8")

        self.assertIn("def operation_detail():", api)
        self.assertIn("def deploy_service_background():", api)
        self.assertIn("deploy_service_background", view)
        self.assertIn("service_id", view)
        self.assertIn("operations_model.detail", api)
        self.assertIn("public async openOperationModal", view)
        self.assertIn("startOperationPolling", view)
        self.assertIn("pending", view)
        self.assertIn("operationOutput", view)
        self.assertIn("처리 로그", template)
        self.assertIn("operationModalOpen", template)

    def test_service_detail_operator_runtime_summary_is_wired(self):
        view = SERVICES_VIEW.read_text(encoding="utf-8")
        template = SERVICES_TEMPLATE.read_text(encoding="utf-8")
        api = SERVICES_API.read_text(encoding="utf-8")
        flow = FLOW_MODEL.read_text(encoding="utf-8")

        for token in ["runtimeServerSummaryText", "certificateSummaryText", "serviceIssue", "runtimeContainers", "runRuntimeContainerAction", "detailTabs", "serviceFlowPaths"]:
            self.assertIn(token, view)
        self.assertIn("flow_model.build", api)
        self.assertIn("service_flow", api)
        self.assertIn("def service_container_action():", api)
        self.assertIn("target_node_id", api)
        self.assertIn("container.node_id", view)
        for token in ["class ServicesFlow", "depends_on", "public_paths", "internal_targets", "nginx"]:
            self.assertIn(token, flow)
        self.assertIn("서버 / 인증서", template)
        self.assertIn("실행 상태", template)
        self.assertIn("처리 로그", template)
        self.assertIn("백업", template)
        self.assertIn("Compose 원문 및 Nginx 설정", template)
        self.assertIn("상태 다시 확인", template)
        self.assertIn("외부에 오픈되는 컨테이너", template)
        self.assertIn("처리 로그 보기", template)

    def test_deploy_status_refresh_and_self_signed_ssl_test_path_are_wired(self):
        view = SERVICES_VIEW.read_text(encoding="utf-8")
        template = SERVICES_TEMPLATE.read_text(encoding="utf-8")
        services = SERVICES_MODEL.read_text(encoding="utf-8")
        deploy = DEPLOY_MODEL.read_text(encoding="utf-8")
        status = STATUS_MODEL.read_text(encoding="utf-8")
        nginx = NGINX_MODEL.read_text(encoding="utf-8")
        nginx_cert = NGINX_CERT_MODEL.read_text(encoding="utf-8")
        config = RUNTIME_CONFIG.read_text(encoding="utf-8")
        commands = (ROOT / "src" / "model" / "struct" / "local_command_catalog.py").read_text(encoding="utf-8")

        self.assertIn("ServiceStatusMixin", services)
        self.assertIn("placement_selector.recommend", services)
        self.assertIn("refresh_deploy_status", deploy)
        self.assertIn("runtime_status", deploy)
        for token in ["service.stack.services", "service.stack.ps", "docker.containers", "def refresh_deploy_status"]:
            self.assertIn(token, status)
        self.assertIn("--no-trunc", commands)
        self.assertIn("def refresh_deploy_status():", SERVICES_API.read_text(encoding="utf-8"))
        self.assertIn("public async refreshRuntimeStatus", view)
        self.assertIn("상태 확인", template)
        self.assertIn("실행 상태", template)
        self.assertIn("runtimeStatusText", view)
        self.assertIn("openssl.self_signed_cert.issue", commands)
        self.assertIn("swarm.nodes.inspect", commands)
        self.assertIn("self_signed_cert_test_enabled", config)
        self.assertIn("service_nginx_certificates", nginx)
        self.assertIn("self_signed_test = certificates.self_signed_test_enabled", nginx)
        self.assertIn("self-signed cert", nginx_cert)
        self.assertIn("def self_signed_test_enabled", nginx_cert)
        self.assertIn("USABLE_CERT_STATUSES", nginx_cert)

    def test_p7_nginx_and_domain_certificate_contract_is_wired(self):
        services_api = SERVICES_API.read_text(encoding="utf-8")
        services_view = SERVICES_VIEW.read_text(encoding="utf-8")
        services_template = SERVICES_TEMPLATE.read_text(encoding="utf-8")
        runtime = (ROOT / "src" / "model" / "struct" / "services_runtime.py").read_text(encoding="utf-8")
        webserver = WEBSERVER_MODEL.read_text(encoding="utf-8")
        domains = DOMAINS_MODEL.read_text(encoding="utf-8")
        domains_view = DOMAINS_VIEW.read_text(encoding="utf-8")
        domains_template = DOMAINS_TEMPLATE.read_text(encoding="utf-8")
        route = DOMAIN_CERT_ROUTE.read_text(encoding="utf-8")

        self.assertIn("def save_nginx_config():", services_api)
        self.assertIn("update_nginx_config", runtime)
        self.assertIn("proxy.nginx.configtest", runtime)
        self.assertIn("nu-monaco-editor", services_template)
        self.assertIn("Compose 원문 및 Nginx 설정", services_template)
        self.assertIn("saveAdvancedEditor", services_view)
        self.assertIn("saveComposeContent", services_view)
        self.assertIn("saveNginxConfig", services_view)
        self.assertIn("chain_file", route)
        self.assertIn("chain_file", domains_view)
        self.assertIn("fullchain.pem", webserver)
        self.assertIn("key_permission_secure", webserver)
        self.assertIn("key_matches", webserver)
        self.assertIn("_service_links", domains)
        self.assertIn("ensure_service_dns_record", domains)
        self.assertIn("domain.record.ensure_service", domains)
        self.assertIn("_ensure_dns_records", NGINX_MODEL.read_text(encoding="utf-8"))
        self.assertIn("dns_records", NGINX_MODEL.read_text(encoding="utf-8"))
        self.assertIn("인증서 적용 서비스", domains_template)
        self.assertIn("certificateKeyText", domains_view)

    def test_certbot_issue_waits_for_runtime_and_exposes_renewal_ops(self):
        deploy = DEPLOY_MODEL.read_text(encoding="utf-8")
        deploy_targets = DEPLOY_TARGETS_MODEL.read_text(encoding="utf-8")
        runtime = (ROOT / "src" / "model" / "struct" / "services_runtime.py").read_text(encoding="utf-8")
        nginx_cert = NGINX_CERT_MODEL.read_text(encoding="utf-8")
        services_certbot = SERVICES_CERTBOT_MODEL.read_text(encoding="utf-8")
        commands = LOCAL_COMMAND_MODEL.read_text(encoding="utf-8")
        config = RUNTIME_CONFIG.read_text(encoding="utf-8")
        services_api = SERVICES_API.read_text(encoding="utf-8")
        services_view = SERVICES_VIEW.read_text(encoding="utf-8")
        services_template = SERVICES_TEMPLATE.read_text(encoding="utf-8")

        self.assertIn("_wait_runtime_ready", deploy)
        self.assertLess(deploy.index("_wait_runtime_ready"), deploy.index("service_nginx.apply"))
        self.assertIn("runtime ready", deploy)
        self.assertIn("current.startswith(\"running\")", deploy_targets)
        self.assertIn("free_certificates", runtime)
        self.assertIn("service_certificates", runtime)
        for token in ["certbot.renew", "certbot.renewal.status", "certbot.renewal.ensure"]:
            self.assertIn(token, commands)
        for token in ["certbot.renew", "certbot.renewal.ensure"]:
            self.assertIn(token, config)
        for token in ["automatic_renewal_status", "ensure_automatic_renewal", "renew_certificate", "manual_renew_enabled"]:
            self.assertIn(token, nginx_cert)
        for token in ["renew_certbot_certificate", "ensure_certbot_renewal", "service.certbot.renew"]:
            self.assertIn(token, services_certbot)
        self.assertIn("def renew_service_certificate():", services_api)
        self.assertIn("def ensure_service_certificate_renewal():", services_api)
        for token in ["freeCertificates", "renewServiceCertificate", "ensureServiceCertificateRenewal", "certificateExpiresText", "certificateAutoRenewText"]:
            self.assertIn(token, services_view)
        for token in ["무료 SSL 인증서", "수동 갱신", "자동 설정"]:
            self.assertIn(token, services_template)


if __name__ == "__main__":
    unittest.main()
