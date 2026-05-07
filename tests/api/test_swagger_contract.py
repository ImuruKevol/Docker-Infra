import os
import unittest
from pathlib import Path

import requests


ROOT = Path(__file__).resolve().parents[2]
SWAGGER_CONTROLLER = ROOT / "src" / "route" / "swagger" / "controller.py"
DEFAULT_BASE_URL = "http://127.0.0.1:3001"


class SwaggerContractTest(unittest.TestCase):
    def test_swagger_route_points_to_static_openapi_document(self):
        controller = SWAGGER_CONTROLLER.read_text(encoding="utf-8")

        self.assertIn("SwaggerUIBundle", controller)
        self.assertIn('url: "/openapi.json"', controller)
        self.assertIn("swagger-ui-dist@5", controller)

    def test_live_swagger_html_loads_openapi_url_when_server_is_available(self):
        base_url = os.environ.get("DOCKER_INFRA_BASE_URL", DEFAULT_BASE_URL)

        response = requests.get(f"{base_url.rstrip('/')}/swagger", timeout=10)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers.get("content-type", "").split(";")[0], "text/html")
        self.assertIn("SwaggerUIBundle", response.text)
        self.assertIn("/openapi.json", response.text)


if __name__ == "__main__":
    unittest.main()
