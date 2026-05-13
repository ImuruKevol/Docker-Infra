from pathlib import Path
import threading

import yaml
from psycopg.types.json import Jsonb


connect = wiz.model("db/postgres").connect
local_executor = wiz.model("struct/local_executor")
operations = wiz.model("struct/operations")
compose_rules = wiz.model("struct/compose_rules")
service_ports = wiz.model("struct/services_ports")
service_nginx = wiz.model("struct/service_nginx")
deploy_targets = wiz.model("struct/services_deploy_targets")
placement_selector = wiz.model("struct/services_placement")
ServiceError = wiz.model("struct/services_shared").ServiceError


def _command_text(result):
    if not result:
        return ""
    return result.get("stdout") or result.get("stderr") or ""


class ServiceDeployMixin:
    def _deploy_operation_payload(self, service, stack_name, compose_path):
        return {
            "service_id": str(service.get("id")),
            "namespace": service.get("namespace"),
            "stack_name": stack_name,
            "compose_path": str(compose_path),
        }

    def _create_deploy_operation(self, service, stack_name, compose_path, status="running", message="서비스 배포를 시작했습니다.", env=None):
        return operations.create(
            "service.deploy",
            target_type="service",
            target_id=service.get("id"),
            status=status,
            message=message,
            requested_payload=self._deploy_operation_payload(service, stack_name, compose_path),
            metadata={"service_id": str(service.get("id")), "namespace": service.get("namespace"), "background": status == "pending"},
            env=env,
        )

    def _prepare_deploy(self, payload, env=None):
        payload = payload or {}
        service_id = payload.get("service_id")
        if not service_id:
            raise ServiceError(400, "service_id는 필수입니다.", "SERVICE_ID_REQUIRED")

        with connect(env=env) as connection:
            with connection.cursor() as cursor:
                service = self._service_row(cursor, service_id)

        compose_path = Path(service.get("compose_path") or "").expanduser()
        if not compose_path.is_file():
            raise ServiceError(404, "서비스 Compose 파일을 찾을 수 없습니다.", "SERVICE_COMPOSE_NOT_FOUND")
        stack_name = service.get("stack_name") or service.get("namespace")
        return service, compose_path, stack_name

    def _active_deploy_operation(self, service, env=None):
        service_id = str(service.get("id") or "")
        namespace = str(service.get("namespace") or "")
        with connect(env=env) as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT id
                    FROM operation_logs
                    WHERE type = 'service.deploy'
                      AND status IN ('pending', 'running')
                      AND (
                        requested_payload->>'service_id' = %s
                        OR metadata->>'service_id' = %s
                        OR requested_payload->>'namespace' = %s
                        OR metadata->>'namespace' = %s
                      )
                    ORDER BY created_at DESC
                    LIMIT 1
                    """,
                    (service_id, service_id, namespace, namespace),
                )
                row = cursor.fetchone()
        if row is None:
            return None
        return operations.detail(row["id"], env=env)

    def _deploy_background_worker(self, payload, operation_id, env=None):
        try:
            body = dict(payload or {})
            body["operation_id"] = operation_id
            self.deploy(body, env=env)
        except ServiceError:
            return
        except Exception as exc:
            try:
                operations.append_output(
                    operation_id,
                    str(exc),
                    stream="stderr",
                    metadata={"step": "background deploy", "error": str(exc)},
                    env=env,
                )
                operations.transition(
                    operation_id,
                    "failed",
                    message="서비스 배포 중 예기치 않은 오류가 발생했습니다.",
                    result_payload={"error": str(exc)},
                    env=env,
                )
            except Exception:
                pass

    def deploy_background(self, payload, env=None):
        payload = dict(payload or {})
        service, compose_path, stack_name = self._prepare_deploy(payload, env=env)
        if payload.get("force_new_operation") is not True:
            active = self._active_deploy_operation(service, env=env)
            if active:
                return {"accepted": True, "service": service, "operation": active, "deduplicated": True}
        operation = self._create_deploy_operation(
            service,
            stack_name,
            compose_path,
            status="pending",
            message="서비스 배포를 백그라운드에서 준비했습니다.",
            env=env,
        )
        thread = threading.Thread(
            target=self._deploy_background_worker,
            args=(payload, operation["id"], env),
            name=f"service-deploy-{operation['id']}",
            daemon=True,
        )
        thread.start()
        return {"accepted": True, "service": service, "operation": operation}

    def _append_result(self, operation_id, result, label, env=None):
        text = _command_text(result)
        if not text:
            text = f"{label}: {result.get('status')}"
        stream = "stdout" if result.get("status") == "ok" else "stderr"
        operations.append_output(operation_id, text, stream=stream, metadata={"step": label}, env=env)

    def _deploy_failure(self, operation_id, message, result=None, env=None):
        payload = {"check": result or {}}
        operation = operations.transition(operation_id, "failed", message=message, result_payload=payload, env=env)
        raise ServiceError(409, message, "SERVICE_DEPLOY_FAILED", operation=operation, check=result)

    def _sync_domain_published_ports(self, service_id, compose_path, env=None):
        return deploy_targets.sync_domain_published_ports(service_id, compose_path, env=env)

    def _record_deploy_adjustments(self, service_id, allocations, domain_port_updates, env=None):
        payload = {
            "port_allocation": (allocations or {}).get("allocations") or [],
            "port_allocation_changed": bool((allocations or {}).get("changed")),
            "domain_port_updates": domain_port_updates or [],
        }
        with connect(env=env) as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT id, metadata
                    FROM compose_versions
                    WHERE service_id = %s
                    ORDER BY version DESC, created_at DESC
                    LIMIT 1
                    """,
                    (service_id,),
                )
                row = cursor.fetchone()
                if row is not None:
                    metadata = dict(row.get("metadata") or {})
                    metadata["deploy_adjustments"] = payload
                    cursor.execute(
                        "UPDATE compose_versions SET metadata = %s WHERE id = %s",
                        (Jsonb(metadata), row["id"]),
                    )
        return payload

    def _deployment_node(self, service, env=None):
        policy = dict(service.get("target_node_policy") or {})
        metadata = dict(service.get("metadata") or {})
        placement = dict(metadata.get("placement") or {})
        selected_id = str(policy.get("node_id") or placement.get("node_id") or "").strip()
        with connect(env=env) as connection:
            with connection.cursor() as cursor:
                if selected_id:
                    cursor.execute("SELECT * FROM nodes WHERE id = %s LIMIT 1", (selected_id,))
                    row = cursor.fetchone()
                    if row is not None:
                        return dict(row)
                try:
                    recommendation = placement_selector.recommend(env=env)
                    selected = recommendation.get("selected") or {}
                    recommended_id = ((selected.get("node") or {}).get("id") or "").strip()
                except Exception:
                    recommended_id = ""
                if recommended_id:
                    cursor.execute("SELECT * FROM nodes WHERE id = %s LIMIT 1", (recommended_id,))
                    row = cursor.fetchone()
                    if row is not None:
                        return dict(row)
                cursor.execute(
                    """
                    SELECT *
                    FROM nodes
                    WHERE is_local_master = true
                    ORDER BY created_at ASC
                    LIMIT 1
                    """
                )
                row = cursor.fetchone()
                if row is not None:
                    return dict(row)
                cursor.execute("SELECT * FROM nodes ORDER BY created_at ASC LIMIT 1")
                row = cursor.fetchone()
                return dict(row) if row is not None else None

    def _deployment_node_summary(self, node):
        if not node:
            return {}
        return {
            "id": str(node.get("id") or ""),
            "name": str(node.get("name") or ""),
            "host": str(node.get("host") or ""),
            "swarm_node_id": str(node.get("swarm_node_id") or ""),
            "is_local_master": bool(node.get("is_local_master")),
        }

    def _apply_stack_placement(self, compose_path, service, operation_id, env=None):
        node = self._deployment_node(service, env=env)
        swarm_node_id = str((node or {}).get("swarm_node_id") or "").strip()
        if not swarm_node_id:
            return {"applied": False, "reason": "node_unavailable"}
        node_summary = self._deployment_node_summary(node)
        compose = yaml.safe_load(compose_path.read_text(encoding="utf-8")) or {}
        services = compose.get("services") or {}
        constraint = f"node.id == {swarm_node_id}"
        changed = False
        for item in services.values():
            if not isinstance(item, dict):
                continue
            deploy = item.setdefault("deploy", {})
            if not isinstance(deploy, dict):
                continue
            placement = deploy.setdefault("placement", {})
            if not isinstance(placement, dict):
                continue
            constraints = placement.setdefault("constraints", [])
            if not isinstance(constraints, list):
                constraints = []
                placement["constraints"] = constraints
            next_constraints = [
                value
                for value in constraints
                if not str(value).strip().startswith("node.id ==")
                and not str(value).strip().startswith("node.hostname ==")
            ]
            if constraint not in next_constraints:
                next_constraints.append(constraint)
            if next_constraints != constraints:
                placement["constraints"] = next_constraints
                changed = True
        if changed:
            compose_path.write_text(yaml.safe_dump(compose, sort_keys=False, allow_unicode=False), encoding="utf-8")
        operations.append_output(
            operation_id,
            f"stack placement: {node_summary.get('name') or node_summary.get('host') or swarm_node_id}",
            stream="system",
            metadata={"step": "stack placement", "node": node_summary, "constraint": constraint, "changed": changed},
            env=env,
        )
        return {"applied": True, "node": node_summary, "constraint": constraint, "changed": changed}

    def deploy(self, payload, env=None):
        payload = dict(payload or {})
        service, compose_path, stack_name = self._prepare_deploy(payload, env=env)
        service_id = service.get("id")
        operation_id = payload.get("operation_id")
        if operation_id:
            operation = operations.transition(
                operation_id,
                "running",
                message="서비스 배포를 시작했습니다.",
                metadata={"service_id": str(service_id), "namespace": service.get("namespace"), "background": True},
                env=env,
            )
        else:
            operation = self._create_deploy_operation(service, stack_name, compose_path, env=env)
        operation_id = operation["id"]

        inspect = local_executor.run(
            "swarm.network.inspect",
            params={"network_name": compose_rules.OVERLAY_NETWORK},
            timeout_seconds=15,
            env=env,
        )
        if inspect.get("status") != "ok":
            ensure = local_executor.run(
                "swarm.network.ensure",
                params={"network_name": compose_rules.OVERLAY_NETWORK},
                timeout_seconds=30,
                env=env,
            )
            self._append_result(operation_id, ensure, "overlay network", env=env)
            if ensure.get("status") != "ok":
                return self._deploy_failure(operation_id, "서비스 네트워크를 준비할 수 없습니다.", ensure, env=env)

        placement = self._apply_stack_placement(compose_path, service, operation_id, env=env)
        allocations = service_ports.allocate_file(compose_path)
        if allocations.get("allocations"):
            operations.append_output(
                operation_id,
                f"port allocation: {allocations['allocations']}",
                stream="system",
                metadata={"step": "port allocation"},
                env=env,
            )
        domain_port_updates = self._sync_domain_published_ports(service_id, compose_path, env=env)
        if domain_port_updates:
            operations.append_output(
                operation_id,
                f"domain port mapping: {domain_port_updates}",
                stream="system",
                metadata={"step": "domain port mapping"},
                env=env,
            )
        deploy_adjustments = self._record_deploy_adjustments(service_id, allocations, domain_port_updates, env=env)

        deploy = local_executor.run(
            "service.stack.deploy",
            params={"compose_path": str(compose_path), "stack_name": stack_name},
            timeout_seconds=payload.get("timeout_seconds") or 300,
            env=env,
        )
        self._append_result(operation_id, deploy, "stack deploy", env=env)
        if deploy.get("status") != "ok":
            return self._deploy_failure(operation_id, "서비스 배포에 실패했습니다.", deploy, env=env)

        proxy_targets = deploy_targets.sync_domain_proxy_targets(service_id, stack_name, env=env)
        if proxy_targets.get("updated") or proxy_targets.get("skipped") is not True:
            operations.append_output(
                operation_id,
                f"domain proxy target: {proxy_targets}",
                stream="system",
                metadata={"step": "domain proxy target", "proxy_targets": proxy_targets},
                env=env,
            )

        nginx = service_nginx.apply(service_id, env=env)
        for command in nginx.get("commands") or []:
            self._append_result(operation_id, command.get("result") or {}, command.get("step") or "nginx", env=env)
        operations.append_output(
            operation_id,
            nginx.get("message") or "nginx status updated",
            stream="system" if nginx.get("status") in {"ok", "skipped"} else "stderr",
            metadata={"step": "nginx apply", "nginx": nginx},
            env=env,
        )
        if nginx.get("status") == "error":
            return self._deploy_failure(operation_id, "nginx 설정을 적용할 수 없습니다.", nginx, env=env)

        metadata = dict(service.get("metadata") or {})
        metadata["last_deploy"] = {
            "operation_id": operation_id,
            "stack_name": stack_name,
            "nginx": nginx,
            "deploy_adjustments": deploy_adjustments,
            "placement": placement,
        }
        with connect(env=env) as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    UPDATE services
                    SET status = 'deployed',
                        metadata = %s,
                        updated_at = now()
                    WHERE id = %s
                    RETURNING *
                    """,
                    (Jsonb(metadata), service_id),
                )
                service = self._service_row(cursor, service_id)

        runtime_status = None
        try:
            refreshed = self.refresh_deploy_status(service_id, operation_id=operation_id, env=env)
            service = refreshed["service"]
            runtime_status = refreshed["runtime_status"]
            stack_summary = runtime_status.get("stack", {}).get("summary", {})
            container_summary = runtime_status.get("containers", {}).get("summary", {})
            operations.append_output(
                operation_id,
                f"runtime status: stack {stack_summary}, containers {container_summary}",
                stream="system",
                metadata={"step": "runtime status", "runtime_status": runtime_status},
                env=env,
            )
        except Exception as exc:
            operations.append_output(
                operation_id,
                f"runtime status refresh failed: {exc}",
                stream="stderr",
                metadata={"step": "runtime status"},
                env=env,
            )

        ai_verification = None
        if payload.get("start_ai_verification") is True:
            try:
                ai_assistant = wiz.model("struct/ai_assistant")
                ai_verification = ai_assistant.start_runtime_verification(
                    {
                        "service_id": service_id,
                        "source_operation_id": operation_id,
                        "model_ref": payload.get("model_ref") or "auto",
                        "intent": payload.get("ai_verification_intent") or payload.get("intent") or "",
                        "client_runtime_issues": payload.get("client_runtime_issues") if isinstance(payload.get("client_runtime_issues"), dict) else {},
                        "allow_container_terminal_actions": payload.get("allow_container_terminal_actions") is not False,
                        "allow_ssh_command": payload.get("allow_ssh_command") is not False,
                        "apply": payload.get("ai_verify_apply") is not False,
                        "deploy": payload.get("ai_verify_deploy") is not False,
                    },
                    env=env,
                )
                operations.append_output(
                    operation_id,
                    "AI 백그라운드 검증을 시작했습니다.",
                    stream="system",
                    metadata={"step": "ai verification", "operation": ai_verification.get("operation")},
                    env=env,
                )
            except Exception as exc:
                operations.append_output(
                    operation_id,
                    "AI 백그라운드 검증을 시작할 수 없습니다: %s" % exc,
                    stream="stderr",
                    metadata={"step": "ai verification", "error": str(exc)},
                    env=env,
                )

        operation = operations.transition(
            operation_id,
            "succeeded",
            message="서비스 배포를 완료했습니다.",
            result_payload={"service_id": service_id, "stack_name": stack_name, "runtime_status": runtime_status, "ai_verification": ai_verification},
            env=env,
        )
        return {"service": service, "operation": operation, "runtime_status": runtime_status, "ai_verification": ai_verification}


Model = ServiceDeployMixin
