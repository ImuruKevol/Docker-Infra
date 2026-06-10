compose_rules = wiz.model("struct/compose_rules")


COMPOSE_TEMPLATE_MCP_TOOLS = [
    "infra_context",
    "docker_search",
    "docker_image_check",
    "server_list",
    "server_port_check",
    "container_logs",
    "container_action",
    "service_stack_status",
    "dns_lookup",
    "tcp_connect_check",
    "http_probe",
    "browser_probe",
    "server_collect",
    "ssh_command",
]


class TemplateAIContract:
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

    def output_format_contract(self):
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
                    "services that provide browser/API/user-facing access must include services.<name>.ports with an explicit published-to-target port mapping",
                    "do not use expose as a substitute for public access; expose is internal-only",
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

    def template_ai_policy(self):
        required_files = ["docker-compose.yaml", "values.default.yaml", "values.schema.json", "README.md"]
        return {
            "scope": "compose_template",
            "purpose": "Reusable Compose template draft only; service deployment and runtime repair are outside this scope.",
            "mcp": {
                "server": "docker_infra",
                "enabled_tools": list(COMPOSE_TEMPLATE_MCP_TOOLS),
                "allowed_use": [
                    "infra_context: Docker Infra compose/network/template constraints and MCP contract",
                    "docker_search/docker_image_check: candidate image discovery and exact tag verification",
                    "server_list/server_collect/ssh_command: registered server inspection when runtime facts are useful",
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
                "port_rules": [
                    "Any browser/API/user-facing service must declare services.<name>.ports; expose alone is internal-only and is not enough.",
                    "Public ports must explicitly map a published port to the container target port, for example \"{{ service_port }}:3000\" or long syntax with target, published, protocol, and mode.",
                    "The published port should be a reusable integer placeholder in values.default.yaml and values.schema.json.",
                    "metadata.public_endpoint.service and metadata.public_endpoint.port must match a service and target port declared under services.<name>.ports.",
                    "Internal dependency services such as databases, caches, and queues should omit ports unless the user explicitly asks to publish them.",
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
            "output_format": self.output_format_contract(),
            "policy": self.template_ai_policy(),
        }


Model = TemplateAIContract()
