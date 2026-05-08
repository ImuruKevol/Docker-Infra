import base64
import json
from urllib import error as urlerror
from urllib import request as urlrequest

from psycopg.types.json import Jsonb


connect = wiz.model("db/postgres").connect
settings = wiz.model("struct/settings")
config = wiz.config("docker_infra")

SPECS = {
    "harbor": {
        "label": "Harbor 백업 저장소",
        "table": "integration_harbor",
        "fields": ["url", "username"],
        "secret_name": "password",
        "secret_column": "password_enc",
    },
}


class IntegrationError(Exception):
    def __init__(self, status_code, message, error_code, **extra):
        super().__init__(message)
        self.status_code = status_code
        self.message = message
        self.error_code = error_code
        self.extra = extra


def _normalize_url(value):
    return str(value or "").strip().rstrip("/")


def _secret_key(env=None):
    return config.secret_key(env)


def _fallback_payload(key, env=None):
    prefix = f"integration.{key}"
    spec = SPECS[key]
    payload = {
        "key": key,
        "label": spec["label"],
        "enabled": False,
        "fields": {field: "" for field in spec["fields"]},
        "secret_name": spec["secret_name"],
        "secret_value": "",
        "secret_configured": False,
    }
    enabled = settings.get(f"{prefix}.enabled", env=env)
    if enabled is not None:
        payload["enabled"] = bool(enabled.get("value"))
    for field in spec["fields"]:
        row = settings.get(f"{prefix}.{field}", env=env)
        if row is not None:
            payload["fields"][field] = row.get("value") or ""
    secret_value = settings.get_secret_value(f"{prefix}.{spec['secret_name']}", env=env)
    payload["secret_value"] = secret_value or ""
    payload["secret_configured"] = bool(secret_value)
    return payload


def _table_payload(cursor, key, env=None):
    spec = SPECS[key]
    columns = ", ".join(spec["fields"])
    cursor.execute(
        f"""
        SELECT
            id,
            enabled,
            {columns},
            CASE
                WHEN {spec['secret_column']} IS NOT NULL
                    THEN pgp_sym_decrypt(decode({spec['secret_column']}, 'base64'), %s)
                ELSE NULL
            END AS secret_value,
            created_at,
            updated_at
        FROM {spec['table']}
        ORDER BY created_at DESC
        LIMIT 1
        """,
        (_secret_key(env),),
    )
    row = cursor.fetchone()
    if row is None:
        return None
    return {
        "id": str(row["id"]),
        "key": key,
        "label": spec["label"],
        "enabled": bool(row["enabled"]),
        "fields": {field: (row.get(field) or "") for field in spec["fields"]},
        "secret_name": spec["secret_name"],
        "secret_value": row.get("secret_value") or "",
        "secret_configured": bool(row.get("secret_value")),
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
    }


def _request_json(url, headers=None, timeout=10):
    req = urlrequest.Request(url, headers=headers or {}, method="GET")
    with urlrequest.urlopen(req, timeout=timeout) as response:
        body = response.read().decode("utf-8")
        return response.status, json.loads(body or "{}")


class Integrations:
    IntegrationError = IntegrationError

    def load(self, env=None):
        payload = []
        with connect(env=env) as connection:
            with connection.cursor() as cursor:
                for key in SPECS:
                    item = _table_payload(cursor, key, env=env)
                    if item is None:
                        item = _fallback_payload(key, env=env)
                    payload.append(item)
        return payload

    def get(self, key, env=None):
        if key not in SPECS:
            raise IntegrationError(400, "지원하지 않는 연동입니다.", "INVALID_INTEGRATION")
        with connect(env=env) as connection:
            with connection.cursor() as cursor:
                item = _table_payload(cursor, key, env=env)
        if item is not None:
            return item
        return _fallback_payload(key, env=env)

    def save(self, key, payload, test_run_id=None, env=None):
        if key not in SPECS:
            raise IntegrationError(400, "지원하지 않는 연동입니다.", "INVALID_INTEGRATION")
        spec = SPECS[key]
        fields = dict(payload.get("fields") or {})
        secret_value = payload.get("secret_value")
        enabled = bool(payload.get("enabled"))

        with connect(env=env) as connection:
            with connection.cursor() as cursor:
                cursor.execute(f"SELECT id FROM {spec['table']} ORDER BY created_at DESC LIMIT 1")
                row = cursor.fetchone()
                values = [_normalize_url(fields.get("url"))] if "url" in spec["fields"] else []
                for field in spec["fields"]:
                    if field == "url":
                        continue
                    values.append(str(fields.get(field, "") or "").strip())

                if row is None:
                    columns = ["enabled", *spec["fields"], spec["secret_column"], "test_run_id", "metadata"]
                    secret_expression = "NULL"
                    params = [enabled, *values]
                    if secret_value:
                        secret_expression = "encode(pgp_sym_encrypt(%s, %s), 'base64')"
                        params.extend([secret_value, _secret_key(env)])
                    params.extend([test_run_id, Jsonb({"source": "system"})])
                    query = f"""
                    INSERT INTO {spec['table']}({", ".join(columns)})
                    VALUES (%s, {", ".join(["%s"] * len(spec["fields"]))}, {secret_expression}, %s, %s)
                    """
                    cursor.execute(query, params)
                else:
                    set_parts = ["enabled = %s"]
                    params = [enabled]
                    for field in spec["fields"]:
                        value = _normalize_url(fields.get(field)) if field == "url" else str(fields.get(field, "") or "").strip()
                        set_parts.append(f"{field} = %s")
                        params.append(value)
                    if secret_value:
                        set_parts.append(f"{spec['secret_column']} = encode(pgp_sym_encrypt(%s, %s), 'base64')")
                        params.extend([secret_value, _secret_key(env)])
                    set_parts.append("test_run_id = %s")
                    set_parts.append("metadata = %s")
                    params.extend([test_run_id, Jsonb({"source": "system"})])
                    params.append(row["id"])
                    cursor.execute(
                        f"""
                        UPDATE {spec['table']}
                        SET {", ".join(set_parts)}
                        WHERE id = %s
                        """,
                        params,
                    )
        return self.get(key, env=env)

    def test_connection(self, key, payload, env=None):
        if key not in SPECS:
            raise IntegrationError(400, "지원하지 않는 연동입니다.", "INVALID_INTEGRATION")
        item = self.get(key, env=env)
        fields = {**item["fields"], **dict(payload.get("fields") or {})}
        secret_value = payload.get("secret_value")
        if secret_value in [None, ""]:
            secret_value = item.get("secret_value", "")

        try:
            if key == "harbor":
                return self._test_harbor(fields, secret_value)
        except IntegrationError:
            raise
        except Exception as exc:
            raise IntegrationError(502, str(exc), "INTEGRATION_TEST_FAILED")

        raise IntegrationError(400, "지원하지 않는 연동입니다.", "INVALID_INTEGRATION")

    def _test_harbor(self, fields, secret_value):
        url = _normalize_url(fields.get("url"))
        username = str(fields.get("username") or "").strip()
        if url == "":
            raise IntegrationError(400, "Harbor URL을 입력해주세요.", "HARBOR_URL_REQUIRED")
        if username == "":
            raise IntegrationError(400, "Harbor 계정을 입력해주세요.", "HARBOR_USERNAME_REQUIRED")
        if str(secret_value or "").strip() == "":
            raise IntegrationError(400, "Harbor 비밀번호를 입력해주세요.", "HARBOR_PASSWORD_REQUIRED")

        token = base64.b64encode(f"{username}:{secret_value}".encode("utf-8")).decode("ascii")
        headers = {"Authorization": f"Basic {token}", "Accept": "application/json"}
        endpoint = f"{url}/api/v2.0/projects?page=1&page_size=1"
        try:
            status, payload = _request_json(endpoint, headers=headers)
        except urlerror.HTTPError as exc:
            message = exc.read().decode("utf-8", errors="ignore")
            raise IntegrationError(exc.code, message or "Harbor 연결에 실패했습니다.", "HARBOR_CONNECTION_FAILED")
        except urlerror.URLError as exc:
            raise IntegrationError(502, str(exc.reason), "HARBOR_CONNECTION_FAILED")
        if status != 200:
            raise IntegrationError(status, "Harbor 연결에 실패했습니다.", "HARBOR_CONNECTION_FAILED")
        return {
            "message": "Harbor 연결에 성공했습니다.",
            "summary": {
                "endpoint": endpoint,
                "username": username,
                "sample_count": len(payload) if isinstance(payload, list) else 0,
            },
        }


Model = Integrations()
