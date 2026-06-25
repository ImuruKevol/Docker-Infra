store = wiz.model("struct/macros_store")
runner = wiz.model("struct/macros_runner")
shared = wiz.model("struct/macros_shared")
schedules = wiz.model("struct/macro_schedules")


class MacroManager:
    MacroError = shared.MacroError
    SCOPE_GLOBAL = shared.SCOPE_GLOBAL
    SCOPE_NODE = shared.SCOPE_NODE

    def list(self, payload=None, env=None):
        return store.list(payload, env=env)

    def save(self, payload, file_storages=None, env=None):
        return store.save(payload, file_storages=file_storages, env=env)

    def delete(self, macro_id, env=None):
        schedules.delete_for_macro(macro_id, env=env)
        return store.delete(macro_id, env=env)

    def download_file(self, file_id, macro_id=None, env=None):
        return store.download_file(file_id, macro_id=macro_id, env=env)

    def delete_file(self, file_id, macro_id=None, env=None):
        return store.delete_file(file_id, macro_id=macro_id, env=env)

    def run(self, payload, env=None):
        return runner.run(payload, env=env)

    def list_schedules(self, macro_id=None, env=None):
        return schedules.list(macro_id=macro_id, env=env)

    def schedule_history(self, schedule_id, macro_id=None, page=1, limit=10, env=None):
        return schedules.history(schedule_id, macro_id=macro_id, page=page, limit=limit, env=env)

    def save_schedule(self, payload=None, env=None):
        return schedules.save(payload, env=env)

    def delete_schedule(self, schedule_id, macro_id=None, env=None):
        return schedules.delete(schedule_id, macro_id=macro_id, env=env)


Model = MacroManager()
