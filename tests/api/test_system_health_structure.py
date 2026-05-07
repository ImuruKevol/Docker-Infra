import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


class SystemHealthStructureTest(unittest.TestCase):
    def test_health_route_is_registered_as_source_route(self):
        route_root = ROOT / "src" / "route" / "api-system-health"
        with (route_root / "app.json").open("r", encoding="utf-8") as handle:
            app_config = json.load(handle)

        self.assertEqual(app_config["route"], "/api/system/health")
        self.assertEqual(app_config["category"], "system")
        self.assertEqual(app_config["controller"], "base")
        self.assertTrue((route_root / "controller.py").is_file())

    def test_health_model_keeps_domain_logic_out_of_route(self):
        model_path = ROOT / "src" / "model" / "struct" / "system.py"
        route_controller = (ROOT / "src" / "route" / "api-system-health" / "controller.py").read_text(
            encoding="utf-8"
        )

        self.assertTrue(model_path.is_file())
        self.assertIn('.system.health()', route_controller)


if __name__ == "__main__":
    unittest.main()
