class Struct:
    def __init__(self):
        self.orm = wiz.model("portal/season/orm")
        self.session = wiz.model("portal/season/session").use()
        self._models = {}
        self._packages = {}

    def db(self, name):
        if name in {"postgres", "migration"}:
            return wiz.model(f"db/{name}")
        return self.orm.use(name)

    def _load(self, name):
        if name not in self._models:
            self._models[name] = wiz.model(f"struct/{name}")
        return self._models[name]

    @property
    def auth(self):
        return self._load("auth")

    @property
    def backup_system(self):
        return self._load("backup_system")

    @property
    def appearance(self):
        return self._load("appearance")

    @property
    def compose_validator(self):
        return self._load("compose_validator")

    @property
    def domains(self):
        return self._load("domains")

    @property
    def infra_catalog(self):
        return self._load("infra_catalog_registry")

    @property
    def images(self):
        return self._load("images")

    @property
    def integrations(self):
        return self._load("integrations_registry")

    @property
    def local_executor(self):
        return self._load("local_executor")

    @property
    def macros(self):
        return self._load("macros")

    @property
    def nodes(self):
        return self._load("nodes")

    @property
    def operations(self):
        return self._load("operations")

    @property
    def secret_masking(self):
        return self._load("secret_masking")

    @property
    def services(self):
        return self._load("services")

    @property
    def settings(self):
        return self._load("settings")

    @property
    def setup(self):
        return self._load("setup")

    @property
    def templates(self):
        return self._load("templates")

    @property
    def ssh_executor(self):
        return self._load("ssh_executor")

    @property
    def system(self):
        return self._load("system")

    @property
    def webserver(self):
        return self._load("webserver")

    def __getattr__(self, name):
        if name.startswith('_'):
            raise AttributeError(name)
        if name not in self._packages:
            try:
                self._packages[name] = wiz.model(f"portal/{name}/struct")
            except Exception:
                raise AttributeError(f"Package '{name}' not found")
        return self._packages[name]


Model = Struct()
