import json
import os
import unittest
from pathlib import Path

from tests.fixtures.api_client import DockerInfraApiClient, password_only_login


ROOT = Path(__file__).resolve().parents[2]
NODES_PATH_ROUTE = ROOT / "src" / "route" / "api-nodes-path" / "controller.py"
REPORTER_ROUTE = ROOT / "src" / "route" / "api-reporter-metrics" / "controller.py"
SERVERS_VIEW = ROOT / "src" / "app" / "page.servers" / "view.pug"
SERVERS_VIEW_TS = ROOT / "src" / "app" / "page.servers" / "view.ts"
SERVERS_API = ROOT / "src" / "app" / "page.servers" / "api.py"
REPORTER_MODEL = ROOT / "src" / "model" / "struct" / "nodes_reporter.py"
LOCAL_MASTER_MODEL = ROOT / "src" / "model" / "struct" / "nodes_local_master.py"
METRIC_HISTORY_MODEL = ROOT / "src" / "model" / "struct" / "nodes_metric_history.py"
MONITORING_MODEL = ROOT / "src" / "model" / "struct" / "nodes_monitoring.py"
NODES_RUNTIME_MODEL = ROOT / "src" / "model" / "struct" / "nodes_runtime.py"
DASHBOARD_MODEL = ROOT / "src" / "model" / "struct" / "infra_catalog_registry.py"
DASHBOARD_API = ROOT / "src" / "app" / "page.dashboard" / "api.py"
DASHBOARD_TEMPLATE = ROOT / "src" / "app" / "page.dashboard" / "view.pug"
DASHBOARD_VIEW_TS = ROOT / "src" / "app" / "page.dashboard" / "view.ts"
RUNTIME_CONFIG = ROOT / "config" / "docker_infra.py"
COMMANDS = ROOT / "src" / "model" / "struct" / "local_command_catalog.py"
LOCAL_COMMAND_SCRIPTS = ROOT / "src" / "model" / "struct" / "local_command_scripts.py"


class NodeReporterStaticContractTest(unittest.TestCase):
    def test_reporter_routes_and_servers_page_contract_are_declared(self):
        nodes_controller = NODES_PATH_ROUTE.read_text(encoding="utf-8")
        reporter_controller = REPORTER_ROUTE.read_text(encoding="utf-8")
        servers_view = SERVERS_VIEW.read_text(encoding="utf-8")
        servers_view_ts = SERVERS_VIEW_TS.read_text(encoding="utf-8")
        servers_api = SERVERS_API.read_text(encoding="utf-8")
        reporter_model = REPORTER_MODEL.read_text(encoding="utf-8")
        local_master_model = LOCAL_MASTER_MODEL.read_text(encoding="utf-8")
        metric_history_model = METRIC_HISTORY_MODEL.read_text(encoding="utf-8")
        monitoring_model = MONITORING_MODEL.read_text(encoding="utf-8")
        nodes_runtime_model = NODES_RUNTIME_MODEL.read_text(encoding="utf-8")
        dashboard_model = DASHBOARD_MODEL.read_text(encoding="utf-8")
        dashboard_api = DASHBOARD_API.read_text(encoding="utf-8")
        dashboard_template = DASHBOARD_TEMPLATE.read_text(encoding="utf-8")
        dashboard_view_ts = DASHBOARD_VIEW_TS.read_text(encoding="utf-8")
        runtime_config = RUNTIME_CONFIG.read_text(encoding="utf-8")
        commands = COMMANDS.read_text(encoding="utf-8")
        local_command_scripts = LOCAL_COMMAND_SCRIPTS.read_text(encoding="utf-8")

        for token in ['action == "reporter-token"', 'action == "metrics"', 'action == "containers"']:
            self.assertIn(token, nodes_controller)
        self.assertIn("ingest_metric", reporter_controller)
        self.assertIn("metric_history.append", reporter_model)
        self.assertIn("metric_history.append_db_row", local_master_model)
        self.assertIn("csv.DictWriter", metric_history_model)
        self.assertIn("node-metrics", metric_history_model)
        self.assertIn("dashboard_chart", metric_history_model)
        self.assertIn("node_metric_history", dashboard_model)
        self.assertIn("node_resource_chart", dashboard_model)
        self.assertIn("nodeMetricPercent", dashboard_template)
        self.assertIn("서버 자원 추이", dashboard_template)
        self.assertIn("chart.js/auto", servers_view_ts)
        self.assertIn("chart.js/auto", dashboard_view_ts)
        self.assertIn('data-resource-chart-canvas="server"', servers_view)
        self.assertIn('data-resource-chart-canvas="dashboard"', dashboard_template)
        self.assertIn("document.querySelector('[data-resource-chart-canvas=\"server\"]')", servers_view_ts)
        self.assertIn("document.querySelector('[data-resource-chart-canvas=\"dashboard\"]')", dashboard_view_ts)
        self.assertIn("scheduleResourceChartRender", servers_view_ts)
        self.assertIn("scheduleResourceChartRender", dashboard_view_ts)
        self.assertIn("refreshCachedDetailInBackground", servers_view_ts)
        self.assertIn('wiz.call("cached_detail"', servers_view_ts)
        self.assertIn('persist: false', servers_view_ts)
        self.assertIn("start_at=body.get(\"start_at\")", servers_api)
        self.assertIn("end_at=body.get(\"end_at\")", servers_api)
        self.assertNotIn("monitoring.ensure_daemon()", servers_api)
        self.assertNotIn("monitoring.ensure_missing_exporters_async()", servers_api)
        self.assertIn("monitoring_auto_configure", servers_api)
        self.assertIn("_parse_datetime", metric_history_model)
        self.assertIn("class NodesMonitoring", monitoring_model)
        self.assertIn("ensure_exporters", monitoring_model)
        self.assertIn("check_exporters", monitoring_model)
        self.assertNotIn("ensure_daemon", monitoring_model)
        self.assertNotIn("ensure_missing_exporters_async", monitoring_model)
        self.assertNotIn("_daemon_loop", monitoring_model)
        self.assertIn("threading.Thread", monitoring_model)
        self.assertIn("def live_metric", nodes_runtime_model)
        self.assertIn("metric_snapshot(node_id) if persist else nodes_model.live_metric(node_id)", servers_api)
        self.assertIn("monitoring.node_exporter.ensure", commands)
        self.assertIn("monitoring.node_exporter.status", commands)
        self.assertIn("systemctl enable", commands)
        self.assertIn("systemctl start", commands)
        self.assertNotIn("systemctl restart", commands)
        self.assertNotIn("enable --now", commands)
        self.assertIn("DOCKER_INFRA_METRICS_STATE_FILE", local_command_scripts)
        self.assertNotIn("sleep 1", local_command_scripts)
        self.assertIn('DEFAULT_NODE_METRIC_COLLECTION_INTERVAL_SECONDS = "600"', runtime_config)
        self.assertIn("return max(600", runtime_config)
        self.assertIn("node_metric_collection_interval_seconds", runtime_config)
        self.assertNotIn("nodes_monitoring", dashboard_api)
        self.assertIn("def ensure_monitoring_agent():", servers_api)
        self.assertIn("def resource_history():", servers_api)
        self.assertIn("def delete_resource_history():", servers_api)
        self.assertIn("overview()", servers_api)
        self.assertIn("정보 수집 중", servers_view)
        self.assertNotIn("모니터링 구성됨", servers_view)
        for token in [
            'data-testid="servers-node-list"',
            'data-testid="servers-detail"',
            'data-testid="servers-cpu"',
            'data-testid="servers-memory"',
            'data-testid="servers-storage"',
            'data-testid="servers-containers-table"',
        ]:
            self.assertIn(token, servers_view)


class NodeReporterLiveFlowTest(unittest.TestCase):
    def setUp(self):
        self.client = DockerInfraApiClient.from_env(self)
        password_only_login(self.client, testcase=self)

    def test_configured_node_reporter_token_metric_and_container_flow(self):
        node_id = os.environ.get("DOCKER_INFRA_TEST_NODE_ID")
        if not node_id:
            self.skipTest("DOCKER_INFRA_TEST_NODE_ID is not set")

        token_response = self.client.post(f"/api/nodes/{node_id}/reporter-token", json={}, validate=False)
        self.assertEqual(token_response.status_code, 200, token_response.text[:500])
        token = token_response.json()["data"]["token"]

        metric = self.client.post(
            "/api/reporter/metrics",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "node_id": node_id,
                "cpu_percent": 12.5,
                "memory": {"used_percent": 25.0},
                "storage": {"used_percent": 40.0},
                "containers": {"items": [{"id": "test-container", "name": "web", "state": "running"}]},
                "metadata": {"test_run_id": self.client.test_run_id},
            },
            validate=False,
        )
        metrics = self.client.get(f"/api/nodes/{node_id}/metrics?limit=1", validate=False)
        containers = self.client.get(f"/api/nodes/{node_id}/containers", validate=False)

        for response in [metric, metrics, containers]:
            self.assertEqual(response.status_code, 200, response.text[:500])
        self.assertEqual(containers.json()["data"]["containers"][0]["id"], "test-container")
        self.assertNotIn(token, json.dumps(metrics.json(), ensure_ascii=False))


if __name__ == "__main__":
    unittest.main()
