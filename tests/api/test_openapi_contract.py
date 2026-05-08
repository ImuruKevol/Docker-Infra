import copy
import json
import os
import unittest
from pathlib import Path

import requests

from openapi_validator import OpenApiValidationError, assert_schema, resolve_ref


ROOT = Path(__file__).resolve().parents[2]
OPENAPI_PATH = ROOT / "docs" / "api" / "openapi.json"
DEFAULT_BASE_URL = "http://127.0.0.1:3001"


class OpenApiContractTest(unittest.TestCase):
    def load_document(self):
        with OPENAPI_PATH.open("r", encoding="utf-8") as handle:
            return json.load(handle)

    def test_static_openapi_contains_initial_contract(self):
        document = self.load_document()
        self.assertEqual(document["openapi"], "3.0.3")
        self.assertIn("/openapi.json", document["paths"])
        self.assertIn("/swagger", document["paths"])
        self.assertIn("/api/system/health", document["paths"])
        self.assertIn("/api/system/settings", document["paths"])
        self.assertIn("/api/system/setup", document["paths"])
        self.assertIn("/api/system/local-command/check", document["paths"])
        self.assertIn("/api/system/local-master/ensure", document["paths"])
        self.assertIn("/api/auth/login", document["paths"])
        self.assertIn("/api/auth/logout", document["paths"])
        self.assertIn("/api/auth/session", document["paths"])
        self.assertNotIn("/api/jobs", document["paths"])
        self.assertIn("/api/nodes", document["paths"])
        self.assertIn("/api/nodes/{node_id}/join", document["paths"])
        self.assertIn("/api/nodes/{node_id}/metrics", document["paths"])
        self.assertIn("/api/reporter/metrics", document["paths"])
        self.assertIn("/api/compose/validate", document["paths"])
        self.assertIn("/wiz/api/page.dashboard/overview", document["paths"])
        self.assertIn("/wiz/api/page.access/login", document["paths"])
        self.assertIn("HealthResponse", document["components"]["schemas"])
        self.assertNotIn("email", json.dumps(document))
        self.assertIn("<redacted>", json.dumps(document))

    def test_static_openapi_contains_p1_common_components(self):
        document = self.load_document()
        components = document["components"]
        schemas = components["schemas"]

        self.assertEqual(components["securitySchemes"]["sessionCookie"]["in"], "cookie")
        for name in [
            "ErrorResponse",
            "PaginationMeta",
            "SecretMaskedValue",
            "SystemSetting",
            "SystemSettingResponse",
            "SystemSettingsListResponse",
            "AuthLoginResponse",
            "AuthLogoutResponse",
            "AuthSessionResponse",
            "BackupSystemStatus",
            "SetupStatusResponse",
            "SetupCompleteResponse",
            "LocalMasterNode",
            "OperationSummary",
            "LocalCommandResult",
            "LocalCommandCheckRequest",
            "LocalCommandCheckResponse",
            "Node",
            "NodeCredential",
            "NodeResponse",
            "NodeListResponse",
            "NodeCheckResponse",
            "NodeJoinResponse",
            "LocalMasterEnsureResponse",
            "NodeMetric",
            "ReporterTokenResponse",
            "MetricIngestResponse",
            "NodeMetricsResponse",
            "NodeContainersResponse",
            "ComposeValidationRequest",
            "ComposeValidationErrorDetail",
            "ComposeValidationResult",
            "ComposeValidationResponse",
            "ComposeValidationErrorResponse",
        ]:
            self.assertIn(name, schemas)

        for removed in [
            "JobStatus",
            "JobSummary",
            "JobStepStatus",
            "JobStepSummary",
            "Job",
            "JobStep",
            "JobLog",
            "JobDetailResponse",
            "JobRetryResponse",
            "JobLogSearchResponse",
            "JobLogDownloadResponse",
        ]:
            self.assertNotIn(removed, schemas)
        self.assertEqual(schemas["OperationSummary"]["properties"]["status"]["enum"], ["pending", "running", "succeeded", "failed", "canceled"])
        self.assertNotIn("plain", json.dumps(schemas["SecretMaskedValue"]).lower())
        self.assertIn("********", json.dumps(schemas["SecretMaskedValue"]))
        self.assertNotIn("user_id", json.dumps(schemas["LoginRequest"]).lower())

    def test_static_response_examples_match_declared_schemas(self):
        document = self.load_document()
        for route, path_item in document["paths"].items():
            for method, operation in path_item.items():
                responses = operation.get("responses", {})
                for status, response in responses.items():
                    media = response.get("content", {}).get("application/json")
                    if not media or "example" not in media:
                        continue
                    with self.subTest(route=route, method=method, status=status):
                        assert_schema(document, media["schema"], media["example"])

    def test_schema_validation_fails_when_required_field_is_missing(self):
        document = self.load_document()
        schema = resolve_ref(document, "#/components/schemas/HealthResponse")
        invalid_payload = {"code": 200}

        with self.assertRaises(OpenApiValidationError):
            assert_schema(document, schema, invalid_payload)

    def test_schema_validation_fails_when_enum_is_invalid(self):
        document = self.load_document()
        schema = resolve_ref(document, "#/components/schemas/HealthResponse")
        valid_payload = document["paths"]["/api/system/health"]["get"]["responses"]["200"]["content"][
            "application/json"
        ]["example"]
        invalid_payload = copy.deepcopy(valid_payload)
        invalid_payload["data"]["status"] = "unknown"

        with self.assertRaises(OpenApiValidationError):
            assert_schema(document, schema, invalid_payload)

    def test_live_openapi_matches_static_contract_when_server_is_available(self):
        base_url = os.environ.get("DOCKER_INFRA_BASE_URL", DEFAULT_BASE_URL)

        response = requests.get(f"{base_url.rstrip('/')}/openapi.json", timeout=10)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers.get("content-type", "").split(";")[0], "application/json")
        self.assertEqual(response.json(), self.load_document())

    def test_live_system_health_contract_when_server_is_available(self):
        base_url = os.environ.get("DOCKER_INFRA_BASE_URL", DEFAULT_BASE_URL)

        response = requests.get(f"{base_url.rstrip('/')}/api/system/health", timeout=10)
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["code"], 200)
        self.assertEqual(payload["data"]["status"], "ok")
        self.assertEqual(payload["data"]["service"], "docker-infra")
        self.assertEqual(payload["data"]["checks"]["api"]["status"], "ok")
        self.assertIn(payload["data"]["checks"]["database"]["status"], {"not_configured", "ok", "degraded", "error"})
        assert_schema(self.load_document(), resolve_ref(self.load_document(), "#/components/schemas/HealthResponse"), payload)

    def test_live_dashboard_overview_contract_when_server_is_available(self):
        base_url = os.environ.get("DOCKER_INFRA_BASE_URL", DEFAULT_BASE_URL)

        response = requests.post(f"{base_url.rstrip('/')}/wiz/api/page.dashboard/overview", json={}, timeout=10)
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["code"], 200)
        self.assertIn("stats", payload["data"])
        self.assertIn("checklist", payload["data"])
        assert_schema(
            self.load_document(),
            resolve_ref(self.load_document(), "#/components/schemas/DashboardOverviewResponse"),
            payload,
        )


if __name__ == "__main__":
    unittest.main()
