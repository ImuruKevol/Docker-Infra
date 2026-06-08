import ast
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
MATCH_FUNCTION_FILES = [
    ROOT / "src" / "model" / "struct" / "webserver.py",
    ROOT / "src" / "app" / "page.services" / "api.py",
    ROOT / "src" / "app" / "page.services.create" / "api.py",
]
SERVICE_NGINX = ROOT / "src" / "model" / "struct" / "service_nginx.py"


def load_domain_match(path):
    module = ast.parse(path.read_text(encoding="utf-8"))
    function = next(node for node in module.body if isinstance(node, ast.FunctionDef) and node.name == "_domain_match")
    isolated = ast.Module(body=[function], type_ignores=[])
    ast.fix_missing_locations(isolated)
    namespace = {}
    exec(compile(isolated, str(path), "exec"), namespace)
    return namespace["_domain_match"]


def function_source(path, name):
    source = path.read_text(encoding="utf-8")
    module = ast.parse(source)
    function = next(node for node in ast.walk(module) if isinstance(node, ast.FunctionDef) and node.name == name)
    return ast.get_source_segment(source, function) or ""


class CertificateWildcardMatchTest(unittest.TestCase):
    def test_wildcard_certificate_matches_only_one_label(self):
        for path in MATCH_FUNCTION_FILES:
            with self.subTest(path=path.relative_to(ROOT)):
                domain_match = load_domain_match(path)
                self.assertTrue(domain_match("notion.nanoha.kr", "*.nanoha.kr"))
                self.assertTrue(domain_match("notion.sub.nanoha.kr", "*.sub.nanoha.kr"))
                self.assertTrue(domain_match("notion.sub.nanoha.kr", "notion.sub.nanoha.kr"))
                self.assertFalse(domain_match("nanoha.kr", "*.nanoha.kr"))
                self.assertFalse(domain_match("notion.sub.nanoha.kr", "*.nanoha.kr"))

    def test_runtime_certificate_lookup_requires_hostname_match(self):
        certificates_for_domain = function_source(ROOT / "src" / "model" / "struct" / "webserver.py", "certificates_for_domain")
        self.assertIn('names = [item.get("domain"), *((item.get("dns_names") or []))]', certificates_for_domain)
        self.assertNotIn('item.get("zone_id")', certificates_for_domain)

    def test_ddns_existing_ssl_without_matching_cert_falls_back_to_certbot(self):
        nginx = SERVICE_NGINX.read_text(encoding="utf-8")
        self.assertIn('ssl_mode in {"existing", "upload"}', nginx)
        self.assertIn('metadata.get("dns_provider") == "ddns"', nginx)
        self.assertIn("needs_managed_certificate", nginx)

    def test_certbot_issue_waits_for_dns_propagation_after_ddns_registration(self):
        nginx = SERVICE_NGINX.read_text(encoding="utf-8")
        apply_block = nginx[nginx.index("    def apply("):]
        self.assertIn("def _wait_certbot_dns_ready", nginx)
        self.assertIn("dns propagation", nginx)
        self.assertLess(apply_block.index("_ensure_dns_records"), apply_block.index("_wait_certbot_dns_ready"))
        self.assertLess(
            apply_block.index("_wait_certbot_dns_ready(certbot_targets"),
            apply_block.index("_issue_certificates(certbot_targets"),
        )


if __name__ == "__main__":
    unittest.main()
