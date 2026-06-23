import datetime
import json
from concurrent.futures import ThreadPoolExecutor, as_completed

from psycopg.types.json import Jsonb


connect = wiz.model("db/postgres").connect
local_executor = wiz.model("struct/local_executor")
compose_rules = wiz.model("struct/compose_rules")
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


def _text(value):
    return str(value or "").strip()


def _node_display_label(node):
    if not node:
        return ""
    return _text(node.get("name")) or _text(node.get("host")) or _text(node.get("id"))


def _node_public_ref(node):
    if not node:
        return None
    return {
        "id": _text(node.get("id")),
        "name": _text(node.get("name")),
        "host": _text(node.get("host")),
        "swarm_node_id": _text(node.get("swarm_node_id")),
        "label": _node_display_label(node),
    }


def _node_lookup_maps(env=None, include_swarm=False):
    maps = {
        "by_id": {},
        "by_swarm_id": {},
        "by_name": {},
        "by_host": {},
        "by_task_node": {},
        "swarm_check": {"status": "skipped", "exit_code": None},
    }

    def add(bucket, key, node):
        key = _text(key)
        if key and node is not None:
            maps[bucket][key] = node

    try:
        node_rows = nodes.list(env=env)
    except Exception:
        node_rows = []

    for node in node_rows:
        node_id = _text(node.get("id"))
        swarm_id = _text(node.get("swarm_node_id"))
        name = _text(node.get("name"))
        host = _text(node.get("host"))
        add("by_id", node_id, node)
        add("by_swarm_id", swarm_id, node)
        add("by_swarm_id", swarm_id[:12], node)
        add("by_name", name, node)
        add("by_host", host, node)
        for candidate in [node_id, swarm_id, swarm_id[:12], name, host]:
            add("by_task_node", candidate, node)

    if not include_swarm:
        return maps

    try:
        result = local_executor.run("swarm.nodes", timeout_seconds=3, env=env)
        maps["swarm_check"] = {"status": result.get("status"), "exit_code": result.get("exit_code")}
        if result.get("status") == "ok":
            for row in _json_lines(result.get("stdout")):
                hostname = _text(row.get("Hostname"))
                swarm_id = _text(row.get("ID"))
                registered = maps["by_swarm_id"].get(swarm_id) or maps["by_swarm_id"].get(swarm_id[:12])
                if registered is None:
                    continue
                add("by_task_node", hostname, registered)
                add("by_task_node", swarm_id, registered)
                add("by_task_node", swarm_id[:12], registered)
    except Exception:
        maps["swarm_check"] = {"status": "error", "exit_code": None}
    return maps


def _registered_node_from_candidates(candidates, node_maps):
    maps = node_maps or {}
    for value in candidates:
        key = _text(value)
        if not key:
            continue
        for bucket in ["by_id", "by_swarm_id", "by_task_node", "by_name", "by_host"]:
            node = (maps.get(bucket) or {}).get(key)
            if node is not None:
                return node
    return None


def _decorate_task_node(task, node_maps):
    if not isinstance(task, dict):
        return task
    registered = _registered_node_from_candidates(
        [
            task.get("registered_node_id"),
            task.get("registered_swarm_node_id"),
            task.get("swarm_node_id"),
            task.get("Node"),
            task.get("node"),
            task.get("Hostname"),
            task.get("hostname"),
        ],
        node_maps,
    )
    ref = _node_public_ref(registered)
    if not ref:
        return task
    return {
        **task,
        "registered_node": ref,
        "registered_node_id": ref["id"],
        "registered_node_name": ref["name"],
        "registered_node_host": ref["host"],
        "registered_swarm_node_id": ref["swarm_node_id"],
        "registered_node_label": ref["label"],
    }


def _decorate_domain_runtime_row(row, node_maps):
    if not isinstance(row, dict):
        return row
    registered = _registered_node_from_candidates(
        [
            row.get("proxy_node_id"),
            row.get("proxy_swarm_node_id"),
            row.get("proxy_swarm_node_name"),
            row.get("proxy_registered_node_name"),
            row.get("proxy_node_name"),
            row.get("proxy_host"),
        ],
        node_maps,
    )
    ref = _node_public_ref(registered)
    if not ref:
        return row
    return {
        **row,
        "proxy_node_registered": True,
        "proxy_registered_node_id": ref["id"],
        "proxy_registered_node_name": ref["name"],
        "proxy_registered_node_host": ref["host"],
        "proxy_node_display_name": ref["label"],
    }


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


def _task_error_active(task):
    error = str(task.get("Error") or "").strip()
    if not error:
        return False
    desired = str(task.get("DesiredState") or task.get("Desired state") or "").lower()
    return desired == "running"


def _compact_stack_service(row):
    return {
        key: row.get(key)
        for key in ["Name", "Mode", "Replicas", "Image", "Ports"]
        if row.get(key) not in (None, "")
    }


def _compact_stack_task(task):
    return {
        key: task.get(key)
        for key in [
            "ID",
            "Name",
            "Service",
            "Image",
            "Node",
            "DesiredState",
            "CurrentState",
            "Error",
            "Ports",
            "registered_node_id",
            "registered_node_name",
            "registered_node_host",
            "registered_swarm_node_id",
            "registered_node_label",
        ]
        if task.get(key) not in (None, "")
    }


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
    def _service_deployment_context(self, service, env=None):
        policy = dict((service or {}).get("target_node_policy") or {})
        metadata = dict((service or {}).get("metadata") or {})
        placement = dict(metadata.get("placement") or {})
        mode = policy.get("mode") or placement.get("deployment_mode")
        network = policy.get("network") or placement.get("network")
        node_id = _text(policy.get("node_id") or placement.get("node_id"))
        if node_id:
            try:
                node = nodes.detail(node_id, env=env)
                mode = "swarm" if _text(node.get("swarm_node_id")) else "compose"
                network = compose_rules.default_network_name(mode)
            except Exception:
                pass
        if not mode and network == compose_rules.BRIDGE_NETWORK:
            mode = "compose"
        deployment_mode = compose_rules.normalize_deployment_mode(mode)
        network_name = network or compose_rules.default_network_name(deployment_mode)
        return {"deployment_mode": deployment_mode, "network": network_name, "node_id": node_id}

    def decorate_runtime_status(self, runtime_status, env=None, node_maps=None):
        if not isinstance(runtime_status, dict):
            return {}
        node_maps = node_maps or _node_lookup_maps(env=env, include_swarm=False)
        runtime = dict(runtime_status)

        stack = dict(runtime.get("stack") or {})
        tasks = stack.get("tasks")
        if isinstance(tasks, list):
            stack["tasks"] = [_decorate_task_node(task, node_maps) for task in tasks]
            runtime["stack"] = stack

        domains = dict(runtime.get("domains") or {})
        domain_rows = domains.get("domains")
        if isinstance(domain_rows, list):
            domains["domains"] = [_decorate_domain_runtime_row(row, node_maps) for row in domain_rows]
            runtime["domains"] = domains

        return runtime

    def _stack_status(self, stack_name, env=None, node_maps=None, deployment_mode="swarm"):
        if deployment_mode == "compose":
            return {
                "services": [],
                "tasks": [],
                "summary": {
                    "service_count": 0,
                    "desired": 0,
                    "running": 0,
                    "task_count": 0,
                    "task_running": 0,
                    "task_errors": 0,
                    "task_error_history": 0,
                },
                "checks": {
                    "services": {"status": "skipped", "exit_code": None, "reason": "compose_deployment"},
                    "tasks": {"status": "skipped", "exit_code": None, "reason": "compose_deployment"},
                    "node_mapping": {"status": "skipped", "exit_code": None, "reason": "compose_deployment"},
                },
            }
        node_maps = node_maps or _node_lookup_maps(env=env, include_swarm=True)
        params = {"stack_name": stack_name}
        services_result = local_executor.run("service.stack.services", params=params, timeout_seconds=6, env=env)
        tasks_result = local_executor.run("service.stack.ps", params=params, timeout_seconds=6, env=env)
        services_rows = _json_lines(services_result.get("stdout")) if services_result.get("status") == "ok" else []
        task_rows = _json_lines(tasks_result.get("stdout")) if tasks_result.get("status") == "ok" else []
        task_rows = [_compact_stack_task(_decorate_task_node(task, node_maps)) for task in task_rows]
        replicas = [_replicas(row.get("Replicas")) for row in services_rows]
        return {
            "services": [_compact_stack_service(row) for row in services_rows],
            "tasks": task_rows,
            "summary": {
                "service_count": len(services_rows),
                "desired": sum(item["desired"] for item in replicas),
                "running": sum(item["running"] for item in replicas),
                "task_count": len(task_rows),
                "task_running": len([task for task in task_rows if _task_running(task)]),
                "task_errors": len([task for task in task_rows if _task_error_active(task)]),
                "task_error_history": len([task for task in task_rows if str(task.get("Error") or "").strip()]),
            },
            "checks": {
                "services": {"status": services_result.get("status"), "exit_code": services_result.get("exit_code")},
                "tasks": {"status": tasks_result.get("status"), "exit_code": tasks_result.get("exit_code")},
                "node_mapping": node_maps.get("swarm_check"),
            },
        }

    def _container_status(self, namespace, stack_name=None, env=None, node_maps=None, target_node_ids=None):
        matched = []
        checks = []
        node_rows = list(((node_maps or {}).get("by_id") or {}).values()) or nodes.list(env=env)
        wanted = {str(item) for item in (target_node_ids or []) if item}
        selected_nodes = [node for node in node_rows if not wanted or str(node.get("id")) in wanted]
        if wanted and not selected_nodes:
            selected_nodes = node_rows

        def load_node(node):
            try:
                panel = nodes.service_containers(node["id"], namespace, stack_name=stack_name, env=env)
                check = panel.get("check") or {}
                return {
                    "check": {
                        "node_id": node["id"],
                        "node_name": node.get("name"),
                        "status": check.get("status"),
                        "exit_code": check.get("exit_code"),
                    },
                    "containers": [
                        {**item, "node_id": node["id"], "node_name": node.get("name"), "node_host": node.get("host")}
                        for item in (panel.get("items") or [])
                    ],
                }
            except nodes.NodeError as exc:
                return {
                    "check": {
                        "node_id": node["id"],
                        "node_name": node.get("name"),
                        "status": "error",
                        "message": exc.message,
                        "error_code": exc.error_code,
                    },
                    "containers": [],
                }

        if selected_nodes:
            with ThreadPoolExecutor(max_workers=min(4, len(selected_nodes))) as executor:
                futures = [executor.submit(load_node, node) for node in selected_nodes]
                for future in as_completed(futures):
                    result = future.result()
                    checks.append(result["check"])
                    matched.extend(result["containers"])
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

    def _domain_status(self, domains, node_maps=None):
        rows = []
        for domain in domains:
            metadata = dict(domain.get("metadata") or {})
            rows.append({
                "domain": domain.get("domain"),
                "ssl_mode": domain.get("ssl_mode"),
                "routing_provider": metadata.get("routing_provider") or "nginx",
                "dns_provider": metadata.get("dns_provider") or ("ddns" if metadata.get("ddns_endpoint_id") else ""),
                "ddns_mode": metadata.get("ddns_mode") or ("ddns_management" if metadata.get("ddns_endpoint_id") else ""),
                "ddns_status": metadata.get("ddns_status"),
                "ddns_registered": metadata.get("ddns_status") == "registered",
                "ddns_endpoint_id": metadata.get("ddns_endpoint_id"),
                "nginx_ssl_mode": metadata.get("nginx_ssl_mode"),
                "nginx_configured": bool(metadata.get("nginx_config_path")),
                "published_port": metadata.get("published_port") or domain.get("port"),
                "target_port": metadata.get("target_port") or domain.get("port"),
                "proxy_host": metadata.get("proxy_host") or "127.0.0.1",
                "proxy_node_name": metadata.get("proxy_node_name"),
                "proxy_swarm_node_name": metadata.get("proxy_swarm_node_name"),
                "proxy_swarm_node_id": metadata.get("proxy_swarm_node_id"),
                "proxy_node_id": metadata.get("proxy_node_id"),
                "proxy_registered_node_name": metadata.get("proxy_registered_node_name"),
                "proxy_registered_node_host": metadata.get("proxy_registered_node_host"),
                "proxy_node_registered": metadata.get("proxy_node_registered"),
            })
        if node_maps is not None:
            rows = [_decorate_domain_runtime_row(row, node_maps) for row in rows]
        return {
            "domains": rows,
            "summary": {
                "total": len(rows),
                "nginx_configured": len([item for item in rows if item["nginx_configured"]]),
                "ddns_registered": len([item for item in rows if item.get("ddns_registered")]),
                "ssl": len([item for item in rows if item.get("nginx_ssl_mode") in {"existing", "certbot", "self_signed"}]),
            },
        }

    def _runtime_target_node_ids(self, service, deployment_context, stack):
        ids = []
        if deployment_context.get("deployment_mode") == "compose" and deployment_context.get("node_id"):
            ids.append(deployment_context.get("node_id"))
        for task in (stack or {}).get("tasks") or []:
            if task.get("registered_node_id"):
                ids.append(task.get("registered_node_id"))
        runtime = ((service.get("metadata") or {}).get("runtime_status") or {}).get("containers") or {}
        for container in runtime.get("containers") or []:
            if container.get("node_id"):
                ids.append(container.get("node_id"))
        result = []
        seen = set()
        for node_id in ids:
            key = str(node_id or "")
            if key and key not in seen:
                seen.add(key)
                result.append(key)
        return result

    def refresh_deploy_status(self, service_id, operation_id=None, env=None):
        with connect(env=env) as connection:
            with connection.cursor() as cursor:
                service = self._service_row(cursor, service_id)
                cursor.execute("SELECT * FROM service_domains WHERE service_id = %s ORDER BY created_at ASC", (service_id,))
                domains = [_row(row) for row in cursor.fetchall()]
        stack_name = service.get("stack_name") or service.get("namespace")
        deployment_context = self._service_deployment_context(service, env=env)
        include_swarm = deployment_context["deployment_mode"] != "compose"
        node_maps = _node_lookup_maps(env=env, include_swarm=include_swarm)
        stack = self._stack_status(stack_name, env=env, node_maps=node_maps, deployment_mode=deployment_context["deployment_mode"])
        target_node_ids = self._runtime_target_node_ids(service, deployment_context, stack)
        runtime = {
            "checked_at": _now(),
            "operation_id": operation_id,
            "stack_name": stack_name,
            "deployment_mode": deployment_context["deployment_mode"],
            "network": deployment_context["network"],
            "stack": stack,
            "containers": self._container_status(
                service.get("namespace"),
                stack_name=stack_name,
                env=env,
                node_maps=node_maps,
                target_node_ids=target_node_ids,
            ),
            "domains": self._domain_status(domains, node_maps=node_maps),
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
