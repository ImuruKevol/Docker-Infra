import json
from pathlib import Path

from tests.api.openapi_validator import assert_schema


ROOT = Path(__file__).resolve().parents[2]
OPENAPI_PATH = ROOT / "docs" / "api" / "openapi.json"


class OpenApiResponseHelper:
    def __init__(self, document=None):
        self.document = document or self.load_document()

    @staticmethod
    def load_document():
        with OPENAPI_PATH.open("r", encoding="utf-8") as handle:
            return json.load(handle)

    def schema_for_response(self, path, method, status_code, content_type="application/json"):
        operation = self.document["paths"][path][method.lower()]
        response = operation["responses"][str(status_code)]
        return response["content"][content_type]["schema"]

    def assert_response_payload(self, path, method, status_code, payload, content_type="application/json"):
        schema = self.schema_for_response(path, method, status_code, content_type=content_type)
        assert_schema(self.document, schema, payload)
