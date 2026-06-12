import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SERVICES_MODEL = ROOT / "src" / "model" / "struct" / "services.py"
MIGRATION_MODEL = ROOT / "src" / "model" / "struct" / "services_migration.py"
VOLUME_MIGRATION_MODEL = ROOT / "src" / "model" / "struct" / "service_volume_migration.py"
SNAPSHOT_RUNNER = ROOT / "src" / "model" / "struct" / "service_image_snapshot_runner.py"
SERVICES_API = ROOT / "src" / "app" / "page.services" / "api.py"
SERVICES_VIEW = ROOT / "src" / "app" / "page.services" / "view.pug"
SERVICES_TS = ROOT / "src" / "app" / "page.services" / "view.ts"
SEARCH_SELECT_TS = ROOT / "src" / "app" / "component.search.select" / "view.ts"
SEARCH_SELECT_HTML = ROOT / "src" / "app" / "component.search.select" / "view.html"


class ServiceMigrationStaticContractTest(unittest.TestCase):
    def test_service_migration_uses_snapshot_then_target_redeploy(self):
        services_model = SERVICES_MODEL.read_text(encoding="utf-8")
        migration_model = MIGRATION_MODEL.read_text(encoding="utf-8")
        volume_migration_model = VOLUME_MIGRATION_MODEL.read_text(encoding="utf-8")
        services_api = SERVICES_API.read_text(encoding="utf-8")
        snapshot_runner = SNAPSHOT_RUNNER.read_text(encoding="utf-8")
        view = SERVICES_VIEW.read_text(encoding="utf-8")
        view_ts = SERVICES_TS.read_text(encoding="utf-8")
        search_select_ts = SEARCH_SELECT_TS.read_text(encoding="utf-8")
        search_select_html = SEARCH_SELECT_HTML.read_text(encoding="utf-8")

        self.assertIn('ServiceMigrationMixin = wiz.model("struct/services_migration")', services_model)
        self.assertIn("def migrate_service():", services_api)
        self.assertIn("def support_options():", services_api)
        self.assertIn('nodes_model = wiz.model("struct").nodes', services_api)
        self.assertIn('payload = {"nodes": nodes_model.list()}', services_api)
        self.assertIn("services_model.migrate_background", services_api)

        self.assertIn('"service.migrate"', migration_model)
        self.assertIn("snapshot_service_image", migration_model)
        self.assertIn('"source": "service_migration_snapshot"', migration_model)
        self.assertIn('"force_recreate": True', migration_model)
        self.assertIn('"ensure_backup_registry": True', migration_model)
        self.assertIn('volume_migration = wiz.model("struct/service_volume_migration")', migration_model)
        self.assertIn("migrate_service_volumes", migration_model)
        self.assertIn('"volume_migration": volume_result', migration_model)
        self.assertIn("target_node_policy", migration_model)
        self.assertIn("container_snapshot", migration_model)
        self.assertIn("def compose_named_volumes", volume_migration_model)
        self.assertIn("docker volume create", volume_migration_model)
        self.assertIn("tar -cpf -", volume_migration_model)
        self.assertIn("tar -xpf -", volume_migration_model)
        self.assertIn("SERVICE_VOLUME_MIGRATION_FAILED", volume_migration_model)
        self.assertIn("def _ensure_registry_for_snapshot_node", snapshot_runner)
        self.assertIn("nodes.configure_backup_registry_for_node", snapshot_runner)
        self.assertIn("registry_setup", snapshot_runner)

        self.assertIn("서비스 마이그레이션", view)
        self.assertIn("wiz-component-search-select([items]=\"migrationNodeOptions()\"", view)
        self.assertNotIn('select([ngModel]="migrationTargetNodeId()"', view)
        self.assertIn("submitServiceMigration()", view)
        self.assertLess(view.index("detailTab() === 'versions'"), view.index('(click)="openMigrationModal()"'))
        self.assertNotIn("컨테이너 일시 정지 후 스냅샷", view)
        self.assertIn("migrate_service", view_ts)
        self.assertIn("pause: true", view_ts)
        self.assertIn("'service.migrate': '서비스 마이그레이션'", view_ts)
        self.assertIn("currentMigrationSourceNodeId", view_ts)
        self.assertIn("visualViewport", search_select_ts)
        self.assertIn("preventScroll: true", search_select_ts)
        self.assertIn("position: 'absolute'", search_select_ts)
        self.assertIn("zIndex: '220'", search_select_ts)
        self.assertIn('class="absolute z-[220]', search_select_html)
        self.assertIn("overflow-visible rounded-md", view)


if __name__ == "__main__":
    unittest.main()
