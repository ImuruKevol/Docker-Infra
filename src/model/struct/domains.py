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

    def upload_certificate(self, zone_id, label, cert_file, key_file, test_run_id=None, env=None):
        with connect(env=env) as connection:
            with connection.cursor() as cursor:
                zone_row = self._fetch_zone(cursor, zone_id, env=env)
        certificate = webserver.store_uploaded_certificate(
            zone_id=zone_row["id"],
            domain=zone_row["domain"],
            label=label,
            cert_file=cert_file,
            key_file=key_file,
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
