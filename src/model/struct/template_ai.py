compose_rules = wiz.model("struct/compose_rules")


COMPOSE_TEMPLATE_MCP_TOOLS = [
    "infra_context",
    "docker_search",
    "docker_image_check",
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
        forbidden_tool_families = [
            "ssh_command",
            "server_collect",
            "server_list",
            "server_port_check",
            "service_stack_status",
            "container_logs",
            "container_action",
            "dns_lookup",
            "tcp_connect_check",
            "http_probe",
            "browser_probe",
        ]
        return {
            "scope": "compose_template",
            "purpose": "Reusable Compose template draft only; service deployment and runtime repair are outside this scope.",
            "mcp": {
                "server": "docker_infra",
                "enabled_tools": list(COMPOSE_TEMPLATE_MCP_TOOLS),
                "allowed_use": [
                    "infra_context: Docker Infra compose/network/template constraints",
                    "docker_search: candidate image discovery when the requested product image is ambiguous",
                    "docker_image_check: exact image tag verification before returning image references",
                ],
                "forbidden_tool_families": forbidden_tool_families,
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
                "can_edit_project_files": False,
                "can_save_template": False,
                "can_deploy": False,
                "can_change_runtime": False,
                "can_read_runtime_logs": False,
                "can_run_container_actions": False,
                "can_run_ssh_command": False,
                "can_run_safe_ssh_diagnostics": False,
                "can_probe_network": False,
                "can_select_deploy_target": False,
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
