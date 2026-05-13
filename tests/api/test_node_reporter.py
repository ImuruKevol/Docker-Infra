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
NODES_SHARED_MODEL = ROOT / "src" / "model" / "struct" / "nodes_shared.py"
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
        nodes_shared_model = NODES_SHARED_MODEL.read_text(encoding="utf-8")
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
        self.assertIn("node_chart", metric_history_model)
        self.assertIn("dashboard_chart_from_metrics", metric_history_model)
        self.assertIn("dashboard_node_charts", metric_history_model)
        self.assertIn("DEDUPLICATE_WINDOW_SECONDS", metric_history_model)
        self.assertIn("RESOURCE_CHART_BUCKET_MINUTES = 10", metric_history_model)
        self.assertIn("RESOURCE_STAT_FIELDS", metric_history_model)
        self.assertIn("node_metric_history", dashboard_model)
        self.assertIn("node_resource_chart", dashboard_model)
        self.assertIn("node_resource_charts", dashboard_model)
        self.assertIn("_node_metric_rows_for_chart", dashboard_model)
        self.assertIn("nodeMetricPercent", dashboard_template)
        self.assertIn("서버 자원 추이", dashboard_template)
        self.assertIn('(click)="applyResourceRange()"', dashboard_template)
        self.assertIn('(click)="openNodeCharts()"', dashboard_template)
        self.assertIn("data-node-resource-chart", dashboard_template)
        self.assertIn("data-node-resource-metric", dashboard_template)
        self.assertIn("apexcharts", servers_view_ts)
        self.assertIn("apexcharts", dashboard_view_ts)
        self.assertNotIn("chart.js/auto", servers_view_ts)
        self.assertNotIn("chart.js/auto", dashboard_view_ts)
        self.assertIn("rangeArea", servers_view_ts)
        self.assertIn("rangeArea", dashboard_view_ts)
        self.assertNotIn("stacked: true", servers_view_ts)
        self.assertNotIn("stacked: true", dashboard_view_ts)
        self.assertIn("this.chartStatValue(row, 'memory_used_percent', 'min')", servers_view_ts)
        self.assertIn("this.chartStatValue(row, 'memory_used_percent', 'min')", dashboard_view_ts)
        self.assertIn("datetimeUTC: false", servers_view_ts)
        self.assertIn("datetimeUTC: false", dashboard_view_ts)
        self.assertIn("formatChartTooltipTime", servers_view_ts)
        self.assertIn("formatChartTooltipTime", dashboard_view_ts)
        self.assertIn("rangeTooltipOptions", servers_view_ts)
        self.assertIn("rangeTooltipOptions", dashboard_view_ts)
        self.assertIn("${title} Min", servers_view_ts)
        self.assertIn("${title} Average", dashboard_view_ts)
        self.assertIn("${title} Max", servers_view_ts)
        self.assertIn("seriesX", servers_view_ts)
        self.assertIn("seriesX", dashboard_view_ts)
        self.assertIn("timeZoneName: 'short'", servers_view_ts)
        self.assertIn("timeZoneName: 'short'", dashboard_view_ts)
        self.assertIn("resourceStatSummary", servers_view_ts)
        self.assertIn("resourceRangePayload", dashboard_view_ts)
        self.assertIn("nodeChartsOpen", dashboard_view_ts)
        self.assertIn('data-resource-chart="cpu"', servers_view)
        self.assertIn('data-resource-chart="memory"', servers_view)
        self.assertIn('data-resource-chart="storage"', servers_view)
        self.assertIn('data-resource-chart="cpu"', dashboard_template)
        self.assertIn('data-resource-chart="memory"', dashboard_template)
        self.assertIn('data-resource-chart="storage"', dashboard_template)
        self.assertNotIn("Used / Cache / Free", servers_view)
        self.assertIn("document.querySelectorAll('[data-resource-chart]')", servers_view_ts)
        self.assertIn("document.querySelectorAll('[data-resource-chart]')", dashboard_view_ts)
        self.assertIn("document.querySelectorAll('[data-node-resource-chart]')", dashboard_view_ts)
        self.assertIn("scheduleResourceChartRender", servers_view_ts)
        self.assertIn("scheduleResourceChartRender", dashboard_view_ts)
        self.assertIn("refreshCachedDetailInBackground", servers_view_ts)
        self.assertIn('wiz.call("cached_detail"', servers_view_ts)
        self.assertIn('persist: false', servers_view_ts)
        self.assertIn("pg_advisory_xact_lock", reporter_model)
        self.assertIn("pg_advisory_xact_lock", local_master_model)
        self.assertIn("start_at=body.get(\"start_at\")", servers_api)
        self.assertIn("end_at=body.get(\"end_at\")", servers_api)
        self.assertIn("start_date=body.get(\"start_date\")", dashboard_api)
        self.assertIn("end_date=body.get(\"end_date\")", dashboard_api)
        self.assertNotIn("monitoring.ensure_daemon()", servers_api)
        self.assertNotIn("monitoring.ensure_missing_exporters_async()", servers_api)
        self.assertIn("monitoring_auto_configure", servers_api)
        self.assertIn("_parse_datetime", metric_history_model)
        self.assertIn("class NodesMonitoring", monitoring_model)
        self.assertIn("ensure_exporters", monitoring_model)
        self.assertIn("ensure_collectors_if_needed_async", monitoring_model)
        self.assertIn("node.monitoring.collector.repair", monitoring_model)
        self.assertIn("check_exporters", monitoring_model)
        self.assertIn("issue_reporter_token", monitoring_model)
        self.assertIn("COLLECTOR_TIMER", monitoring_model)
        self.assertIn("node.monitoring.collector.ensure", monitoring_model)
        self.assertIn("REPORTER_BASE_URL_REQUIRED", monitoring_model)
        self.assertNotIn("ensure_daemon", monitoring_model)
        self.assertNotIn("ensure_missing_exporters_async", monitoring_model)
        self.assertNotIn("_daemon_loop", monitoring_model)
        self.assertIn("threading.Thread", monitoring_model)
        self.assertIn("def live_metric", nodes_runtime_model)
        self.assertIn("containers_refreshed_at", nodes_runtime_model)
        self.assertNotIn('"containers_refresh"', nodes_runtime_model)
        self.assertIn("astimezone(datetime.timezone.utc)", nodes_shared_model)
        self.assertIn('replace("+00:00", "Z")', metric_history_model)
        self.assertIn("metric_snapshot(node_id) if persist else nodes_model.live_metric(node_id)", servers_api)
        self.assertIn("monitoring.node_exporter.ensure", commands)
        self.assertIn("monitoring.node_exporter.status", commands)
        self.assertIn("monitoring.metrics_collector.ensure", commands)
        self.assertIn("monitoring.metrics_collector.status", commands)
        self.assertIn("systemctl enable", commands)
        self.assertIn("systemctl start", commands)
        self.assertIn("DOCKER_INFRA_METRICS_AGENT_VERSION", commands)
        self.assertIn("DOCKER_INFRA_METRICS_SAMPLE_SECONDS", commands)
        self.assertIn("configuration drift", commands)
        self.assertIn("OnUnitInactiveSec", commands)
        self.assertIn("TimeoutStartSec", commands)
        self.assertIn("systemctl is-failed", commands)
        self.assertNotIn("systemctl restart", commands)
        self.assertNotIn("enable --now", commands)
        self.assertIn("DOCKER_INFRA_METRICS_STATE_FILE", local_command_scripts)
        self.assertIn("NODE_METRICS_AGENT_SCRIPT", local_command_scripts)
        self.assertIn("resource_window", local_command_scripts)
        self.assertIn("collect_window", local_command_scripts)
        self.assertIn("memory_cache_percent", local_command_scripts)
        self.assertIn("memory_free_percent", local_command_scripts)
        self.assertIn('storage_used_percent": stat([disk.get("used_percent")])', local_command_scripts)
        self.assertNotIn('sample["storage"]', local_command_scripts)
        self.assertIn("/api/reporter/metrics", local_command_scripts)
        self.assertIn("systemd_collector", local_command_scripts)
        self.assertNotIn("sleep 1", local_command_scripts)
        self.assertIn('DEFAULT_NODE_METRIC_COLLECTION_INTERVAL_SECONDS = "600"', runtime_config)
        self.assertIn('DEFAULT_NODE_METRIC_SAMPLE_INTERVAL_SECONDS = "1"', runtime_config)
        self.assertIn("return max(600", runtime_config)
        self.assertIn("node_metric_collection_interval_seconds", runtime_config)
        self.assertIn("node_metric_sample_interval_seconds", runtime_config)
        self.assertIn("memory_cache_percent", metric_history_model)
        self.assertIn("memory_free_percent", metric_history_model)
        self.assertIn("MEMORY_STACK_KEYS", metric_history_model)
        self.assertIn("MEMORY_COMPONENT_STAT_FIELDS", metric_history_model)
        self.assertIn("DOCKER_INFRA_REPORTER_BASE_URL", runtime_config)
        self.assertIn("reporter_base_url", runtime_config)
        self.assertIn("ensure_collectors_if_needed_async", dashboard_api)
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
