import shlex
import subprocess
import time
from collections import Counter
from pathlib import Path

import yaml


nodes = wiz.model("struct/nodes")
operations = wiz.model("struct/operations")
services_shared = wiz.model("struct/services_shared")
nodes_shared = wiz.model("struct/nodes_shared")
ssh_executor = wiz.model("struct/ssh_executor")
ServiceError = services_shared.ServiceError

TRANSFER_IMAGE = "alpine:3.20"
TRANSFER_TIMEOUT_SECONDS = 1800
MAX_CAPTURE_CHARS = 12000


def _trim(value):
    if value is None:
        return ""
    text = str(value)
    if len(text) <= MAX_CAPTURE_CHARS:
        return text
    return text[:MAX_CAPTURE_CHARS] + "\n[truncated]"


def _is_local_master_node(node):
    return bool((node or {}).get("is_local_master") or (node or {}).get("role") == "local_master" or (node or {}).get("name") == "local-master")


def _node_summary(node):
    node = node or {}
    return {
        "id": str(node.get("id") or ""),
        "name": str(node.get("name") or ""),
        "host": str(node.get("host") or ""),
        "private_host": str(node.get("private_host") or ""),
        "swarm_node_id": str(node.get("swarm_node_id") or ""),
        "is_local_master": bool(node.get("is_local_master")),
    }


def _operation_output(operation_id, message, stream="system", metadata=None, env=None):
    if not operation_id or not message:
        return
    operations.append_output(operation_id, message, stream=stream, metadata=metadata or {}, env=env)


class ServiceVolumeMigration:
    ServiceError = ServiceError

    def _compose_document(self, service):
        compose_path = Path(service.get("compose_path") or "").expanduser()
        if not compose_path.is_file():
            raise ServiceError(404, "서비스 Compose 파일을 찾을 수 없습니다.", "SERVICE_COMPOSE_NOT_FOUND")
        return yaml.safe_load(compose_path.read_text(encoding="utf-8") or "{}") or {}

    def _docker_volume_name(self, namespace, source, top_level):
        source = str(source or "").strip()
        config = (top_level or {}).get(source) if isinstance(top_level, dict) else {}
        config = config if isinstance(config, dict) else {}
        explicit_name = str(config.get("name") or "").strip()
        if explicit_name:
            return explicit_name
        external = config.get("external")
        if isinstance(external, dict):
            return str(external.get("name") or source).strip()
        if external is True:
            return source
        return f"{namespace}_{source}"

    def _is_named_volume_source(self, source):
        source = str(source or "").strip()
        return bool(source) and not source.startswith(("/", ".", "~"))

    def _parse_volume_ref(self, raw, namespace, top_level):
        if isinstance(raw, dict):
            mount_type = str(raw.get("type") or "volume").strip().lower()
            if mount_type not in {"", "volume"}:
                return None
            source = str(raw.get("source") or raw.get("src") or raw.get("name") or "").strip()
            target = str(raw.get("target") or raw.get("dst") or raw.get("destination") or "").strip()
            if not self._is_named_volume_source(source):
                return None
            return {
                "compose_volume": source,
                "docker_volume": self._docker_volume_name(namespace, source, top_level),
                "target": target,
                "read_only": bool(raw.get("read_only")),
            }

        text = str(raw or "").strip()
        if not text:
            return None
        parts = text.split(":")
        if len(parts) < 2:
            return None
        source = parts[0].strip()
        target = parts[1].strip()
        if not self._is_named_volume_source(source):
            return None
        mode = ":".join(parts[2:]).lower()
        return {
            "compose_volume": source,
            "docker_volume": self._docker_volume_name(namespace, source, top_level),
            "target": target,
            "read_only": any(item in {"ro", "readonly"} for item in mode.split(",")),
        }

    def compose_named_volumes(self, service):
        compose = self._compose_document(service)
        namespace = str(service.get("namespace") or service.get("stack_name") or "").strip()
        top_level = compose.get("volumes") or {}
        by_volume = {}
        for service_name, service_def in (compose.get("services") or {}).items():
            if not isinstance(service_def, dict):
                continue
            for raw in service_def.get("volumes") or []:
                ref = self._parse_volume_ref(raw, namespace, top_level)
                if not ref:
                    continue
                key = ref["docker_volume"]
                entry = by_volume.setdefault(
                    key,
                    {
                        "compose_volume": ref["compose_volume"],
                        "docker_volume": ref["docker_volume"],
                        "mounts": [],
                    },
                )
                entry["mounts"].append({
                    "compose_service": str(service_name),
                    "target": ref.get("target") or "",
                    "read_only": bool(ref.get("read_only")),
                })
        return list(by_volume.values())

    def _compose_service_name(self, item):
        runtime = str(item.get("runtime_service_name") or "")
        namespace = str(item.get("service_namespace") or "")
        prefix = f"{namespace}_"
        if namespace and runtime.startswith(prefix):
            return runtime[len(prefix):]
        return runtime

    def _source_node(self, service, env=None):
        service_id = str(service.get("id") or "")
        namespace = str(service.get("namespace") or "")
        counts = Counter()
        for node_ref in nodes.list(env=env):
            try:
                panel = nodes.live_containers(node_ref["id"], persist=False, env=env)
            except Exception:
                continue
            for item in panel.get("items") or []:
                registered = item.get("registered_service") or {}
                same_service = str(registered.get("id") or "") == service_id
                same_namespace = item.get("service_namespace") == namespace
                if not same_service and not same_namespace:
                    continue
                weight = 2 if str(item.get("state") or "").lower() == "running" else 1
                counts[node_ref["id"]] += weight
        if counts:
            return nodes.detail(counts.most_common(1)[0][0], env=env)

        policy = service.get("target_node_policy") or {}
        metadata = service.get("metadata") or {}
        placement = metadata.get("placement") or {}
        fallback_node_id = str(policy.get("node_id") or placement.get("node_id") or "").strip()
        if fallback_node_id:
            return nodes.detail(fallback_node_id, env=env)
        raise ServiceError(404, "named volume을 복사할 원본 서버를 찾을 수 없습니다.", "SERVICE_VOLUME_SOURCE_NODE_NOT_FOUND")

    def _ssh_argv(self, node, command, env=None):
        credential = node.get("credential") or {}
        key_file = credential.get("key_file") or (credential.get("metadata") or {}).get("key_file")
        username = credential.get("username")
        if not username:
            raise ServiceError(409, "대상 서버 SSH 계정 정보가 없습니다.", "SERVICE_VOLUME_SSH_USERNAME_MISSING", node_id=node.get("id"))
        if not key_file:
            raise ServiceError(409, "대상 서버 SSH key file 정보가 없습니다.", "SERVICE_VOLUME_SSH_KEY_MISSING", node_id=node.get("id"))
        host = nodes_shared.node_access_host(node)
        port = node.get("ssh_port")
        known_hosts = ssh_executor.known_hosts_for_run(host, port=port, env=env)
        argv = [
            "ssh",
            *ssh_executor._port_args(port),
            "-i",
            str(key_file),
            "-o",
            "BatchMode=yes",
            "-o",
            "IdentitiesOnly=yes",
            "-o",
            f"UserKnownHostsFile={known_hosts}",
            "-o",
            "StrictHostKeyChecking=accept-new",
            "-o",
            "LogLevel=ERROR",
            "-o",
            "ConnectTimeout=30",
            ssh_executor._target(host, username),
            command,
        ]
        return argv

    def _node_command_argv(self, node, script, env=None):
        if _is_local_master_node(node):
            return ["sh", "-lc", script]
        return self._ssh_argv(node, script, env=env)

    def _node_detail(self, node, env=None):
        if not node or not node.get("id"):
            return node or {}
        if node.get("credential") and node.get("private_host"):
            return node
        try:
            return nodes.detail(node["id"], env=env)
        except Exception:
            return node

    def _export_script(self, volume_name):
        inner = "cd /volume && tar -cpf - ."
        return (
            "set -eu; "
            f"docker volume inspect {shlex.quote(volume_name)} >/dev/null; "
            f"docker run --rm -v {shlex.quote(volume_name)}:/volume:ro {shlex.quote(TRANSFER_IMAGE)} sh -lc {shlex.quote(inner)}"
        )

    def _import_script(self, volume_name):
        inner = "cd /volume && find . -mindepth 1 -maxdepth 1 -exec rm -rf -- {} + && tar -xpf -"
        return (
            "set -eu; "
            f"docker volume create {shlex.quote(volume_name)} >/dev/null; "
            f"docker run --rm -i -v {shlex.quote(volume_name)}:/volume {shlex.quote(TRANSFER_IMAGE)} sh -lc {shlex.quote(inner)}"
        )

    def _transfer_volume(self, source_node, target_node, volume_name, env=None):
        source_argv = self._node_command_argv(source_node, self._export_script(volume_name), env=env)
        target_argv = self._node_command_argv(target_node, self._import_script(volume_name), env=env)
        pipeline = f"{shlex.join(source_argv)} | {shlex.join(target_argv)}"
        started = time.monotonic()
        try:
            completed = subprocess.run(
                ["bash", "-o", "pipefail", "-lc", pipeline],
                capture_output=True,
                text=True,
                timeout=TRANSFER_TIMEOUT_SECONDS,
                check=False,
            )
            duration_ms = int((time.monotonic() - started) * 1000)
            return {
                "status": "ok" if completed.returncode == 0 else "error",
                "exit_code": completed.returncode,
                "stdout": _trim(completed.stdout),
                "stderr": _trim(completed.stderr),
                "duration_ms": duration_ms,
            }
        except subprocess.TimeoutExpired as exc:
            duration_ms = int((time.monotonic() - started) * 1000)
            return {
                "status": "timeout",
                "exit_code": None,
                "stdout": _trim(exc.stdout),
                "stderr": _trim(exc.stderr or f"named volume transfer timed out after {TRANSFER_TIMEOUT_SECONDS}s"),
                "duration_ms": duration_ms,
                "timed_out": True,
            }

    def migrate_service_volumes(self, service, target_node, operation_id=None, env=None):
        refs = self.compose_named_volumes(service)
        if not refs:
            result = {"status": "skipped", "reason": "no_named_volumes", "volumes": []}
            _operation_output(operation_id, "마이그레이션할 named volume이 없습니다.", metadata={"step": "volume skipped"}, env=env)
            return result

        source_node = self._node_detail(self._source_node(service, env=env), env=env)
        target_node = self._node_detail(target_node, env=env)
        source_summary = _node_summary(source_node)
        target_summary = _node_summary(target_node)
        if str(source_node.get("id") or "") == str(target_node.get("id") or ""):
            result = {
                "status": "skipped",
                "reason": "same_node",
                "source_node": source_summary,
                "target_node": target_summary,
                "volumes": refs,
            }
            _operation_output(operation_id, "원본 서버와 대상 서버가 같아 named volume 복사를 건너뜁니다.", metadata={"step": "volume skipped", **result}, env=env)
            return result

        _operation_output(
            operation_id,
            f"named volume {len(refs)}개를 {source_summary.get('name') or source_summary.get('host')}에서 {target_summary.get('name') or target_summary.get('host')}로 복사합니다.",
            metadata={"step": "volume transfer start", "source_node": source_summary, "target_node": target_summary, "volumes": refs},
            env=env,
        )
        transferred = []
        failures = []
        for ref in refs:
            volume_name = ref["docker_volume"]
            transfer = self._transfer_volume(source_node, target_node, volume_name, env=env)
            item = {**ref, "transfer": transfer}
            transferred.append(item)
            if transfer.get("status") != "ok":
                failures.append(item)
                _operation_output(
                    operation_id,
                    f"named volume 복사 실패: {volume_name}",
                    stream="stderr",
                    metadata={"step": "volume transfer failed", "volume": item},
                    env=env,
                )
                continue
            _operation_output(
                operation_id,
                f"named volume 복사 완료: {volume_name}",
                metadata={"step": "volume transfer volume", "volume": item},
                env=env,
            )

        result = {
            "status": "failed" if failures else "succeeded",
            "source_node": source_summary,
            "target_node": target_summary,
            "volumes": transferred,
        }
        if failures:
            raise ServiceError(
                409,
                "named volume 이관에 실패했습니다.",
                "SERVICE_VOLUME_MIGRATION_FAILED",
                volume_migration=result,
            )
        return result


Model = ServiceVolumeMigration()
