connect = wiz.model("db/postgres").connect
operations = wiz.model("struct/operations")
service_nginx = wiz.model("struct/service_nginx")
certificates = wiz.model("struct/service_nginx_certificates")
shared = wiz.model("struct/services_shared")
ServiceError = shared.ServiceError
_row = shared.row


def _command_text(result):
    if not result:
        return ""
    return result.get("stdout") or result.get("stderr") or result.get("message") or str(result.get("status") or "")


class ServiceCertbotMixin:
    def service_certificates(self, domains, env=None):
        return certificates.service_certificates(domains, env=env)

    def _append_command_result(self, operation_id, command, env=None):
        result = command.get("result") or {}
        label = command.get("step") or "certbot"
        text = _command_text(result) or f"{label}: {result.get('status')}"
        stream = "stdout" if result.get("status") == "ok" else "stderr"
        operations.append_output(operation_id, text, stream=stream, metadata={"step": label, "result": result}, env=env)

    def _certbot_domain_row(self, service_id, domain, require_certificate=True, env=None):
        target = str(domain or "").strip().lower()
        if not service_id:
            raise ServiceError(400, "service_id는 필수입니다.", "SERVICE_ID_REQUIRED")
        if not target:
            raise ServiceError(400, "domain은 필수입니다.", "SERVICE_DOMAIN_REQUIRED")
        with connect(env=env) as connection:
            with connection.cursor() as cursor:
                service = self._service_row(cursor, service_id)
                cursor.execute(
                    "SELECT * FROM service_domains WHERE service_id = %s AND lower(domain) = %s LIMIT 1",
                    (service_id, target),
                )
                row = cursor.fetchone()
        if row is None:
            raise ServiceError(404, "서비스 도메인 설정을 찾을 수 없습니다.", "SERVICE_DOMAIN_NOT_FOUND")
        domain_row = _row(row)
        metadata = dict(domain_row.get("metadata") or {})
        if domain_row.get("ssl_mode") != "certbot" and metadata.get("nginx_ssl_mode") != "certbot":
            raise ServiceError(409, "무료 인증서로 관리되는 도메인이 아닙니다.", "SERVICE_DOMAIN_NOT_CERTBOT")
        cert = certificates.certbot_certificate(target, env=env)
        if require_certificate and (not cert or not cert.get("cert_path")):
            raise ServiceError(409, "아직 발급된 무료 인증서가 없습니다. 먼저 서비스를 적용해 인증서를 발급하세요.", "SERVICE_CERTBOT_CERT_MISSING")
        return service, domain_row

    def renew_certbot_certificate(self, payload, env=None):
        body = payload or {}
        service_id = body.get("service_id")
        domain = str(body.get("domain") or "").strip().lower()
        service, domain_row = self._certbot_domain_row(service_id, domain, env=env)
        operation = operations.create(
            "service.certbot.renew",
            target_type="service",
            target_id=service_id,
            status="running",
            message=f"{domain} 무료 인증서 수동 갱신을 시작했습니다.",
            requested_payload={"service_id": str(service_id), "domain": domain, "domain_id": str(domain_row.get("id"))},
            metadata={"service_id": str(service_id), "namespace": service.get("namespace"), "domain": domain},
            env=env,
        )
        operation_id = operation["id"]
        commands = []
        try:
            renewal = certificates.renew_certificate(domain, commands=commands, env=env)
            for command in commands:
                self._append_command_result(operation_id, command, env=env)
            nginx = service_nginx.apply(service_id, env=env)
            for command in nginx.get("commands") or []:
                self._append_command_result(operation_id, command, env=env)
            operations.append_output(
                operation_id,
                nginx.get("message") or "nginx status updated",
                stream="system" if nginx.get("status") in {"ok", "skipped"} else "stderr",
                metadata={"step": "nginx apply", "nginx": nginx},
                env=env,
            )
            if nginx.get("status") == "error":
                raise RuntimeError(nginx.get("message") or "nginx 설정을 적용할 수 없습니다.")
            refreshed = self.refresh_deploy_status(service_id, operation_id=operation_id, env=env)
            operation = operations.transition(
                operation_id,
                "succeeded",
                message=f"{domain} 무료 인증서를 갱신했습니다.",
                result_payload={"service_id": str(service_id), "domain": domain, "renewal": renewal, "nginx": nginx},
                env=env,
            )
            return {
                "operation": operation,
                "certificate": renewal.get("certificate"),
                "auto_renewal": renewal.get("auto_renewal"),
                "nginx": nginx,
                "runtime_status": refreshed.get("runtime_status"),
            }
        except Exception as exc:
            operation = operations.transition(
                operation_id,
                "failed",
                message=f"{domain} 무료 인증서를 갱신할 수 없습니다.",
                result_payload={"service_id": str(service_id), "domain": domain, "error": str(exc), "commands": commands},
                env=env,
            )
            raise ServiceError(409, "무료 인증서를 갱신할 수 없습니다.", "SERVICE_CERTBOT_RENEW_FAILED", operation=operation, error=str(exc))

    def ensure_certbot_renewal(self, payload, env=None):
        body = payload or {}
        service_id = body.get("service_id")
        domain = str(body.get("domain") or "").strip().lower()
        service, domain_row = self._certbot_domain_row(service_id, domain, require_certificate=False, env=env)
        operation = operations.create(
            "service.certbot.renewal.ensure",
            target_type="service",
            target_id=service_id,
            status="running",
            message="무료 인증서 자동 갱신 설정을 확인합니다.",
            requested_payload={"service_id": str(service_id), "domain": domain, "domain_id": str(domain_row.get("id"))},
            metadata={"service_id": str(service_id), "namespace": service.get("namespace"), "domain": domain},
            env=env,
        )
        operation_id = operation["id"]
        commands = []
        try:
            result = certificates.ensure_automatic_renewal(commands, env=env)
            for command in commands:
                self._append_command_result(operation_id, command, env=env)
            if result.get("status") != "ok":
                raise RuntimeError(result.get("stderr") or result.get("stdout") or "certbot 자동 갱신 설정에 실패했습니다.")
            status = certificates.automatic_renewal_status(env=env)
            operation = operations.transition(
                operation_id,
                "succeeded",
                message="무료 인증서 자동 갱신 설정을 확인했습니다.",
                result_payload={"service_id": str(service_id), "domain": domain, "auto_renewal": status},
                env=env,
            )
            return {"operation": operation, "auto_renewal": status}
        except Exception as exc:
            operation = operations.transition(
                operation_id,
                "failed",
                message="무료 인증서 자동 갱신 설정을 완료할 수 없습니다.",
                result_payload={"service_id": str(service_id), "domain": domain, "error": str(exc), "commands": commands},
                env=env,
            )
            raise ServiceError(409, "무료 인증서 자동 갱신 설정을 완료할 수 없습니다.", "SERVICE_CERTBOT_RENEWAL_ENSURE_FAILED", operation=operation, error=str(exc))


Model = ServiceCertbotMixin
