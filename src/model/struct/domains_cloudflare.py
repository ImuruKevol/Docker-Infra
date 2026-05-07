import datetime
import decimal
import json
import uuid
from urllib import error as urlerror
from urllib import parse as urlparse
from urllib import request as urlrequest

from psycopg.types.json import Jsonb


connect = wiz.model("db/postgres").connect
config = wiz.config("docker_infra")
DomainError = wiz.model("struct/domains_shared")

CLOUDFLARE_API = "https://api.cloudflare.com/client/v4"


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


def zone_select_sql():
    return """
    SELECT
        id,
        domain,
        zone_id,
        usable_for_service,
        enabled,
        record_count,
        last_sync_at,
        last_sync_status,
        last_sync_message,
        metadata,
        created_at,
        updated_at,
        CASE
            WHEN api_token_enc IS NOT NULL
                THEN pgp_sym_decrypt(decode(api_token_enc, 'base64'), %s)
            ELSE NULL
        END AS api_token_value
    FROM cloudflare_zones
    """


def zone_status(row):
    if not row["enabled"]:
        return "disabled"
    if not row.get("api_token_value"):
        return "manual"
    if row.get("last_sync_status") == "success":
        return "active"
    if row.get("last_sync_status") == "error":
        return "error"
    return "pending"


def normalize_zone(row):
    item = serialize(dict(row))
    item["api_token_value"] = row.get("api_token_value") or ""
    item["secret_configured"] = bool(row.get("api_token_value"))
    item["status"] = zone_status(row)
    item["enabled"] = bool(row["enabled"])
    item["usable_for_service"] = bool(row["usable_for_service"])
    return item


def record_payload(row):
    item = serialize(dict(row))
    item["ttl"] = int(row["ttl"]) if row.get("ttl") is not None else None
    item["priority"] = int(row["priority"]) if row.get("priority") is not None else None
    item["proxied"] = row.get("proxied")
    item["is_internal_only"] = bool((row.get("metadata") or {}).get("is_internal_only"))
    return item


def upsert_zone_cache(cursor, zone_id, record_count, status, message=None):
    cursor.execute(
        """
        UPDATE cloudflare_zones
        SET record_count = %s,
            last_sync_status = %s,
            last_sync_message = %s,
            last_sync_at = now()
        WHERE id = %s
        """,
        (record_count, status, message, zone_id),
    )


def cf_request(token, method, path, payload=None, query=None, timeout=15):
    if str(token or "").strip() == "":
        raise DomainError(400, "Cloudflare API token을 입력해주세요.", "CLOUDFLARE_TOKEN_REQUIRED")
    suffix = "" if not query else "?" + urlparse.urlencode(query, doseq=True)
    url = f"{CLOUDFLARE_API}{path}{suffix}"
    headers = {"Authorization": f"Bearer {token}", "Accept": "application/json"}
    data = None
    if payload is not None:
        headers["Content-Type"] = "application/json"
        data = json.dumps(payload).encode("utf-8")
    req = urlrequest.Request(url, headers=headers, data=data, method=method.upper())
    try:
        with urlrequest.urlopen(req, timeout=timeout) as response:
            parsed = json.loads(response.read().decode("utf-8") or "{}")
    except urlerror.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="ignore")
        try:
            parsed = json.loads(body or "{}")
            errors = parsed.get("errors") or []
            message = errors[0].get("message") if errors else body
        except Exception:
            message = body or str(exc)
        raise DomainError(exc.code, message or "Cloudflare API 요청에 실패했습니다.", "CLOUDFLARE_API_FAILED")
    except urlerror.URLError as exc:
        raise DomainError(502, str(exc.reason), "CLOUDFLARE_API_FAILED")
    if parsed.get("success") is not True:
        errors = parsed.get("errors") or []
        message = errors[0].get("message") if errors else "Cloudflare API 요청에 실패했습니다."
        raise DomainError(502, message, "CLOUDFLARE_API_FAILED", errors=errors)
    return parsed.get("result")


class DomainCloudflareMixin:
    serialize = staticmethod(serialize)
    secret_key = staticmethod(secret_key)
    zone_select_sql = staticmethod(zone_select_sql)
    normalize_zone = staticmethod(normalize_zone)
    record_payload = staticmethod(record_payload)
    upsert_zone_cache = staticmethod(upsert_zone_cache)
    cf_request = staticmethod(cf_request)

    def sync_zone(self, zone_id, env=None):
        with connect(env=env) as connection:
            with connection.cursor() as cursor:
                zone = self._fetch_zone(cursor, zone_id, env=env)
        try:
            result = cf_request(zone.get("api_token_value"), "GET", f"/zones/{zone['zone_id']}")
            records = cf_request(
                zone.get("api_token_value"),
                "GET",
                f"/zones/{zone['zone_id']}/dns_records",
                query={"page": 1, "per_page": 500},
            )
            mapped_records = []
            for item in records:
                mapped_records.append(
                    {
                        "cloudflare_record_id": item["id"],
                        "record_type": item["type"],
                        "record_name": item["name"],
                        "content": item.get("content"),
                        "proxied": item.get("proxied"),
                        "ttl": item.get("ttl"),
                        "priority": item.get("priority"),
                        "comment": item.get("comment"),
                        "metadata": {"raw": item},
                        "last_synced_at": datetime.datetime.utcnow(),
                    }
                )
            with connect(env=env) as connection:
                with connection.cursor() as cursor:
                    cursor.execute("DELETE FROM cloudflare_dns_records WHERE zone_config_id = %s", (zone_id,))
                    for record in mapped_records:
                        cursor.execute(
                            """
                            INSERT INTO cloudflare_dns_records(
                                zone_config_id, cloudflare_record_id, record_type, record_name, content,
                                proxied, ttl, priority, comment, metadata, last_synced_at
                            )
                            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                            """,
                            (
                                zone_id,
                                record["cloudflare_record_id"],
                                record["record_type"],
                                record["record_name"],
                                record["content"],
                                record["proxied"],
                                record["ttl"],
                                record["priority"],
                                record["comment"],
                                Jsonb(record["metadata"]),
                                record["last_synced_at"],
                            ),
                        )
                    upsert_zone_cache(cursor, zone_id, len(mapped_records), "success", f"{result.get('name') or zone['domain']} 동기화 완료")
            return self.detail(zone_id, env=env)
        except DomainError as exc:
            with connect(env=env) as connection:
                with connection.cursor() as cursor:
                    upsert_zone_cache(cursor, zone_id, int(zone.get("record_count") or 0), "error", exc.message)
            raise

    def sync_all(self, env=None):
        synced = []
        failed = []
        for zone in self.load(env=env)["zones"]:
            try:
                synced.append(self.sync_zone(zone["id"], env=env)["zone"])
            except DomainError as exc:
                failed.append({"id": zone["id"], "domain": zone["domain"], "message": exc.message})
        return {"synced": synced, "failed": failed}

    def save_record(self, zone_id, payload, env=None):
        payload = dict(payload or {})
        record_type = str(payload.get("record_type") or payload.get("type") or "").strip().upper()
        record_name = str(payload.get("record_name") or payload.get("name") or "").strip()
        content = str(payload.get("content") or "").strip()
        record_id = str(payload.get("cloudflare_record_id") or payload.get("id") or "").strip()
        if record_type == "":
            raise DomainError(400, "레코드 타입을 선택해주세요.", "RECORD_TYPE_REQUIRED")
        if record_name == "":
            raise DomainError(400, "레코드 이름을 입력해주세요.", "RECORD_NAME_REQUIRED")
        if content == "" and record_type not in {"TXT"}:
            raise DomainError(400, "레코드 값을 입력해주세요.", "RECORD_CONTENT_REQUIRED")
        with connect(env=env) as connection:
            with connection.cursor() as cursor:
                zone = self._fetch_zone(cursor, zone_id, env=env)
        cf_payload = {"type": record_type, "name": record_name, "content": content, "ttl": int(payload.get("ttl") or 1)}
        if payload.get("proxied") is not None:
            cf_payload["proxied"] = bool(payload.get("proxied"))
        if payload.get("comment") not in [None, ""]:
            cf_payload["comment"] = str(payload.get("comment"))
        if payload.get("priority") not in [None, ""]:
            cf_payload["priority"] = int(payload.get("priority"))
        if record_id:
            cf_request(zone.get("api_token_value"), "PUT", f"/zones/{zone['zone_id']}/dns_records/{record_id}", payload=cf_payload)
        else:
            cf_request(zone.get("api_token_value"), "POST", f"/zones/{zone['zone_id']}/dns_records", payload=cf_payload)
        return self.sync_zone(zone_id, env=env)

    def delete_record(self, zone_id, record_id, env=None):
        record_id = str(record_id or "").strip()
        if record_id == "":
            raise DomainError(400, "삭제할 레코드가 없습니다.", "RECORD_ID_REQUIRED")
        with connect(env=env) as connection:
            with connection.cursor() as cursor:
                zone = self._fetch_zone(cursor, zone_id, env=env)
        cf_request(zone.get("api_token_value"), "DELETE", f"/zones/{zone['zone_id']}/dns_records/{record_id}")
        return self.sync_zone(zone_id, env=env)


Model = DomainCloudflareMixin
