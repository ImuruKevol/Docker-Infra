import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


class PlaywrightSetupTest(unittest.TestCase):
    def test_playwright_package_and_scripts_are_declared(self):
        package = json.loads((ROOT / "package.json").read_text(encoding="utf-8"))

        self.assertIn("@playwright/test", package["devDependencies"])
        self.assertEqual(package["scripts"]["e2e"], "playwright test")
        self.assertEqual(package["scripts"]["e2e:list"], "playwright test --list")

    def test_playwright_config_defines_required_runtime_outputs(self):
        config = (ROOT / "playwright.config.ts").read_text(encoding="utf-8")

        self.assertIn("DOCKER_INFRA_BASE_URL", config)
        self.assertIn("DOCKER_INFRA_E2E_OUTPUT_ROOT", config)
        self.assertIn("trace: 'retain-on-failure'", config)
        self.assertIn("screenshot: 'only-on-failure'", config)
        self.assertIn(".runtime/e2e", config)
        self.assertIn("Desktop Chrome", config)

    def test_e2e_helpers_and_specs_exist(self):
        expected = [
            "tests/e2e/helpers/env.ts",
            "tests/e2e/helpers/auth.ts",
            "tests/e2e/helpers/cleanup.ts",
            "tests/e2e/specs/access.spec.ts",
            "tests/e2e/specs/shell.spec.ts",
            "tests/e2e/specs/servers.spec.ts",
            "tests/e2e/specs/services.spec.ts",
        ]
        for path in expected:
            self.assertTrue((ROOT / path).is_file(), path)

    def test_e2e_specs_assert_real_auth_navigation(self):
        auth = (ROOT / "tests" / "e2e" / "helpers" / "auth.ts").read_text(encoding="utf-8")
        shell = (ROOT / "tests" / "e2e" / "specs" / "shell.spec.ts").read_text(encoding="utf-8")
        access = (ROOT / "tests" / "e2e" / "specs" / "access.spec.ts").read_text(encoding="utf-8")

        self.assertIn("toHaveURL(/\\/dashboard/)", auth)
        self.assertIn("redirects unauthenticated protected routes to access", shell)
        self.assertIn("toHaveURL(/\\/access/)", shell)
        self.assertNotIn("Password-only authentication is not available", auth)
        self.assertNotIn("P3|구현|활성화|Password-only", access)

    def test_access_page_has_stable_e2e_selectors(self):
        view = (ROOT / "src" / "app" / "page.access" / "view.pug").read_text(encoding="utf-8")

        self.assertIn('data-testid="password-input"', view)
        self.assertIn('data-testid="login-submit"', view)
        self.assertIn('data-testid="setup-password-input"', view)
        self.assertIn('data-testid="setup-submit"', view)
        self.assertIn('aria-label="비밀번호"', view)


if __name__ == "__main__":
    unittest.main()
