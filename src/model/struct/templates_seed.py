SEED_VERSION = "2026-05-09-domain-stack-v1"
DEFAULT_NAMESPACES = ("wordpress_site", "nextcloud_stack", "odoo_suite", "wikijs_site")
LEGACY_NAMESPACES = {
    "nginx_static",
    "node_api",
    "springboot_api",
    "postgres_db",
    "mariadb_db",
    "redis_cache",
    "rabbitmq_queue",
    "harbor_registry",
    "gitlab_ce",
}

web_stacks = wiz.model("struct/templates_seed_web_stacks")
business_stacks = wiz.model("struct/templates_seed_business_stacks")


def default_templates():
    return web_stacks.templates() + business_stacks.templates()


def managed_namespaces():
    return LEGACY_NAMESPACES | set(DEFAULT_NAMESPACES)


class TemplatesSeed:
    default_templates = staticmethod(default_templates)
    managed_namespaces = staticmethod(managed_namespaces)


Model = TemplatesSeed()
