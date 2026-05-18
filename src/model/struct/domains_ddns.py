import datetime
import decimal
import json
import ssl
import uuid
from urllib import error as urlerror, parse as urlparse, request as urlrequest

from psycopg.types.json import Jsonb


connect = wiz.model("db/postgres").connect
config = wiz.config("docker_infra")
DomainError = wiz.model("struct/domains_shared")
operations = wiz.model("struct/operations")

PROVIDER = "ddns"
PROVIDER_LABEL = "DDNS"
DEFAULT_REGISTRATION_PATH = "/api/ddns/records"


def serialize(value):
    if isinstance(value, (datetime.datetime, datetime.date)):
        return value.isoformat()
    if isinstance(value, uuid.UUID):
        return str(value)
    if isinstance(value, decimal.Decimal):
        return float(value)
    if isinstance(value, list):
        return [serialize(item) for item in value]
    if isinstance(value, dict):
        return {key: serialize(item) for key, item in value.items()}
    return value


def secret_key(env=None):
    return config.secret_key(env)


def _normalize_suffix(value):
    return str(value or "").strip().lower().lstrip("*.").strip(".")


def _matches_suffix(domain, suffix):
    domain = str(domain or "").strip().lower().strip(".")
    suffix = _normalize_suffix(suffix)
    return bool(domain and suffix and (domain == suffix or domain.endswith(f".{suffix}")))


def _path(value, fallback=""):
    path = str(value or "").strip() or fallback
    if path and not path.startswith("/"):
        path = f"/{path}"
    return path


def _url(value):
    url = str(value or "").strip().rstrip("/")
    parsed = urlparse.urlparse(url)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise DomainError(400, "DDNS 관리 서버 API URL을 http 또는 https URL로 입력해주세요.", "DDNS_API_URL_INVALID")
    return url


def _api_endpoint(value):
    url = _url(value)
    parsed = urlparse.urlparse(url)
    if parsed.params or parsed.query or parsed.fragment:
        raise DomainError(400, "DDNS 서버 API URL은 query string 없이 path까지만 입력해주세요.", "DDNS_API_URL_INVALID")
    base_url = f"{parsed.scheme}://{parsed.netloc}".rstrip("/")
    return base_url, _path(parsed.path, DEFAULT_REGISTRATION_PATH)


def empty_payload(available=True, message="", error_code=""):
    payload = {
        "endpoints": [],
        "summary": {
            "endpoint_count": 0,
            "enabled_endpoint_count": 0,
            "registration_count": 0,
        },
        "available": bool(available),
    }
    if message:
        payload["message"] = message
    if error_code:
        payload["error_code"] = error_code
    return payload


def schema_pending_payload():
    return empty_payload(
        available=False,
        message="DDNS 관리 서버 테이블이 아직 준비되지 않았습니다. DB 마이그레이션을 적용해주세요.",
        error_code="DDNS_SCHEMA_PENDING",
    )


def _schema_ready(cursor):
    cursor.execute(
        """
        SELECT
            to_regclass('ddns_endpoints') AS endpoints_table,
            to_regclass('ddns_registrations') AS registrations_table
        """
    )
    row = cursor.fetchone() or {}
    return bool(row.get("endpoints_table") and row.get("registrations_table"))


def endpoint_select_sql():
    return """
    SELECT
        id,
        name,
        domain_suffix,
        COALESCE(api_base_url, '') AS api_base_url,
        COALESCE(registration_path, '') AS registration_path,
        health_path,
        enabled,
        tls_verify,
        last_check_at,
        last_check_status,
        last_check_message,
        test_run_id,
        metadata,
        created_at,
        updated_at,
        CASE
            WHEN token_enc IS NOT NULL
                THEN pgp_sym_decrypt(decode(token_enc, 'base64'), %s)
            ELSE NULL
        END AS token_value
    FROM ddns_endpoints
    """


def endpoint_status(row):
    if not row.get("enabled"):
        return "disabled"
    if row.get("last_check_status") == "error":
        return "error"
    return "active"


def normalize_endpoint(row, registration_count=0):
    item = serialize(dict(row))
    item.pop("token_value", None)
    api_base_url = str(item.get("api_base_url") or "").rstrip("/")
    registration_path = _path(item.get("registration_path"), DEFAULT_REGISTRATION_PATH)
    metadata = dict(item.get("metadata") or {})
    metadata["mode"] = metadata.get("mode") or "ddns_management"
    item["metadata"] = metadata
    item["api_url"] = f"{api_base_url}{registration_path}" if api_base_url else ""
    item["secret_configured"] = bool(row.get("token_value"))
    item["enabled"] = bool(row.get("enabled"))
    item["tls_verify"] = bool(row.get("tls_verify"))
    item["registration_count"] = int(registration_count or 0)
    item["provider"] = PROVIDER
    item["provider_label"] = PROVIDER_LABEL
    item["mode"] = "ddns_management"
    item["status"] = endpoint_status(row)
    return item


def _safe_json_loads(value):
    try:
        return json.loads(value or "{}")
    except Exception:
        return {"raw": value or ""}


def _request(endpoint, method, path, payload=None, timeout=15, query=None):
    base_url = str(endpoint.get("api_base_url") or "").rstrip("/")
    if not base_url:
        raise DomainError(400, "DDNS 서버 API URL이 필요합니다.", "DDNS_API_URL_REQUIRED")
    suffix = "" if not query else "?" + urlparse.urlencode(query, doseq=True)
    url = f"{base_url}{_path(path, DEFAULT_REGISTRATION_PATH)}{suffix}"
    headers = {"Accept": "application/json"}
    token = str(endpoint.get("token_value") or "").strip()
    if token:
        headers["Authorization"] = f"Bearer {token}"
    data = None
    if payload is not None:
        headers["Content-Type"] = "application/json"
        data = json.dumps(payload).encode("utf-8")
    context = None
    if endpoint.get("tls_verify") is False:
        context = ssl._create_unverified_context()
    request = urlrequest.Request(url, headers=headers, data=data, method=method.upper())
    try:
        with urlrequest.urlopen(request, timeout=timeout, context=context) as response:
            body = response.read().decode("utf-8", errors="ignore")
            parsed = _safe_json_loads(body)
            return {"status_code": response.status, "body": parsed, "raw_body": body}
    except urlerror.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="ignore")
        parsed = _safe_json_loads(body)
        message = parsed.get("message") or parsed.get("error") or body or str(exc)
        raise DomainError(exc.code, message, "DDNS_API_FAILED", response=parsed)
    except urlerror.URLError as exc:
        raise DomainError(502, str(exc.reason), "DDNS_API_FAILED")


class DomainDdns:
    DomainError = DomainError

    def _record_operation(self, operation_type, payload=None, result=None, status="succeeded", env=None):
        return operations.create(
            operation_type,
            target_type="domain",
            status=status,
            message=f"{operation_type} {status}",
            requested_payload=payload or {},
            result_payload=result or {},
            env=env,
        )

    def _require_schema(self, cursor):
        if not _schema_ready(cursor):
            raise DomainError(
                503,
                "DDNS 관리 서버 테이블이 아직 준비되지 않았습니다. DB 마이그레이션을 적용해주세요.",
                "DDNS_SCHEMA_PENDING",
            )

    def _fetch_endpoint(self, cursor, endpoint_id, env=None):
        self._require_schema(cursor)
        cursor.execute(f"{endpoint_select_sql()} WHERE id = %s", (secret_key(env), endpoint_id))
        row = cursor.fetchone()
        if row is None:
            raise DomainError(404, "DDNS 관리 서버 설정을 찾을 수 없습니다.", "DDNS_ENDPOINT_NOT_FOUND")
        return row

    def _registration_counts(self, endpoint_ids, env=None):
        if not endpoint_ids:
            return {}
        with connect(env=env) as connection:
            with connection.cursor() as cursor:
                if not _schema_ready(cursor):
                    return {}
                cursor.execute(
                    """
                    SELECT endpoint_id, count(*) AS count
                    FROM ddns_registrations
                    WHERE endpoint_id = ANY(%s)
                    GROUP BY endpoint_id
                    """,
                    (endpoint_ids,),
                )
                return {str(row["endpoint_id"]): int(row["count"]) for row in cursor.fetchall()}

    def load(self, env=None):
        with connect(env=env) as connection:
            with connection.cursor() as cursor:
                if not _schema_ready(cursor):
                    return schema_pending_payload()
                cursor.execute(f"{endpoint_select_sql()} ORDER BY domain_suffix ASC", (secret_key(env),))
                rows = [dict(row) for row in cursor.fetchall()]
        counts = self._registration_counts([row["id"] for row in rows], env=env)
        endpoints = [normalize_endpoint(row, counts.get(str(row["id"]), 0)) for row in rows]
        return {
            "endpoints": endpoints,
            "summary": {
                "endpoint_count": len(endpoints),
                "enabled_endpoint_count": len([item for item in endpoints if item.get("enabled")]),
                "registration_count": sum(int(item.get("registration_count") or 0) for item in endpoints),
            },
            "available": True,
        }

    def detail(self, endpoint_id, env=None):
        with connect(env=env) as connection:
            with connection.cursor() as cursor:
                endpoint = self._fetch_endpoint(cursor, endpoint_id, env=env)
                cursor.execute(
                    """
                    SELECT
                        dr.*,
                        s.name AS service_name,
                        s.namespace AS service_namespace
                    FROM ddns_registrations dr
                    LEFT JOIN services s ON s.id = dr.service_id
                    WHERE dr.endpoint_id = %s
                    ORDER BY dr.domain ASC
                    """,
                    (endpoint_id,),
                )
                registrations = [serialize(dict(row)) for row in cursor.fetchall()]
        return {
            "endpoint": normalize_endpoint(endpoint, len(registrations)),
            "registrations": registrations,
        }

    def service_zone_options(self, env=None):
        options = []
        for endpoint in self.load(env=env).get("endpoints", []):
            if endpoint.get("enabled") is not True:
                continue
            options.append({
                "id": endpoint["id"],
                "domain": endpoint["domain_suffix"],
                "zone_id": "",
                "provider": PROVIDER,
                "provider_label": PROVIDER_LABEL,
                "mode": "ddns_management",
                "enabled": True,
                "usable_for_service": True,
                "record_count": endpoint.get("registration_count") or 0,
                "secret_configured": endpoint.get("secret_configured"),
                "status": endpoint.get("status"),
                "last_sync_at": endpoint.get("last_check_at"),
                "last_sync_message": endpoint.get("last_check_message"),
                "certificate_summary": {"edge": 1},
            })
        return options

    def save_endpoint(self, payload, test_run_id=None, env=None):
        payload = dict(payload or {})
        endpoint_id = str(payload.get("id") or "").strip()
        domain_suffix = _normalize_suffix(payload.get("domain_suffix") or payload.get("domain"))
        name = str(payload.get("name") or domain_suffix).strip()
        api_url = payload.get("api_url") or payload.get("ddns_api_url")
        if str(api_url or "").strip():
            api_base_url, registration_path = _api_endpoint(api_url)
        else:
            api_base_url = _url(payload.get("api_base_url"))
            registration_path = _path(payload.get("registration_path"), DEFAULT_REGISTRATION_PATH)
        health_path = None
        enabled = True
        tls_verify = payload.get("tls_verify") is not False
        token_value = payload.get("token_value") or payload.get("api_token_value")

        if not domain_suffix or "." not in domain_suffix:
            raise DomainError(400, "DDNS wildcard suffix를 입력해주세요.", "DDNS_DOMAIN_SUFFIX_REQUIRED")
        if not name:
            raise DomainError(400, "DDNS 관리 서버 이름을 입력해주세요.", "DDNS_NAME_REQUIRED")

        metadata = {"source": "domains_ddns", "mode": "ddns_management"}
        try:
            with connect(env=env) as connection:
                with connection.cursor() as cursor:
                    self._require_schema(cursor)
                    if endpoint_id:
                        current = self._fetch_endpoint(cursor, endpoint_id, env=env)
                        if not str(token_value or "").strip() and not current.get("token_value"):
                            raise DomainError(400, "DDNS 관리 서버 API Token을 입력해주세요.", "DDNS_TOKEN_REQUIRED")
                        set_parts = [
                            "name = %s",
                            "domain_suffix = %s",
                            "api_base_url = %s",
                            "registration_path = %s",
                            "health_path = %s",
                            "enabled = %s",
                            "tls_verify = %s",
                            "test_run_id = %s",
                            "metadata = %s",
                            "updated_at = now()",
                        ]
                        params = [name, domain_suffix, api_base_url, registration_path, health_path or None, enabled, tls_verify, test_run_id, Jsonb(metadata)]
                        if str(token_value or "").strip():
                            set_parts.append("token_enc = encode(pgp_sym_encrypt(%s, %s), 'base64')")
                            params.extend([token_value, secret_key(env)])
                        params.append(endpoint_id)
                        cursor.execute(f"UPDATE ddns_endpoints SET {', '.join(set_parts)} WHERE id = %s", params)
                    else:
                        if not str(token_value or "").strip():
                            raise DomainError(400, "DDNS 관리 서버 API Token을 입력해주세요.", "DDNS_TOKEN_REQUIRED")
                        cursor.execute(
                            """
                            INSERT INTO ddns_endpoints(
                                name, domain_suffix, api_base_url, registration_path, health_path,
                                token_enc, enabled, tls_verify, test_run_id, metadata
                            )
                            VALUES (%s, %s, %s, %s, %s, encode(pgp_sym_encrypt(%s, %s), 'base64'), %s, %s, %s, %s)
                            RETURNING id
                            """,
                            (name, domain_suffix, api_base_url, registration_path, health_path or None, token_value, secret_key(env), enabled, tls_verify, test_run_id, Jsonb(metadata)),
                        )
                        endpoint_id = str(cursor.fetchone()["id"])
        except Exception as exc:
            if "duplicate key value" in str(exc):
                raise DomainError(409, "이미 등록된 DDNS wildcard suffix입니다.", "DDNS_DOMAIN_SUFFIX_DUPLICATED")
            raise

        detail = self.detail(endpoint_id, env=env)
        self._record_operation(
            "domain.ddns.endpoint.save",
            payload={"domain_suffix": domain_suffix, "api_url": f"{api_base_url}{registration_path}"},
            result={"endpoint_id": endpoint_id, "domain_suffix": domain_suffix},
            env=env,
        )
        return detail["endpoint"]

    def delete_endpoint(self, endpoint_id, env=None):
        with connect(env=env) as connection:
            with connection.cursor() as cursor:
                endpoint = self._fetch_endpoint(cursor, endpoint_id, env=env)
                cursor.execute("DELETE FROM ddns_endpoints WHERE id = %s", (endpoint_id,))
        self._record_operation(
            "domain.ddns.endpoint.delete",
            payload={"endpoint_id": endpoint_id},
            result={"deleted": True, "domain_suffix": endpoint.get("domain_suffix")},
            env=env,
        )
        return {"deleted": True, "id": endpoint_id}

    def match_domain(self, domain, endpoint_id=None, enabled_only=True, env=None):
        domain = str(domain or "").strip().lower().strip(".")
        if not domain:
            return None
        with connect(env=env) as connection:
            with connection.cursor() as cursor:
                if not _schema_ready(cursor):
                    return None
                if endpoint_id:
                    try:
                        endpoint = self._fetch_endpoint(cursor, endpoint_id, env=env)
                    except DomainError:
                        return None
                    if (enabled_only and endpoint.get("enabled") is not True) or not _matches_suffix(domain, endpoint.get("domain_suffix")):
                        return None
                    return dict(endpoint)
                clause = "WHERE enabled = true" if enabled_only else ""
                cursor.execute(f"{endpoint_select_sql()} {clause} ORDER BY length(domain_suffix) DESC", (secret_key(env),))
                for row in cursor.fetchall():
                    if _matches_suffix(domain, row.get("domain_suffix")):
                        return dict(row)
        return None

    def is_ddns_domain(self, domain, metadata=None, env=None):
        metadata = dict(metadata or {})
        endpoint_id = metadata.get("ddns_endpoint_id")
        return self.match_domain(domain, endpoint_id=endpoint_id, env=env) is not None

    def _service(self, cursor, service_id):
        cursor.execute("SELECT * FROM services WHERE id = %s", (service_id,))
        row = cursor.fetchone()
        return dict(row) if row else None

    def _domain_rows(self, service_id, env=None):
        with connect(env=env) as connection:
            with connection.cursor() as cursor:
                service = self._service(cursor, service_id)
                cursor.execute("SELECT * FROM service_domains WHERE service_id = %s ORDER BY created_at ASC", (service_id,))
                domains = [dict(row) for row in cursor.fetchall()]
        return service, domains

    def _registration_target(self, domain_row, env=None):
        metadata = dict(domain_row.get("metadata") or {})
        target_host = str(metadata.get("ddns_target_host") or config.advertise_address(env) or "").strip()
        if not target_host:
            target_host = str(metadata.get("proxy_host") or "").strip()
        if not target_host:
            raise DomainError(400, "DDNS에 등록할 IP 주소를 확인할 수 없습니다.", "DDNS_TARGET_IP_REQUIRED")
        record_type = "AAAA" if ":" in target_host else "A"
        return {"host": target_host, "record_type": record_type, "port": int(metadata.get("published_port") or domain_row.get("port") or metadata.get("target_port") or 80)}

    def _relative_subdomain(self, domain, suffix):
        domain = str(domain or "").strip().lower().strip(".")
        suffix = _normalize_suffix(suffix)
        if domain == suffix:
            return "@"
        if domain.endswith(f".{suffix}"):
            return domain[: -(len(suffix) + 1)]
        return domain

    def _register_payload(self, service, endpoint, domain_row, target):
        metadata = dict(domain_row.get("metadata") or {})
        domain = str(domain_row.get("domain") or "").strip().lower()
        return {
            "domain": domain,
            "subdomain": self._relative_subdomain(domain, endpoint.get("domain_suffix")),
            "wildcard_suffix": endpoint.get("domain_suffix"),
            "ip": target["host"],
            "record_type": target["record_type"],
            "ttl": metadata.get("dns_ttl") or 60,
            "proxied": metadata.get("dns_proxied") is True,
            "source": "docker-infra",
            "service": {
                "id": str((service or {}).get("id") or ""),
                "namespace": (service or {}).get("namespace"),
                "name": (service or {}).get("name"),
                "stack_name": (service or {}).get("stack_name"),
            },
            "service_domain_id": str(domain_row.get("id") or ""),
            "metadata": {
                "compose_service": metadata.get("compose_service"),
                "target_port": metadata.get("target_port") or domain_row.get("port"),
                "published_port": target["port"],
                "proxy_node_name": metadata.get("proxy_node_name"),
                "proxy_node_registered": metadata.get("proxy_node_registered"),
            },
        }

    def _upsert_registration(self, cursor, endpoint, service, domain_row, target, status, message="", remote_record_id="", response=None):
        metadata = dict(domain_row.get("metadata") or {})
        registration_metadata = {
            "response": response or {},
            "service_namespace": (service or {}).get("namespace"),
            "service_name": (service or {}).get("name"),
            "compose_service": metadata.get("compose_service"),
            "record_type": target["record_type"],
        }
        cursor.execute(
            """
            INSERT INTO ddns_registrations(
                endpoint_id, service_id, service_domain_id, domain, target_scheme, target_host,
                target_port, remote_record_id, status, last_sync_at, last_sync_message, test_run_id, metadata
            )
            VALUES (%s, %s, %s, %s, 'dns', %s, %s, %s, %s, now(), %s, %s, %s)
            ON CONFLICT (endpoint_id, domain)
            DO UPDATE SET
                service_id = EXCLUDED.service_id,
                service_domain_id = EXCLUDED.service_domain_id,
                target_scheme = EXCLUDED.target_scheme,
                target_host = EXCLUDED.target_host,
                target_port = EXCLUDED.target_port,
                remote_record_id = EXCLUDED.remote_record_id,
                status = EXCLUDED.status,
                last_sync_at = now(),
                last_sync_message = EXCLUDED.last_sync_message,
                test_run_id = EXCLUDED.test_run_id,
                metadata = EXCLUDED.metadata,
                updated_at = now()
            RETURNING *
            """,
            (
                endpoint["id"],
                (service or {}).get("id"),
                domain_row.get("id"),
                domain_row.get("domain"),
                target["host"],
                target["port"],
                remote_record_id or None,
                status,
                message,
                domain_row.get("test_run_id"),
                Jsonb(registration_metadata),
            ),
        )
        return serialize(dict(cursor.fetchone()))

    def _mark_service_domain(self, cursor, domain_row, endpoint, registration, target):
        metadata = dict(domain_row.get("metadata") or {})
        metadata.update({
            "routing_provider": "nginx",
            "dns_provider": PROVIDER,
            "ddns_endpoint_id": str(endpoint["id"]),
            "ddns_domain_suffix": endpoint.get("domain_suffix"),
            "ddns_registration_id": registration.get("id"),
            "ddns_remote_record_id": registration.get("remote_record_id") or "",
            "ddns_status": registration.get("status"),
            "ddns_last_sync_at": registration.get("last_sync_at"),
            "ddns_target_host": target["host"],
            "ddns_record_type": target["record_type"],
        })
        cursor.execute("UPDATE service_domains SET metadata = %s, updated_at = now() WHERE id = %s", (Jsonb(metadata), domain_row["id"]))

    def register_service_domains(self, service_id, domain_rows=None, env=None):
        service, domains = self._domain_rows(service_id, env=env)
        domains = domain_rows if domain_rows is not None else domains
        if not domains:
            return {"status": "skipped", "registered": [], "skipped": [], "failures": []}

        registered = []
        skipped = []
        failures = []

        for domain_row in domains:
            domain_row = dict(domain_row or {})
            domain = str(domain_row.get("domain") or "").strip().lower()
            metadata = dict(domain_row.get("metadata") or {})
            endpoint = self.match_domain(domain, endpoint_id=metadata.get("ddns_endpoint_id"), env=env)
            if endpoint is None:
                skipped.append({"domain": domain, "reason": "ddns_endpoint_not_matched"})
                continue
            target = self._registration_target(domain_row, env=env)
            request_payload = self._register_payload(service, endpoint, domain_row, target)
            try:
                response = _request(endpoint, "POST", endpoint.get("registration_path") or DEFAULT_REGISTRATION_PATH, payload=request_payload)
                body = response.get("body") or {}
                if body.get("success") is False:
                    raise DomainError(502, body.get("message") or "DDNS DNS 레코드 등록에 실패했습니다.", "DDNS_API_FAILED", response=body)
                remote_record_id = str(body.get("id") or body.get("record_id") or body.get("registration_id") or "").strip()
                with connect(env=env) as connection:
                    with connection.cursor() as cursor:
                        registration = self._upsert_registration(
                            cursor,
                            endpoint,
                            service,
                            domain_row,
                            target,
                            "registered",
                            body.get("message") or "registered",
                            remote_record_id=remote_record_id,
                            response=body,
                        )
                        self._mark_service_domain(cursor, domain_row, endpoint, registration, target)
                registered.append({
                    "domain": domain,
                    "endpoint_id": str(endpoint["id"]),
                    "endpoint": endpoint.get("domain_suffix"),
                    "target": target,
                    "registration": registration,
                })
            except DomainError as exc:
                failure = {"domain": domain, "message": exc.message, "error_code": exc.error_code, **exc.extra}
                failures.append(failure)
                with connect(env=env) as connection:
                    with connection.cursor() as cursor:
                        registration = self._upsert_registration(
                            cursor,
                            endpoint,
                            service,
                            domain_row,
                            target,
                            "failed",
                            exc.message,
                            response=exc.extra,
                        )
                        self._mark_service_domain(cursor, domain_row, endpoint, registration, target)

        result = {"registered": registered, "skipped": skipped, "failures": failures}
        self._record_operation(
            "domain.ddns.register_service",
            payload={"service_id": str(service_id)},
            result=result,
            status="failed" if failures else "succeeded",
            env=env,
        )
        if failures:
            raise DomainError(409, "DDNS 관리 서버에 DNS 레코드를 등록할 수 없습니다.", "DDNS_SERVICE_REGISTER_FAILED", **result)
        return {"status": "ok" if registered else "skipped", **result}

    def unregister_service_domains(self, service_domains, env=None):
        rows = service_domains if isinstance(service_domains, list) else [service_domains]
        unregistered = []
        skipped = []
        failures = []

        for row in rows:
            domain_row = dict(row or {})
            domain = str(domain_row.get("domain") or "").strip().lower()
            metadata = dict(domain_row.get("metadata") or {})
            endpoint = self.match_domain(domain, endpoint_id=metadata.get("ddns_endpoint_id"), enabled_only=False, env=env)
            if endpoint is None:
                skipped.append({"domain": domain, "reason": "ddns_endpoint_not_matched"})
                continue
            try:
                remote_id = str(metadata.get("ddns_remote_record_id") or "").strip()
                target = remote_id or domain
                delete_path = f"{(endpoint.get('registration_path') or DEFAULT_REGISTRATION_PATH).rstrip('/')}/{urlparse.quote(target, safe='')}"
                response = _request(endpoint, "DELETE", delete_path)
                body = response.get("body") or {}
                if body.get("success") is False:
                    raise DomainError(502, body.get("message") or "DDNS DNS 레코드 삭제에 실패했습니다.", "DDNS_API_FAILED", response=body)
                unregistered.append({"domain": domain, "endpoint_id": str(endpoint["id"]), "response": body})
                with connect(env=env) as connection:
                    with connection.cursor() as cursor:
                        cursor.execute("DELETE FROM ddns_registrations WHERE endpoint_id = %s AND domain = %s", (endpoint["id"], domain))
            except DomainError as exc:
                failures.append({"domain": domain, "message": exc.message, "error_code": exc.error_code, **exc.extra})

        result = {"unregistered": unregistered, "skipped": skipped, "failures": failures}
        self._record_operation(
            "domain.ddns.unregister_service",
            payload={"domains": [str((row or {}).get("domain") or "") for row in rows]},
            result=result,
            status="failed" if failures else "succeeded",
            env=env,
        )
        if failures:
            raise DomainError(409, "DDNS 관리 서버에서 DNS 레코드를 삭제할 수 없습니다.", "DDNS_SERVICE_UNREGISTER_FAILED", **result)
        return {"status": "ok", **result}

    def check_endpoint(self, endpoint_id, env=None):
        with connect(env=env) as connection:
            with connection.cursor() as cursor:
                endpoint = self._fetch_endpoint(cursor, endpoint_id, env=env)
        health_path = endpoint.get("health_path")
        if not health_path:
            return {"status": "skipped", "message": "health path가 없어 연결 확인을 건너뛰었습니다."}
        try:
            response = _request(endpoint, "GET", health_path)
            body = response.get("body") or {}
            status = "success" if body.get("success", True) is not False else "error"
            message = body.get("message") or ("DDNS 관리 서버 연결을 확인했습니다." if status == "success" else "DDNS 관리 서버 확인에 실패했습니다.")
        except DomainError as exc:
            status = "error"
            message = exc.message
            body = {"error_code": exc.error_code, **exc.extra}
        with connect(env=env) as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    UPDATE ddns_endpoints
                    SET last_check_at = now(), last_check_status = %s, last_check_message = %s
                    WHERE id = %s
                    """,
                    (status, message, endpoint_id),
                )
        return {"status": "ok" if status == "success" else "error", "message": message, "response": body}


Model = DomainDdns()
