import os
from urllib.parse import urljoin

import requests

from tests.fixtures.openapi_response import OpenApiResponseHelper
from tests.fixtures.test_ids import make_test_run_id


DEFAULT_BASE_URL = "http://127.0.0.1:3001"


class DockerInfraApiClient:
    def __init__(self, base_url, test_run_id=None, session=None, response_helper=None):
        self.base_url = base_url.rstrip("/") + "/"
        self.test_run_id = test_run_id or make_test_run_id()
        self.session = session or requests.Session()
        self.response_helper = response_helper or OpenApiResponseHelper()
        self.session.headers.update({"X-Test-Run-ID": self.test_run_id})

    @classmethod
    def from_env(cls, testcase=None):
        base_url = os.environ.get("DOCKER_INFRA_BASE_URL", DEFAULT_BASE_URL)
        return cls(base_url, test_run_id=os.environ.get("DOCKER_INFRA_TEST_RUN_ID"))

    def url(self, path):
        return urljoin(self.base_url, path.lstrip("/"))

    def request(self, method, path, expected_status=None, validate=True, **kwargs):
        response = self.session.request(method.upper(), self.url(path), timeout=kwargs.pop("timeout", 10), **kwargs)
        if expected_status is not None and response.status_code != expected_status:
            raise AssertionError(f"expected HTTP {expected_status}, got {response.status_code}: {response.text[:200]}")

        if validate:
            content_type = response.headers.get("content-type", "").split(";")[0]
            if content_type == "application/json":
                self.response_helper.assert_response_payload(path, method, response.status_code, response.json())
        return response

    def get(self, path, **kwargs):
        return self.request("GET", path, **kwargs)

    def post(self, path, **kwargs):
        return self.request("POST", path, **kwargs)


def password_only_login(client, testcase=None, password=None):
    password = password or os.environ.get("DOCKER_INFRA_TEST_PASSWORD")
    if not password:
        if testcase is not None:
            testcase.skipTest("DOCKER_INFRA_TEST_PASSWORD is not set")
        raise RuntimeError("DOCKER_INFRA_TEST_PASSWORD is not set")

    response = client.post("/api/auth/login", json={"password": password}, validate=False)
    if response.status_code in {423, 503} and testcase is not None:
        testcase.skipTest("Password-only authentication requires a migrated and completed setup database")
    if response.status_code != 200:
        raise AssertionError(f"login failed with HTTP {response.status_code}")
    return response
