import unittest
from pathlib import Path

from tests.fixtures.api_client import DockerInfraApiClient


ROOT = Path(__file__).resolve().parents[2]
MIGRATION_DIR = ROOT / "src" / "model" / "db" / "migrations"


class MigrationSchemaStaticContractTest(unittest.TestCase):
    def test_schema_migrations_declare_required_tables(self):
        sql_files = sorted(path.name for path in MIGRATION_DIR.glob("*.sql"))
        self.assertEqual(
            sql_files,
            [
                "019_current_schema.down.sql",
                "019_current_schema.sql",
                "020_actual_schema_cleanup.down.sql",
                "020_actual_schema_cleanup.sql",
            ],
        )

        sql = "\n".join(
            (MIGRATION_DIR / name).read_text(encoding="utf-8")
            for name in ["019_current_schema.sql", "020_actual_schema_cleanup.sql"]
        )

        for table in [
            "system_settings",
            "cloudflare_dns_records",
            "ddns_endpoints",
            "ddns_registrations",
            "nodes",
            "node_credentials",
            "node_metrics",
            "shell_macros",
            "shell_macro_files",
            "operation_logs",
            "backup_system_settings",
            "service_image_backups",
            "operator_auth",
            "auth_sessions",
            "auth_login_attempts",
        ]:
            self.assertIn(f"CREATE TABLE IF NOT EXISTS {table}", sql)
        self.assertIn("metadata JSONB NOT NULL DEFAULT '{}'::jsonb", sql)
        self.assertIn("test_run_id TEXT", sql)

    def test_removed_tables_are_not_created_by_current_schema(self):
        sql = (MIGRATION_DIR / "019_current_schema.sql").read_text(encoding="utf-8")

        for table in [
            "templates",
            "template_versions",
            "jobs",
            "job_steps",
            "job_logs",
            "image_builds",
            "integration_gitlab",
            "integration_harbor",
        ]:
            self.assertNotIn(f"CREATE TABLE IF NOT EXISTS {table}", sql)
            self.assertIn(f"DROP TABLE IF EXISTS {table}", sql)

    def test_actual_schema_cleanup_drops_unused_tables(self):
        sql = (MIGRATION_DIR / "020_actual_schema_cleanup.sql").read_text(encoding="utf-8")

        for table in [
            "proxy_configs",
            "certificates",
            "electron_setting_backups",
        ]:
            self.assertIn(f"DROP TABLE IF EXISTS {table}", sql)

        self.assertIn("CREATE TABLE IF NOT EXISTS service_image_backups", sql)
        self.assertIn("service_image_backups_set_updated_at", sql)
        self.assertIn("ALTER TABLE cloudflare_dns_records", sql)
        self.assertIn("DROP COLUMN IF EXISTS test_run_id", sql)


class MigrationSchemaLiveFlowTest(unittest.TestCase):
    def setUp(self):
        self.client = DockerInfraApiClient.from_env(self)

    def test_health_api_reports_database_status_through_wiz_runtime(self):
        response = self.client.get("/api/system/health", expected_status=200, validate=False)

        payload = response.json()
        self.assertEqual(payload["code"], 200)
        self.assertEqual(payload["data"]["service"], "docker-infra")
        self.assertIn(payload["data"]["checks"]["database"]["status"], {"not_configured", "ok", "degraded", "error"})


if __name__ == "__main__":
    unittest.main()
