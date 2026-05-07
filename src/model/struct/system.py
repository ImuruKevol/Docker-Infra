import datetime

postgres = wiz.model("db/postgres")
migration = wiz.model("db/migration")


class System:
    def health(self):
        now = datetime.datetime.now(datetime.timezone.utc)
        database = {
            "status": "not_configured",
            "schema_version": None,
        }

        if postgres.has_database_config():
            try:
                schema_version = migration.current_schema_version()
                database = {
                    "status": "ok" if schema_version is not None else "degraded",
                    "schema_version": schema_version,
                }
            except Exception as exc:
                database = {
                    "status": "error",
                    "schema_version": None,
                    "message": str(exc),
                }

        status = "ok" if database["status"] in {"ok", "not_configured"} else "degraded"
        return {
            "status": status,
            "service": "docker-infra",
            "version": "0.1.0",
            "timestamp": now.isoformat().replace("+00:00", "Z"),
            "checks": {
                "api": {
                    "status": "ok"
                },
                "database": database,
            }
        }


Model = System()
