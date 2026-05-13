from psycopg.types.json import Jsonb


connect = wiz.model("db/postgres").connect
config = wiz.config("docker_infra")
DomainError = wiz.model("struct/domains_shared")
cloudflare = wiz.model("struct/domains_cloudflare")
webserver = wiz.model("struct/webserver")
operations = wiz.model("struct/operations")

secret_key = cloudflare.secret_key
zone_select_sql = cloudflare.zone_select_sql
normalize_zone = cloudflare.normalize_zone
record_payload = cloudflare.record_payload

SERVICE_DNS_COMMENT = "Managed by Docker Infra"
SERVICE_DNS_RECORD_TYPES = {"A", "AAAA"}


class Domains(cloudflare):
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

    def _fetch_zone(self, cursor, zone_id, env=None):
        cursor.execute(f"{zone_select_sql()} WHERE id = %s", (secret_key(env), zone_id))
        row = cursor.fetchone()
        if row is None:
            raise DomainError(404, "도메인 설정을 찾을 수 없습니다.", "ZONE_NOT_FOUND")
        return row

    def _load_zone_cache(self, zone_row, env=None):
        with connect(env=env) as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT *
                    FROM cloudflare_dns_records
                    WHERE zone_config_id = %s
                    ORDER BY record_name ASC, record_type ASC, created_at ASC
                    """,
                    (zone_row["id"],),
                )
                records = [record_payload(row) for row in cursor.fetchall()]
        ssl_info = webserver.certificates_for_domain(zone_row["domain"], zone_id=zone_row["id"], env=env)
        return records, ssl_info

    def _service_links(self, zone_row, env=None):
        domain = str(zone_row["domain"] or "").strip().lower()
        if not domain:
            return []
        with connect(env=env) as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT
                        sd.id AS service_domain_id,
                        sd.domain,
                        sd.port,
                        sd.ssl_mode,
                        sd.metadata,
                        sd.updated_at,
                        s.id AS service_id,
                        s.name AS service_name,
                        s.namespace,
                        s.status AS service_status
                    FROM service_domains sd
                    JOIN services s ON s.id = sd.service_id
                    WHERE lower(sd.domain) = lower(%s)
                       OR lower(sd.domain) LIKE lower(%s)
                    ORDER BY sd.domain ASC, s.name ASC
                    """,
                    (domain, f"%.{domain}"),
                )
                rows = []
                for row in cursor.fetchall():
                    metadata = dict(row["metadata"] or {})
                    nginx_ssl_mode = metadata.get("nginx_ssl_mode") or row["ssl_mode"]
                    rows.append({
                        "service_domain_id": row["service_domain_id"],
                        "service_id": row["service_id"],
                        "service_name": row["service_name"],
                        "namespace": row["namespace"],
                        "service_status": row["service_status"],
                        "domain": row["domain"],
                        "port": row["port"],
                        "ssl_mode": row["ssl_mode"],
                        "nginx_ssl_mode": nginx_ssl_mode,
                        "nginx_configured": bool(metadata.get("nginx_config_path")),
                        "certificate_applied": nginx_ssl_mode in {"existing", "certbot", "self_signed"},
                        "updated_at": row["updated_at"],
                    })
                return rows

    def _find_zone_for_domain(self, cursor, domain, zone_config_id=None, env=None, service_only=True):
        domain = str(domain or "").strip().lower()
        if zone_config_id:
            try:
                return self._fetch_zone(cursor, zone_config_id, env=env)
            except DomainError:
                pass
        clause = "WHERE enabled = true AND usable_for_service = true" if service_only else ""
        cursor.execute(
            f"{zone_select_sql()} {clause} ORDER BY length(domain) DESC",
            (secret_key(env),),
        )
        for row in cursor.fetchall():
            zone_domain = str(row["domain"] or "").strip().lower()
            if domain == zone_domain or domain.endswith(f".{zone_domain}"):
                return row
        return None

    def _service_dns_record_ids(self, metadata):
        metadata = dict(metadata or {})
        values = []
        for key in ["dns_record_id", "cloudflare_record_id"]:
            if metadata.get(key):
                values.append(metadata.get(key))
        for item in metadata.get("dns_records") or []:
            if isinstance(item, dict):
                values.append(item.get("record_id") or item.get("cloudflare_record_id") or item.get("id"))
        return {str(value).strip() for value in values if str(value or "").strip()}

    def _service_dns_record_matches(self, record, expected_content="", record_ids=None):
        record_ids = record_ids or set()
        record_id = str(record.get("id") or record.get("cloudflare_record_id") or "").strip()
        if record_id and record_id in record_ids:
            return True
        record_type = str(record.get("type") or record.get("record_type") or "").strip().upper()
        if record_type not in SERVICE_DNS_RECORD_TYPES:
            return False
        comment = str(record.get("comment") or "").strip()
        if comment == SERVICE_DNS_COMMENT:
            return True
        metadata = dict(record.get("metadata") or {})
        raw = metadata.get("raw") if isinstance(metadata.get("raw"), dict) else {}
        if str(raw.get("comment") or "").strip() == SERVICE_DNS_COMMENT:
            return True
        return bool(expected_content) and str(record.get("content") or "").strip() == expected_content

    def ensure_service_dns_record(self, domain, zone_config_id=None, content=None, proxied=False, env=None):
        domain = str(domain or "").strip().lower()
        content = str(content or config.advertise_address(env) or "").strip()
        if not domain or not content:
            return {"status": "skipped", "reason": "domain_or_content_missing"}
        record_type = "AAAA" if ":" in content else "A"
        with connect(env=env) as connection:
            with connection.cursor() as cursor:
                zone = self._find_zone_for_domain(cursor, domain, zone_config_id=zone_config_id, env=env)
        if not zone:
            return {"status": "skipped", "domain": domain, "reason": "zone_not_configured"}
        if not zone.get("api_token_value"):
            return {"status": "skipped", "domain": domain, "zone": zone["domain"], "reason": "zone_token_missing"}

        records = self.cf_request(
            zone.get("api_token_value"),
            "GET",
            f"/zones/{zone['zone_id']}/dns_records",
            query={"type": record_type, "name": domain},
        )
        cf_payload = {
            "type": record_type,
            "name": domain,
            "content": content,
            "ttl": 1,
            "proxied": bool(proxied),
            "comment": SERVICE_DNS_COMMENT,
        }
        action = "created"
        record_id = ""
        if records:
            current = records[0]
            record_id = current["id"]
            action = "unchanged"
            if current.get("content") != content or bool(current.get("proxied")) != bool(proxied):
                self.cf_request(zone.get("api_token_value"), "PUT", f"/zones/{zone['zone_id']}/dns_records/{record_id}", payload=cf_payload)
                action = "updated"
        else:
            result = self.cf_request(zone.get("api_token_value"), "POST", f"/zones/{zone['zone_id']}/dns_records", payload=cf_payload)
            record_id = result.get("id") or ""
        detail = self.sync_zone(zone["id"], env=env)
        self._record_domain_operation(
            "domain.record.ensure_service",
            zone_id=zone["id"],
            payload={"domain": domain, "record_type": record_type, "content": content, "proxied": bool(proxied)},
            result={"action": action, "record_id": record_id, "zone": zone["domain"]},
            env=env,
        )
        zone_payload = dict(detail.get("zone") or {})
        zone_payload.pop("api_token_value", None)
        return {
            "status": "ok",
            "action": action,
            "domain": domain,
            "record_id": record_id,
            "record_type": record_type,
            "content": content,
            "proxied": bool(proxied),
            "zone_id": str(zone["id"]),
            "zone": zone_payload,
        }

    def delete_service_dns_records(self, service_domains, env=None):
        rows = service_domains if isinstance(service_domains, list) else [service_domains]
        expected_content = str(config.advertise_address(env) or "").strip()
        deleted = []
        skipped = []
        failures = []
        sync_zone_ids = set()

        for row in rows:
            row = dict(row or {})
            domain = str(row.get("domain") or "").strip().lower()
            metadata = dict(row.get("metadata") or {})
            if not domain:
                skipped.append({"service_domain_id": str(row.get("id") or ""), "reason": "domain_missing"})
                continue

            try:
                with connect(env=env) as connection:
                    with connection.cursor() as cursor:
                        zone = self._find_zone_for_domain(
                            cursor,
                            domain,
                            zone_config_id=metadata.get("dns_zone_id") or metadata.get("zone_id"),
                            env=env,
                            service_only=False,
                        )
                if not zone:
                    skipped.append({"domain": domain, "reason": "zone_not_configured"})
                    continue
                if not zone.get("api_token_value"):
                    skipped.append({"domain": domain, "zone": zone["domain"], "reason": "zone_token_missing"})
                    continue

                records = self.cf_request(
                    zone.get("api_token_value"),
                    "GET",
                    f"/zones/{zone['zone_id']}/dns_records",
                    query={"name": domain, "page": 1, "per_page": 100},
                )
                record_ids = self._service_dns_record_ids(metadata)
                targets = [
                    record for record in records
                    if self._service_dns_record_matches(record, expected_content=expected_content, record_ids=record_ids)
                ]
                if not targets:
                    skipped.append({"domain": domain, "zone": zone["domain"], "reason": "record_not_found"})
                    continue

                for record in targets:
                    record_id = str(record.get("id") or "").strip()
                    if not record_id:
                        continue
                    try:
                        self.cf_request(zone.get("api_token_value"), "DELETE", f"/zones/{zone['zone_id']}/dns_records/{record_id}")
                    except DomainError as exc:
                        if int(getattr(exc, "status_code", 0) or 0) != 404:
                            raise
                    deleted.append({
                        "service_domain_id": str(row.get("id") or ""),
                        "domain": domain,
                        "zone_id": str(zone["id"]),
                        "zone": zone["domain"],
                        "record_id": record_id,
                        "record_type": record.get("type"),
                        "content": record.get("content"),
                    })
                    sync_zone_ids.add(str(zone["id"]))
            except DomainError as exc:
                failures.append({
                    "domain": domain,
                    "message": exc.message,
                    "error_code": exc.error_code,
                    **exc.extra,
                })

        sync_errors = []
        for zone_id in sorted(sync_zone_ids):
            try:
                self.sync_zone(zone_id, env=env)
            except DomainError as exc:
                sync_errors.append({"zone_id": zone_id, "message": exc.message, "error_code": exc.error_code})

        result = {"deleted": deleted, "skipped": skipped, "sync_errors": sync_errors}
        if failures:
            result["failures"] = failures
        self._record_domain_operation(
            "domain.record.delete_service",
            payload={"domains": [str((row or {}).get("domain") or "") for row in rows]},
            result=result,
            status="failed" if failures else "succeeded",
            env=env,
        )
        if failures:
            raise DomainError(
                409,
                "서비스 DNS 레코드를 삭제할 수 없습니다.",
                "SERVICE_DNS_RECORD_DELETE_FAILED",
                **result,
            )
        return {"status": "ok", **result}

    def load(self, env=None):
        with connect(env=env) as connection:
            with connection.cursor() as cursor:
                cursor.execute(f"{zone_select_sql()} ORDER BY domain ASC", (secret_key(env),))
                zones = [normalize_zone(row) for row in cursor.fetchall()]
        return {
            "zones": zones,
            "summary": {
                "zone_count": len(zones),
                "active_zone_count": len([zone for zone in zones if zone["status"] == "active"]),
                "record_count": sum(int(zone.get("record_count") or 0) for zone in zones),
            },
        }

    def detail(self, zone_id, env=None):
        with connect(env=env) as connection:
            with connection.cursor() as cursor:
                zone_row = self._fetch_zone(cursor, zone_id, env=env)
        records, ssl_info = self._load_zone_cache(zone_row, env=env)
        return {
            "zone": normalize_zone(zone_row),
            "records": records,
            "ssl_certificates": ssl_info["certificates"],
            "ssl_summary": ssl_info["summary"],
            "service_links": self._service_links(zone_row, env=env),
        }

    def save_zone(self, payload, test_run_id=None, env=None):
        payload = dict(payload or {})
        domain = str(payload.get("domain") or "").strip().lower()
        zone_id = str(payload.get("zone_id") or "").strip()
        enabled = bool(payload.get("enabled"))
        usable_for_service = bool(payload.get("usable_for_service", True))
        api_token_value = payload.get("api_token_value")
        record_id = payload.get("id")
        if domain == "":
            raise DomainError(400, "도메인 이름을 입력해주세요.", "ZONE_DOMAIN_REQUIRED")
        if zone_id == "":
            raise DomainError(400, "Zone ID를 입력해주세요.", "ZONE_ID_REQUIRED")
        try:
            with connect(env=env) as connection:
                with connection.cursor() as cursor:
                    if record_id:
                        self._fetch_zone(cursor, record_id, env=env)
                        set_parts = ["domain = %s", "zone_id = %s", "enabled = %s", "usable_for_service = %s", "test_run_id = %s", "metadata = %s"]
                        params = [domain, zone_id, enabled, usable_for_service, test_run_id, Jsonb({"source": "domains"})]
                        if str(api_token_value or "").strip() != "":
                            set_parts.append("api_token_enc = encode(pgp_sym_encrypt(%s, %s), 'base64')")
                            params.extend([api_token_value, secret_key(env)])
                        params.append(record_id)
                        cursor.execute(f"UPDATE cloudflare_zones SET {', '.join(set_parts)} WHERE id = %s", params)
                    else:
                        if str(api_token_value or "").strip() != "":
                            cursor.execute(
                                """
                                INSERT INTO cloudflare_zones(domain, zone_id, api_token_enc, usable_for_service, enabled, test_run_id, metadata)
                                VALUES (%s, %s, encode(pgp_sym_encrypt(%s, %s), 'base64'), %s, %s, %s, %s)
                                RETURNING id
                                """,
                                (domain, zone_id, api_token_value, secret_key(env), usable_for_service, enabled, test_run_id, Jsonb({"source": "domains"})),
                            )
                        else:
                            cursor.execute(
                                """
                                INSERT INTO cloudflare_zones(domain, zone_id, usable_for_service, enabled, test_run_id, metadata)
                                VALUES (%s, %s, %s, %s, %s, %s)
                                RETURNING id
                                """,
                                (domain, zone_id, usable_for_service, enabled, test_run_id, Jsonb({"source": "domains"})),
                            )
                        record_id = str(cursor.fetchone()["id"])
        except Exception as exc:
            if "duplicate key value" in str(exc):
                raise DomainError(409, "이미 등록된 도메인입니다.", "ZONE_DOMAIN_DUPLICATED")
            raise
        zone = self.detail(record_id, env=env)["zone"]
        self._record_domain_operation(
            "domain.zone.save",
            zone_id=record_id,
            payload={"domain": domain, "enabled": enabled, "usable_for_service": usable_for_service},
            result={"zone_id": zone.get("id"), "domain": zone.get("domain")},
            env=env,
        )
        return zone

    def delete_zone(self, zone_id, env=None):
        with connect(env=env) as connection:
            with connection.cursor() as cursor:
                zone = self._fetch_zone(cursor, zone_id, env=env)
                cursor.execute("DELETE FROM cloudflare_zones WHERE id = %s", (zone_id,))
        self._record_domain_operation(
            "domain.zone.delete",
            zone_id=zone_id,
            payload={"zone_id": zone_id},
            result={"deleted": True, "domain": zone.get("domain")},
            env=env,
        )
        return {"deleted": True, "id": zone_id}

    def upload_certificate(self, zone_id, label, cert_file, key_file, chain_file=None, test_run_id=None, env=None):
        with connect(env=env) as connection:
            with connection.cursor() as cursor:
                zone_row = self._fetch_zone(cursor, zone_id, env=env)
        certificate = webserver.store_uploaded_certificate(
            zone_id=zone_row["id"],
            domain=zone_row["domain"],
            label=label,
            cert_file=cert_file,
            key_file=key_file,
            chain_file=chain_file,
            test_run_id=test_run_id,
            env=env,
        )
        self._record_domain_operation(
            "domain.certificate.upload",
            zone_id=zone_row["id"],
            payload={"zone_id": zone_row["id"], "label": label},
            result={"certificate_id": certificate.get("id"), "domain": zone_row["domain"]},
            env=env,
        )
        return {**self.detail(zone_row["id"], env=env), "certificate": certificate}

    def delete_certificate(self, zone_id, certificate_id, test_run_id=None, env=None):
        with connect(env=env) as connection:
            with connection.cursor() as cursor:
                zone_row = self._fetch_zone(cursor, zone_id, env=env)
        webserver.delete_certificate(certificate_id, zone_id=zone_row["id"], test_run_id=test_run_id, env=env)
        self._record_domain_operation(
            "domain.certificate.delete",
            zone_id=zone_row["id"],
            payload={"zone_id": zone_row["id"], "certificate_id": certificate_id},
            result={"deleted": True, "domain": zone_row["domain"]},
            env=env,
        )
        return self.detail(zone_row["id"], env=env)


Model = Domains()
