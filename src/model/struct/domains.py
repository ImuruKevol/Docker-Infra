DomainError = wiz.model("struct/domains_shared")
ddns = wiz.model("struct/domains_ddns")
operations = wiz.model("struct/operations")


REMOVED_ERROR_CODE = "DIRECT_DOMAIN_MANAGEMENT_REMOVED"


class Domains:
    DomainError = DomainError

    def _record_domain_operation(self, operation_type, zone_id=None, payload=None, result=None, status="succeeded", env=None):
        return operations.create(
            operation_type,
            target_type="domain",
            target_id=zone_id,
            status=status,
            message=f"{operation_type} {status}",
            requested_payload=payload or {},
            result_payload=result or {},
            env=env,
        )

    def _removed(self, message):
        raise DomainError(410, message, REMOVED_ERROR_CODE)

    def load(self, env=None):
        return {
            "zones": [],
            "summary": {
                "zone_count": 0,
                "active_zone_count": 0,
                "record_count": 0,
            },
        }

    def service_options(self, env=None):
        return {"zones": ddns.service_zone_options(env=env)}

    def ensure_service_dns_record(self, domain, zone_config_id=None, content=None, proxied=False, env=None):
        domain = str(domain or "").strip().lower()
        if not domain:
            return {"status": "skipped", "reason": "domain_missing"}
        self._record_domain_operation(
            "domain.record.ensure_service",
            payload={"domain": domain, "zone_config_id": zone_config_id},
            result={"status": "skipped", "reason": "ddns_only"},
            env=env,
        )
        return {
            "status": "skipped",
            "domain": domain,
            "reason": "ddns_only",
            "message": "DDNS 도메인만 자동 등록합니다.",
        }

    def delete_service_dns_records(self, service_domains, env=None):
        rows = service_domains if isinstance(service_domains, list) else [service_domains]
        skipped = []
        for row in rows:
            row = dict(row or {})
            domain = str(row.get("domain") or "").strip().lower()
            metadata = dict(row.get("metadata") or {})
            if not domain:
                skipped.append({"service_domain_id": str(row.get("id") or ""), "reason": "domain_missing"})
                continue
            if metadata.get("dns_provider") == "ddns" or metadata.get("ddns_endpoint_id"):
                skipped.append({"domain": domain, "reason": "ddns_managed"})
                continue
            skipped.append({"domain": domain, "reason": "ddns_only"})
        result = {"deleted": [], "skipped": skipped, "sync_errors": []}
        self._record_domain_operation(
            "domain.record.delete_service",
            payload={"domains": [str((row or {}).get("domain") or "") for row in rows]},
            result=result,
            env=env,
        )
        return {"status": "ok", **result}

    def detail(self, zone_id, env=None):
        self._removed("외부 DNS API 기반 도메인 상세 조회는 제거되었습니다.")

    def sync_zone(self, zone_id, env=None):
        self._removed("외부 DNS API 기반 도메인 동기화는 제거되었습니다.")

    def sync_all(self, env=None):
        return {"synced": [], "failed": []}

    def save_zone(self, payload, test_run_id=None, env=None):
        self._removed("외부 DNS API 기반 도메인 설정 저장은 제거되었습니다. DDNS 관리 서버를 등록해주세요.")

    def delete_zone(self, zone_id, env=None):
        self._removed("외부 DNS API 기반 도메인 설정 삭제는 제거되었습니다. DDNS 관리 서버만 관리할 수 있습니다.")

    def save_record(self, zone_id, payload, env=None):
        self._removed("외부 DNS API 기반 DNS 레코드 관리는 제거되었습니다.")

    def delete_record(self, zone_id, record_id, env=None):
        self._removed("외부 DNS API 기반 DNS 레코드 관리는 제거되었습니다.")

    def upload_certificate(self, zone_id, label, cert_file, key_file, chain_file=None, test_run_id=None, env=None):
        self._removed("도메인 관리 화면의 직접 인증서 업로드는 제거되었습니다. 서비스 배포의 DDNS/certbot 흐름을 사용해주세요.")

    def delete_certificate(self, zone_id, certificate_id, test_run_id=None, env=None):
        self._removed("도메인 관리 화면의 직접 인증서 삭제는 제거되었습니다.")


Model = Domains()
