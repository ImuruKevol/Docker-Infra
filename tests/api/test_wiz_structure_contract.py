import ast
import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
WIZ_ROOT = ROOT.parents[1]


def is_wiz_response_call(node):
    if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Attribute):
        return False
    value = node.func.value
    return (
        isinstance(value, ast.Attribute)
        and value.attr == "response"
        and isinstance(value.value, ast.Name)
        and value.value.id == "wiz"
    )


class WizStructureContractTest(unittest.TestCase):
    def test_model_files_declare_model_and_stay_small(self):
        for path in sorted((ROOT / "src" / "model").rglob("*.py")):
            with self.subTest(path=path.relative_to(ROOT)):
                text = path.read_text(encoding="utf-8")
                self.assertLessEqual(len(text.splitlines()), 300)
                tree = ast.parse(text, filename=str(path))
                self.assertTrue(
                    any(isinstance(node, ast.Assign) and any(getattr(target, "id", None) == "Model" for target in node.targets) for node in tree.body),
                    "WIZ model files must expose Model",
                )

    def test_wiz_response_is_not_called_inside_try_except_blocks(self):
        scan_roots = [ROOT / "src" / "app", ROOT / "src" / "route", ROOT / "src" / "controller"]
        failures = []
        for scan_root in scan_roots:
            for path in sorted(scan_root.rglob("*.py")):
                if "src/portal/" in path.as_posix():
                    continue
                tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
                for try_node in [node for node in ast.walk(tree) if isinstance(node, ast.Try)]:
                    blocks = [try_node.body, try_node.orelse, try_node.finalbody]
                    blocks.extend(handler.body for handler in try_node.handlers)
                    for block in blocks:
                        for child in block:
                            for nested in ast.walk(child):
                                if is_wiz_response_call(nested):
                                    failures.append(f"{path.relative_to(ROOT)}:{nested.lineno}")
        self.assertEqual(failures, [])

    def test_boot_base_user_and_route_controller_boundaries(self):
        boot = (WIZ_ROOT / "config" / "boot.py").read_text(encoding="utf-8")
        base = (ROOT / "src" / "controller" / "base.py").read_text(encoding="utf-8")
        user = (ROOT / "src" / "controller" / "user.py").read_text(encoding="utf-8")

        for token in ["def bootstrap(app, config):", "def before_request(wiz):", "def after_request(wiz, response):", "SESSION_COOKIE_NAME"]:
            self.assertIn(token, boot)
        self.assertNotIn("SESSION_COOKIE", base)
        self.assertNotIn("enforce_access", base)
        self.assertIn("AUTHENTICATION_REQUIRED", user)

        protected_routes = [
            "api-compose-validate",
            "api-jobs",
            "api-jobs-path",
            "api-nodes",
            "api-nodes-path",
            "api-system-local-command-check",
            "api-system-local-master-ensure",
            "api-system-settings",
        ]
        for route in protected_routes:
            app_json = ROOT / "src" / "route" / route / "app.json"
            with self.subTest(route=route):
                self.assertEqual(json.loads(app_json.read_text(encoding="utf-8"))["controller"], "user")

    def test_runtime_config_owns_database_and_daemon_env_loading(self):
        runtime_config = ROOT / "config" / "docker_infra.py"
        self.assertTrue(runtime_config.is_file())
        config_text = runtime_config.read_text(encoding="utf-8")
        self.assertIn("config.env", config_text)
        self.assertIn("def database_url(env=None):", config_text)

        model_paths = [
            ROOT / "src" / "model" / "db" / "postgres.py",
            ROOT / "src" / "model" / "struct" / "settings.py",
            ROOT / "src" / "model" / "struct" / "local_executor.py",
            ROOT / "src" / "model" / "struct" / "setup_environment.py",
        ]
        for path in model_paths:
            with self.subTest(path=path.relative_to(ROOT)):
                text = path.read_text(encoding="utf-8")
                self.assertNotIn("os.environ", text)
                self.assertIn('wiz.config("docker_infra")', text)

        service_file = Path("/etc/systemd/system/wiz.docker-infra.service")
        if service_file.is_file():
            self.assertIn("EnvironmentFile=-/root/docker-infra/config.env", service_file.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
