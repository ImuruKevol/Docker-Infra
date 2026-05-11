import datetime
import os
import unittest
from pathlib import Path

from tests.cleanup.cleanup_registry import CleanupRegistry, register_cleanup
from tests.cleanup.stale_cleanup import cleanup_stale_resources, write_resource_marker
from tests.fixtures.api_client import DockerInfraApiClient, password_only_login
from tests.fixtures.openapi_response import OpenApiResponseHelper
from tests.fixtures.test_ids import make_namespace, make_resource_names


ROOT = Path(__file__).resolve().parents[2]


class FakeResponse:
    def __init__(self, status_code, payload=None, content_type="application/json"):
        self.status_code = status_code
        self._payload = payload or {}
        self.headers = {"content-type": content_type}
        self.text = str(self._payload)

    def json(self):
        return self._payload


class FakeSession:
    def __init__(self, response):
        self.response = response
        self.headers = {}
        self.requests = []

    def request(self, method, url, timeout=10, **kwargs):
        self.requests.append({"method": method, "url": url, "timeout": timeout, **kwargs})
        return self.response


class FakeTestCase:
    def __init__(self):
        self.cleanups = []

    def addCleanup(self, callback):
        self.cleanups.append(callback)


class ApiTestHarnessTest(unittest.TestCase):
    def test_test_run_id_helpers_generate_expected_names(self):
        test_run_id = "12345678-90ab-cdef-1234-567890abcdef"
        namespace = make_namespace(test_run_id, run_date=datetime.date(2026, 5, 6))
        names = make_resource_names(test_run_id, run_date=datetime.date(2026, 5, 6), staging_zone="staging.test")

        self.assertEqual(namespace, "di_test_20260506_1234567890ab")
        self.assertEqual(names["namespace"], namespace)
        self.assertEqual(names["stack"], "di_test_1234567890ab")
        self.assertEqual(names["domain"], "di-test-1234567890ab.staging.test")
        self.assertEqual(names["image_tag"], "test-20260506-1234567890ab")
        self.assertEqual(names["job_label"], f"test_run_id={test_run_id}")

    def test_openapi_response_helper_validates_declared_payload(self):
        helper = OpenApiResponseHelper()
        payload = {
            "code": 200,
            "data": {
                "status": "ok",
                "service": "docker-infra",
                "version": "0.1.0",
                "timestamp": "2026-05-06T00:00:00Z",
                "checks": {
                    "api": {"status": "ok"},
                    "database": {"status": "not_configured", "schema_version": None},
                },
            },
        }

        helper.assert_response_payload("/api/system/health", "GET", 200, payload)

    def test_api_client_sends_test_run_id_and_validates_response(self):
        payload = {
            "code": 200,
            "data": {
                "status": "ok",
                "service": "docker-infra",
                "version": "0.1.0",
                "timestamp": "2026-05-06T00:00:00Z",
                "checks": {
                    "api": {"status": "ok"},
                    "database": {"status": "not_configured", "schema_version": None},
                },
            },
        }
        session = FakeSession(FakeResponse(200, payload=payload))
        client = DockerInfraApiClient("http://docker-infra.test", test_run_id="run-1", session=session)

        response = client.get("/api/system/health", expected_status=200)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(session.headers["X-Test-Run-ID"], "run-1")
        self.assertEqual(session.requests[0]["method"], "GET")
        self.assertEqual(session.requests[0]["url"], "http://docker-infra.test/api/system/health")

    def test_password_only_login_fixture_sends_no_identity_field(self):
        previous = os.environ.get("DOCKER_INFRA_TEST_PASSWORD")
        os.environ["DOCKER_INFRA_TEST_PASSWORD"] = "secret-for-test"
        try:
            session = FakeSession(FakeResponse(200, payload={"code": 200, "data": {}}))
            client = DockerInfraApiClient("http://docker-infra.test", test_run_id="run-1", session=session)

            password_only_login(client)

            self.assertEqual(session.requests[0]["json"], {"password": "secret-for-test"})
        finally:
            if previous is None:
                os.environ.pop("DOCKER_INFRA_TEST_PASSWORD", None)
            else:
                os.environ["DOCKER_INFRA_TEST_PASSWORD"] = previous

    def test_cleanup_registry_retries_failures_and_reports_remaining_failures(self):
        registry = CleanupRegistry()
        attempts = {"flaky": 0}

        def flaky_cleanup():
            attempts["flaky"] += 1
            if attempts["flaky"] == 1:
                raise RuntimeError("try again")

        def broken_cleanup():
            raise RuntimeError("still broken")

        registry.add("flaky", flaky_cleanup, retries=1)
        registry.add("broken", broken_cleanup, retries=1)

        with self.assertRaisesRegex(AssertionError, "broken"):
            registry.run()

        self.assertEqual(attempts["flaky"], 2)
        self.assertEqual(registry.last_report["failed"][0]["attempts"], 2)
        self.assertEqual(registry.last_report["failed"][0]["label"], "broken")
        self.assertIn("flaky", {item["label"] for item in registry.last_report["succeeded"]})

    def test_cleanup_registry_can_be_registered_as_finalizer(self):
        testcase = FakeTestCase()
        registry = register_cleanup(testcase)
        cleaned = []
        registry.add("record", lambda: cleaned.append("done"))

        self.assertEqual(len(testcase.cleanups), 1)
        testcase.cleanups[0]()
        self.assertEqual(cleaned, ["done"])

    def test_stale_cleanup_removes_only_marked_old_test_resources(self):
        now = datetime.datetime(2026, 5, 6, tzinfo=datetime.timezone.utc)
        stale = ROOT / ".runtime" / "test" / "services" / "stale-resource"
        fresh = ROOT / ".runtime" / "test" / "services" / "fresh-resource"
        write_resource_marker(stale, "old-run", "di_test_20260505_old", created_at=now - datetime.timedelta(hours=25))
        write_resource_marker(fresh, "new-run", "di_test_20260506_new", created_at=now)

        removed = cleanup_stale_resources(older_than_hours=24, now=now)

        self.assertEqual([item["path"] for item in removed], [str(stale)])
        self.assertFalse(stale.exists())
        self.assertTrue(fresh.exists())

        cleanup = CleanupRegistry()
        cleanup.add_path(fresh)
        cleanup.run()


if __name__ == "__main__":
    unittest.main()
