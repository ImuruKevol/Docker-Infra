import datetime
from urllib.parse import urlparse

from psycopg.types.json import Jsonb


backup_system = wiz.model("struct/backup_system")
resources = wiz.model("struct/backup_system_resources")
operations = wiz.model("struct/operations")
catalog = wiz.model("struct/local_command_catalog")
shared = wiz.model("struct/nodes_shared")
connect = wiz.model("db/postgres").connect

NodeError = shared.NodeError
_node_access_host = shared.node_access_host

LOOPBACK_HOSTS = {"", "127.0.0.1", "localhost", "::1", "0.0.0.0"}


def _utc_now():
    return datetime.datetime.now(datetime.timezone.utc).isoformat().replace("+00:00", "Z")


def _parse_registry_url(value):
    raw = str(value or "").strip()
    if not raw:
        return None
    candidate = raw if "://" in raw else f"http://{raw}"
    parsed = urlparse(candidate)
    registry = parsed.netloc or parsed.path
    registry = registry.strip().strip("/")
    return {"registry": registry, "host": parsed.hostname or "", "port": parsed.port}


def _clean_host(value):
    host = str(value or "").strip()
    if "://" in host:
        parsed = urlparse(host)
        host = parsed.hostname or parsed.netloc or host
    if "/" in host:
        host = host.split("/", 1)[0]
    if host.count(":") == 1:
        host = host.rsplit(":", 1)[0]
    return host.strip("[]")


def _unique(items):
    result = []
    for item in items:
        value = str(item or "").strip()
        if value and value not in result:
            result.append(value)
    return result


class NodeBackupRegistryMixin:
    def _backup_registry_master_host(self, env=None):
        masters = [node for node in self.list(env=env) if node.get("is_local_master")]
        if not masters:
            return ""
        return _clean_host(_node_access_host(masters[0]))

    def backup_registry_config(self, backup_config=None, env=None):
        status = dict(backup_config or {})
        if backup_config is None:
            status = backup_system.status(env=env)
        parsed = _parse_registry_url(status.get("harbor_url") or resources.harbor_url(env))
        if not parsed or not parsed["registry"]:
            raise NodeError(409, "백업 레지스트리 주소를 확인할 수 없습니다.", "BACKUP_REGISTRY_UNAVAILABLE")
        master_host = self._backup_registry_master_host(env=env)
        port = parsed["port"]
        remote_registry = parsed["registry"]
        if master_host not in LOOPBACK_HOSTS and port:
            remote_registry = f"{master_host}:{port}"
        return {
            "enabled": bool(status.get("enabled")),
            "installed": bool(status.get("installed")),
            "status": status.get("status"),
            "harbor_url": status.get("harbor_url") or resources.harbor_url(env),
            "local_registry": parsed["registry"],
            "remote_registry": remote_registry,
            "master_host": master_host,
            "port": port,
        }

    def backup_registry_reference_for_node(self, node, backup_config=None, env=None):
        config = self.backup_registry_config(backup_config=backup_config, env=env)
        if node.get("is_local_master"):
            return config["local_registry"]
        return config["remote_registry"] or config["local_registry"]

    def _backup_registry_required(self, config):
        return bool(config.get("enabled") or config.get("installed") or config.get("status") in {"running", "stopped", "failed"})

    def backup_registry_registries_for_node(self, node, backup_config=None, env=None):
        config = self.backup_registry_config(backup_config=backup_config, env=env)
        if not self._backup_registry_required(config):
            return []
        if node.get("is_local_master"):
            registries = []
            parsed = _parse_registry_url(config["local_registry"])
            if parsed and parsed["host"] not in LOOPBACK_HOSTS:
                registries.append(config["local_registry"])
            remote = config.get("remote_registry")
            remote_parsed = _parse_registry_url(remote)
            if remote and remote != config["local_registry"] and remote_parsed and remote_parsed["host"] not in LOOPBACK_HOSTS:
                registries.append(remote)
            return _unique(registries)
        return _unique([config["remote_registry"] or config["local_registry"]])

    def _backup_registry_command(self, registries):
        return catalog.docker_daemon_insecure_registries_command({"registries": registries})

    def _run_backup_registry_command(self, node, registries, env=None):
        params = {"registries": registries}
        if node.get("is_local_master"):
            return self.local_executor.run(
                "docker.daemon.insecure_registries.ensure",
                params=params,
                timeout_seconds=180,
                env=env,
            )
        return self._run_ssh_command(
            node,
            self._backup_registry_command(registries),
            timeout_seconds=180,
            env=env,
        )

    def _record_backup_registry_metadata(self, node_id, status, registries, result=None, env=None):
        metadata = {
            "backup_registry": {
                "status": status,
                "registries": registries,
                "updated_at": _utc_now(),
                "exit_code": (result or {}).get("exit_code"),
            }
        }
        with connect(env=env) as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    UPDATE nodes
                    SET metadata = metadata || %s
                    WHERE id = %s
                    """,
                    (Jsonb(metadata), node_id),
                )

    def _append_backup_registry_output(self, operation_id, node, result, env=None):
        if not operation_id or not result:
            return
        stream = "stdout" if result.get("status") == "ok" else "stderr"
        text = "\n".join(part for part in [result.get("stdout"), result.get("stderr")] if part).strip()
        if not text:
            text = f"Docker daemon registry setup finished with status={result.get('status')}"
        operations.append_output(
            operation_id,
            f"[{node.get('name') or node.get('host')}] {text}",
            stream=stream,
            metadata={"node_id": node.get("id"), "status": result.get("status"), "exit_code": result.get("exit_code")},
            env=env,
        )

    def configure_backup_registry_for_node(self, node_id, operation_id=None, env=None):
        node = self.detail(node_id, env=env)
        registries = self.backup_registry_registries_for_node(node, env=env)
        if not registries:
            if operation_id:
                operations.append_output(
                    operation_id,
                    f"[{node.get('name') or node.get('host')}] 백업 시스템이 설치되지 않아 노드 레지스트리 설정을 건너뜁니다.",
                    stream="system",
                    metadata={"node_id": node.get("id"), "status": "skipped"},
                    env=env,
                )
            return {"node": node, "registries": [], "status": "skipped", "result": None}

        if operation_id:
            operations.append_output(
                operation_id,
                f"[{node.get('name') or node.get('host')}] Docker insecure registry 설정을 적용합니다: {', '.join(registries)}",
                stream="system",
                metadata={"node_id": node.get("id"), "registries": registries, "status": "running"},
                env=env,
            )

        try:
            result = self._run_backup_registry_command(node, registries, env=env)
        except NodeError as exc:
            self._record_backup_registry_metadata(node_id, "failed", registries, env=env)
            exc.extra.setdefault("registries", registries)
            raise
        except Exception as exc:
            self._record_backup_registry_metadata(node_id, "failed", registries, env=env)
            raise NodeError(409, f"노드 백업 레지스트리 설정에 실패했습니다: {exc}", "BACKUP_REGISTRY_NODE_CONFIG_FAILED", registries=registries)

        self._append_backup_registry_output(operation_id, node, result, env=env)
        if result.get("status") != "ok":
            self._record_backup_registry_metadata(node_id, "failed", registries, result=result, env=env)
            raise NodeError(
                409,
                "노드 Docker insecure registry 설정에 실패했습니다.",
                "BACKUP_REGISTRY_NODE_CONFIG_FAILED",
                node_id=node_id,
                registries=registries,
                check=result,
            )

        self._record_backup_registry_metadata(node_id, "ok", registries, result=result, env=env)
        return {"node": node, "registries": registries, "status": "ok", "result": result}

    def _public_registry_result(self, item):
        node = item.get("node") or {}
        return {
            "node": {
                "id": node.get("id"),
                "name": node.get("name"),
                "host": node.get("host"),
                "is_local_master": node.get("is_local_master"),
            },
            "registries": item.get("registries") or [],
            "status": item.get("status"),
            "message": item.get("message"),
            "error_code": item.get("error_code"),
        }

    def ensure_backup_registry_all(self, env=None):
        config = self.backup_registry_config(env=env)
        operation = operations.create(
            "node.backup_registry.ensure",
            target_type="backup_system",
            target_id="default",
            message="등록된 노드의 백업 레지스트리 설정을 적용합니다.",
            requested_payload={"local_registry": config["local_registry"], "remote_registry": config["remote_registry"]},
            metadata={"backup_registry": config},
            env=env,
        )
        results = []
        for node_ref in self.list(env=env):
            try:
                item = self.configure_backup_registry_for_node(node_ref["id"], operation_id=operation["id"], env=env)
            except NodeError as exc:
                item = {
                    "node": node_ref,
                    "registries": exc.extra.get("registries") or [],
                    "status": "failed",
                    "message": exc.message,
                    "error_code": exc.error_code,
                }
                operations.append_output(
                    operation["id"],
                    f"[{node_ref.get('name') or node_ref.get('host')}] {exc.message}",
                    stream="stderr",
                    metadata={"node_id": node_ref.get("id"), "error_code": exc.error_code},
                    env=env,
                )
            results.append(item)

        public_results = [self._public_registry_result(item) for item in results]
        failed = [item for item in public_results if item.get("status") == "failed"]
        skipped = [item for item in public_results if item.get("status") == "skipped"]
        succeeded = [item for item in public_results if item.get("status") == "ok"]
        status = "failed" if failed else "succeeded"
        message = (
            f"노드 {len(succeeded)}개 적용, {len(skipped)}개 건너뜀, {len(failed)}개 실패"
            if failed or skipped
            else f"노드 {len(succeeded)}개에 백업 레지스트리 설정을 적용했습니다."
        )
        operation = operations.transition(
            operation["id"],
            status,
            message=message,
            result_payload={"results": public_results, "summary": {"ok": len(succeeded), "skipped": len(skipped), "failed": len(failed)}},
            env=env,
        )
        return {"operation": operation, "results": public_results, "backup_registry": config}


Model = NodeBackupRegistryMixin
