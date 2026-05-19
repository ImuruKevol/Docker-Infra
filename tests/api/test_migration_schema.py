import unittest
from pathlib import Path

from tests.fixtures.api_client import DockerInfraApiClient


ROOT = Path(__file__).resolve().parents[2]
MIGRATION_DIR = ROOT / "src" / "model" / "db" / "migrations"


class MigrationSchemaStaticContractTest(unittest.TestCase):
    def test_current_schema_migration_declares_required_tables(self):
        sql_files = sorted(path.name for path in MIGRATION_DIR.glob("*.sql"))
        self.assertEqual(sql_files, ["019_current_schema.down.sql", "019_current_schema.sql"])

        sql = (MIGRATION_DIR / "019_current_schema.sql").read_text(encoding="utf-8")

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
