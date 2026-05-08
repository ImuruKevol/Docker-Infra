import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
OPERATIONS_MODEL = ROOT / "src" / "model" / "struct" / "operations.py"
MACROS_RUNNER = ROOT / "src" / "model" / "struct" / "macros_runner.py"


class SecretMaskingLogsStaticContractTest(unittest.TestCase):
    def test_operation_output_masks_runtime_secret_values(self):
        operations = OPERATIONS_MODEL.read_text(encoding="utf-8")

        self.assertIn("secret_values", operations)
        self.assertIn('text = text.replace(str(secret), "********")', operations)

    def test_macro_runner_writes_streaming_output_to_operation_log(self):
        runner = MACROS_RUNNER.read_text(encoding="utf-8")

        self.assertIn("operations_model.append_output", runner)
        self.assertIn("operations_model.transition", runner)
        self.assertNotIn("/api/jobs", runner)


if __name__ == "__main__":
    unittest.main()
