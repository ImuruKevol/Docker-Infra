store = wiz.model("struct/templates_store")
seed = wiz.model("struct/templates_seed")


class Templates:
    TemplateError = store.TemplateError

    def ensure_defaults(self, env=None):
        store.migrate_storage_root(env=env)
        desired = {item["namespace"]: item for item in seed.default_templates()}
        managed = set(seed.managed_namespaces())
        existing_rows = store.overview(env=env).get("templates", [])
        existing = {item["namespace"]: item for item in existing_rows}
        for namespace in sorted(managed - set(desired)):
            store.remove_namespace(namespace, env=env)
            existing.pop(namespace, None)
        for item in seed.default_templates():
            current = existing.get(item["namespace"])
            metadata = {**(item.get("metadata") or {})}
            payload = {
                "name": item["name"],
                "namespace": item["namespace"],
                "description": item["description"],
                "enabled": True,
                "metadata": metadata,
                "compose": item["files"]["docker-compose.yaml"],
                "values_default": item["files"]["values.default.yaml"],
                "values_schema": item["files"]["values.schema.json"],
                "readme": item["files"]["README.md"],
                "source": "seed",
            }
            if current:
                if (current.get("metadata") or {}).get("seed_version") == metadata.get("seed_version"):
                    continue
                payload["id"] = current["id"]
            store.save(
                payload,
                env=env,
            )
            if not current:
                existing[item["namespace"]] = {"namespace": item["namespace"]}

    def reset_defaults(self, env=None):
        for namespace in sorted(seed.managed_namespaces()):
            store.remove_namespace(namespace, env=env)
        store.migrate_storage_root(env=env)
        for item in seed.default_templates():
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
                    "source": "seed_reset",
                },
                env=env,
            )
        return store.overview(env=env)

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
