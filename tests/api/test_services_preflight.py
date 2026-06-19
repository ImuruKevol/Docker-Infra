import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
CREATE_API = ROOT / "src" / "app" / "page.services.create" / "api.py"
CREATE_VIEW = ROOT / "src" / "app" / "page.services.create" / "view.ts"
CREATE_TEMPLATE = ROOT / "src" / "app" / "page.services.create" / "view.pug"
TEMPLATES_API = ROOT / "src" / "app" / "page.templates" / "api.py"
TEMPLATES_VIEW = ROOT / "src" / "app" / "page.templates" / "view.ts"
TEMPLATES_TEMPLATE = ROOT / "src" / "app" / "page.templates" / "view.pug"
SERVERS_VIEW = ROOT / "src" / "app" / "page.servers" / "view.ts"
SERVERS_TEMPLATE = ROOT / "src" / "app" / "page.servers" / "view.pug"
SERVICES_API = ROOT / "src" / "app" / "page.services" / "api.py"
SERVICES_VIEW = ROOT / "src" / "app" / "page.services" / "view.ts"
SERVICES_TEMPLATE = ROOT / "src" / "app" / "page.services" / "view.pug"
SERVICES_SOCKET = ROOT / "src" / "app" / "page.services" / "socket.py"
PREFLIGHT_MODEL = ROOT / "src" / "model" / "struct" / "services_preflight.py"
SERVICES_MODEL = ROOT / "src" / "model" / "struct" / "services.py"
NODES_TERMINAL_MODEL = ROOT / "src" / "model" / "struct" / "nodes_terminal.py"
UPDATE_MODEL = ROOT / "src" / "model" / "struct" / "services_update.py"
RELEASE_MODEL = ROOT / "src" / "model" / "struct" / "services_release.py"
ROLLBACK_MODEL = ROOT / "src" / "model" / "struct" / "services_rollback.py"
RUNTIME_MODEL = ROOT / "src" / "model" / "struct" / "services_runtime.py"
SNAPSHOT_RUNNER_MODEL = ROOT / "src" / "model" / "struct" / "service_image_snapshot_runner.py"
STATUS_MODEL = ROOT / "src" / "model" / "struct" / "services_status.py"
FLOW_MODEL = ROOT / "src" / "model" / "struct" / "services_flow.py"
WIZARD_MODEL = ROOT / "src" / "model" / "struct" / "services_wizard.py"
TEMPLATES_MODEL = ROOT / "src" / "model" / "struct" / "templates.py"
TEMPLATES_SEED_MODEL = ROOT / "src" / "model" / "struct" / "templates_seed.py"
TEMPLATE_AI_MODEL = ROOT / "src" / "model" / "struct" / "template_ai.py"
AI_ASSISTANT_MODEL = ROOT / "src" / "model" / "struct" / "ai_assistant.py"
AI_SETTINGS_MODEL = ROOT / "src" / "model" / "struct" / "ai_settings.py"
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
            {"jsonrpc": "2.0", "id": 5, "method": "resources/read", "params": {"uri": "docker-infra://mcp/contract"}},
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
        self.assertEqual(by_id[3]["result"]["resources"][0]["uri"], "docker-infra://mcp/contract")
        infra_context = json.loads(by_id[4]["result"]["content"][0]["text"])
        self.assertEqual(infra_context["ai_request_summary"]["mode"], "test")
        self.assertEqual(infra_context["request_context_keys"], ["mode"])
        self.assertEqual(infra_context["mcp_contract"]["permission_mode"], "agent_full_control_except_critical_destruction")
        contract = json.loads(by_id[5]["result"]["contents"][0]["text"])
        self.assertEqual(contract["permission_mode"], "agent_full_control_except_critical_destruction")
        self.assertIn("ssh_command", [tool["name"] for tool in contract["tools"]])
        self.assertEqual(contract["volume_destruction_policy"]["default"], "blocked")
        self.assertIn("docker compose down --volumes", json.dumps(contract, ensure_ascii=False))

    def test_docker_infra_mcp_blocks_persistent_volume_deletion_by_default(self):
        spec = importlib.util.spec_from_file_location("docker_infra_mcp_policy_test", DOCKER_INFRA_MCP)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        module.CONTEXT = {}
        self.assertEqual(module.critical_command_violation("docker restart app_container"), "")
        self.assertEqual(module.critical_command_violation("docker compose -p app -f docker-compose.yaml down"), "")
        self.assertIn("OS critical command", module.critical_command_violation("reboot"))
        self.assertIn(
            "Docker Infra protected path",
            module.critical_command_violation("rm -rf /root/docker-infra/project/main/src"),
        )
        for command in [
            "docker compose -p app -f docker-compose.yaml down --volumes",
            "docker-compose -p app down -v",
            "docker volume rm app_data",
            "docker volume prune -f",
            "docker system prune --volumes -f",
        ]:
            with self.subTest(command=command):
                self.assertIn("Persistent Docker volume deletion", module.critical_command_violation(command))
        module.CONTEXT = {"ai_permission_scope": {"allow_volume_destruction": True}}
        self.assertEqual(
            module.critical_command_violation("docker compose -p app -f docker-compose.yaml down --volumes"),
            "",
        )

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
        ddns = (ROOT / "src" / "model" / "struct" / "domains_ddns.py").read_text(encoding="utf-8")
        config = RUNTIME_CONFIG.read_text(encoding="utf-8")

        self.assertIn("def preflight():", api)
        self.assertIn("deploy_service_background", api)
        self.assertIn("wizard.preflight", api)
        self.assertIn("public async runPreflight", view)
        self.assertIn("deploy_service_background", view)
        self.assertIn("createCheck().open", template)
        self.assertIn("this.service.href(serviceId ? this.serviceDetailRoute(serviceId) : '/services')", view)
        for token in ["editableTemplateFields", "isManagedTemplateField", "generateTemplateSecret", "shouldGenerateTemplateSecret", "mergeGeneratedSecretKeys"]:
            self.assertIn(token, view)
        for token in ['*ngFor="let field of editableTemplateFields()"', "변수 {{editableTemplateFields().length}}개", "자동 생성된 기본값입니다."]:
            self.assertIn(token, template)
        self.assertNotIn('*ngFor="let field of templateFields()"', template)
        self.assertIn("services_preflight", wizard)
        self.assertIn("SERVICE_PREFLIGHT_BLOCKED", wizard)
        self.assertIn('"mode": "host"', wizard)
        self.assertIn("_rewrite_internal_service_ref", wizard)
        self.assertIn("return _rewrite_internal_service_ref(content, namespace, service_names)", wizard)
        for token in ["_check_placement", "_check_images", "_check_volumes", "_check_ports", "_check_domain", "_remote_port_usage"]:
            self.assertIn(token, preflight)
        self.assertIn("def preview_content", ports)
        for token in ["PortCheckError", "REMOTE_PORT_FREE_SCRIPT", "_is_free_on_node", "nodes_model._run_ssh_command", "REMOTE_PORT_CHECK_FAILED", "def allocate_file(self, compose_path, node=None, env=None)"]:
            self.assertIn(token, ports)
        self.assertNotIn('if result.get("status") != "ok":\n            return _is_free(port)', ports)
        self.assertNotIn("except Exception:\n        return _is_free(port)", ports)
        self.assertIn("_sync_domain_published_ports", deploy)
        self.assertIn("_record_deploy_adjustments", deploy)
        self.assertIn("_apply_stack_placement", deploy)
        self.assertIn('service_ports.allocate_file(compose_path, node=placement.get("node"), env=env)', deploy)
        self.assertIn("배포 서버의 공개 포트를 확인할 수 없습니다.", deploy)
        self.assertIn("deployment node unavailable", deploy)
        self.assertIn("node.id ==", deploy)
        self.assertIn("deploy_adjustments", deploy)
        self.assertIn("placement_selector.recommend", deploy)
        for token in ["least_loaded_resource_score", "cpu_percent", "memory_used_percent", "storage_used_percent", "containers"]:
            self.assertIn(token, placement)
        for token in ["swarm.nodes", "swarm_ready", "swarm_hostname_mismatch", "swarm_availability", "selectable"]:
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
        self.assertIn("domain.ddns.endpoint", preflight)
        self.assertIn("DDNS_SERVICE_ENDPOINT_NOT_MATCHED", ddns)
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

    def _load_ports_module(self):
        class FakeStruct:
            nodes = object()

        class FakeWiz:
            def model(self, name):
                if name == "struct":
                    return FakeStruct()
                raise AssertionError(f"unexpected model: {name}")

        spec = importlib.util.spec_from_file_location("services_ports_contract", PORTS_MODEL)
        module = importlib.util.module_from_spec(spec)
        module.wiz = FakeWiz()
        spec.loader.exec_module(module)
        return module

    def test_service_port_allocation_avoids_well_known_published_ports(self):
        ports_module = self._load_ports_module()
        checked = []

        def fake_is_free_on_node(port, node=None, env=None):
            checked.append(port)
            return True

        ports_module._is_free_on_node = fake_is_free_on_node
        plan = ports_module.Model.preview_content("""
services:
  ssh:
    image: linuxserver/openssh-server:latest
    ports:
      - "22"
  web:
    image: nginx:alpine
    ports:
      - "80:80"
  admin:
    image: example/admin:latest
    ports:
      - target: 443
        published: 443
        protocol: tcp
        mode: host
""")

        allocations = plan["allocations"]
        self.assertEqual([item["previous"] for item in allocations], [22, 80, 443])
        self.assertEqual([item["published"] for item in allocations], [49152, 49153, 49154])
        self.assertTrue(all(item["published"] > ports_module.WELL_KNOWN_PORT_MAX for item in allocations))
        self.assertTrue(all(item.get("reason") == "well_known_reserved" for item in allocations))
        self.assertEqual(plan["compose"]["services"]["ssh"]["ports"], ["49152:22"])
        self.assertEqual(plan["compose"]["services"]["web"]["ports"], ["49153:80"])
        self.assertEqual(plan["compose"]["services"]["admin"]["ports"][0]["published"], 49154)
        self.assertEqual(checked[:3], [49152, 49153, 49154])

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

    def test_service_create_supports_templates_and_draft_sources(self):
        api = CREATE_API.read_text(encoding="utf-8")
        view = CREATE_VIEW.read_text(encoding="utf-8")
        template = CREATE_TEMPLATE.read_text(encoding="utf-8")
        templates_api = TEMPLATES_API.read_text(encoding="utf-8")
        templates_view = TEMPLATES_VIEW.read_text(encoding="utf-8")
        templates_template = TEMPLATES_TEMPLATE.read_text(encoding="utf-8")
        templates_model = TEMPLATES_MODEL.read_text(encoding="utf-8")
        templates_seed = TEMPLATES_SEED_MODEL.read_text(encoding="utf-8")
        template_ai = TEMPLATE_AI_MODEL.read_text(encoding="utf-8")
        wizard = WIZARD_MODEL.read_text(encoding="utf-8")
        assistant = AI_ASSISTANT_MODEL.read_text(encoding="utf-8")
        ai_settings = AI_SETTINGS_MODEL.read_text(encoding="utf-8")
        codex_runtime = CODEX_RUNTIME_MODEL.read_text(encoding="utf-8")
        mcp = DOCKER_INFRA_MCP.read_text(encoding="utf-8")
        deploy = DEPLOY_MODEL.read_text(encoding="utf-8")
        local_commands = LOCAL_COMMAND_MODEL.read_text(encoding="utf-8")

        self.assertIn("def prepare_compose_draft():", api)
        self.assertIn("def template_detail():", api)
        self.assertIn("def prepare_template_draft():", api)
        self.assertIn("prepare_manual", api)
        self.assertIn("public async applyManualCompose", view)
        self.assertIn("public async applyTemplateDraft", view)
        self.assertIn("public nextStepLabel", view)
        self.assertIn("public nextStepBusy", view)
        self.assertIn("this.creationMode.set('template')", view)
        self.assertIn("템플릿 기반 생성만 사용할 수 있습니다.", view)
        self.assertIn("await this.applyTemplateDraft({ advance: false, showSuccess: false })", view)
        self.assertIn("public async generateServiceWithAi", view)
        self.assertIn("public async applyManualCompose", view)
        self.assertIn("applyComposeDraft", view)
        self.assertIn("draft_metadata", view)
        self.assertIn("draftSourceRef", view)
        self.assertIn("compose_template", view)
        self.assertIn("manual_compose", view)
        self.assertIn("manualComposeEditorOptions", view)
        self.assertIn("templateSelectorItems", view)
        self.assertIn("selectedTemplateId", view)
        self.assertIn("selectedTemplateReadme", view)
        self.assertIn("creationModeCards", view)
        self.assertIn("selectCreationMode", view)
        self.assertIn("템플릿 기반", view)
        self.assertIn("readmeOpen", view)
        self.assertIn("const detailRows = Array.isArray(data?.details) ? data.details : []", view)
        self.assertIn("[data?.reason, ...detailRows]", view)
        self.assertIn("manualComposeOpen.set(true)", view)
        self.assertIn("hasAiModels()", view)
        self.assertIn("server_compose_import", view)
        for token in ["템플릿 선택", "기본 정보", "템플릿 변수", "도메인 설정", "생성 요약", "DDNS 사용"]:
            self.assertIn(token, template)
        self.assertIn("{{createButtonLabel()}}", template)
        self.assertIn("createBusy()", template)
        self.assertIn("createButtonIconClass()", template)
        self.assertIn("selectedTemplateReadme()", template)
        self.assertIn("createCheck().open", template)
        self.assertIn('(click)="save(true)"', template)
        self.assertNotIn("AI 자동 구성", template)
        self.assertNotIn("Compose 직접 작성", template)
        self.assertNotIn("creationMode() === 'ai' && hasAiModels()", template)
        self.assertNotIn("creationMode() === 'manual'", template)
        self.assertIn("class Templates", templates_model)
        self.assertIn("prepare_service_draft", templates_model)
        self.assertIn("values.schema.json", templates_model)
        self.assertIn("readme_excerpt", templates_model)
        self.assertIn("def _compose_validator()", templates_model)
        self.assertIn("def _services_wizard()", templates_model)
        self.assertIn("ComposeValidationError = compose_rules.ComposeValidationError", templates_model)
        self.assertNotIn("services_wizard = wiz.model(\"struct/services_wizard\")", templates_model)
        self.assertNotIn("validator = wiz.model(\"struct/compose_validator\")", templates_model)
        self.assertIn("def _is_template_source", wizard)
        self.assertIn("source_ref.get(\"source\") == \"compose_template\"", wizard)
        self.assertIn("self._is_template_source(body)", wizard)
        self.assertIn("TEMPLATE_README_REQUIRED", templates_model)
        self.assertIn("DELETED_SEEDS_FILENAME", templates_model)
        self.assertIn("_deleted_seed_namespaces", templates_model)
        self.assertIn("_mark_deleted_seed(namespace", templates_model)
        self.assertIn("_unmark_deleted_seed(namespace", templates_model)
        ensure_defaults_start = templates_model.index("def ensure_defaults")
        self.assertLess(
            templates_model.index("deleted_seeds = _deleted_seed_namespaces(root)", ensure_defaults_start),
            templates_model.index("for item in _seed_templates():", ensure_defaults_start),
        )
        self.assertIn("if namespace in deleted_seeds:", templates_model)
        self.assertIn("WIZ Framework 개발환경", templates_seed)
        self.assertIn('"tags": tags', templates_seed)
        self.assertIn("templates_model.load_summaries", templates_api)
        self.assertIn("def save_template():", templates_api)
        self.assertIn("def preview_template():", templates_api)
        self.assertIn("def ai_model_options():", templates_api)
        self.assertIn("def ai_contract():", templates_api)
        self.assertIn("payload = ai_settings.model_options()", templates_api)
        self.assertIn("payload = {\"contract\": template_ai.template_contract()}", templates_api)
        self.assertIn("def stream_template_ai():", templates_api)
        self.assertIn("COMPOSE_TEMPLATE_MCP_TOOLS", template_ai)
        self.assertIn('"port_rules"', template_ai)
        self.assertIn("services.<name>.ports", template_ai)
        self.assertIn("\"can_run_ssh_command\": True", template_ai)
        self.assertIn("\"permission_mode\": \"agent_full_control_except_critical_destruction\"", template_ai)
        self.assertIn("public useTemplate", templates_view)
        self.assertIn("activeEditorOptions", templates_view)
        self.assertIn("setActiveTab", templates_view)
        self.assertIn("detailCache", templates_view)
        self.assertIn("handleTagKeydown", templates_view)
        self.assertIn("loadAiContract", templates_view)
        self.assertIn("loadAuxiliaryData", templates_view)
        self.assertIn("selectInitialTemplate", templates_view)
        self.assertIn("templateAiModalOpen", templates_view)
        self.assertIn("newTemplateMode", templates_view)
        self.assertIn("cloneSourceId", templates_view)
        self.assertIn("cloneTemplateOptions", templates_view)
        self.assertIn("chooseNewTemplateMode", templates_view)
        self.assertIn("showTemplateEditor", templates_view)
        self.assertIn("removeDeletedTemplateFromList", templates_view)
        self.assertIn("upsertSavedTemplate", templates_view)
        self.assertIn("templateSummaryFromDetail", templates_view)
        self.assertIn("templateStandardGuide", templates_view)
        self.assertIn("templateAiTargetRows", templates_view)
        self.assertIn("Compose 탭 표준", templates_view)
        self.assertIn("기본값 탭 표준", templates_view)
        self.assertIn("Schema 탭 표준", templates_view)
        self.assertIn("generateTemplateWithAi", templates_view)
        self.assertIn("streamTemplateAi", templates_view)
        self.assertIn("Compose 템플릿", templates_template)
        self.assertIn("작성 방식을 선택하세요.", templates_template)
        self.assertIn("AI로 초안 작성", templates_template)
        self.assertIn("직접 작성", templates_template)
        self.assertIn("기반 템플릿", templates_template)
        self.assertIn("AI 템플릿 초안", templates_template)
        self.assertIn('*ngIf="newTemplateMode() === \'ai\' && !newTemplateDraftReady()"', templates_template)
        self.assertIn('*ngIf="showTemplateEditor()"', templates_template)
        self.assertIn("AI 수정/점검", templates_template)
        self.assertNotIn("AI 허용 범위", templates_template)
        self.assertIn("AI로 초안 만들기", templates_template)
        self.assertIn("입력 후 Enter", templates_template)
        self.assertNotIn("대표 이미지", templates_template)
        self.assertNotIn("[(ngModel)]=\"form.description\"", templates_template)
        self.assertIn('[options]="activeEditorOptions"', templates_template)
        self.assertIn("template_contract", assistant)
        self.assertIn("template_ai_policy", assistant)
        self.assertIn("AI_TEMPLATE_PUBLIC_PORT_REQUIRED", assistant)
        self.assertIn("_validate_template_public_ports", assistant)
        self.assertIn('"compose_template"', assistant)
        self.assertIn('"can_save_template": False', assistant)
        self.assertIn('"blocked_action_families"', assistant)
        self.assertIn('"placeholder_format": "{{ variable_name }}"', assistant)
        self.assertIn("stream_template", assistant)
        self.assertIn("AI_TEMPLATE_README_REQUIRED", assistant)
        remove_start = templates_view.index("public async remove()")
        remove_end = templates_view.index("public async runPreview()", remove_start)
        remove_block = templates_view[remove_start:remove_end]
        self.assertIn("removeDeletedTemplateFromList(id)", remove_block)
        self.assertNotIn("await this.load", remove_block)
        save_start = templates_view.index("public async save()")
        save_end = templates_view.index("public async remove()", save_start)
        save_block = templates_view[save_start:save_end]
        self.assertIn("this.upsertSavedTemplate(data.template || {})", save_block)
        self.assertNotIn("await this.load", save_block)
        self.assertNotIn("await this.selectTemplate", save_block)
        self.assertIn("COMPOSE_TEMPLATE_MCP_TOOLS", codex_runtime)
        self.assertIn('"compose_template": COMPOSE_TEMPLATE_MCP_TOOLS', codex_runtime)
        self.assertIn("SERVICE_DRAFT_REQUIRED", wizard)
        self.assertIn("def prepare_manual", wizard)
        self.assertIn("draft_metadata", wizard)
        self.assertIn('"draft"', (ROOT / "src" / "model" / "struct" / "services.py").read_text(encoding="utf-8"))
        services_view = SERVICES_VIEW.read_text(encoding="utf-8")
        services_template = SERVICES_TEMPLATE.read_text(encoding="utf-8")
        services_api = SERVICES_API.read_text(encoding="utf-8")
        services_runtime = RUNTIME_MODEL.read_text(encoding="utf-8")
        snapshot_runner = SNAPSHOT_RUNNER_MODEL.read_text(encoding="utf-8")
        self.assertIn("versionSourceLabel", services_view)
        self.assertIn("versionDraftText", services_view)
        self.assertIn("versionSourceLabel(version)", services_template)
        self.assertIn("openReleaseModal", services_view)
        self.assertIn('(click)="openReleaseModal()"', services_template)
        self.assertIn("수동 릴리즈한 버전만 이력에 남고", services_view)
        self.assertNotIn("백업 저장소에 백업이 있으면 이미지 참조도 함께 반영", services_template)
        self.assertNotIn("Harbor 백업", services_template)
        self.assertIn("잠깐 일시 정지", services_view)
        self.assertIn("pause: true", services_view)
        self.assertIn("background: true", services_view)
        self.assertIn("openOperationModal(data.operation)", services_view)
        self.assertIn("service.image.snapshot", services_view)
        self.assertIn("snapshotBackupErrorMessage", services_view)
        self.assertIn("versionSnapshotBackupCount(version)", services_template)
        self.assertIn("image_backup_summary", services_runtime)
        self.assertIn('source=payload.get("source") or "manual_snapshot"', services_runtime)
        self.assertIn("snapshot_service_image_async", services_runtime)
        self.assertIn("progress_operation_id", services_runtime)
        self.assertIn("_is_service_error_like", services_runtime)
        self.assertIn("_service_error_response", services_api)
        self.assertIn("runtime[len(prefix):]", snapshot_runner)
        self.assertIn("generated_secret_keys", assistant)
        for token in ["_complete_service_multiphase", "_service_plan_system_prompt", "_inspect_service_plan", "_service_review_system_prompt", "docker_infra_inspection", "repair_runtime", "runtime_diagnostics", "form.domains", "_assert_ai_runtime_compose_contract", "AI_RUNTIME_COMPOSE_CONTRACT_FAILED", "Do not use *_FILE", "can_select_ddns_domains", "can_register_ddns_records_via_deploy", "can_inspect_ddns_domains", "ddns_endpoint_id", "wildcard_suffix", "domain_provider_policy", "ddns_registration_flow", "ddns_repair_suggestion", "_service_zones_for_ai", "_ddns_repair_suggestion", "_ddns_verification_fallback_data", "_ddns_repair_fallback_data", "_ddns_direct_verification_data", "_ddns_direct_repair_data", "_compact_runtime_status", "_compact_recent_operations", "_register_ddns_after_ai_update", "_ddns_register_summary_text", "ddns_register_result", "_apply_ddns_repair_fallback", "_service_warnings", "_is_stale_ddns_registration_warning", "_ddns_child_domain", "_ddns_default_prefix", "never use sub.nanoha.kr itself as the service domain"]:
            self.assertIn(token, assistant)
        self.assertIn('"can_register_ddns_records_via_deploy": True', assistant)
        self.assertIn("Do not warn that requested DDNS subdomains are unregistered", assistant)
        self.assertIn("never remove all public domains just because the DDNS record is not registered yet", assistant)
        self.assertIn("AI 수정 호출 실패로 DDNS deterministic fallback", assistant)
        self.assertIn("기존 DDNS 등록 정보와 공인 IP가 같아 DDNS API 호출은 생략되었습니다.", assistant)
        for token in ["has_enabled_models", "시스템 설정에서 사용 중인 AI Agent가 없습니다."]:
            self.assertIn(token, ai_settings)
        for token in ["default_agent", "enabled_agent_count", "기본 AI Agent는 사용 중인 Agent 중에서 선택하세요."]:
            self.assertIn(token, ai_settings)
        for token in ["선택한 AI Agent를 사용하려면 시스템 설정에서 먼저 사용 설정하세요.", "AI_PROVIDER_NOT_CONFIGURED", "default_agent = self._default_model_ref(config)"]:
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
        for token in ["MCP_PERMISSION_MODE", "AGENT_FULL_CONTROL_MCP_TOOLS", "agent_full_control_except_critical_destruction", "danger-full-access"]:
            self.assertIn(token, codex_runtime)
        for token in ["_prompt_context", "_semantic_prompt_context", "PROMPT_CONTEXT_CHAR_BUDGET", "context_delivery", "ai_request_summary", "request_context_keys", "large Docker Infra runtime data is kept out of the prompt"]:
            self.assertIn(token, codex_runtime)
        for token in ["ai_request_summary", "request_context_keys", "compact AI request summary"]:
            self.assertIn(token, mcp)
        for token in ["mcp_contract", "critical_command_violation", "MCP_CONTRACT_URI", "agent_full_control_except_critical_destruction", "Docker Infra control containers are protected"]:
            self.assertIn(token, mcp)
        self.assertIn("create_session_id", wizard)
        self.assertIn("_existing_create_session", wizard)
        self.assertIn("createSessionId", view)
        self.assertIn("createdServiceId", view)
        for token in ["_active_deploy_operation", "deduplicated"]:
            self.assertIn(token, deploy)
        self.assertIn("--prune", local_commands)
        for token in ["AGENT_TYPES", "claude_code", "hermes", "_run_agent", "_agent_mcp_config", "_render_agent_command", "docker_infra MCP"]:
            self.assertIn(token, codex_runtime)
        for token in ["_run_direct_api", "_complete_openai_api", "_complete_gemini_api", "_complete_ollama_api", "_direct_api_prompt_context", "embedded_direct_api"]:
            self.assertNotIn(token, codex_runtime)
        self.assertIn("domains", wizard)
        services_update = (ROOT / "src" / "model" / "struct" / "services_update.py").read_text(encoding="utf-8")
        self.assertIn("domains", services_update)
        self.assertIn("DDNS_ENDPOINT_REQUIRED", services_update)
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
        self.assertIn("compose_template: 'Compose 템플릿'", SERVICES_VIEW.read_text(encoding="utf-8"))

    def test_seed_template_delete_persists_across_default_reload(self):
        class FakeConfig:
            def __init__(self, root):
                self.root = root

            def data_dir(self, env=None):
                return str(self.root)

        class FakeSeed:
            def default_templates(self):
                return [
                    {
                        "name": "Seed One",
                        "namespace": "seed_one",
                        "enabled": True,
                        "metadata": {"tags": ["seed"]},
                        "files": {
                            "docker-compose.yaml": "services:\n  app:\n    image: nginx:alpine\n",
                            "values.default.yaml": "namespace: seed_one\n",
                            "values.schema.json": json.dumps({"type": "object", "properties": {}}),
                            "README.md": "# Seed One\n",
                        },
                    }
                ]

        class FakeValidator:
            class ComposeValidationError(Exception):
                pass

            def validate(self, payload):
                return {"ok": True}

        class FakeWiz:
            def __init__(self, root):
                self._config = FakeConfig(root)
                self._seed = FakeSeed()
                self._validator = FakeValidator()

            def config(self, name):
                return self._config

            def model(self, name):
                if name == "struct/templates_seed":
                    return self._seed
                if name == "struct/compose_rules":
                    return self._validator
                if name == "struct/compose_validator":
                    return self._validator
                return object()

        with tempfile.TemporaryDirectory() as tmpdir:
            spec = importlib.util.spec_from_file_location("templates_delete_test", TEMPLATES_MODEL)
            module = importlib.util.module_from_spec(spec)
            module.wiz = FakeWiz(Path(tmpdir))
            spec.loader.exec_module(module)

            templates = module.Model
            self.assertEqual([item["namespace"] for item in templates.load()["templates"]], ["seed_one"])

            templates.delete("seed_one")
            self.assertEqual(templates.load()["templates"], [])
            tombstone = Path(templates.root()) / module.DELETED_SEEDS_FILENAME
            self.assertIn("seed_one", json.loads(tombstone.read_text(encoding="utf-8"))["namespaces"])

            templates.save(
                {
                    "namespace": "seed_one",
                    "name": "Seed One Custom",
                    "enabled": True,
                    "metadata": {"tags": ["custom"]},
                    "files": {
                        "compose": "services:\n  app:\n    image: nginx:alpine\n",
                        "values_default": "namespace: seed_one\n",
                        "values_schema": json.dumps({"type": "object", "properties": {}}),
                        "readme": "# Seed One Custom\n",
                    },
                }
            )
            self.assertEqual([item["name"] for item in templates.load()["templates"]], ["Seed One Custom"])
            self.assertFalse(tombstone.exists())

    def test_service_management_hides_ambiguous_lifecycle_status(self):
        view = SERVICES_VIEW.read_text(encoding="utf-8")
        template = SERVICES_TEMPLATE.read_text(encoding="utf-8")

        self.assertIn("return '다시 적용';", view)
        self.assertNotIn("실행 기준", template)
        self.assertIn("runtimeContainerSummary", view)
        self.assertEqual(template.count('(click)="deploySelectedService()"'), 1)
        self.assertEqual(template.count('(click)="openReleaseModal()"'), 1)
        self.assertEqual(template.count('(click)="openMigrationModal()"'), 1)
        self.assertLess(template.index("detailTab() === 'versions'"), template.index('(click)="openReleaseModal()"'))
        self.assertLess(template.index("detailTab() === 'versions'"), template.index('(click)="openMigrationModal()"'))
        self.assertLess(template.index('(click)="openReleaseModal()"'), template.index("versionSourceLabel(version)"))
        self.assertLess(template.index('(click)="openMigrationModal()"'), template.index("versionSourceLabel(version)"))
        self.assertNotIn("statusClass(item.status)", template)
        self.assertNotIn("statusLabel(item.status)", template)
        self.assertNotIn("statusClass(detail()?.service?.status)", template)
        self.assertNotIn("statusLabel(detail()?.service?.status)", template)
        self.assertNotIn("서비스 적용", view)
        self.assertNotIn("서비스 적용", template)
        self.assertNotIn("준비 중", view)
        self.assertNotIn("준비 중", template)

    def test_service_list_container_and_port_columns_are_wired(self):
        view = SERVICES_VIEW.read_text(encoding="utf-8")
        template = SERVICES_TEMPLATE.read_text(encoding="utf-8")

        self.assertIn("컨테이너", template)
        self.assertIn("포트", template)
        self.assertIn("serviceListContainers(item)", template)
        self.assertIn("serviceListPortBadges(item)", template)
        self.assertIn("serviceListPortEmptyText(item)", template)
        self.assertIn("serviceListContainerEmptyText(item)", template)
        self.assertNotIn('th(class="w-44 px-4 py-2 text-left font-semibold") 버전', template)
        for token in ["serviceRuntimeStatus", "serviceListContainers", "serviceListContainerName", "serviceExternalPortLabels", "serviceListPortBadges", "serviceListPortEmptyText"]:
            self.assertIn(token, view)
        self.assertIn("badges.push(`${name}: ${port}`)", view)
        self.assertIn("containerNameSortKey", view)
        self.assertIn("compareContainersByName(a, b, namespace)", view)
        self.assertIn(".sort((a: any, b: any) => this.compareContainersByName(a, b, namespace))", view)

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
        self.assertIn("public returnBasicEditMode", view)
        self.assertIn("editLoading = signal", view)
        self.assertLess(view.index("this.editModalOpen.set(true)"), view.index("await this.loadDetailSection('source')"))
        self.assertIn("editOperatorComment", view)
        self.assertIn("operator_comment", view)
        self.assertIn("operator_comment", update)
        self.assertIn("서비스 수정", template)
        self.assertIn('(click)="returnBasicEditMode()"', template)
        self.assertIn("span 간편 수정", template)
        self.assertIn("수정 정보를 불러오는 중입니다.", template)
        self.assertIn('editBusy() || editLoading()', template)
        self.assertIn("추가 코멘트", template)
        self.assertIn("ServiceUpdateMixin", services)
        for token in ["def update_wizard", "service_domains", "SERVICE_PREFLIGHT_BLOCKED", "last_update"]:
            self.assertIn(token, update)
        self.assertNotIn("INSERT INTO compose_versions", update)

    def test_service_release_contract_is_wired(self):
        api = SERVICES_API.read_text(encoding="utf-8")
        view = SERVICES_VIEW.read_text(encoding="utf-8")
        template = SERVICES_TEMPLATE.read_text(encoding="utf-8")
        services = SERVICES_MODEL.read_text(encoding="utf-8")
        release = RELEASE_MODEL.read_text(encoding="utf-8")

        self.assertIn("def release_service():", api)
        self.assertIn("services_model.release", api)
        self.assertIn("snapshot_service_image_async", api)
        self.assertIn("public openReleaseModal", view)
        self.assertIn("public async runRelease", view)
        self.assertIn("수동 릴리즈", template)
        self.assertIn("Compose만 릴리즈", template)
        self.assertIn("스냅샷도 백업", template)
        self.assertIn("ServiceReleaseMixin", services)
        for token in ["def release", "INSERT INTO compose_versions", "manual_release", "service.compose.release"]:
            self.assertIn(token, release)

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
        for token in ["def delete", "_managed_nginx_delete_path", "_remove_volumes", "_remove_dns_records", "delete_service_dns_records", "SERVICE_DNS_RECORD_REMOVE_FAILED", "service.stack.remove", "service.stack.volumes.remove", "service.compose.down", "compose_down_removed_volumes", "--volumes", "com.docker.compose.project", "proxy.nginx.configtest", "proxy.nginx.reload", "DDNS unregister warning"]:
            self.assertIn(token, delete_model)
        self.assertIn("service.stack.remove", commands)
        self.assertIn("service.stack.volumes.remove", commands)
        self.assertIn("service.compose.down", commands)
        self.assertIn('"remove_volumes"', commands)
        self.assertIn("service.stack.remove", config)
        self.assertIn("service.stack.volumes.remove", config)
        self.assertIn("service.compose.down", config)

    def test_compose_volume_removal_is_limited_to_service_delete(self):
        deploy = DEPLOY_MODEL.read_text(encoding="utf-8")
        delete_model = (ROOT / "src" / "model" / "struct" / "services_delete.py").read_text(encoding="utf-8")
        migration = (ROOT / "src" / "model" / "struct" / "services_migration.py").read_text(encoding="utf-8")
        release = RELEASE_MODEL.read_text(encoding="utf-8")
        rollback = ROLLBACK_MODEL.read_text(encoding="utf-8")
        mcp = DOCKER_INFRA_MCP.read_text(encoding="utf-8")
        runtime = CODEX_RUNTIME_MODEL.read_text(encoding="utf-8")
        assistant = AI_ASSISTANT_MODEL.read_text(encoding="utf-8")

        self.assertIn('"remove_volumes": True', delete_model)
        self.assertIn("docker compose -p \"$STACK\" -f \"$FILE\" down --volumes", delete_model)
        self.assertIn("service.compose.down", deploy)
        self.assertNotIn('"remove_volumes": True', deploy)
        self.assertIn('docker compose -p "$STACK" -f "$FILE" down || true', deploy)
        self.assertNotIn("down --volumes", deploy)
        self.assertIn('"force_recreate": True', migration)
        self.assertNotIn("remove_volumes", migration)
        self.assertNotIn("service.compose.down", release)
        self.assertNotIn("service.compose.down", rollback)
        for token in ["persistent_volume_destruction_violation", "allow_volume_destruction", "docker compose down --volumes", "docker volume rm/prune"]:
            self.assertIn(token, mcp)
        for token in ["volume_destruction_policy", "docker compose down --volumes", "docker volume rm/prune"]:
            self.assertIn(token, runtime)
        self.assertIn("Do not run docker compose down --volumes", assistant)

    def test_service_delete_uses_ddns_unregister_and_skips_legacy_dns(self):
        delete_model = (ROOT / "src" / "model" / "struct" / "services_delete.py").read_text(encoding="utf-8")
        domains = DOMAINS_MODEL.read_text(encoding="utf-8")
        ddns = (ROOT / "src" / "model" / "struct" / "domains_ddns.py").read_text(encoding="utf-8")

        self.assertIn("domains_model.delete_service_dns_records", delete_model)
        self.assertIn("def delete_service_dns_records", domains)
        self.assertIn("domain.record.delete_service", domains)
        self.assertIn("ddns_only", domains)
        self.assertIn("ddns_registration_not_found", ddns)

    def test_service_rollback_contract_is_wired(self):
        api = SERVICES_API.read_text(encoding="utf-8")
        view = SERVICES_VIEW.read_text(encoding="utf-8")
        template = SERVICES_TEMPLATE.read_text(encoding="utf-8")
        services = SERVICES_MODEL.read_text(encoding="utf-8")
        rollback = ROLLBACK_MODEL.read_text(encoding="utf-8")
        deploy = DEPLOY_MODEL.read_text(encoding="utf-8")

        self.assertIn("def rollback_plan():", api)
        self.assertIn("def rollback_service():", api)
        self.assertIn("services_model.rollback_plan", api)
        self.assertIn("services_model.rollback", api)
        self.assertIn("public async openRollbackModal", view)
        self.assertIn("public async runRollback", view)
        self.assertIn("버전 되돌리기", template)
        self.assertIn('(click)="runRollback()"', template)
        self.assertNotIn('(click)="runRollback(false)"', template)
        self.assertNotIn("되돌린 뒤 상태는 준비 중", template)
        self.assertIn("ServiceRollbackMixin", services)
        for token in ["def rollback_plan", "def rollback", "compose_versions", "service.compose.rollback"]:
            self.assertIn(token, rollback)
        self.assertNotIn("INSERT INTO compose_versions", rollback)
        self.assertIn("source = 'container_snapshot'", rollback)
        self.assertIn("planned_image_refs", rollback)
        self.assertIn("force_recreate: true", view)
        self.assertIn("ensure_backup_registry", view)
        self.assertIn("deployment_reason: 'compose_rollback'", view)
        self.assertIn("def _remove_stack_before_deploy", deploy)
        self.assertIn("service.stack.remove", deploy)
        self.assertIn("configure_backup_registry_for_node", deploy)
        self.assertNotIn("docker.daemon.insecure_registries.ensure", deploy)
        self.assertIn("def _ensure_backup_system_running_for_deploy", deploy)
        self.assertIn("backup_system.refresh", deploy)
        self.assertIn("backup_system.enable", deploy)
        self.assertIn("def _docker_login_for_deploy", deploy)
        self.assertIn("backup registry login wait", deploy)
        self.assertIn("def _login_backup_registry_for_deploy", deploy)
        self.assertIn("--password-stdin", deploy)
        self.assertIn("backup_registry_login", deploy)
        self.assertIn("task_error_history", deploy)
        self.assertIn("_serialize = shared.serialize", deploy)
        self.assertIn("Jsonb(_serialize(metadata))", deploy)
        self.assertIn("force_recreate", deploy)
        self.assertIn("ensure_backup_registry", deploy)
        self.assertLess(deploy.index("_login_backup_registry_for_deploy(compose_path"), deploy.index("_remove_stack_before_deploy(stack_name"))

    def test_service_operation_output_polling_is_wired(self):
        api = SERVICES_API.read_text(encoding="utf-8")
        view = SERVICES_VIEW.read_text(encoding="utf-8")
        template = SERVICES_TEMPLATE.read_text(encoding="utf-8")

        self.assertIn("def operation_detail():", api)
        self.assertIn("def deploy_service_background():", api)
        self.assertIn('"operation": result.get("operation")', api)
        self.assertIn("DatabaseOperationalError", api)
        self.assertIn("except DATABASE_ERRORS as exc", api)
        self.assertIn("deploy_service_background", view)
        self.assertIn("service_id", view)
        self.assertIn("data?.result?.operation", view)
        self.assertIn("openOperationModal(operation, false)", view)
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
        style = (ROOT / "src" / "app" / "page.services" / "view.scss").read_text(encoding="utf-8")
        api = SERVICES_API.read_text(encoding="utf-8")
        flow = FLOW_MODEL.read_text(encoding="utf-8")
        status = STATUS_MODEL.read_text(encoding="utf-8")
        deploy_targets = DEPLOY_TARGETS_MODEL.read_text(encoding="utf-8")
        servers_view = SERVERS_VIEW.read_text(encoding="utf-8")

        for token in ["runtimeServerSummaryText", "serviceIssue", "runtimeContainers", "runRuntimeContainerAction", "detailTabs", "serviceFlowPaths", "proxy_node_display_name", "registered_node_label", "runtimeServerLinks", "runtimeServerDetailQueryParams"]:
            self.assertIn(token, view)
        for token in ['[routerLink]="runtimeServerDetailRoute()"', "runtimeServerDetailNodeId", "fa-arrow-up-right-from-square"]:
            self.assertIn(token, template)
        for token in ["URLSearchParams", "node_id", "selected_node_id"]:
            self.assertIn(token, servers_view)
        for token in ["decorate_runtime_status", "proxy_node_display_name", "registered_node_name", "node_mapping"]:
            self.assertIn(token, status)
        for token in ["proxy_swarm_node_name", "proxy_registered_node_name", "registered_node_host"]:
            self.assertIn(token, deploy_targets)
        self.assertIn("flow_model.build", api)
        self.assertIn("service_flow", api)
        self.assertIn("def service_container_action():", api)
        self.assertIn("target_node_id", api)
        self.assertIn("container.node_id", view)
        for token in ["class ServicesFlow", "depends_on", "public_paths", "internal_targets", "nginx"]:
            self.assertIn(token, flow)
        for token in ["서버 / 인증서", "실행 기준", "구성요소", "lg:grid-cols-4"]:
            self.assertNotIn(token, template)
        self.assertIn("실행 상태", template)
        self.assertIn("처리 로그", template)
        self.assertIn("백업", template)
        self.assertNotIn("Compose/Nginx", view)
        self.assertIn("상태 다시 확인", template)
        self.assertIn("외부에 오픈되는 컨테이너", template)
        self.assertIn("처리 로그 보기", template)
        self.assertIn("service-runtime-container-group", template)
        self.assertIn("service-runtime-container-card", template)
        self.assertIn("service-runtime-container-menu", template)
        self.assertIn("service-runtime-container-menu-panel", template)
        self.assertIn(".service-runtime-container-menu[open]", style)
        self.assertIn(".service-runtime-container-group:has(.service-runtime-container-menu[open])", style)
        self.assertIn(".service-runtime-container-card:has(.service-runtime-container-menu[open])", style)
        self.assertIn("z-index: 90", style)

    def test_service_container_context_log_streaming_is_wired(self):
        api = SERVICES_API.read_text(encoding="utf-8")
        view = SERVICES_VIEW.read_text(encoding="utf-8")
        template = SERVICES_TEMPLATE.read_text(encoding="utf-8")
        socket = SERVICES_SOCKET.read_text(encoding="utf-8")
        nodes_terminal = NODES_TERMINAL_MODEL.read_text(encoding="utf-8")

        for token in ["openContainerLogs", "containerLogsOpen", "connectContainerLogs", "refreshContainerLogsSnapshot", "containerLogsText"]:
            self.assertIn(token, view)
        self.assertIn("span 로그", template)
        self.assertIn("services-container-logs-output", template)
        self.assertIn("containerLogsText()", template)
        self.assertIn("service_container_logs_snapshot", view)
        self.assertIn("setInterval", view)
        self.assertIn("def service_container_logs_snapshot", api)
        self.assertIn("docker logs --tail", api)
        self.assertIn("_run_node_command", api)
        self.assertIn("log_output", socket)
        self.assertIn("log_status", socket)
        self.assertIn('"mode") or "terminal"', socket)
        self.assertIn("create_container_logs_session", socket)
        self.assertIn('"docker", "logs", "--tail"', nodes_terminal)
        self.assertIn("def create_container_logs_session", nodes_terminal)

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
        nginx = NGINX_MODEL.read_text(encoding="utf-8")
        deploy_targets = DEPLOY_TARGETS_MODEL.read_text(encoding="utf-8")
        webserver = WEBSERVER_MODEL.read_text(encoding="utf-8")
        domains = DOMAINS_MODEL.read_text(encoding="utf-8")
        domains_view = DOMAINS_VIEW.read_text(encoding="utf-8")
        domains_template = DOMAINS_TEMPLATE.read_text(encoding="utf-8")
        route = DOMAIN_CERT_ROUTE.read_text(encoding="utf-8")

        self.assertIn("def save_nginx_config():", services_api)
        self.assertIn("update_nginx_config", runtime)
        self.assertIn("proxy.nginx.configtest", runtime)
        self.assertIn("nu-monaco-editor", services_template)
        self.assertNotIn("Compose/Nginx", services_view)
        self.assertIn("saveAdvancedEditor", services_view)
        self.assertIn("saveComposeContent", services_view)
        self.assertIn("saveNginxConfig", services_view)
        self.assertIn("applyAdvancedCompose", services_view)
        self.assertIn("compose_source_apply", services_view)
        self.assertIn('(click)="applyAdvancedCompose()"', services_template)
        self.assertIn("deploy_targets.compose_ports", runtime)
        self.assertIn("service_nginx.render_preview", runtime)
        self.assertIn('"preview": not readable', runtime)
        self.assertIn("def render_preview", nginx)
        for token in ["_domain_proxy_profile", "_render_header", "DNS provider:", "DDNS endpoint:", "Proxy topology:", "ddns_management", "managed_dns"]:
            self.assertIn(token, nginx)
        for token in ["proxy_topology", "local-master", "remote-node", "proxy_node_is_local_master", "registered_private_host", "registered_public_ip", "proxy_swarm_addr"]:
            self.assertIn(token, deploy_targets)
        self.assertIn("chain_file", route)
        self.assertNotIn("chain_file", domains_view)
        self.assertIn("fullchain.pem", webserver)
        self.assertIn("key_permission_secure", webserver)
        self.assertIn("key_matches", webserver)
        self.assertIn("service_options", domains)
        self.assertIn("ensure_service_dns_record", domains)
        self.assertIn("domain.record.ensure_service", domains)
        self.assertIn("_ensure_dns_records", NGINX_MODEL.read_text(encoding="utf-8"))
        self.assertIn("dns_records", NGINX_MODEL.read_text(encoding="utf-8"))
        self.assertIn("등록된 DDNS 레코드", domains_template)
        self.assertNotIn("certificateKeyText", domains_view)

    def test_services_api_handles_reloaded_service_error_shapes(self):
        spec = importlib.util.spec_from_file_location("services_api_contract", SERVICES_API)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)

        class ReloadedComposeValidationError(Exception):
            status_code = 409
            message = "Compose validation failed."
            error_code = "COMPOSE_VALIDATION_FAILED"
            details = [{"path": "networks.default", "error_code": "UNSUPPORTED_NETWORK"}]
            warning = True
            can_continue = True

        code, payload = module._raise_unless_service_error_like(ReloadedComposeValidationError())

        self.assertEqual(code, 409)
        self.assertEqual(payload["error_code"], "COMPOSE_VALIDATION_FAILED")
        self.assertEqual(payload["details"][0]["error_code"], "UNSUPPORTED_NETWORK")
        self.assertTrue(payload["warning"])
        self.assertTrue(payload["can_continue"])

        services_api = SERVICES_API.read_text(encoding="utf-8")
        for function_name in ["deploy_service", "save_nginx_config", "save_compose_content"]:
            block = services_api[services_api.index(f"def {function_name}():"):]
            block = block[: block.find("\ndef ", 1) if block.find("\ndef ", 1) != -1 else len(block)]
            self.assertIn("_raise_unless_service_error_like", block)

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
        for token in ["_runtime_progress_snapshot", "runtime wait", "runtime_progress", "이미지 pull", "runtime_ready_timeout_seconds\") or 600"]:
            self.assertIn(token, deploy)
        self.assertIn("include_operations=True", services_api)
        for token in ["activeOperationProgressTitle", "activeOperationProgressMessage", "deploymentProgressRows", "runtimeEmptyText", "refreshActiveOperationOverview", "이미지 pull 또는 Docker 작업 처리 중"]:
            self.assertIn(token, services_view)
        for token in ["백그라운드 작업 진행 중", "Docker 작업", "컨테이너", "{{runtimeEmptyText()}}"]:
            self.assertIn(token, services_template)
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

    def test_service_detail_splits_slow_extras_from_initial_overview(self):
        fast_model = (ROOT / "src" / "model" / "struct" / "services_detail_fast.py").read_text(encoding="utf-8")
        runtime = RUNTIME_MODEL.read_text(encoding="utf-8")
        services_api = SERVICES_API.read_text(encoding="utf-8")
        services_view = SERVICES_VIEW.read_text(encoding="utf-8")
        nginx_cert = NGINX_CERT_MODEL.read_text(encoding="utf-8")

        self.assertIn('wiz.model("struct/services_detail_fast").overview', services_api)
        self.assertIn('wiz.model("struct/services_detail_fast").extras', services_api)
        self.assertIn("def _operations", fast_model)
        self.assertIn("FROM operation_logs", fast_model)
        self.assertIn("target_type = 'service'", fast_model)
        self.assertIn('"operations": operations', fast_model)
        self.assertIn("include_backup_system=not lightweight", services_api)
        self.assertIn("def detail_service_extras():", services_api)
        self.assertIn("def detail_extras", runtime)
        self.assertIn("include_backup_system=True", runtime)
        self.assertIn("detail_service_extras", services_view)
        self.assertIn("lightweight: true", services_view)
        self.assertNotIn("this.loadAiModelOptions().catch", services_view)
        self.assertIn("payload = ai_settings.model_options()", services_api)
        self.assertNotIn("payload = ai_assistant.model_options()", services_api)
        self.assertIn("class ServiceDetailFast", fast_model)
        self.assertIn("def overview", fast_model)
        self.assertIn("def extras", fast_model)
        self.assertNotIn("refreshOverviewExtras", services_view)
        self.assertIn('"auto_renewal": None', nginx_cert)
        self.assertIn("if rows:", nginx_cert)


if __name__ == "__main__":
    unittest.main()
