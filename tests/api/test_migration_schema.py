import unittest
from pathlib import Path

from tests.fixtures.api_client import DockerInfraApiClient


ROOT = Path(__file__).resolve().parents[2]
MIGRATION_DIR = ROOT / "src" / "model" / "db" / "migrations"


class MigrationSchemaStaticContractTest(unittest.TestCase):
    def test_core_and_auth_migrations_declare_required_tables(self):
        sql = "\n".join(path.read_text(encoding="utf-8") for path in sorted(MIGRATION_DIR.glob("*.sql")))

        for table in [
            "system_settings",
            "cloudflare_dns_records",
            "nodes",
            "node_credentials",
            "node_metrics",
            "shell_macros",
            "operation_logs",
            "backup_system_settings",
            "operator_auth",
            "auth_sessions",
            "auth_login_attempts",
        ]:
            self.assertIn(f"CREATE TABLE IF NOT EXISTS {table}", sql)
        self.assertIn("metadata JSONB NOT NULL DEFAULT '{}'::jsonb", sql)
        self.assertIn("test_run_id TEXT", sql)

    def test_template_tables_are_not_created_by_core_schema(self):
        core = (MIGRATION_DIR / "001_core_schema.sql").read_text(encoding="utf-8")
        removal = (MIGRATION_DIR / "012_remove_templates.sql").read_text(encoding="utf-8")

        self.assertNotIn("CREATE TABLE IF NOT EXISTS templates", core)
        self.assertNotIn("CREATE TABLE IF NOT EXISTS template_versions", core)
        self.assertIn("DROP TABLE IF EXISTS template_versions", removal)
        self.assertIn("DROP TABLE IF EXISTS templates", removal)


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
