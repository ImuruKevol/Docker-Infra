import datetime
import shlex
import threading

from psycopg.types.json import Jsonb


config = wiz.config("docker_infra")
connect = wiz.model("db/postgres").connect
nodes = wiz.model("struct/nodes")
operations = wiz.model("struct/operations")

EXPORTER_CONTAINER = "docker-infra-node-exporter"
EXPORTER_SERVICE = "docker-infra-node-exporter.service"
COLLECTOR_SERVICE = "docker-infra-node-metrics.service"
COLLECTOR_TIMER = "docker-infra-node-metrics.timer"
COLLECTOR_SCRIPT = "/usr/local/bin/docker-infra-node-metrics-agent"
COLLECTOR_ENV = "/etc/docker-infra/node-metrics.env"
COLLECTOR_STATE_FILE = "/var/lib/docker-infra/node-metrics.prev"


class NodesMonitoring:
    def __init__(self):
        self._lock = threading.Lock()
        self._running = False
        self._last_tick_at = None
        self._last_result = None
        self._collecting_node_ids = []
        self._repair_running = False
        self._last_repair_at = None
        self._last_repair_result = None

    def _recent(self, seconds):
        if self._last_tick_at is None:
            return False
        return (datetime.datetime.now(datetime.timezone.utc) - self._last_tick_at).total_seconds() < seconds

    def _repair_recent(self, seconds=300):
        if self._last_repair_at is None:
            return False
        return (datetime.datetime.now(datetime.timezone.utc) - self._last_repair_at).total_seconds() < seconds

    def _exporter_script(self, image):
        return (
            "set -eu\n"
            "SUDO=''\n"
            "if [ \"$(id -u)\" != '0' ]; then SUDO='sudo -n'; fi\n"
            "DOCKER_BIN=$(command -v docker)\n"
            f"UNIT=/etc/systemd/system/{shlex.quote(EXPORTER_SERVICE)}\n"
            f"cat > /tmp/{shlex.quote(EXPORTER_SERVICE)} <<EOF\n"
            "[Unit]\n"
            "Description=Docker Infra node exporter\n"
            "After=docker.service network-online.target\n"
            "Wants=docker.service network-online.target\n\n"
            "[Service]\n"
            "Restart=always\n"
            "RestartSec=5\n"
            f"ExecStartPre=-${{DOCKER_BIN}} rm -f {EXPORTER_CONTAINER}\n"
            f"ExecStart=${{DOCKER_BIN}} run --rm --name {EXPORTER_CONTAINER} --pid=host --net=host -v /:/host:ro,rslave {image} --path.rootfs=/host\n"
            f"ExecStop=-${{DOCKER_BIN}} rm -f {EXPORTER_CONTAINER}\n\n"
            "[Install]\n"
            "WantedBy=multi-user.target\n"
            "EOF\n"
            f"$SUDO mv /tmp/{shlex.quote(EXPORTER_SERVICE)} \"$UNIT\"\n"
            "$SUDO systemctl daemon-reload\n"
            f"$SUDO systemctl enable {shlex.quote(EXPORTER_SERVICE)}\n"
            f"$SUDO systemctl start {shlex.quote(EXPORTER_SERVICE)}\n"
            f"$SUDO systemctl is-active --quiet {shlex.quote(EXPORTER_SERVICE)}\n"
            "printf 'Running\n'\n"
            f"$SUDO systemctl --no-pager --full status {shlex.quote(EXPORTER_SERVICE)} | sed -n '1,12p'\n"
        )

    def _exporter_status_script(self):
        return (
            "set -eu\n"
            "SUDO=''\n"
            "if [ \"$(id -u)\" != '0' ]; then SUDO='sudo -n'; fi\n"
            f"$SUDO systemctl is-active --quiet {shlex.quote(EXPORTER_SERVICE)}\n"
            "printf 'Running\n'\n"
            f"$SUDO systemctl --no-pager --full status {shlex.quote(EXPORTER_SERVICE)} | sed -n '1,12p'\n"
        )

    def _run_exporter_ensure(self, node, env=None):
        image = config.node_exporter_image(env)
        if node.get("is_local_master") or node.get("role") == "local_master" or node.get("name") == "local-master":
            return nodes.local_executor.run(
                "monitoring.node_exporter.ensure",
                params={"image": image, "container_name": EXPORTER_CONTAINER, "service_name": EXPORTER_SERVICE},
                timeout_seconds=120,
                env=env,
            )
        return nodes._run_ssh_command(
            node,
            ["sh", "-lc", self._exporter_script(image)],
            timeout_seconds=120,
            env=env,
        )

    def _run_exporter_status(self, node, env=None):
        if node.get("is_local_master") or node.get("role") == "local_master" or node.get("name") == "local-master":
            return nodes.local_executor.run(
                "monitoring.node_exporter.status",
                params={"service_name": EXPORTER_SERVICE},
                timeout_seconds=20,
                env=env,
            )
        return nodes._run_ssh_command(
            node,
            ["sh", "-lc", self._exporter_status_script()],
            timeout_seconds=20,
            env=env,
        )

    def _reporter_base_url(self, payload=None, env=None):
        configured = config.reporter_base_url(env)
        requested = (payload or {}).get("reporter_base_url") or (payload or {}).get("base_url")
        return str(requested or configured or "").rstrip("/")

    def _collector_params(self, node_id, reporter_token, payload=None, env=None):
        interval = config.node_metric_collection_interval_seconds(env)
        return {
            "node_id": node_id,
            "reporter_token": reporter_token,
            "reporter_base_url": self._reporter_base_url(payload, env=env),
            "interval_seconds": interval,
            "service_name": COLLECTOR_SERVICE,
            "timer_name": COLLECTOR_TIMER,
            "script_path": COLLECTOR_SCRIPT,
            "env_path": COLLECTOR_ENV,
            "state_file": COLLECTOR_STATE_FILE,
        }

    def _collector_script(self, params):
        return nodes.local_executor._argv(
            "monitoring.metrics_collector.ensure",
            nodes.local_executor._command_spec("monitoring.metrics_collector.ensure"),
            params,
        )[2]

    def _collector_status_script(self):
        return nodes.local_executor._argv(
            "monitoring.metrics_collector.status",
            nodes.local_executor._command_spec("monitoring.metrics_collector.status"),
            {"service_name": COLLECTOR_SERVICE, "timer_name": COLLECTOR_TIMER},
        )[2]

    def _run_collector_ensure(self, node, reporter_token, payload=None, env=None):
        params = self._collector_params(node["id"], reporter_token, payload=payload, env=env)
        if node.get("is_local_master") or node.get("role") == "local_master" or node.get("name") == "local-master":
            return nodes.local_executor.run(
                "monitoring.metrics_collector.ensure",
                params=params,
                timeout_seconds=120,
                env=env,
            )
        return nodes._run_ssh_command(
            node,
            ["sh", "-lc", self._collector_script(params)],
            timeout_seconds=120,
            env=env,
        )

    def _run_collector_status(self, node, env=None):
        if node.get("is_local_master") or node.get("role") == "local_master" or node.get("name") == "local-master":
            return nodes.local_executor.run(
                "monitoring.metrics_collector.status",
                params={"service_name": COLLECTOR_SERVICE, "timer_name": COLLECTOR_TIMER},
                timeout_seconds=20,
                env=env,
            )
        return nodes._run_ssh_command(
            node,
            ["sh", "-lc", self._collector_status_script()],
            timeout_seconds=20,
            env=env,
        )

    def _mark_agent(self, node_id, result, env=None):
        configured = result.get("status") == "ok"
        with connect(env=env) as connection:
            with connection.cursor() as cursor:
                cursor.execute("SELECT metadata FROM nodes WHERE id = %s", (node_id,))
                row = cursor.fetchone()
                metadata = dict((row or {}).get("metadata") or {})
                metadata["monitoring_agent"] = {
                    "configured": configured,
                    "status": result.get("status"),
                    "runtime_status": "running" if configured else "stopped",
                    "running": configured,
                    "exit_code": result.get("exit_code"),
                    "service": COLLECTOR_SERVICE,
                    "timer": COLLECTOR_TIMER,
                    "script": COLLECTOR_SCRIPT,
                    "collector": {
                        "service": COLLECTOR_SERVICE,
                        "timer": COLLECTOR_TIMER,
                        "interval_seconds": config.node_metric_collection_interval_seconds(env),
                    },
                    "checked_at": datetime.datetime.now(datetime.timezone.utc).isoformat().replace("+00:00", "Z"),
                }
                cursor.execute("UPDATE nodes SET metadata = %s, updated_at = now() WHERE id = %s", (Jsonb(metadata), node_id))

    def state(self):
        with self._lock:
            return {
                "running": self._running,
                "last_tick_at": self._last_tick_at.isoformat().replace("+00:00", "Z") if self._last_tick_at else None,
                "collecting_node_ids": list(self._collecting_node_ids),
                "last_result": self._last_result,
                "collector_repair_running": self._repair_running,
                "last_collector_repair_at": self._last_repair_at.isoformat().replace("+00:00", "Z") if self._last_repair_at else None,
                "last_collector_repair_result": self._last_repair_result,
            }

    def _monitoring_configured(self, node):
        metadata = (node or {}).get("metadata") or {}
        return bool((metadata.get("monitoring_agent") or {}).get("configured"))

    def _node_ids_for_payload(self, payload=None, env=None):
        body = payload or {}
        target_node_id = str(body.get("node_id") or "").strip()
        try:
            rows = nodes.list(env=env)
        except Exception:
            return []
        if target_node_id:
            rows = [item for item in rows if item.get("id") == target_node_id]
        elif not body.get("include_unconfigured"):
            rows = [item for item in rows if self._monitoring_configured(item)]
        return [str(item.get("id")) for item in rows if item.get("id")]

    def ensure_exporters(self, payload=None, env=None):
        body = dict(payload or {})
        body["reporter_base_url"] = self._reporter_base_url(body, env=env)
        if not body["reporter_base_url"]:
            raise nodes.NodeError(400, "자원 수집 reporter_base_url을 확인할 수 없습니다.", "REPORTER_BASE_URL_REQUIRED")
        target_node_id = str(body.get("node_id") or "").strip()
        selected = []
        for item in nodes.list(env=env):
            if target_node_id and item.get("id") != target_node_id:
                continue
            selected.append(nodes.detail(item["id"], env=env))
        if target_node_id and not selected:
            raise nodes.NodeError(404, "서버를 찾을 수 없습니다.", "NODE_NOT_FOUND")
        results = []
        failed = 0
        for node in selected:
            token_result = nodes.issue_reporter_token(node["id"], env=env)
            result = self._run_collector_ensure(node, token_result["token"], payload=body, env=env)
            ok = result.get("status") == "ok"
            try:
                self._mark_agent(node["id"], result, env=env)
            except Exception:
                pass
            if not ok:
                failed += 1
            results.append({
                "node": {"id": node["id"], "name": node["name"], "host": node["host"]},
                "status": "succeeded" if ok else "failed",
                "check": {
                    "status": result.get("status"),
                    "exit_code": result.get("exit_code"),
                    "stdout": result.get("stdout"),
                    "stderr": result.get("stderr"),
                },
                "collector": {"service": COLLECTOR_SERVICE, "timer": COLLECTOR_TIMER},
            })
        operation = operations.create(
            "node.monitoring.collector.ensure",
            target_type="node" if target_node_id else "nodes",
            target_id=target_node_id or None,
            status="failed" if failed else "succeeded",
            message="서버 자원 수집 systemd timer를 확인했습니다.",
            requested_payload={"node_id": target_node_id, "service": COLLECTOR_SERVICE, "timer": COLLECTOR_TIMER},
            result_payload={"count": len(results), "failed": failed, "results": results},
            env=env,
        )
        return {"operation": operation, "results": results, "failed": failed, "succeeded": len(results) - failed}

    def ensure_collectors_if_needed(self, payload=None, env=None):
        body = dict(payload or {})
        body["reporter_base_url"] = self._reporter_base_url(body, env=env)
        if not body["reporter_base_url"]:
            return {"status": "skipped", "reason": "reporter_base_url_required", "results": [], "failed": 0, "succeeded": 0}
        target_node_id = str(body.get("node_id") or "").strip()
        selected = []
        for item in nodes.list(env=env):
            if target_node_id and item.get("id") != target_node_id:
                continue
            selected.append(nodes.detail(item["id"], env=env))
        if target_node_id and not selected:
            raise nodes.NodeError(404, "서버를 찾을 수 없습니다.", "NODE_NOT_FOUND")
        results = []
        failed = 0
        repaired = 0
        for node in selected:
            status_result = self._run_collector_status(node, env=env)
            if status_result.get("status") == "ok":
                try:
                    self._mark_agent(node["id"], status_result, env=env)
                except Exception:
                    pass
                results.append({
                    "node": {"id": node["id"], "name": node["name"], "host": node["host"]},
                    "status": "running",
                    "action": "checked",
                    "check": {
                        "status": status_result.get("status"),
                        "exit_code": status_result.get("exit_code"),
                        "stdout": status_result.get("stdout"),
                        "stderr": status_result.get("stderr"),
                    },
                    "collector": {"service": COLLECTOR_SERVICE, "timer": COLLECTOR_TIMER},
                })
                continue
            token_result = nodes.issue_reporter_token(node["id"], env=env)
            ensure_result = self._run_collector_ensure(node, token_result["token"], payload=body, env=env)
            ok = ensure_result.get("status") == "ok"
            try:
                self._mark_agent(node["id"], ensure_result, env=env)
            except Exception:
                pass
            if ok:
                repaired += 1
            else:
                failed += 1
            results.append({
                "node": {"id": node["id"], "name": node["name"], "host": node["host"]},
                "status": "repaired" if ok else "failed",
                "action": "reinstalled",
                "previous_check": {
                    "status": status_result.get("status"),
                    "exit_code": status_result.get("exit_code"),
                    "stdout": status_result.get("stdout"),
                    "stderr": status_result.get("stderr"),
                },
                "check": {
                    "status": ensure_result.get("status"),
                    "exit_code": ensure_result.get("exit_code"),
                    "stdout": ensure_result.get("stdout"),
                    "stderr": ensure_result.get("stderr"),
                },
                "collector": {"service": COLLECTOR_SERVICE, "timer": COLLECTOR_TIMER},
            })
        operation = operations.create(
            "node.monitoring.collector.repair",
            target_type="node" if target_node_id else "nodes",
            target_id=target_node_id or None,
            status="failed" if failed else "succeeded",
            message="서버 자원 수집 systemd timer를 점검하고 누락 시 재구성했습니다.",
            requested_payload={"node_id": target_node_id, "service": COLLECTOR_SERVICE, "timer": COLLECTOR_TIMER},
            result_payload={"count": len(results), "failed": failed, "repaired": repaired, "results": results},
            env=env,
        )
        return {"operation": operation, "results": results, "failed": failed, "repaired": repaired, "succeeded": len(results) - failed}

    def _execute_repair(self, payload=None, env=None):
        try:
            self._last_repair_result = self.ensure_collectors_if_needed(payload or {}, env=env)
        except Exception as exc:
            self._last_repair_result = {"failed": 1, "succeeded": 0, "message": str(exc)}
        finally:
            with self._lock:
                self._repair_running = False

    def ensure_collectors_if_needed_async(self, payload=None, env=None):
        body = dict(payload or {})
        with self._lock:
            if self._repair_running:
                return {"scheduled": False, "reason": "running", "last_result": self._last_repair_result}
            if not body.get("force") and self._repair_recent(300):
                return {"scheduled": False, "reason": "throttled", "last_result": self._last_repair_result}
            self._repair_running = True
            self._last_repair_at = datetime.datetime.now(datetime.timezone.utc)
        worker = threading.Thread(target=self._execute_repair, kwargs={"payload": body, "env": env}, daemon=True)
        worker.start()
        return {"scheduled": True, "reason": "started"}

    def check_exporters(self, payload=None, env=None):
        body = payload or {}
        target_node_id = str(body.get("node_id") or "").strip()
        selected = []
        for item in nodes.list(env=env):
            if target_node_id and item.get("id") != target_node_id:
                continue
            selected.append(nodes.detail(item["id"], env=env))
        if target_node_id and not selected:
            raise nodes.NodeError(404, "서버를 찾을 수 없습니다.", "NODE_NOT_FOUND")
        results = []
        failed = 0
        for node in selected:
            result = self._run_collector_status(node, env=env)
            ok = result.get("status") == "ok"
            try:
                self._mark_agent(node["id"], result, env=env)
            except Exception:
                pass
            if not ok:
                failed += 1
            results.append({
                "node": {"id": node["id"], "name": node["name"], "host": node["host"]},
                "status": "running" if ok else "stopped",
                "check": {
                    "status": result.get("status"),
                    "exit_code": result.get("exit_code"),
                    "stdout": result.get("stdout"),
                    "stderr": result.get("stderr"),
                },
                "collector": {"service": COLLECTOR_SERVICE, "timer": COLLECTOR_TIMER},
            })
        return {"results": results, "failed": failed, "succeeded": len(results) - failed}

    def collect_node(self, node_id, env=None):
        metric = None
        containers = None
        metric_error = None
        container_error = None
        try:
            metric = nodes.metric_snapshot(node_id, env=env)
        except Exception as exc:
            metric_error = str(exc)
        try:
            containers = nodes.refresh_containers_panel(node_id, env=env)
        except Exception as exc:
            container_error = str(exc)
        status = "succeeded" if metric_error is None or container_error is None else "failed"
        return {
            "node_id": node_id,
            "status": status,
            "metric": metric,
            "containers": {
                "summary": (containers or {}).get("summary"),
                "count": len((containers or {}).get("containers") or []),
            } if containers else None,
            "errors": [item for item in [metric_error, container_error] if item],
        }

    def collect_all(self, payload=None, env=None):
        body = payload or {}
        target_node_id = str(body.get("node_id") or "").strip()
        node_rows = nodes.list(env=env)
        if target_node_id:
            node_rows = [item for item in node_rows if item.get("id") == target_node_id]
        elif not body.get("include_unconfigured"):
            node_rows = [item for item in node_rows if self._monitoring_configured(item)]
        with self._lock:
            self._collecting_node_ids = [str(item.get("id")) for item in node_rows if item.get("id")]
        results = []
        for node in node_rows:
            results.append(self.collect_node(node["id"], env=env))
        failed = len([item for item in results if item["status"] == "failed"])
        return {"checked_at": datetime.datetime.now(datetime.timezone.utc).isoformat().replace("+00:00", "Z"), "results": results, "failed": failed, "succeeded": len(results) - failed}

    def _execute(self, payload=None, env=None):
        try:
            self._last_result = self.collect_all(payload or {}, env=env)
        except Exception as exc:
            self._last_result = {"failed": 1, "succeeded": 0, "message": str(exc)}
        finally:
            with self._lock:
                self._running = False
                self._collecting_node_ids = []

    def tick(self, payload=None, env=None):
        body = payload or {}
        interval = config.node_metric_collection_interval_seconds(env)
        collecting_node_ids = self._node_ids_for_payload(body, env=env)
        if not collecting_node_ids:
            return {"scheduled": False, "reason": "no_configured_nodes", "last_result": self._last_result}
        with self._lock:
            if self._running:
                return {"scheduled": False, "reason": "running", "last_result": self._last_result}
            if not body.get("force") and self._recent(interval):
                return {"scheduled": False, "reason": "throttled", "last_result": self._last_result}
            self._running = True
            self._last_tick_at = datetime.datetime.now(datetime.timezone.utc)
            self._collecting_node_ids = collecting_node_ids
        worker = threading.Thread(target=self._execute, kwargs={"payload": body, "env": env}, daemon=True)
        worker.start()
        return {"scheduled": True, "reason": "started", "interval_seconds": interval}


Model = NodesMonitoring()
