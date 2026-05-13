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
DOMAINS_MODEL = ROOT / "src" / "model" / "struct" / "domains.py"
DOMAINS_VIEW = ROOT / "src" / "app" / "page.domains" / "view.ts"
DOMAINS_TEMPLATE = ROOT / "src" / "app" / "page.domains" / "view.pug"
DOMAIN_CERT_ROUTE = ROOT / "src" / "route" / "api-domain-certificates" / "controller.py"
WEBSERVER_MODEL = ROOT / "src" / "model" / "struct" / "webserver.py"
RUNTIME_CONFIG = ROOT / "config" / "docker_infra.py"


class ServicesPreflightStaticContractTest(unittest.TestCase):
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
        self.assertIn("server_compose_import", view)
        self.assertIn("Compose 직접 작성", template)
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
        for token in ["_complete_service_multiphase", "_service_plan_system_prompt", "_inspect_service_plan", "_service_review_system_prompt", "docker_infra_inspection", "repair_runtime", "runtime_diagnostics", "form.domains", "_assert_ai_runtime_compose_contract", "AI_RUNTIME_COMPOSE_CONTRACT_FAILED", "Do not use *_FILE"]:
            self.assertIn(token, assistant)
        for token in ["_runtime_issue_signals", "_client_failed_operations", "_merge_runtime_operations", "client_runtime_issues", "terminal_actions", "container_action", "operator_message", "service_status", "failed_operations", "stack_replicas", "containers_stopped", "stream_runtime_repair", "runtime_actions", "terminal_action_results", "_execute_runtime_actions", "start_runtime_verification", "_runtime_verification_worker", "_wait_runtime_ready", "_runtime_snapshot_blocked", "_runtime_snapshot_key", "AI_VERIFY_UNCHANGED_BLOCKED_ATTEMPTS", "동일한 상태 확인 로그", "다음 검증 시도", "verify_runtime", "service.ai.verify"]:
            self.assertIn(token, assistant)
        for token in ["runtimeIssueSnapshot", "client_runtime_issues", "runtimeIssueOperations", "runtimeAiIntent", "runtimeAiAllowContainerActions", "allow_container_terminal_actions", "allow_ssh_command", "submitRuntimeAiRepair", "start_runtime_ai_verification", "activeBackgroundOperation", "service.ai.verify", "editOperatorComment", "operator_comment", "doneSeen", "완료 이벤트 없이 종료"]:
            self.assertIn(token, services_view)
        for token in ["infra_context", "docker_image_check", "server_port_check", "container_logs", "container_action", "service_stack_status", "dns_lookup", "tcp_connect_check", "http_probe", "server_collect", "ssh_command"]:
            self.assertIn(token, codex_runtime)
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
        self.assertIn("domains", (ROOT / "src" / "model" / "struct" / "services_update.py").read_text(encoding="utf-8"))
        self.assertIn("ai_runtime_repair", SERVICES_API.read_text(encoding="utf-8"))
        self.assertIn("stream_runtime_ai_repair", SERVICES_API.read_text(encoding="utf-8"))
        self.assertIn("start_runtime_ai_verification", SERVICES_API.read_text(encoding="utf-8"))
        self.assertIn("start_ai_verification", deploy)
        self.assertNotIn("start_ai_verification: true", view)
        self.assertNotIn("start_ai_verification: true", SERVICES_VIEW.read_text(encoding="utf-8"))
        self.assertIn("start_runtime_ai_verification", SERVICES_VIEW.read_text(encoding="utf-8"))
        self.assertIn("runRuntimeAiRepair", SERVICES_VIEW.read_text(encoding="utf-8"))
        self.assertIn("AI 검사/수정", SERVICES_TEMPLATE.read_text(encoding="utf-8"))
        self.assertIn("AI 자동 조치 허용", SERVICES_TEMPLATE.read_text(encoding="utf-8"))
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

        for token in ["runtimeServerSummaryText", "certificateSummaryText", "serviceIssue", "runtimeContainerRows", "runRuntimeContainerAction", "detailTabs", "serviceFlowPaths"]:
            self.assertIn(token, view)
        self.assertIn("flow_model.build", api)
        self.assertIn("service_flow", api)
        self.assertIn("def service_container_action():", api)
        self.assertIn("target_node_id", api)
        self.assertIn("container.node_id", view)
        for token in ["class ServicesFlow", "depends_on", "public_paths", "internal_targets", "nginx"]:
            self.assertIn(token, flow)
        self.assertIn("서버 / 인증서", template)
        self.assertIn("접속 흐름", template)
        self.assertIn("처리 로그", template)
        self.assertIn("백업", template)
        self.assertIn("고급 관리", template)
        self.assertIn("상태 다시 확인", template)
        self.assertIn("실행 구성요소", template)
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
        self.assertIn("원문 설정", services_template)
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


if __name__ == "__main__":
    unittest.main()
