import shutil
import re
import shlex
from pathlib import Path


connect = wiz.model("db/postgres").connect
local_executor = wiz.model("struct/local_executor")
operations = wiz.model("struct/operations")
nodes = wiz.model("struct").nodes
webserver = wiz.model("struct/webserver")
domains_model = wiz.model("struct/domains")
ddns_model = wiz.model("struct/domains_ddns")
ServiceError = wiz.model("struct/services_shared").ServiceError


def _safe_segment(value):
    return re.sub(r"[^A-Za-z0-9_.-]+", "-", str(value or "").strip()).strip(".-") or "service"


def _stack_missing(result):
    output = f"{result.get('stderr', '')}\n{result.get('stdout', '')}".lower()
    return "nothing found" in output or "not found" in output or "no such" in output


class ServiceDeleteMixin:
    def _managed_nginx_delete_path(self, raw_path, base_path):
        raw = str(raw_path or "").strip()
        if not raw:
            return None
        target = Path(raw).expanduser()
        if not target.name.startswith("docker-infra-") or target.suffix != ".conf":
            return None
        base = Path(base_path).expanduser()
        try:
            parent = target.parent.resolve(strict=False)
            resolved_base = base.resolve(strict=False)
            if parent != resolved_base and not parent.is_relative_to(resolved_base):
                return None
        except Exception:
            return None
        return target

    def _service_domains(self, service_id, env=None):
        with connect(env=env) as connection:
            with connection.cursor() as cursor:
                cursor.execute("SELECT * FROM service_domains WHERE service_id = %s ORDER BY domain ASC", (service_id,))
                return [dict(row) for row in cursor.fetchall()]

    def _deployment_node(self, service, env=None):
        policy = dict(service.get("target_node_policy") or {})
        metadata = dict(service.get("metadata") or {})
        placement = dict(metadata.get("placement") or {})
        node_id = str(policy.get("node_id") or placement.get("node_id") or "").strip()
        with connect(env=env) as connection:
            with connection.cursor() as cursor:
                if node_id:
                    cursor.execute("SELECT * FROM nodes WHERE id = %s LIMIT 1", (node_id,))
                    row = cursor.fetchone()
                    if row is not None:
                        return dict(row)
                cursor.execute("SELECT * FROM nodes WHERE is_local_master = true ORDER BY created_at ASC LIMIT 1")
                row = cursor.fetchone()
                return dict(row) if row is not None else None

    def _deployment_mode(self, service, node=None):
        if node is not None:
            return "swarm" if str(node.get("swarm_node_id") or "").strip() else "compose"
        policy = dict(service.get("target_node_policy") or {})
        return "compose" if str(policy.get("mode") or "").strip().lower() == "compose" else "swarm"

    def _remove_compose(self, service, operation_id, env=None):
        stack_name = service.get("stack_name") or service.get("namespace")
        node = self._deployment_node(service, env=env)
        if not stack_name or not node:
            return None
        if node.get("is_local_master"):
            result = local_executor.run(
                "service.compose.down",
                params={"compose_path": service.get("compose_path"), "stack_name": stack_name, "remove_volumes": True},
                timeout_seconds=120,
                env=env,
            )
        else:
            node_detail = nodes.detail(node.get("id"), env=env)
            script = (
                "set -eu\n"
                f"STACK={shlex.quote(stack_name)}\n"
                'FILE="$HOME/.docker-infra/services/$STACK/docker-compose.yaml"\n'
                'if [ -f "$FILE" ]; then\n'
                '  docker compose -p "$STACK" -f "$FILE" down --volumes\n'
                "else\n"
                '  ids="$(docker ps -aq --filter "label=com.docker.compose.project=$STACK" 2>/dev/null || true)"\n'
                '  [ -z "$ids" ] || docker rm -f $ids\n'
                "fi\n"
                'tmp="$(mktemp)"\n'
                'trap \'rm -f "$tmp" "${tmp}.uniq"\' EXIT\n'
                'docker volume ls -q --filter "label=com.docker.compose.project=$STACK" 2>/dev/null >> "$tmp" || true\n'
                'docker volume ls -q 2>/dev/null | awk -v prefix="${STACK}_" \'index($0, prefix) == 1 {print $0}\' >> "$tmp" || true\n'
                'sort -u "$tmp" | awk \'NF\' > "${tmp}.uniq"\n'
                'mv "${tmp}.uniq" "$tmp"\n'
                'if [ -s "$tmp" ]; then\n'
                '  while IFS= read -r volume; do\n'
                '    [ -n "$volume" ] || continue\n'
                '    docker volume inspect "$volume" >/dev/null 2>&1 || continue\n'
                '    docker volume rm -f "$volume"\n'
                '  done < "$tmp"\n'
                "fi\n"
            )
            result = nodes._run_ssh_command(node_detail, ["sh", "-lc", script], timeout_seconds=120, env=env, capture_limit=12000)
        operations.append_output(operation_id, result.get("stdout") or result.get("stderr") or result.get("status"), stream="stdout" if result.get("status") == "ok" else "stderr", metadata={"step": "compose down", "result": result}, env=env)
        if result.get("status") != "ok":
            raise ServiceError(409, "Docker Compose 서비스를 삭제할 수 없습니다.", "SERVICE_COMPOSE_REMOVE_FAILED", check=result)
        return result

    def _remove_stack(self, service, operation_id, env=None):
        node = self._deployment_node(service, env=env)
        if self._deployment_mode(service, node=node) == "compose":
            return self._remove_compose(service, operation_id, env=env)
        stack_name = service.get("stack_name") or service.get("namespace")
        if not stack_name:
            return None
        result = local_executor.run("service.stack.remove", params={"stack_name": stack_name}, timeout_seconds=120, env=env)
        operations.append_output(operation_id, result.get("stdout") or result.get("stderr") or result.get("status"), stream="stdout" if result.get("status") == "ok" else "stderr", metadata={"step": "stack remove", "result": result}, env=env)
        if result.get("status") != "ok" and not _stack_missing(result):
            raise ServiceError(409, "Docker 서비스를 삭제할 수 없습니다.", "SERVICE_STACK_REMOVE_FAILED", check=result)
        return result

    def _remove_volumes(self, service, operation_id, env=None):
        node = self._deployment_node(service, env=env)
        if self._deployment_mode(service, node=node) == "compose":
            return {"status": "skipped", "reason": "compose_down_removed_volumes"}
        stack_name = service.get("stack_name") or service.get("namespace")
        if not stack_name:
            return None
        result = local_executor.run("service.stack.volumes.remove", params={"stack_name": stack_name}, timeout_seconds=90, env=env)
        operations.append_output(operation_id, result.get("stdout") or result.get("stderr") or result.get("status"), stream="stdout" if result.get("status") == "ok" else "stderr", metadata={"step": "stack volumes remove", "result": result}, env=env)
        if result.get("status") != "ok":
            raise ServiceError(409, "Docker 서비스 볼륨을 삭제할 수 없습니다.", "SERVICE_STACK_VOLUME_REMOVE_FAILED", check=result)
        return result

    def _remove_nginx_configs(self, domains, operation_id, env=None):
        nginx = webserver.nginx_defaults()
        available = Path(nginx.get("available_site_path") or "/etc/nginx/sites-available")
        enabled = Path(nginx.get("site_path") or "/etc/nginx/sites-enabled")
        targets = []
        for domain in domains:
            metadata = dict(domain.get("metadata") or {})
            for raw_path, base in [
                (metadata.get("nginx_config_path"), available),
                (metadata.get("nginx_enabled_path"), enabled),
                (available / f"docker-infra-{_safe_segment(domain.get('domain'))}.conf", available),
                (enabled / f"docker-infra-{_safe_segment(domain.get('domain'))}.conf", enabled),
            ]:
                target = self._managed_nginx_delete_path(raw_path, base)
                if target and target not in targets:
                    targets.append(target)

        removed = []
        for target in targets:
            if target.exists() or target.is_symlink():
                target.unlink()
                removed.append(str(target))
        if not removed:
            return {"removed": []}

        operations.append_output(operation_id, f"removed nginx configs: {removed}", stream="system", metadata={"step": "nginx config remove", "removed": removed}, env=env)
        configtest = local_executor.run("proxy.nginx.configtest", timeout_seconds=20, env=env)
        operations.append_output(operation_id, configtest.get("stdout") or configtest.get("stderr") or configtest.get("status"), stream="stdout" if configtest.get("status") == "ok" else "stderr", metadata={"step": "nginx configtest", "result": configtest}, env=env)
        if configtest.get("status") != "ok":
            raise ServiceError(409, "nginx 설정 검사에 실패해 삭제를 중단했습니다.", "SERVICE_DELETE_NGINX_CONFIGTEST_FAILED", check=configtest)
        reload_result = local_executor.run("proxy.nginx.reload", timeout_seconds=20, env=env)
        operations.append_output(operation_id, reload_result.get("stdout") or reload_result.get("stderr") or reload_result.get("status"), stream="stdout" if reload_result.get("status") == "ok" else "stderr", metadata={"step": "nginx reload", "result": reload_result}, env=env)
        if reload_result.get("status") != "ok":
            raise ServiceError(409, "nginx reload에 실패해 삭제를 중단했습니다.", "SERVICE_DELETE_NGINX_RELOAD_FAILED", check=reload_result)
        return {"removed": removed, "configtest": configtest, "reload": reload_result}

    def _remove_dns_records(self, domains, operation_id, env=None):
        if not domains:
            return {"status": "ok", "deleted": [], "skipped": [], "sync_errors": []}
        try:
            result = domains_model.delete_service_dns_records(domains, env=env)
        except domains_model.DomainError as exc:
            metadata = {"step": "legacy dns remove", "error_code": exc.error_code, **exc.extra}
            operations.append_output(operation_id, exc.message, stream="stderr", metadata=metadata, env=env)
            raise ServiceError(
                409,
                "외부 DNS 레코드를 삭제할 수 없습니다.",
                "SERVICE_DNS_RECORD_REMOVE_FAILED",
                dns={"message": exc.message, "error_code": exc.error_code, **exc.extra},
            )
        operations.append_output(
            operation_id,
            f"checked legacy DNS records: deleted={len(result.get('deleted') or [])}, skipped={len(result.get('skipped') or [])}",
            stream="system",
            metadata={"step": "legacy dns remove", "result": result},
            env=env,
        )
        return result

    def _remove_ddns_records(self, domains, operation_id, env=None):
        if not domains:
            return {"status": "ok", "unregistered": [], "skipped": [], "failures": []}
        try:
            result = ddns_model.unregister_service_domains(domains, env=env)
        except ddns_model.DomainError as exc:
            result = {"status": "warning", "message": exc.message, "error_code": exc.error_code, **exc.extra}
            operations.append_output(
                operation_id,
                f"DDNS unregister warning: {exc.message}",
                stream="stderr",
                metadata={"step": "ddns unregister", "result": result},
                env=env,
            )
            return result
        operations.append_output(
            operation_id,
            f"checked DDNS registrations: unregistered={len(result.get('unregistered') or [])}, skipped={len(result.get('skipped') or [])}",
            stream="system",
            metadata={"step": "ddns unregister", "result": result},
            env=env,
        )
        return result

    def _remove_service_files(self, service, operation_id, env=None):
        root = self._service_root(service)
        service_roots = [self.service_root().resolve(), self.legacy_service_root().resolve()]
        try:
            managed = any(root != service_root and root.is_relative_to(service_root) for service_root in service_roots)
            if managed and root.exists():
                shutil.rmtree(root)
                operations.append_output(operation_id, f"removed service files: {root}", stream="system", metadata={"step": "service files remove", "path": str(root)}, env=env)
                return str(root)
        except Exception as exc:
            raise ServiceError(409, "서비스 파일을 삭제할 수 없습니다.", "SERVICE_FILES_REMOVE_FAILED", path=str(root), reason=str(exc))
        return ""

    def delete(self, payload, env=None):
        payload = payload or {}
        service_id = payload.get("service_id")
        if not service_id:
            raise ServiceError(400, "service_id는 필수입니다.", "SERVICE_ID_REQUIRED")
        with connect(env=env) as connection:
            with connection.cursor() as cursor:
                service = self._service_row(cursor, service_id)

        operation = operations.create(
            "service.delete",
            target_type="service",
            target_id=service_id,
            message="서비스 삭제를 시작했습니다.",
            requested_payload={"service_id": service_id, "namespace": service.get("namespace"), "stack_name": service.get("stack_name")},
            metadata={"service_id": str(service_id), "namespace": service.get("namespace")},
            env=env,
        )
        operation_id = operation["id"]
        try:
            domains = self._service_domains(service_id, env=env)
            stack_result = self._remove_stack(service, operation_id, env=env)
            volume_result = self._remove_volumes(service, operation_id, env=env)
            nginx_result = self._remove_nginx_configs(domains, operation_id, env=env)
            ddns_result = self._remove_ddns_records(domains, operation_id, env=env)
            dns_result = self._remove_dns_records(domains, operation_id, env=env)
            removed_path = self._remove_service_files(service, operation_id, env=env)
            with connect(env=env) as connection:
                with connection.cursor() as cursor:
                    cursor.execute("DELETE FROM services WHERE id = %s", (service_id,))
            operation = operations.transition(
                operation_id,
                "succeeded",
                message="서비스 삭제를 완료했습니다.",
                result_payload={"service_id": service_id, "stack": stack_result, "volumes": volume_result, "nginx": nginx_result, "ddns": ddns_result, "dns": dns_result, "removed_path": removed_path},
                env=env,
            )
            return {"deleted_service_id": service_id, "operation": operation}
        except ServiceError as exc:
            operation = operations.transition(operation_id, "failed", message=exc.message, result_payload={"error_code": exc.error_code, **exc.extra}, env=env)
            exc.extra["operation"] = operation
            raise
        except Exception as exc:
            operation = operations.transition(operation_id, "failed", message=str(exc), result_payload={"error": str(exc)}, env=env)
            raise ServiceError(409, "서비스를 삭제할 수 없습니다.", "SERVICE_DELETE_FAILED", operation=operation, reason=str(exc))


Model = ServiceDeleteMixin
