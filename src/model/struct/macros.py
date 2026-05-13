store = wiz.model("struct/macros_store")
runner = wiz.model("struct/macros_runner")
shared = wiz.model("struct/macros_shared")


class MacroManager:
    MacroError = shared.MacroError
    SCOPE_GLOBAL = shared.SCOPE_GLOBAL
    SCOPE_NODE = shared.SCOPE_NODE

    def list(self, payload=None, env=None):
        return store.list(payload, env=env)

    def save(self, payload, file_storages=None, env=None):
        return store.save(payload, file_storages=file_storages, env=env)

    def delete(self, macro_id, env=None):
        return store.delete(macro_id, env=env)

    def run(self, payload, env=None):
        return runner.run(payload, env=env)


Model = MacroManager()
