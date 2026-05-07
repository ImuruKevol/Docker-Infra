import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
API_TEST_ROOT = ROOT / "tests" / "api"


class TestPolicyTest(unittest.TestCase):
    def test_api_tests_do_not_import_docker_infra_models_directly(self):
        forbidden = [
            "MODEL_ROOT",
            "sys.path.append",
            "sys.path.insert",
            "from docker_infra",
            "import docker_infra",
            "wiz.model(",
        ]
        offenders = []
        for path in sorted(API_TEST_ROOT.glob("test_*.py")):
            if path.name == "test_test_policy.py":
                continue
            text = path.read_text(encoding="utf-8")
            for token in forbidden:
                if token in text:
                    offenders.append(f"{path.relative_to(ROOT)} contains {token!r}")

        self.assertEqual(offenders, [])

    def test_api_tests_do_not_use_fake_domain_executors_for_feature_success(self):
        pattern = re.compile(r"class Fake(Local|SSH|.*Executor|.*Service|.*Repository)|Fake(Local|SSH).*\(")
        offenders = []
        for path in sorted(API_TEST_ROOT.glob("test_*.py")):
            if path.name == "test_test_policy.py":
                continue
            text = path.read_text(encoding="utf-8")
            if pattern.search(text):
                offenders.append(str(path.relative_to(ROOT)))

        self.assertEqual(offenders, [])


if __name__ == "__main__":
    unittest.main()
