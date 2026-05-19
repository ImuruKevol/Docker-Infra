import json
import time
from pathlib import Path

import yaml
from psycopg.types.json import Jsonb


connect = wiz.model("db/postgres").connect
local_executor = wiz.model("struct/local_executor")


def _json_lines(stdout):
    rows = []
    for line in (stdout or "").splitlines():
        try:
            rows.append(json.loads(line))
        except Exception:
            continue
    return rows


def _compose_service_name(stack_name, task):
    name = str(task.get("Name") or "")
    prefix = f"{stack_name}_"
    if name.startswith(prefix):
        return name[len(prefix):].split(".", 1)[0]
    return name.rsplit("_", 1)[-1].split(".", 1)[0] if name else ""


def _task_active(task):
    desired = str(task.get("DesiredState") or task.get("Desired state") or "").lower()
    current = str(task.get("CurrentState") or task.get("Current state") or "").lower()
    return desired == "running" and current.startswith("running")


def _node_maps(env=None):
    result = local_executor.run("swarm.nodes", timeout_seconds=10, env=env)
    inspect_result = local_executor.run("swarm.nodes.inspect", timeout_seconds=15, env=env)
    swarm_rows = _json_lines(result.get("stdout")) if result.get("status") == "ok" else []
    inspected = {}
    if inspect_result.get("status") == "ok":
        try:
            for row in json.loads(inspect_result.get("stdout") or "[]"):
                node_id = str(row.get("ID") or "").strip()
                hostname = str(((row.get("Description") or {}).get("Hostname")) or "").strip()
                for key in {node_id, node_id[:12], hostname}:
                    if key:
                        inspected[key] = row
        except Exception:
            inspected = {}
    by_hostname = {str(row.get("Hostname") or ""): row for row in swarm_rows if row.get("Hostname")}
    by_node_id = {str(row.get("ID") or ""): row for row in swarm_rows if row.get("ID")}
    with connect(env=env) as connection:
        with connection.cursor() as cursor:
            cursor.execute("SELECT * FROM nodes ORDER BY is_local_master DESC, created_at ASC")
            nodes = [dict(row) for row in cursor.fetchall()]
    registered_by_swarm_id = {}
    for row in nodes:
        swarm_node_id = str(row.get("swarm_node_id") or "").strip()
        if not swarm_node_id:
            continue
        registered_by_swarm_id[swarm_node_id] = row
        registered_by_swarm_id[swarm_node_id[:12]] = row
    registered_by_name = {str(row.get("name") or ""): row for row in nodes if row.get("name")}
    registered_by_host = {str(row.get("host") or ""): row for row in nodes if row.get("host")}
    return {
        "swarm_check": {"status": result.get("status"), "exit_code": result.get("exit_code")},
        "inspect_check": {"status": inspect_result.get("status"), "exit_code": inspect_result.get("exit_code")},
        "inspected": inspected,
        "by_hostname": by_hostname,
        "by_node_id": by_node_id,
        "registered_by_swarm_id": registered_by_swarm_id,
        "registered_by_name": registered_by_name,
        "registered_by_host": registered_by_host,
    }


def _task_node(task, maps):
    swarm_node_name = str(task.get("Node") or "").strip()
    swarm_row = maps["by_hostname"].get(swarm_node_name) or maps["by_node_id"].get(swarm_node_name) or {}
    swarm_id = str(swarm_row.get("ID") or "")
    inspected = maps["inspected"].get(swarm_id) or maps["inspected"].get(swarm_id[:12]) or maps["inspected"].get(swarm_node_name) or {}
    swarm_addr = str((inspected.get("Status") or {}).get("Addr") or "").strip()
    registered = (
        maps["registered_by_swarm_id"].get(swarm_id)
        or maps["registered_by_name"].get(swarm_node_name)
        or maps["registered_by_host"].get(swarm_node_name)
    )
    registered_name = str((registered or {}).get("name") or "").strip()
    registered_host = str((registered or {}).get("host") or "").strip()
    display_name = registered_name or registered_host or swarm_node_name
    host = str(swarm_addr or registered_host or swarm_node_name or "127.0.0.1").strip()
    return {
        "node_name": display_name,
        "swarm_node_name": swarm_node_name,
        "swarm_node_id": swarm_id or str((registered or {}).get("swarm_node_id") or ""),
        "node_id": "" if registered is None else str(registered.get("id")),
        "node_host": host,
        "registered_node_name": registered_name,
        "registered_node_host": registered_host,
        "registered": registered is not None,
    }


def compose_ports(compose_path):
    compose = yaml.safe_load(Path(compose_path).read_text(encoding="utf-8")) or {}
    ports = {}
    for service_name, service in (compose.get("services") or {}).items():
        for item in service.get("ports") or []:
            if isinstance(item, dict):
                target = int(item.get("target") or item.get("published") or 0)
                published = int(item.get("published") or target)
            else:
                raw = str(item).strip().strip('"')
                base = raw.split("/", 1)[0]
                chunks = base.split(":")
                target = int(chunks[-1])
                published = int(chunks[-2]) if len(chunks) >= 2 and chunks[-2].isdigit() else target
            ports[(service_name, target)] = published
    return ports


def sync_domain_published_ports(service_id, compose_path, env=None):
    ports = compose_ports(compose_path)
    updates = []
    with connect(env=env) as connection:
        with connection.cursor() as cursor:
            cursor.execute("SELECT * FROM service_domains WHERE service_id = %s", (service_id,))
            for row in cursor.fetchall():
                domain = dict(row)
                metadata = dict(domain.get("metadata") or {})
                compose_service = metadata.get("compose_service") or ""
                target = int(metadata.get("target_port") or domain.get("port") or 0)
                published = ports.get((compose_service, target))
                if published is None:
                    for (service_name, target_port), published_port in ports.items():
                        if target_port == target:
                            compose_service = service_name
                            published = published_port
                            break
                if published is None:
                    continue
                metadata.update({"compose_service": compose_service, "target_port": target, "published_port": published})
                cursor.execute(
                    "UPDATE service_domains SET metadata = %s, updated_at = now() WHERE id = %s",
                    (Jsonb(metadata), domain["id"]),
                )
                updates.append({"domain": domain.get("domain"), "target_port": target, "published_port": published})
    return updates


def _stack_tasks(stack_name, env=None):
    result = local_executor.run("service.stack.ps", params={"stack_name": stack_name}, timeout_seconds=20, env=env)
    rows = _json_lines(result.get("stdout")) if result.get("status") == "ok" else []
    return result, [row for row in rows if _task_active(row)]


def sync_domain_proxy_targets(service_id, stack_name, attempts=10, delay_seconds=2, env=None):
    domains = []
    with connect(env=env) as connection:
        with connection.cursor() as cursor:
            cursor.execute("SELECT * FROM service_domains WHERE service_id = %s ORDER BY created_at ASC", (service_id,))
            domains = [dict(row) for row in cursor.fetchall()]
    if not domains:
        return {"updated": [], "skipped": True, "reason": "no_domains"}

    task_check = {}
    tasks = []
    for _ in range(max(1, int(attempts or 1))):
        task_check, tasks = _stack_tasks(stack_name, env=env)
        if tasks:
            break
        time.sleep(max(0, int(delay_seconds or 0)))

    maps = _node_maps(env=env)
    task_by_service = {}
    for task in tasks:
        service_name = _compose_service_name(stack_name, task)
        if service_name and service_name not in task_by_service:
            task_by_service[service_name] = task

    updates = []
    with connect(env=env) as connection:
        with connection.cursor() as cursor:
            for domain in domains:
                metadata = dict(domain.get("metadata") or {})
                compose_service = str(metadata.get("compose_service") or "").strip()
                task = task_by_service.get(compose_service) if compose_service else None
                if task is None and len(task_by_service) == 1:
                    task = next(iter(task_by_service.values()))
                if task is None:
                    continue
                node = _task_node(task, maps)
                metadata.update({
                    "proxy_host": node["node_host"],
                    "proxy_node_name": node["node_name"],
                    "proxy_swarm_node_name": node["swarm_node_name"],
                    "proxy_swarm_node_id": node["swarm_node_id"],
                    "proxy_node_id": node["node_id"],
                    "proxy_registered_node_name": node["registered_node_name"],
                    "proxy_registered_node_host": node["registered_node_host"],
                    "proxy_node_registered": node["registered"],
                })
                cursor.execute(
                    "UPDATE service_domains SET metadata = %s, updated_at = now() WHERE id = %s",
                    (Jsonb(metadata), domain["id"]),
                )
                updates.append({"domain": domain.get("domain"), "compose_service": compose_service, **node})
    return {
        "updated": updates,
        "task_check": {"status": task_check.get("status"), "exit_code": task_check.get("exit_code")},
        "swarm_check": maps["swarm_check"],
        "inspect_check": maps["inspect_check"],
    }


class ServicesDeployTargets:
    compose_ports = staticmethod(compose_ports)
    sync_domain_published_ports = staticmethod(sync_domain_published_ports)
    sync_domain_proxy_targets = staticmethod(sync_domain_proxy_targets)


Model = ServicesDeployTargets()
