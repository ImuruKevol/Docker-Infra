store = wiz.model("struct/templates_store")
seed = wiz.model("struct/templates_seed")

DEPRECATED_TEMPLATE_NAMESPACES = {
    "gitlab_ce",
}


class Templates:
    TemplateError = store.TemplateError

    def ensure_defaults(self, env=None):
        store.migrate_storage_root(env=env)
        for namespace in DEPRECATED_TEMPLATE_NAMESPACES:
            store.remove_namespace(namespace, env=env)
        existing = store.namespaces(env=env)
        for item in seed.default_templates():
            if item["namespace"] in existing:
                continue
            store.save(
                {
                    "name": item["name"],
                    "namespace": item["namespace"],
                    "description": item["description"],
                    "enabled": True,
                    "metadata": item.get("metadata") or {},
                    "compose": item["files"]["docker-compose.yaml"],
                    "values_default": item["files"]["values.default.yaml"],
                    "values_schema": item["files"]["values.schema.json"],
                    "readme": item["files"]["README.md"],
                    "source": "seed",
                },
                env=env,
            )
            existing.add(item["namespace"])

    def load(self, env=None):
        self.ensure_defaults(env=env)
        return store.overview(env=env)

    def detail(self, template_id, env=None):
        self.ensure_defaults(env=env)
        return store.detail(template_id, env=env)

    def version_detail(self, version_id, env=None):
        self.ensure_defaults(env=env)
        return store.version_detail(version_id, env=env)

    def save(self, payload, env=None):
        self.ensure_defaults(env=env)
        return store.save(payload, env=env)

    def release(self, payload, env=None):
        self.ensure_defaults(env=env)
        return store.release(payload, env=env)

    def preview(self, payload, env=None):
        self.ensure_defaults(env=env)
        return store.preview(payload, env=env)

    def delete(self, template_id, env=None):
        return store.delete(template_id, env=env)


Model = Templates()
