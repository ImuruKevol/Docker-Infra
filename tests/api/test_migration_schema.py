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
            "jobs",
            "job_steps",
            "job_logs",
            "operator_auth",
            "auth_sessions",
            "auth_login_attempts",
        ]:
            self.assertIn(f"CREATE TABLE IF NOT EXISTS {table}", sql)
        self.assertIn("metadata JSONB NOT NULL DEFAULT '{}'::jsonb", sql)
        self.assertIn("test_run_id TEXT", sql)


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
