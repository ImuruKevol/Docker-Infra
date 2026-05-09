import datetime
import json

from psycopg.types.json import Jsonb


connect = wiz.model("db/postgres").connect
local_executor = wiz.model("struct/local_executor")
nodes = wiz.model("struct/nodes")
shared = wiz.model("struct/services_shared")
node_shared = wiz.model("struct/nodes_shared")
ServiceError = shared.ServiceError
_row = shared.row
_parse_containers = node_shared.parse_docker_ps_lines
_container_summary = node_shared.container_summary


def _now():
    return datetime.datetime.now(datetime.timezone.utc).isoformat().replace("+00:00", "Z")


def _json_lines(stdout):
    rows = []
    for line in (stdout or "").splitlines():
        try:
            rows.append(json.loads(line))
        except Exception:
            continue
    return rows


def _replicas(value):
    raw = str(value or "")
    if "/" not in raw:
        return {"running": 0, "desired": 0, "raw": raw}
    running, desired = raw.split("/", 1)
    try:
        return {"running": int(running), "desired": int(desired), "raw": raw}
    except Exception:
        return {"running": 0, "desired": 0, "raw": raw}


def _task_running(task):
    desired = str(task.get("DesiredState") or task.get("Desired state") or "").lower()
    current = str(task.get("CurrentState") or task.get("Current state") or "").lower()
    return desired == "running" and current.startswith("running")


def _container_health(containers):
    summary = {"healthy": 0, "unhealthy": 0, "starting": 0, "running": 0, "stopped": 0, "unknown": 0}
    for item in containers:
        state = str(item.get("state") or "").lower()
        status = str(item.get("status") or "").lower()
        if "unhealthy" in status:
            summary["unhealthy"] += 1
        elif "health: starting" in status:
            summary["starting"] += 1
        elif "healthy" in status:
            summary["healthy"] += 1
        elif state == "running":
            summary["running"] += 1
        elif state:
            summary["stopped"] += 1
        else:
            summary["unknown"] += 1
    return summary


class ServiceStatusMixin:
    def _stack_status(self, stack_name, env=None):
        params = {"stack_name": stack_name}
        services_result = local_executor.run("service.stack.services", params=params, timeout_seconds=20, env=env)
        tasks_result = local_executor.run("service.stack.ps", params=params, timeout_seconds=20, env=env)
        services_rows = _json_lines(services_result.get("stdout")) if services_result.get("status") == "ok" else []
        task_rows = _json_lines(tasks_result.get("stdout")) if tasks_result.get("status") == "ok" else []
        replicas = [_replicas(row.get("Replicas")) for row in services_rows]
        return {
            "services": services_rows,
            "tasks": task_rows,
            "summary": {
                "service_count": len(services_rows),
                "desired": sum(item["desired"] for item in replicas),
                "running": sum(item["running"] for item in replicas),
                "task_count": len(task_rows),
                "task_running": len([task for task in task_rows if _task_running(task)]),
                "task_errors": len([task for task in task_rows if str(task.get("Error") or "").strip()]),
            },
            "checks": {
                "services": {"status": services_result.get("status"), "exit_code": services_result.get("exit_code")},
                "tasks": {"status": tasks_result.get("status"), "exit_code": tasks_result.get("exit_code")},
            },
        }

    def _container_status(self, namespace, env=None):
        # Keep service runtime aligned with the shared docker.containers collector so each row carries its real container id and node id.
        matched = []
        checks = []
        node_rows = nodes.list(env=env)
        for node in node_rows:
            try:
                panel = nodes.live_containers(node["id"], persist=True, env=env)
                check = panel.get("check") or {}
                checks.append({
                    "node_id": node["id"],
                    "node_name": node.get("name"),
                    "status": check.get("status"),
                    "exit_code": check.get("exit_code"),
                })
                containers = panel.get("items") or []
            except nodes.NodeError as exc:
                checks.append({
                    "node_id": node["id"],
                    "node_name": node.get("name"),
                    "status": "error",
                    "message": exc.message,
                    "error_code": exc.error_code,
                })
                containers = []
            for item in containers:
                if item.get("service_namespace") != namespace and not str(item.get("runtime_service_name") or "").startswith(f"{namespace}_"):
                    continue
                matched.append({**item, "node_id": node["id"], "node_name": node.get("name"), "node_host": node.get("host")})
        return {
            "summary": _container_summary(matched),
            "health": _container_health(matched),
            "containers": [
                {
                    "id": item.get("id"),
                    "node_id": item.get("node_id"),
                    "node_name": item.get("node_name"),
                    "node_host": item.get("node_host"),
                    "name": item.get("name"),
                    "image": item.get("image"),
                    "state": item.get("state"),
                    "status": item.get("status"),
                    "runtime_service_name": item.get("runtime_service_name"),
                    "port_bindings": item.get("port_bindings") or [],
                }
                for item in matched
            ],
            "check": {"status": "ok" if any(item.get("status") == "ok" for item in checks) else "error", "nodes": checks},
        }

    def _domain_status(self, domains):
        rows = []
        for domain in domains:
            metadata = dict(domain.get("metadata") or {})
            rows.append({
                "domain": domain.get("domain"),
                "ssl_mode": domain.get("ssl_mode"),
                "nginx_ssl_mode": metadata.get("nginx_ssl_mode"),
                "nginx_configured": bool(metadata.get("nginx_config_path")),
                "published_port": metadata.get("published_port") or domain.get("port"),
                "target_port": metadata.get("target_port") or domain.get("port"),
                "proxy_host": metadata.get("proxy_host") or "127.0.0.1",
                "proxy_node_name": metadata.get("proxy_node_name"),
                "proxy_node_registered": metadata.get("proxy_node_registered"),
            })
        return {
            "domains": rows,
            "summary": {
                "total": len(rows),
                "nginx_configured": len([item for item in rows if item["nginx_configured"]]),
                "ssl": len([item for item in rows if item.get("nginx_ssl_mode") in {"existing", "certbot", "self_signed"}]),
            },
        }

    def refresh_deploy_status(self, service_id, operation_id=None, env=None):
        with connect(env=env) as connection:
            with connection.cursor() as cursor:
                service = self._service_row(cursor, service_id)
                cursor.execute("SELECT * FROM service_domains WHERE service_id = %s ORDER BY created_at ASC", (service_id,))
                domains = [_row(row) for row in cursor.fetchall()]
        stack_name = service.get("stack_name") or service.get("namespace")
        runtime = {
            "checked_at": _now(),
            "operation_id": operation_id,
            "stack_name": stack_name,
            "stack": self._stack_status(stack_name, env=env),
            "containers": self._container_status(service.get("namespace"), env=env),
            "domains": self._domain_status(domains),
        }
        metadata = dict(service.get("metadata") or {})
        metadata["runtime_status"] = runtime
        with connect(env=env) as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    "UPDATE services SET metadata = %s, updated_at = now() WHERE id = %s RETURNING *",
                    (Jsonb(metadata), service_id),
                )
                return {"service": _row(cursor.fetchone()), "runtime_status": runtime}


Model = ServiceStatusMixin
