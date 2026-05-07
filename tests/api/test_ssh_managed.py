import importlib.util
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
MODULE_PATH = ROOT / "src" / "model" / "struct" / "ssh_managed.py"


def load_module():
    spec = importlib.util.spec_from_file_location("ssh_managed_test_module", MODULE_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


class SSHManagedPromptTest(unittest.TestCase):
    def test_interactive_password_run_handles_split_password_prompt(self):
        module = load_module()
        manager = module.Model
        script = (
            "import sys, time; "
            "sys.stdout.write('Pass'); sys.stdout.flush(); "
            "time.sleep(0.1); "
            "sys.stdout.write('word:'); sys.stdout.flush(); "
            "value = sys.stdin.readline().strip(); "
            "sys.stdout.write('\\nOK' if value == 'secret-pass' else '\\nFAIL'); sys.stdout.flush(); "
            "raise SystemExit(0 if value == 'secret-pass' else 7)"
        )

        result = manager.interactive_password_run([sys.executable, "-c", script], "secret-pass", 5)

        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["exit_code"], 0)
        self.assertIn("OK", result["stdout"])


if __name__ == "__main__":
    unittest.main()
