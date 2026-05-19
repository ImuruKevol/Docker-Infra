import datetime
import decimal
import hashlib
import ipaddress
import json
import os
import re
import ssl
import tempfile
import uuid
from pathlib import Path
from urllib import error as urlerror, parse as urlparse, request as urlrequest

from psycopg.types.json import Jsonb


connect = wiz.model("db/postgres").connect
config = wiz.config("docker_infra")
DomainError = wiz.model("struct/domains_shared")
local_executor = wiz.model("struct/local_executor")
operations = wiz.model("struct/operations")

PROVIDER = "ddns"
PROVIDER_LABEL = "DDNS"
DEFAULT_REGISTRATION_PATH = "/api/ddns/update"


class PreserveMethodRedirectHandler(urlrequest.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        method = req.get_method()
        if method not in {"GET", "HEAD"} and code in {301, 302, 303, 307, 308}:
            request_headers = dict(req.headers)
            request_headers.update(getattr(req, "unredirected_hdrs", {}) or {})
            return urlrequest.Request(
                newurl,
                data=req.data,
                headers=request_headers,
                origin_req_host=req.origin_req_host,
                unverifiable=True,
                method=method,
            )
        return super().redirect_request(req, fp, code, msg, headers, newurl)


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


def _normalize_service_prefix(value):
    prefix = re.sub(r"[^a-z0-9-]+", "-", str(value or "").strip().lower())
    prefix = re.sub(r"-+", "-", prefix).strip("-")
    prefix = re.sub(r"-[a-f0-9]{6,}$", "", prefix)
    trimmed = re.sub(r"-(service|app)$", "", prefix)
    return (trimmed or prefix)[:50]


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


def _endpoint_api_url(endpoint):
    api_base_url = str(endpoint.get("api_base_url") or "").rstrip("/")
    registration_path = _path(endpoint.get("registration_path"), DEFAULT_REGISTRATION_PATH)
    return f"{api_base_url}{registration_path}" if api_base_url else ""


def _public_ip_override(record_type, env=None):
    values = config.runtime_env(env)
    keys = ["DOCKER_INFRA_DDNS_PUBLIC_IPV6"] if record_type == "AAAA" else ["DOCKER_INFRA_DDNS_PUBLIC_IPV4", "DOCKER_INFRA_DDNS_PUBLIC_IP"]
    for key in keys:
        value = str(values.get(key) or "").strip()
        if value:
            return value
    return ""


def _parse_public_ip(value, record_type="A"):
    for token in str(value or "").replace(",", " ").split():
        try:
            address = ipaddress.ip_address(token.strip())
        except Exception:
            continue
        if record_type == "A" and address.version != 4:
            continue
        if record_type == "AAAA" and address.version != 6:
            continue
        if not address.is_global:
            continue
        return str(address)
    return ""


def _lookup_public_ip(record_type="A", env=None):
    record_type = str(record_type or "A").upper()
    if record_type not in {"A", "AAAA"}:
        record_type = "A"
    override = _parse_public_ip(_public_ip_override(record_type, env=env), record_type=record_type)
    if override:
        return override
    for url in config.ddns_public_ip_urls(env):
        request = urlrequest.Request(url, headers={"User-Agent": "docker-infra-ddns/1.0"})
        try:
            with urlrequest.urlopen(request, timeout=5) as response:
                value = _parse_public_ip(response.read().decode("utf-8", errors="replace"), record_type=record_type)
                if value:
                    return value
        except Exception:
            continue
    raise DomainError(502, f"DDNS에 보낼 공인 {record_type} IP를 조회할 수 없습니다.", "DDNS_PUBLIC_IP_LOOKUP_FAILED")


def _write_json_file(path, payload, mode=0o600):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        os.chmod(path.parent, 0o700)
    except Exception:
        pass
    fd, tmp_path = tempfile.mkstemp(prefix=".tmp-", dir=str(path.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, ensure_ascii=False, sort_keys=True)
            handle.write("\n")
        os.chmod(tmp_path, mode)
        os.replace(tmp_path, path)
    finally:
        try:
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)
        except Exception:
            pass


def _read_json_file(path, fallback=None):
    try:
        with open(path, "r", encoding="utf-8") as handle:
            payload = json.load(handle)
        return payload if isinstance(payload, type(fallback if fallback is not None else {})) else (fallback if fallback is not None else {})
    except Exception:
        return fallback if fallback is not None else {}


def _utcnow():
    return datetime.datetime.now(datetime.timezone.utc).isoformat().replace("+00:00", "Z")


def _parse_datetime(value):
    text = str(value or "").strip()
    if not text:
        return None
    if text.endswith("Z"):
        text = f"{text[:-1]}+00:00"
    try:
        parsed = datetime.datetime.fromisoformat(text)
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=datetime.timezone.utc)
        return parsed
    except Exception:
        return None


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
    metadata = dict(item.get("metadata") or {})
    metadata["mode"] = metadata.get("mode") or "ddns_management"
    item["metadata"] = metadata
    item["api_url"] = _endpoint_api_url(item)
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


def _int_value(value):
    try:
        if value is None or value == "":
            return None
        return int(str(value).strip())
    except Exception:
        return None


def _response_message(body, fallback="DDNS API 응답이 실패 상태입니다."):
    if not isinstance(body, dict):
        return fallback
    for key in ["message", "error", "detail", "reason"]:
        value = str(body.get(key) or "").strip()
        if value:
            return value
    data = body.get("data")
    if isinstance(data, dict):
        return _response_message(data, fallback=fallback)
    response = body.get("response")
    if isinstance(response, dict):
        return _response_message(response, fallback=fallback)
    return fallback


def _response_failure(body):
    if not isinstance(body, dict):
        return None
    if set(body.keys()) == {"raw"} and str(body.get("raw") or "").strip():
        return {"message": "DDNS API 응답이 JSON 형식이 아닙니다.", "response": body}
    if body.get("success") is False or body.get("ok") is False:
        return {"message": _response_message(body), "response": body}
    status = str(body.get("status") or "").strip().lower()
    if status in {"error", "failed", "failure"}:
        return {"message": _response_message(body), "response": body}
    code = _int_value(body.get("code") if "code" in body else body.get("status_code"))
    if code is not None and code not in {0} and not 200 <= code < 300:
        return {"message": _response_message(body), "code": code, "response": body}
    for nested_key in ["data", "response", "body"]:
        nested = body.get(nested_key)
        if isinstance(nested, dict):
            failure = _response_failure(nested)
            if failure:
                return failure
    return None


def _assert_response_ok(body):
    failure = _response_failure(body)
    if failure:
        raise DomainError(502, failure.get("message") or "DDNS API 응답이 실패 상태입니다.", "DDNS_API_FAILED", response=body, remote_error=failure)


def _request(endpoint, method, path, payload=None, timeout=15, query=None):
    base_url = str(endpoint.get("api_base_url") or "").rstrip("/")
    if not base_url:
        raise DomainError(400, "DDNS 서버 API URL이 필요합니다.", "DDNS_API_URL_REQUIRED")
    suffix = "" if not query else "?" + urlparse.urlencode(query, doseq=True)
    url = f"{base_url}{_path(path, DEFAULT_REGISTRATION_PATH)}{suffix}"
    headers = {"Accept": "application/json"}
    token = str(endpoint.get("token_value") or "").strip()
    if token:
        headers["X-DDNS-Key"] = token
    data = None
    if payload is not None:
        headers["Content-Type"] = "application/json"
        data = json.dumps(payload).encode("utf-8")
    context = None
    if endpoint.get("tls_verify") is False:
        context = ssl._create_unverified_context()
    request = urlrequest.Request(url, headers=headers, data=data, method=method.upper())
    handlers = [PreserveMethodRedirectHandler()]
    if context is not None:
        handlers.append(urlrequest.HTTPSHandler(context=context))
    opener = urlrequest.build_opener(*handlers)
    try:
        with opener.open(request, timeout=timeout) as response:
            body = response.read().decode("utf-8", errors="ignore")
            parsed = _safe_json_loads(body)
            return {"status_code": response.status, "body": parsed, "raw_body": body, "method": method.upper(), "url": response.geturl()}
    except urlerror.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="ignore")
        parsed = _safe_json_loads(body)
        message = parsed.get("message") or parsed.get("error") or body or str(exc)
        raise DomainError(exc.code, message, "DDNS_API_FAILED", response=parsed, status_code=exc.code, method=method.upper(), url=url)
    except urlerror.URLError as exc:
        raise DomainError(502, str(exc.reason), "DDNS_API_FAILED", method=method.upper(), url=url)


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

    def normalize_service_domain(self, domain, endpoint_id=None, prefix="", fallback_prefix="", env=None):
        clean_domain = str(domain or "").strip().lower().strip(".")
        clean_prefix = _normalize_service_prefix(prefix) or _normalize_service_prefix(fallback_prefix)
        endpoint = None
        if endpoint_id:
            with connect(env=env) as connection:
                with connection.cursor() as cursor:
                    try:
                        endpoint = self._fetch_endpoint(cursor, endpoint_id, env=env)
                    except DomainError:
                        endpoint = None
            if endpoint is not None:
                suffix = _normalize_suffix(endpoint.get("domain_suffix"))
                if endpoint.get("enabled") is not True or (clean_domain and suffix and not _matches_suffix(clean_domain, suffix)):
                    endpoint = None
        if endpoint is None and clean_domain and not endpoint_id:
            endpoint = self.match_domain(clean_domain, env=env)

        suffix = _normalize_suffix((endpoint or {}).get("domain_suffix"))
        apex_suffix = bool(endpoint and suffix and clean_domain == suffix)
        if endpoint and suffix and (not clean_domain or apex_suffix) and clean_prefix:
            clean_domain = f"{clean_prefix}.{suffix}"
            apex_suffix = False
        if endpoint and suffix and clean_domain.endswith(f".{suffix}"):
            current_prefix = clean_domain[: -(len(suffix) + 1)]
            normalized_prefix = _normalize_service_prefix(current_prefix)
            if normalized_prefix and normalized_prefix != current_prefix and re.search(r"-[a-f0-9]{6,}$", current_prefix):
                clean_prefix = normalized_prefix
                clean_domain = f"{clean_prefix}.{suffix}"
        if endpoint and suffix and not clean_prefix and clean_domain.endswith(f".{suffix}"):
            clean_prefix = clean_domain[: -(len(suffix) + 1)]
        return {
            "domain": clean_domain,
            "endpoint": dict(endpoint) if endpoint else None,
            "prefix": clean_prefix,
            "suffix": suffix,
            "apex_suffix": apex_suffix,
        }

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
        dispatcher_summaries = self._dispatcher_summaries(env=env)
        for endpoint in endpoints:
            endpoint["dispatcher"] = dispatcher_summaries.get(str(endpoint.get("id")), self._empty_dispatcher_summary())
        return {
            "endpoints": endpoints,
            "summary": {
                "endpoint_count": len(endpoints),
                "enabled_endpoint_count": len([item for item in endpoints if item.get("enabled")]),
                "registration_count": sum(int(item.get("registration_count") or 0) for item in endpoints),
            },
            "dispatcher": self.dispatcher_status(env=env),
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
        dispatcher = self.sync_dispatcher(env=env)
        self._record_operation(
            "domain.ddns.endpoint.save",
            payload={"domain_suffix": domain_suffix, "api_url": f"{api_base_url}{registration_path}"},
            result={"endpoint_id": endpoint_id, "domain_suffix": domain_suffix, "dispatcher": dispatcher},
            env=env,
        )
        return detail["endpoint"]

    def delete_endpoint(self, endpoint_id, env=None):
        with connect(env=env) as connection:
            with connection.cursor() as cursor:
                endpoint = self._fetch_endpoint(cursor, endpoint_id, env=env)
                cursor.execute("DELETE FROM ddns_endpoints WHERE id = %s", (endpoint_id,))
        dispatcher = self.sync_dispatcher(env=env)
        self._record_operation(
            "domain.ddns.endpoint.delete",
            payload={"endpoint_id": endpoint_id},
            result={"deleted": True, "domain_suffix": endpoint.get("domain_suffix"), "dispatcher": dispatcher},
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
        preferred_record_type = str(metadata.get("ddns_record_type") or "A").strip().upper()
        if preferred_record_type not in {"A", "AAAA"}:
            preferred_record_type = "A"
        target_host = _lookup_public_ip(preferred_record_type, env=env)
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
        domain = str(domain_row.get("domain") or "").strip().lower()
        return {
            "hostname": domain,
            "ip": target["host"],
            "record_type": target["record_type"],
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

    def _existing_registration(self, endpoint_id, domain, env=None):
        with connect(env=env) as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    "SELECT * FROM ddns_registrations WHERE endpoint_id = %s AND domain = %s",
                    (endpoint_id, domain),
                )
                row = cursor.fetchone()
        return serialize(dict(row)) if row else None

    def _existing_registration_current(self, existing, target):
        if not existing or existing.get("status") != "registered":
            return False
        metadata = dict(existing.get("metadata") or {})
        if _response_failure(metadata.get("response") or {}):
            return False
        return (
            str(existing.get("target_host") or "") == target["host"]
            and str(metadata.get("record_type") or target["record_type"]).upper() == target["record_type"]
        )

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

    def _mark_registration_failed(self, endpoint, registration, exc, target, env=None):
        metadata = dict(registration.get("metadata") or {})
        metadata.update({"response": getattr(exc, "extra", {}) or {}, "record_type": target["record_type"]})
        with connect(env=env) as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    UPDATE ddns_registrations
                    SET status = 'failed',
                        last_sync_at = now(),
                        last_sync_message = %s,
                        metadata = %s,
                        updated_at = now()
                    WHERE id = %s
                    RETURNING *
                    """,
                    (getattr(exc, "message", str(exc)), Jsonb(metadata), registration["id"]),
                )
                saved = serialize(dict(cursor.fetchone()))
                if saved.get("service_domain_id"):
                    cursor.execute("SELECT * FROM service_domains WHERE id = %s", (saved["service_domain_id"],))
                    domain_row = cursor.fetchone()
                    if domain_row:
                        self._mark_service_domain(cursor, dict(domain_row), endpoint, saved, target)
        return saved

    def _dispatcher_paths(self, env=None):
        return {
            "config_path": str(Path(config.data_dir(env)) / "ddns" / "dispatcher.json"),
            "state_file": config.ddns_state_file(env),
            "script_path": config.ddns_dispatcher_script_path(env),
            "dispatcher_path": config.ddns_dispatcher_path(env),
        }

    def dispatcher_status(self, env=None):
        paths = self._dispatcher_paths(env=env)
        dispatcher_path = Path(paths["dispatcher_path"])
        script_path = Path(paths["script_path"])
        config_path = Path(paths["config_path"])
        dispatcher_exists = dispatcher_path.is_file()
        script_exists = script_path.is_file()
        dispatcher_executable = dispatcher_exists and os.access(dispatcher_path, os.X_OK)
        script_executable = script_exists and os.access(script_path, os.X_OK)
        registered = dispatcher_exists and script_exists and dispatcher_executable and script_executable
        if registered:
            status = "registered"
            message = "NetworkManager dispatcher가 등록되어 있습니다."
        elif dispatcher_exists or script_exists:
            status = "partial"
            message = "NetworkManager dispatcher 등록이 일부만 완료되어 있습니다."
        else:
            status = "missing"
            message = "NetworkManager dispatcher가 등록되어 있지 않습니다."
        return {
            "registered": registered,
            "status": status,
            "message": message,
            "dispatcher_path": paths["dispatcher_path"],
            "script_path": paths["script_path"],
            "config_path": paths["config_path"],
            "config_exists": config_path.is_file(),
            "dispatcher_exists": dispatcher_exists,
            "script_exists": script_exists,
            "dispatcher_executable": dispatcher_executable,
            "script_executable": script_executable,
        }

    def _dispatcher_state_key(self, record):
        raw = "|".join([
            str(record.get("api_url") or ""),
            str(record.get("hostname") or ""),
            str(record.get("record_type") or "A").upper(),
        ])
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()

    def _dispatcher_state(self, env=None):
        return _read_json_file(self._dispatcher_paths(env=env)["state_file"], fallback={})

    def _empty_dispatcher_summary(self):
        return {
            "record_count": 0,
            "last_sent_at": "",
            "last_sent_ip": "",
            "last_hostname": "",
            "last_record_type": "",
            "source": "",
            "items": [],
        }

    def _dispatcher_summaries(self, records=None, state=None, env=None):
        records = self._dispatcher_records(env=env) if records is None else records
        state = self._dispatcher_state(env=env) if state is None else state
        summaries = {}
        for record in records:
            endpoint_id = str(record.get("endpoint_id") or "").strip()
            if not endpoint_id:
                continue
            current = state.get(self._dispatcher_state_key(record))
            current = current if isinstance(current, dict) else {}
            item = {
                "endpoint_id": endpoint_id,
                "hostname": current.get("hostname") or record.get("hostname") or "",
                "record_type": current.get("record_type") or record.get("record_type") or "A",
                "last_sent_ip": current.get("last_sent_ip") or record.get("last_sent_ip") or "",
                "last_sent_at": current.get("last_sent_at") or record.get("last_sent_at") or "",
                "source": current.get("source") or "",
            }
            summary = summaries.setdefault(endpoint_id, self._empty_dispatcher_summary())
            summary["items"].append(item)
            summary["record_count"] = len(summary["items"])
            latest = summary.get("_latest")
            latest_at = _parse_datetime((latest or {}).get("last_sent_at"))
            item_at = _parse_datetime(item.get("last_sent_at"))
            if latest is None or (item_at and (latest_at is None or item_at > latest_at)):
                summary["_latest"] = item

        for summary in summaries.values():
            latest = summary.pop("_latest", None) or (summary["items"][0] if summary["items"] else {})
            summary["last_sent_at"] = latest.get("last_sent_at") or ""
            summary["last_sent_ip"] = latest.get("last_sent_ip") or ""
            summary["last_hostname"] = latest.get("hostname") or ""
            summary["last_record_type"] = latest.get("record_type") or ""
            summary["source"] = latest.get("source") or ""
        return summaries

    def _merge_dispatcher_state(self, existing, seed):
        if not isinstance(existing, dict) or not existing:
            return seed
        merged = dict(existing)
        existing_at = _parse_datetime(merged.get("last_sent_at"))
        seed_at = _parse_datetime(seed.get("last_sent_at"))
        if existing_at and seed_at and seed_at > existing_at:
            return {**merged, **seed}
        for key in ["endpoint_id", "hostname", "record_type", "last_sent_ip", "last_sent_at", "source"]:
            if not merged.get(key) and seed.get(key):
                merged[key] = seed.get(key)
        return merged

    def _write_dispatcher_sent_state(self, records, source="docker-infra", env=None):
        paths = self._dispatcher_paths(env=env)
        state = self._dispatcher_state(env=env)
        sent_at = _utcnow()
        changed = False
        for record in records or []:
            last_sent_ip = str(record.get("last_sent_ip") or "").strip()
            if not last_sent_ip:
                continue
            state[self._dispatcher_state_key(record)] = {
                "endpoint_id": str(record.get("endpoint_id") or ""),
                "hostname": record.get("hostname") or "",
                "record_type": record.get("record_type") or "A",
                "last_sent_ip": last_sent_ip,
                "last_sent_at": record.get("last_sent_at") or sent_at,
                "source": source,
            }
            changed = True
        if changed:
            _write_json_file(paths["state_file"], state)
        return state

    def _dispatcher_records(self, env=None):
        with connect(env=env) as connection:
            with connection.cursor() as cursor:
                if not _schema_ready(cursor):
                    return []
                cursor.execute(
                    """
                    SELECT
                        dr.domain,
                        dr.target_host,
                        dr.last_sync_at,
                        dr.metadata AS registration_metadata,
                        e.id AS endpoint_id,
                        e.domain_suffix,
                        COALESCE(e.api_base_url, '') AS api_base_url,
                        COALESCE(e.registration_path, '') AS registration_path,
                        e.tls_verify,
                        CASE
                            WHEN e.token_enc IS NOT NULL
                                THEN pgp_sym_decrypt(decode(e.token_enc, 'base64'), %s)
                            ELSE NULL
                        END AS token_value
                    FROM ddns_registrations dr
                    JOIN ddns_endpoints e ON e.id = dr.endpoint_id
                    WHERE e.enabled = true
                      AND dr.status = 'registered'
                    ORDER BY dr.domain ASC
                    """,
                    (secret_key(env),),
                )
                rows = [dict(row) for row in cursor.fetchall()]
        records = []
        seen = set()
        for row in rows:
            token = str(row.get("token_value") or "").strip()
            api_url = _endpoint_api_url(row)
            hostname = str(row.get("domain") or "").strip().lower().strip(".")
            if not token or not api_url or not hostname:
                continue
            metadata = dict(row.get("registration_metadata") or {})
            record_type = str(metadata.get("record_type") or ("AAAA" if ":" in str(row.get("target_host") or "") else "A")).upper()
            if record_type not in {"A", "AAAA"}:
                record_type = "A"
            key = (api_url, hostname, record_type)
            if key in seen:
                continue
            seen.add(key)
            records.append({
                "endpoint_id": str(row.get("endpoint_id") or ""),
                "api_url": api_url,
                "hostname": hostname,
                "record_type": record_type,
                "token": token,
                "tls_verify": row.get("tls_verify") is not False,
                "last_sent_ip": str(row.get("target_host") or "").strip(),
                "last_sent_at": serialize(row.get("last_sync_at")) or "",
                "timeout_seconds": 15,
            })
        return records

    def sync_dispatcher(self, env=None, force_install=False):
        paths = self._dispatcher_paths(env=env)
        records = self._dispatcher_records(env=env)
        state_records = [dict(record) for record in records]
        config_records = []
        for record in records:
            clean = dict(record)
            clean.pop("last_sent_ip", None)
            clean.pop("last_sent_at", None)
            config_records.append(clean)
        payload = {
            "version": 1,
            "public_ip_urls": config.ddns_public_ip_urls(env),
            "timeout_seconds": 8,
            "state_file": paths["state_file"],
            "records": config_records,
        }
        _write_json_file(paths["config_path"], payload)

        state = _read_json_file(paths["state_file"], fallback={})
        for record in state_records:
            last_sent_ip = str(record.get("last_sent_ip") or "").strip()
            if not last_sent_ip:
                continue
            key = self._dispatcher_state_key(record)
            seed = {
                "endpoint_id": str(record.get("endpoint_id") or ""),
                "hostname": record.get("hostname") or "",
                "record_type": record.get("record_type") or "A",
                "last_sent_ip": last_sent_ip,
                "last_sent_at": record.get("last_sent_at") or "",
                "source": "docker-infra",
            }
            state[key] = self._merge_dispatcher_state(state.get(key), seed)
        if state_records:
            _write_json_file(paths["state_file"], state)

        result = {
            "config_path": paths["config_path"],
            "state_file": paths["state_file"],
            "record_count": len(config_records),
            "installed": False,
        }
        should_install = force_install or config.ddns_dispatcher_auto_install(env) is True
        if not should_install or (not config_records and not force_install):
            return result
        install_result = local_executor.run("ddns.dispatcher.ensure", params=paths, timeout_seconds=60, env=env)
        result["installed"] = install_result.get("status") == "ok"
        result["install"] = {
            "status": install_result.get("status"),
            "exit_code": install_result.get("exit_code"),
            "stdout": install_result.get("stdout"),
            "stderr": install_result.get("stderr"),
        }
        if install_result.get("status") != "ok":
            raise DomainError(500, "DDNS NetworkManager dispatcher를 설치할 수 없습니다.", "DDNS_DISPATCHER_INSTALL_FAILED", dispatcher=result)
        return result

    def ensure_dispatcher(self, env=None):
        install_result = self.sync_dispatcher(env=env, force_install=True)
        status = self.dispatcher_status(env=env)
        result = {
            "status": "ok" if status.get("registered") else "error",
            "message": status.get("message") or "",
            "dispatcher": status,
            "install": install_result,
        }
        self._record_operation(
            "domain.ddns.dispatcher.ensure",
            payload={},
            result=result,
            status="succeeded" if status.get("registered") else "failed",
            env=env,
        )
        if status.get("registered") is not True:
            extra = {key: value for key, value in result.items() if key not in {"message", "status"}}
            raise DomainError(500, status.get("message") or "DDNS NetworkManager dispatcher를 등록할 수 없습니다.", "DDNS_DISPATCHER_INSTALL_FAILED", **extra)
        return result

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
            normalized = self.normalize_service_domain(
                domain,
                endpoint_id=metadata.get("ddns_endpoint_id"),
                prefix=metadata.get("domain_prefix"),
                fallback_prefix=(service or {}).get("name") or (service or {}).get("namespace") or metadata.get("compose_service"),
                env=env,
            )
            endpoint = normalized.get("endpoint")
            normalized_domain = normalized.get("domain") or domain
            if endpoint is not None and normalized_domain and normalized_domain != domain:
                metadata["ddns_original_domain"] = domain
                metadata["domain_prefix"] = normalized.get("prefix")
                domain = normalized_domain
                domain_row["domain"] = domain
                domain_row["metadata"] = metadata
                if domain_row.get("id"):
                    with connect(env=env) as connection:
                        with connection.cursor() as cursor:
                            cursor.execute(
                                "UPDATE service_domains SET domain = %s, metadata = %s, updated_at = now() WHERE id = %s RETURNING *",
                                (domain, Jsonb(metadata), domain_row["id"]),
                            )
                            updated = cursor.fetchone()
                            if updated:
                                domain_row = dict(updated)
                                metadata = dict(domain_row.get("metadata") or {})
            if endpoint is None:
                endpoint = self.match_domain(domain, endpoint_id=metadata.get("ddns_endpoint_id"), env=env)
            if endpoint is None:
                skipped.append({"domain": domain, "reason": "ddns_endpoint_not_matched"})
                continue
            target = self._registration_target(domain_row, env=env)
            request_payload = self._register_payload(service, endpoint, domain_row, target)
            try:
                existing = self._existing_registration(endpoint["id"], domain, env=env)
                if self._existing_registration_current(existing, target):
                    with connect(env=env) as connection:
                        with connection.cursor() as cursor:
                            self._mark_service_domain(cursor, domain_row, endpoint, existing, target)
                    skipped.append({"domain": domain, "reason": "public_ip_unchanged", "target": target, "registration": existing})
                    continue
                response = _request(endpoint, "POST", endpoint.get("registration_path") or DEFAULT_REGISTRATION_PATH, payload=request_payload)
                body = response.get("body") or {}
                _assert_response_ok(body)
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

        dispatcher = {}
        if not failures:
            dispatcher = self.sync_dispatcher(env=env)
        result = {"registered": registered, "skipped": skipped, "failures": failures, "dispatcher": dispatcher}
        self._record_operation(
            "domain.ddns.register_service",
            payload={"service_id": str(service_id)},
            result=result,
            status="failed" if failures else "succeeded",
            env=env,
        )
        if failures:
            raise DomainError(409, "DDNS 관리 서버에 DNS 레코드를 등록할 수 없습니다.", "DDNS_SERVICE_REGISTER_FAILED", **result)
        unchanged = [item for item in skipped if item.get("reason") == "public_ip_unchanged"]
        return {"status": "ok" if registered or unchanged else "skipped", **result}

    def force_update_endpoint(self, endpoint_id, env=None):
        endpoint_id = str(endpoint_id or "").strip()
        if not endpoint_id:
            raise DomainError(400, "DDNS 관리 서버 ID가 필요합니다.", "DDNS_ENDPOINT_ID_REQUIRED")

        with connect(env=env) as connection:
            with connection.cursor() as cursor:
                endpoint = self._fetch_endpoint(cursor, endpoint_id, env=env)
                cursor.execute(
                    """
                    SELECT *
                    FROM ddns_registrations
                    WHERE endpoint_id = %s
                      AND status = 'registered'
                    ORDER BY domain ASC
                    """,
                    (endpoint_id,),
                )
                registrations = [dict(row) for row in cursor.fetchall()]

        if not registrations:
            raise DomainError(409, "수동으로 갱신할 DDNS 등록 레코드가 없습니다.", "DDNS_REGISTRATION_NOT_FOUND")

        api_url = _endpoint_api_url(endpoint)
        ip_cache = {}
        updated = []
        failures = []
        state_records = []

        for registration in registrations:
            domain = str(registration.get("domain") or "").strip().lower()
            metadata = dict(registration.get("metadata") or {})
            record_type = str(metadata.get("record_type") or ("AAAA" if ":" in str(registration.get("target_host") or "") else "A")).upper()
            if record_type not in {"A", "AAAA"}:
                record_type = "A"
            target = {
                "host": str(registration.get("target_host") or ""),
                "record_type": record_type,
                "port": int(registration.get("target_port") or 80),
            }
            try:
                if record_type not in ip_cache:
                    ip_cache[record_type] = _lookup_public_ip(record_type, env=env)
                ip = ip_cache[record_type]
                target_record_type = "AAAA" if ":" in ip else "A"
                target = {
                    "host": ip,
                    "record_type": target_record_type,
                    "port": int(registration.get("target_port") or 80),
                }
                request_payload = {
                    "hostname": domain,
                    "ip": target["host"],
                    "record_type": target["record_type"],
                }
                response = _request(endpoint, "POST", endpoint.get("registration_path") or DEFAULT_REGISTRATION_PATH, payload=request_payload)
                body = response.get("body") or {}
                _assert_response_ok(body)

                message = body.get("message") or "manual update"
                remote_record_id = str(body.get("id") or body.get("record_id") or body.get("registration_id") or registration.get("remote_record_id") or "").strip()
                registration_metadata = dict(metadata)
                registration_metadata.update({"response": body, "record_type": target["record_type"]})
                with connect(env=env) as connection:
                    with connection.cursor() as cursor:
                        cursor.execute(
                            """
                            UPDATE ddns_registrations
                            SET target_host = %s,
                                remote_record_id = %s,
                                status = 'registered',
                                last_sync_at = now(),
                                last_sync_message = %s,
                                metadata = %s,
                                updated_at = now()
                            WHERE id = %s
                            RETURNING *
                            """,
                            (target["host"], remote_record_id or None, message, Jsonb(registration_metadata), registration["id"]),
                        )
                        saved = serialize(dict(cursor.fetchone()))
                        if saved.get("service_domain_id"):
                            cursor.execute("SELECT * FROM service_domains WHERE id = %s", (saved["service_domain_id"],))
                            domain_row = cursor.fetchone()
                            if domain_row:
                                self._mark_service_domain(cursor, dict(domain_row), endpoint, saved, target)
                updated.append({
                    "domain": domain,
                    "endpoint_id": endpoint_id,
                    "target": target,
                    "registration": saved,
                    "response": body,
                })
                state_records.append({
                    "endpoint_id": endpoint_id,
                    "api_url": api_url,
                    "hostname": domain,
                    "record_type": target["record_type"],
                    "last_sent_ip": target["host"],
                    "last_sent_at": saved.get("last_sync_at") or _utcnow(),
                })
            except DomainError as exc:
                failures.append({"domain": domain, "message": exc.message, "error_code": exc.error_code, **exc.extra})
                self._mark_registration_failed(endpoint, registration, exc, target, env=env)

        dispatcher = {}
        if updated:
            dispatcher = self.sync_dispatcher(env=env)
            self._write_dispatcher_sent_state(state_records, source="manual", env=env)
        dispatcher_summary = self._dispatcher_summaries(env=env).get(endpoint_id, self._empty_dispatcher_summary())
        result = {
            "status": "ok" if not failures else "error",
            "message": f"DDNS API를 {len(updated)}개 레코드에 호출했습니다.",
            "updated": updated,
            "failures": failures,
            "dispatcher": dispatcher,
            "dispatcher_summary": dispatcher_summary,
        }
        self._record_operation(
            "domain.ddns.endpoint.force_update",
            payload={"endpoint_id": endpoint_id},
            result=result,
            status="failed" if failures else "succeeded",
            env=env,
        )
        if failures:
            extra = {key: value for key, value in result.items() if key not in {"message", "status"}}
            raise DomainError(409, "일부 DDNS API 호출에 실패했습니다.", "DDNS_FORCE_UPDATE_FAILED", **extra)
        return result

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
                _assert_response_ok(body)
                unregistered.append({"domain": domain, "endpoint_id": str(endpoint["id"]), "response": body})
                with connect(env=env) as connection:
                    with connection.cursor() as cursor:
                        cursor.execute("DELETE FROM ddns_registrations WHERE endpoint_id = %s AND domain = %s", (endpoint["id"], domain))
            except DomainError as exc:
                failures.append({"domain": domain, "message": exc.message, "error_code": exc.error_code, **exc.extra})

        dispatcher = {}
        if not failures:
            dispatcher = self.sync_dispatcher(env=env)
        result = {"unregistered": unregistered, "skipped": skipped, "failures": failures, "dispatcher": dispatcher}
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
