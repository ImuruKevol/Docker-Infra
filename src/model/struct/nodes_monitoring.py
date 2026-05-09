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


class NodesMonitoring:
    def __init__(self):
        self._lock = threading.Lock()
        self._running = False
        self._last_tick_at = None
        self._last_result = None
        self._collecting_node_ids = []

    def _recent(self, seconds):
        if self._last_tick_at is None:
            return False
        return (datetime.datetime.now(datetime.timezone.utc) - self._last_tick_at).total_seconds() < seconds

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
                    "service": EXPORTER_SERVICE,
                    "container": EXPORTER_CONTAINER,
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
            result = self._run_exporter_ensure(node, env=env)
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
            })
        operation = operations.create(
            "node.monitoring.exporter.ensure",
            target_type="node" if target_node_id else "nodes",
            target_id=target_node_id or None,
            status="failed" if failed else "succeeded",
            message="서버 모니터링 에이전트를 확인했습니다.",
            requested_payload={"node_id": target_node_id, "container": EXPORTER_CONTAINER, "service": EXPORTER_SERVICE},
            result_payload={"count": len(results), "failed": failed, "results": results},
            env=env,
        )
        return {"operation": operation, "results": results, "failed": failed, "succeeded": len(results) - failed}

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
            result = self._run_exporter_status(node, env=env)
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
