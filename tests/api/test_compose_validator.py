import unittest
from pathlib import Path

from tests.fixtures.api_client import DockerInfraApiClient, password_only_login


ROOT = Path(__file__).resolve().parents[2]
ROUTE_ROOT = ROOT / "src" / "route" / "api-compose-validate"
OPENAPI_JSON = ROOT / "docs" / "api" / "openapi.json"


class ComposeValidateStaticContractTest(unittest.TestCase):
    def test_compose_validate_route_and_contract_are_registered(self):
        app_config = (ROUTE_ROOT / "app.json").read_text(encoding="utf-8")
        controller = (ROUTE_ROOT / "controller.py").read_text(encoding="utf-8")
        document = OPENAPI_JSON.read_text(encoding="utf-8")

        self.assertIn('"/api/compose/validate"', app_config)
        self.assertIn('"controller": "user"', app_config)
        self.assertIn("validator.validate", controller)
        for token in [
            "/api/compose/validate",
            "ComposeValidationRequest",
            "ComposeValidationResponse",
            "ComposeValidationErrorDetail",
        ]:
            self.assertIn(token, document)


class ComposeValidateLiveFlowTest(unittest.TestCase):
    def setUp(self):
        self.client = DockerInfraApiClient.from_env(self)
        password_only_login(self.client, testcase=self)

    def test_valid_compose_returns_augmented_normalized_compose(self):
        response = self.client.post(
            "/api/compose/validate",
            json={
                "namespace": "demo_app",
                "filename": "docker-compose.yaml",
                "content": """
services:
  web:
    image: nginx:1.27
    healthcheck:
      test: ["CMD-SHELL", "true"]
""",
            },
            validate=False,
        )

        self.assertEqual(response.status_code, 200, response.text[:500])
        validation = response.json()["data"]["validation"]
        self.assertTrue(validation["valid"])
        service = validation["normalized"]["services"]["web"]
        self.assertEqual(service["networks"], ["docker_infra_overlay"])
        self.assertEqual(service["deploy"]["replicas"], 1)
        self.assertEqual(service["deploy"]["update_config"]["failure_action"], "rollback")
        self.assertTrue(validation["normalized"]["networks"]["docker_infra_overlay"]["external"])

    def test_forbidden_field_returns_exact_error_path_and_code(self):
        response = self.client.post(
            "/api/compose/validate",
            json={
                "namespace": "demo_app",
                "content": """
services:
  web:
    image: nginx:1.27
    container_name: fixed-web
    healthcheck:
      test: ["CMD-SHELL", "true"]
""",
            },
            validate=False,
        )

        self.assertEqual(response.status_code, 400, response.text[:500])
        detail = response.json()["data"]["details"][0]
        self.assertEqual(detail["path"], "services.web.container_name")
        self.assertEqual(detail["error_code"], "FORBIDDEN_CONTAINER_NAME")


if __name__ == "__main__":
    unittest.main()
