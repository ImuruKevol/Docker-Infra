import csv
import datetime
import decimal
import io
import json
import re
import uuid

from psycopg.types.json import Jsonb


connect = wiz.model("db/postgres").connect

STATUSES = {"succeeded", "failed"}
MAX_EXPORT_ROWS = 5000
MAX_SESSION_TURNS = 200


class AIHistoryError(Exception):
    def __init__(self, status_code, message, error_code, **extra):
        super().__init__(message)
        self.status_code = status_code
        self.message = message
        self.error_code = error_code
        self.extra = extra


def _utc_now():
    return datetime.datetime.now(datetime.timezone.utc)


def _iso(value=None):
    if value is None:
        value = _utc_now()
    if isinstance(value, datetime.datetime):
        parsed = value
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=datetime.timezone.utc)
        return parsed.astimezone(datetime.timezone.utc).isoformat().replace("+00:00", "Z")
    if isinstance(value, datetime.date):
        return value.isoformat()
    return str(value or "")


def _coerce_duration_ms(value):
    try:
        number = int(round(float(value)))
    except Exception:
        return None
    if number <= 0:
        return None
    return number


def _duration_ms(started, finished):
    if not isinstance(started, datetime.datetime) or not isinstance(finished, datetime.datetime):
        return None
    if started.tzinfo is None:
        started = started.replace(tzinfo=datetime.timezone.utc)
    if finished.tzinfo is None:
        finished = finished.replace(tzinfo=datetime.timezone.utc)
    elapsed = (finished.astimezone(datetime.timezone.utc) - started.astimezone(datetime.timezone.utc)).total_seconds()
    return _coerce_duration_ms(max(0.001, elapsed) * 1000)


def _serialize(value):
    if isinstance(value, (datetime.datetime, datetime.date)):
        return _iso(value)
    if isinstance(value, uuid.UUID):
        return str(value)
    if isinstance(value, decimal.Decimal):
        return float(value)
    if isinstance(value, list):
        return [_serialize(item) for item in value]
    if isinstance(value, dict):
        return {str(key): _serialize(item) for key, item in value.items()}
    return value


def _clean_text(value, limit=None):
    text = str(value or "").strip()
    if limit is not None:
        return text[:limit]
    return text


def _normalize_session_id(value):
    text = _clean_text(value, 160)
    if not text:
        return ""
    return re.sub(r"[^A-Za-z0-9_.:-]", "", text)[:160]


def _normalize_request_id(value):
    text = _clean_text(value, 160)
    if not text:
        return ""
    return re.sub(r"[^A-Za-z0-9_.:-]", "", text)[:160]


def _session_title(message):
    title = re.sub(r"\s+", " ", _clean_text(message, 160))
    return title or "AI Agent 세션"


def _safe_json(value, depth=0):
    if depth > 5:
        return _clean_text(value, 500)
    if value is None or isinstance(value, (bool, int, float)):
        return value
    if isinstance(value, (datetime.datetime, datetime.date, uuid.UUID, decimal.Decimal)):
        return _serialize(value)
    if isinstance(value, str):
        return value[:12000]
    if isinstance(value, list):
        rows = [_safe_json(item, depth + 1) for item in value[:120]]
        if len(value) > 120:
            rows.append({"_truncated": True, "omitted": len(value) - 120})
        return rows
    if isinstance(value, dict):
        result = {}
        for index, key in enumerate(value.keys()):
            if index >= 120:
                result["_truncated"] = True
                result["_omitted_keys"] = len(value.keys()) - 120
                break
            result[_clean_text(key, 100)] = _safe_json(value.get(key), depth + 1)
        return result
    return _clean_text(value, 1000)


def _parse_datetime(value, field):
    if value in (None, ""):
        return None
    if isinstance(value, datetime.datetime):
        parsed = value
    elif isinstance(value, datetime.date):
        parsed = datetime.datetime.combine(value, datetime.time.min, tzinfo=datetime.timezone.utc)
    else:
        raw = str(value).strip()
        try:
            parsed = datetime.datetime.fromisoformat(raw.replace("Z", "+00:00"))
        except Exception:
            raise AIHistoryError(400, f"{field} 형식이 올바르지 않습니다.", "INVALID_AI_HISTORY_DATETIME", field=field)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=datetime.timezone.utc)
    return parsed.astimezone(datetime.timezone.utc)


def _parse_date(value, field):
    if value in (None, ""):
        return None
    if isinstance(value, datetime.datetime):
        return value.date()
    if isinstance(value, datetime.date):
        return value
    try:
        return datetime.date.fromisoformat(str(value).strip()[:10])
    except Exception:
        raise AIHistoryError(400, f"{field} 형식은 YYYY-MM-DD여야 합니다.", "INVALID_AI_HISTORY_DATE", field=field)


def _range_bounds(filters):
    filters = filters or {}
    start_at = _parse_datetime(filters.get("start_at"), "start_at")
    end_at = _parse_datetime(filters.get("end_at"), "end_at")
    start_date = _parse_date(filters.get("start_date"), "start_date")
    end_date = _parse_date(filters.get("end_date"), "end_date")

    if start_at is None and start_date is not None:
        start_at = datetime.datetime.combine(start_date, datetime.time.min, tzinfo=datetime.timezone.utc)
    if end_at is None and end_date is not None:
        end_at = datetime.datetime.combine(end_date, datetime.time.max, tzinfo=datetime.timezone.utc)
    if start_at is None and end_at is not None:
        start_at = datetime.datetime.combine(end_at.date(), datetime.time.min, tzinfo=datetime.timezone.utc)
    if end_at is None and start_at is not None:
        end_at = datetime.datetime.combine(start_at.date(), datetime.time.max, tzinfo=datetime.timezone.utc)
    if start_at is not None and end_at is not None:
        if start_at > end_at:
            raise AIHistoryError(400, "시작일은 종료일보다 늦을 수 없습니다.", "INVALID_AI_HISTORY_DATE_RANGE")
        if (end_at.date() - start_at.date()).days > 366:
            raise AIHistoryError(400, "한 번에 처리할 수 있는 기간은 최대 366일입니다.", "AI_HISTORY_RANGE_TOO_LARGE")
    return start_at, end_at


def _limit(value, default=60, maximum=200):
    try:
        number = int(value)
    except Exception:
        number = default
    return max(1, min(number, maximum))


def _offset(value):
    try:
        number = int(value)
    except Exception:
        number = 0
    return max(0, number)


def _browser_from_user_agent(user_agent):
    ua = _clean_text(user_agent, 1000)
    lowered = ua.lower()
    browser = "Unknown"
    version = ""
    patterns = [
        ("Edge", r"Edg/([0-9.]+)"),
        ("Opera", r"OPR/([0-9.]+)"),
        ("Chrome", r"Chrome/([0-9.]+)"),
        ("Firefox", r"Firefox/([0-9.]+)"),
        ("Safari", r"Version/([0-9.]+).*Safari/"),
        ("Internet Explorer", r"(?:MSIE |rv:)([0-9.]+)"),
        ("curl", r"curl/([0-9.]+)"),
    ]
    for label, pattern in patterns:
        match = re.search(pattern, ua)
        if match:
            browser = label
            version = match.group(1)
            break

    platform = "Unknown"
    if "windows" in lowered:
        platform = "Windows"
    elif "iphone" in lowered or "ipad" in lowered:
        platform = "iOS"
    elif "android" in lowered:
        platform = "Android"
    elif "mac os x" in lowered or "macintosh" in lowered:
        platform = "macOS"
    elif "linux" in lowered:
        platform = "Linux"
    return {"name": browser, "version": version, "platform": platform, "user_agent": ua}


def _client_metadata(request_meta):
    request_meta = request_meta if isinstance(request_meta, dict) else {}
    user_agent = request_meta.get("user_agent") or request_meta.get("User-Agent") or ""
    return {
        "ip": _clean_text(request_meta.get("ip") or request_meta.get("remote_addr"), 120),
        "remote_addr": _clean_text(request_meta.get("remote_addr"), 120),
        "forwarded_for": _clean_text(request_meta.get("forwarded_for"), 500),
        "user_agent": _clean_text(user_agent, 1000),
        "browser": _browser_from_user_agent(user_agent),
    }


def _compact_screen(screen):
    screen = screen if isinstance(screen, dict) else {}
    modal = screen.get("modal") if isinstance(screen.get("modal"), dict) else {}
    return {
        "url": _clean_text(screen.get("url"), 1200),
        "route": _clean_text(screen.get("route"), 300),
        "title": _clean_text(screen.get("title"), 300),
        "context_summary": _clean_text(screen.get("context_summary"), 500),
        "viewport": _safe_json(screen.get("viewport") or {}),
        "headings": _safe_json(screen.get("headings") or []),
        "modal": {
            "open": bool(modal.get("open")),
            "title": _clean_text(modal.get("title"), 300),
        },
    }


def _compact_request_payload(payload, message):
    payload = payload if isinstance(payload, dict) else {}
    return {
        "request_id": _normalize_request_id(payload.get("request_id") or payload.get("idempotency_key")),
        "message": _clean_text(message, 12000),
        "history": _safe_json(payload.get("history") or []),
        "screen": _compact_screen(payload.get("screen")),
        "events": _safe_json((payload.get("events") or [])[-30:] if isinstance(payload.get("events"), list) else []),
        "selection": _safe_json(payload.get("selection") or {}),
    }


def _row(row):
    raw = dict(row) if row is not None else None
    item = _serialize(raw) if raw is not None else None
    if item is None:
        return None
    metadata = item.get("metadata") if isinstance(item.get("metadata"), dict) else {}
    response_payload = item.get("response_payload") if isinstance(item.get("response_payload"), dict) else {}
    client = metadata.get("client") if isinstance(metadata.get("client"), dict) else {}
    browser = client.get("browser") if isinstance(client.get("browser"), dict) else {}
    screen = metadata.get("screen") if isinstance(metadata.get("screen"), dict) else {}
    duration_ms = (
        _coerce_duration_ms(metadata.get("duration_ms"))
        or _coerce_duration_ms(response_payload.get("duration_ms"))
        or _duration_ms(raw.get("started_at"), raw.get("finished_at"))
    )
    item["ip"] = client.get("ip") or ""
    item["browser"] = browser
    item["browser_label"] = " ".join([part for part in [browser.get("name"), browser.get("version")] if part]).strip()
    item["platform"] = browser.get("platform") or ""
    item["route"] = screen.get("route") or ""
    item["context_summary"] = screen.get("context_summary") or ""
    item["duration_ms"] = duration_ms or 0
    item["request_id"] = _normalize_request_id(
        item.get("request_id")
        or metadata.get("request_id")
        or ((item.get("request_payload") or {}).get("request_id") if isinstance(item.get("request_payload"), dict) else "")
    )
    item["session_id"] = _normalize_session_id(item.get("session_id") or item.get("group_session_id") or item.get("id"))
    item["provider_session_id"] = _normalize_session_id(item.get("provider_session_id"))
    try:
        item["turn_count"] = int(item.get("turn_count") or 1)
    except Exception:
        item["turn_count"] = 1
    try:
        item["turn_index"] = int(item.get("turn_index") or 1)
    except Exception:
        item["turn_index"] = 1
    return item


class AIHistory:
    AIHistoryError = AIHistoryError

    def ensure_table(self, env=None):
        with connect(env=env) as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    CREATE TABLE IF NOT EXISTS ai_agent_histories (
                        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                        request_id TEXT NOT NULL DEFAULT '',
                        session_id TEXT NOT NULL DEFAULT '',
                        provider_session_id TEXT NOT NULL DEFAULT '',
                        session_title TEXT NOT NULL DEFAULT '',
                        turn_index INTEGER NOT NULL DEFAULT 1,
                        agent_type TEXT NOT NULL DEFAULT '',
                        agent_label TEXT NOT NULL DEFAULT '',
                        model TEXT NOT NULL DEFAULT '',
                        status TEXT NOT NULL DEFAULT 'succeeded' CHECK (status IN ('succeeded', 'failed')),
                        request_message TEXT NOT NULL DEFAULT '',
                        response_answer TEXT NOT NULL DEFAULT '',
                        response_summary TEXT NOT NULL DEFAULT '',
                        request_payload JSONB NOT NULL DEFAULT '{}'::jsonb,
                        response_payload JSONB NOT NULL DEFAULT '{}'::jsonb,
                        test_run_id TEXT,
                        metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
                        error_code TEXT NOT NULL DEFAULT '',
                        error_message TEXT NOT NULL DEFAULT '',
                        started_at TIMESTAMPTZ NOT NULL DEFAULT now(),
                        finished_at TIMESTAMPTZ,
                        created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
                        updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
                    )
                    """
                )
                cursor.execute(
                    """
                    ALTER TABLE ai_agent_histories
                        ADD COLUMN IF NOT EXISTS request_id TEXT NOT NULL DEFAULT '',
                        ADD COLUMN IF NOT EXISTS session_id TEXT NOT NULL DEFAULT '',
                        ADD COLUMN IF NOT EXISTS provider_session_id TEXT NOT NULL DEFAULT '',
                        ADD COLUMN IF NOT EXISTS session_title TEXT NOT NULL DEFAULT '',
                        ADD COLUMN IF NOT EXISTS turn_index INTEGER NOT NULL DEFAULT 1
                    """
                )
                cursor.execute(
                    "CREATE INDEX IF NOT EXISTS ai_agent_histories_created_at_idx ON ai_agent_histories(created_at DESC)"
                )
                cursor.execute(
                    "CREATE INDEX IF NOT EXISTS ai_agent_histories_agent_type_idx ON ai_agent_histories(agent_type, created_at DESC)"
                )
                cursor.execute(
                    "CREATE INDEX IF NOT EXISTS ai_agent_histories_status_idx ON ai_agent_histories(status, created_at DESC)"
                )
                cursor.execute(
                    "CREATE INDEX IF NOT EXISTS ai_agent_histories_session_idx ON ai_agent_histories(agent_type, session_id, created_at DESC)"
                )
                cursor.execute(
                    """
                    CREATE INDEX IF NOT EXISTS ai_agent_histories_request_idx
                    ON ai_agent_histories(agent_type, request_id)
                    WHERE request_id <> ''
                    """
                )
                cursor.execute(
                    """
                    CREATE INDEX IF NOT EXISTS ai_agent_histories_provider_session_idx
                    ON ai_agent_histories(agent_type, provider_session_id, created_at DESC)
                    WHERE provider_session_id <> ''
                    """
                )

    def record(self, payload=None, response=None, provider=None, request_meta=None, status="succeeded", error=None, started_at=None, env=None):
        if status not in STATUSES:
            status = "failed" if error else "succeeded"
        payload = payload if isinstance(payload, dict) else {}
        response = response if isinstance(response, dict) else {}
        provider = provider if isinstance(provider, dict) else {}
        message = _clean_text(payload.get("message"), 12000)
        public_provider = provider.get("public") if isinstance(provider.get("public"), dict) else provider
        agent_type = _clean_text(public_provider.get("type") or provider.get("type"), 80)
        response_provider = response.get("provider") if isinstance(response.get("provider"), dict) else {}
        session_id = _normalize_session_id(
            payload.get("session_id")
            or payload.get("client_session_id")
            or payload.get("conversation_id")
            or response.get("session_id")
            or response_provider.get("session_id")
            or public_provider.get("session_id")
        )
        provider_session_id = _normalize_session_id(
            response.get("provider_session_id")
            or response_provider.get("provider_session_id")
            or public_provider.get("provider_session_id")
        )
        request_id = _normalize_request_id(payload.get("request_id") or payload.get("idempotency_key"))
        agent_label = _clean_text(public_provider.get("label") or provider.get("label"), 120)
        model = _clean_text(public_provider.get("model") or provider.get("model"), 200)
        response_answer = _clean_text(response.get("answer"), 12000)
        response_summary = _clean_text(response.get("summary"), 4000)
        request_payload = _compact_request_payload(payload, message)
        response_payload = _safe_json(response)
        test_run_id = _clean_text(payload.get("test_run_id"), 120) or None
        metadata = {
            "request_id": request_id,
            "client": _client_metadata(request_meta or payload.get("request_meta")),
            "screen": _compact_screen(payload.get("screen")),
            "provider": _safe_json(public_provider),
            "session": {
                "session_id": session_id,
                "provider_session_id": provider_session_id,
                "title": _session_title(message),
            },
        }
        error_code = _clean_text(getattr(error, "code", None) or getattr(error, "error_code", None), 120)
        error_message = _clean_text(getattr(error, "message", None) or (str(error) if error else ""), 2000)
        started = _parse_datetime(started_at, "started_at") if started_at else _utc_now()
        finished = _utc_now()
        duration_ms = _coerce_duration_ms(response.get("duration_ms")) or _duration_ms(started, finished)
        if duration_ms is not None:
            metadata["duration_ms"] = duration_ms
            if "duration_ms" not in response:
                response["duration_ms"] = duration_ms

        self.ensure_table(env=env)
        with connect(env=env) as connection:
            with connection.cursor() as cursor:
                if request_id:
                    cursor.execute(
                        """
                        SELECT *
                        FROM ai_agent_histories
                        WHERE agent_type = %s AND request_id = %s
                        ORDER BY created_at ASC
                        LIMIT 1
                        FOR UPDATE
                        """,
                        (agent_type, request_id),
                    )
                    existing = cursor.fetchone()
                    if existing:
                        existing_status = _clean_text(existing.get("status"), 40)
                        existing_provider_session_id = _normalize_session_id(existing.get("provider_session_id"))
                        if existing_status != "succeeded" and status == "succeeded":
                            cursor.execute(
                                """
                                UPDATE ai_agent_histories
                                   SET provider_session_id = %s,
                                       session_title = %s,
                                       agent_label = %s,
                                       model = %s,
                                       status = %s,
                                       request_message = %s,
                                       response_answer = %s,
                                       response_summary = %s,
                                       request_payload = %s,
                                       response_payload = %s,
                                       test_run_id = %s,
                                       metadata = %s,
                                       error_code = '',
                                       error_message = '',
                                       finished_at = %s,
                                       updated_at = now()
                                 WHERE id = %s
                                 RETURNING *
                                """,
                                (
                                    provider_session_id or existing_provider_session_id,
                                    _session_title(message),
                                    agent_label,
                                    model,
                                    status,
                                    message,
                                    response_answer,
                                    response_summary,
                                    Jsonb(request_payload),
                                    Jsonb(response_payload),
                                    test_run_id,
                                    Jsonb(metadata),
                                    finished,
                                    existing.get("id"),
                                ),
                            )
                            return _row(cursor.fetchone())
                        if provider_session_id and not existing_provider_session_id:
                            cursor.execute(
                                """
                                UPDATE ai_agent_histories
                                   SET provider_session_id = %s,
                                       metadata = jsonb_set(metadata, '{session,provider_session_id}', to_jsonb(%s::text), true),
                                       updated_at = now()
                                 WHERE id = %s
                                 RETURNING *
                                """,
                                (provider_session_id, provider_session_id, existing.get("id")),
                            )
                            return _row(cursor.fetchone())
                        return _row(existing)

                turn_index = 1
                if session_id:
                    cursor.execute(
                        """
                        SELECT COALESCE(MAX(turn_index), 0) + 1 AS next_turn
                        FROM ai_agent_histories
                        WHERE agent_type = %s AND session_id = %s
                        """,
                        (agent_type, session_id),
                    )
                    turn_index = int((cursor.fetchone() or {}).get("next_turn") or 1)
                cursor.execute(
                    """
                    INSERT INTO ai_agent_histories(
                        request_id, session_id, provider_session_id, session_title, turn_index,
                        agent_type, agent_label, model, status,
                        request_message, response_answer, response_summary,
                        request_payload, response_payload, test_run_id, metadata,
                        error_code, error_message, started_at, finished_at
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    RETURNING *
                    """,
                    (
                        request_id,
                        session_id,
                        provider_session_id,
                        _session_title(message),
                        turn_index,
                        agent_type,
                        agent_label,
                        model,
                        status,
                        message,
                        response_answer,
                        response_summary,
                        Jsonb(request_payload),
                        Jsonb(response_payload),
                        test_run_id,
                        Jsonb(metadata),
                        error_code,
                        error_message,
                        started,
                        finished,
                    ),
                )
                return _row(cursor.fetchone())

    def _where(self, filters):
        filters = filters or {}
        clauses = []
        params = []
        start_at, end_at = _range_bounds(filters)
        if start_at is not None:
            clauses.append("created_at >= %s")
            params.append(start_at)
        if end_at is not None:
            clauses.append("created_at <= %s")
            params.append(end_at)
        agent = _clean_text(filters.get("agent") or filters.get("agent_type"), 80)
        if agent:
            clauses.append("agent_type = %s")
            params.append(agent)
        status = _clean_text(filters.get("status"), 40)
        if status:
            clauses.append("status = %s")
            params.append(status)
        query = _clean_text(filters.get("q") or filters.get("query"), 200)
        if query:
            clauses.append("(request_message ILIKE %s OR response_answer ILIKE %s OR response_summary ILIKE %s)")
            pattern = f"%{query}%"
            params.extend([pattern, pattern, pattern])
        test_run_id = _clean_text(filters.get("test_run_id"), 120)
        if test_run_id:
            clauses.append("test_run_id = %s")
            params.append(test_run_id)
        session_id = _normalize_session_id(filters.get("session_id") or filters.get("conversation_id"))
        if session_id:
            clauses.append("(session_id = %s OR (session_id = '' AND id::text = %s))")
            params.extend([session_id, session_id])
        return clauses, params

    def list(self, filters=None, limit=60, offset=0, env=None):
        filters = filters or {}
        limit = _limit(filters.get("limit") or limit)
        offset = _offset(filters.get("offset") or offset)
        clauses, params = self._where(filters)
        where_sql = (" WHERE " + " AND ".join(clauses)) if clauses else ""
        self.ensure_table(env=env)
        with connect(env=env) as connection:
            with connection.cursor() as cursor:
                cursor.execute(f"SELECT count(*) AS count FROM ai_agent_histories{where_sql}", params)
                total = int((cursor.fetchone() or {}).get("count") or 0)
                cursor.execute(
                    f"""
                    SELECT *
                    FROM ai_agent_histories
                    {where_sql}
                    ORDER BY created_at DESC
                    LIMIT %s OFFSET %s
                    """,
                    [*params, limit, offset],
                )
                items = [_row(row) for row in cursor.fetchall()]
        return {"items": items, "total": total, "limit": limit, "offset": offset}

    def sessions(self, filters=None, limit=60, offset=0, env=None):
        filters = filters or {}
        limit = _limit(filters.get("limit") or limit)
        offset = _offset(filters.get("offset") or offset)
        clauses, params = self._where(filters)
        where_sql = (" WHERE " + " AND ".join(clauses)) if clauses else ""
        group_expr = "COALESCE(NULLIF(session_id, ''), id::text)"
        self.ensure_table(env=env)
        with connect(env=env) as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    f"""
                    WITH filtered AS (
                        SELECT *, {group_expr} AS group_session_id
                        FROM ai_agent_histories
                        {where_sql}
                    ),
                    grouped AS (
                        SELECT agent_type, group_session_id
                        FROM filtered
                        GROUP BY agent_type, group_session_id
                    )
                    SELECT count(*) AS count FROM grouped
                    """,
                    params,
                )
                total = int((cursor.fetchone() or {}).get("count") or 0)
                cursor.execute(
                    f"""
                    WITH filtered AS (
                        SELECT *, {group_expr} AS group_session_id
                        FROM ai_agent_histories
                        {where_sql}
                    ),
                    ranked AS (
                        SELECT
                            filtered.*,
                            count(*) OVER (PARTITION BY agent_type, group_session_id) AS turn_count,
                            min(created_at) OVER (PARTITION BY agent_type, group_session_id) AS session_started_at,
                            max(created_at) OVER (PARTITION BY agent_type, group_session_id) AS session_last_at,
                            row_number() OVER (PARTITION BY agent_type, group_session_id ORDER BY created_at DESC) AS rn
                        FROM filtered
                    )
                    SELECT *
                    FROM ranked
                    WHERE rn = 1
                    ORDER BY session_last_at DESC
                    LIMIT %s OFFSET %s
                    """,
                    [*params, limit, offset],
                )
                items = [_row(row) for row in cursor.fetchall()]
        return {"items": items, "total": total, "limit": limit, "offset": offset}

    def session(self, session_id, agent_type=None, env=None):
        session_id = _normalize_session_id(session_id)
        agent_type = _clean_text(agent_type, 80)
        if not session_id:
            raise AIHistoryError(400, "session_id는 필수입니다.", "AI_HISTORY_SESSION_ID_REQUIRED")
        clauses = ["(session_id = %s OR (session_id = '' AND id::text = %s))"]
        params = [session_id, session_id]
        if agent_type:
            clauses.append("agent_type = %s")
            params.append(agent_type)
        self.ensure_table(env=env)
        with connect(env=env) as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT *
                    FROM ai_agent_histories
                    WHERE """ + " AND ".join(clauses) + """
                    ORDER BY created_at ASC
                    LIMIT %s
                    """,
                    [*params, MAX_SESSION_TURNS],
                )
                turns = [_row(row) for row in cursor.fetchall()]
        if not turns:
            raise AIHistoryError(404, "AI Agent 세션 히스토리를 찾을 수 없습니다.", "AI_HISTORY_SESSION_NOT_FOUND")
        latest = dict(turns[-1])
        latest["turns"] = turns
        latest["turn_count"] = len(turns)
        latest["session_id"] = session_id
        latest["session_started_at"] = turns[0].get("created_at")
        latest["session_last_at"] = turns[-1].get("created_at")
        return latest

    def delete_session(self, session_id, agent_type=None, env=None):
        session_id = _normalize_session_id(session_id)
        agent_type = _clean_text(agent_type, 80)
        if not session_id:
            raise AIHistoryError(400, "session_id는 필수입니다.", "AI_HISTORY_SESSION_ID_REQUIRED")
        clauses = ["(session_id = %s OR (session_id = '' AND id::text = %s))"]
        params = [session_id, session_id]
        if agent_type:
            clauses.append("agent_type = %s")
            params.append(agent_type)
        self.ensure_table(env=env)
        with connect(env=env) as connection:
            with connection.cursor() as cursor:
                cursor.execute("DELETE FROM ai_agent_histories WHERE " + " AND ".join(clauses), params)
                return {"deleted": cursor.rowcount > 0, "deleted_count": cursor.rowcount}

    def provider_session_id(self, agent_type, session_id, env=None):
        agent_type = _clean_text(agent_type, 80)
        session_id = _normalize_session_id(session_id)
        if not agent_type or not session_id:
            return ""
        self.ensure_table(env=env)
        with connect(env=env) as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT provider_session_id
                    FROM ai_agent_histories
                    WHERE agent_type = %s
                      AND session_id = %s
                      AND provider_session_id <> ''
                    ORDER BY created_at DESC
                    LIMIT 1
                    """,
                    (agent_type, session_id),
                )
                row = cursor.fetchone()
        return _normalize_session_id((row or {}).get("provider_session_id"))

    def detail(self, history_id, env=None):
        history_id = _clean_text(history_id, 120)
        if not history_id:
            raise AIHistoryError(400, "history_id는 필수입니다.", "AI_HISTORY_ID_REQUIRED")
        self.ensure_table(env=env)
        with connect(env=env) as connection:
            with connection.cursor() as cursor:
                cursor.execute("SELECT * FROM ai_agent_histories WHERE id = %s", (history_id,))
                row = cursor.fetchone()
                if row is None:
                    raise AIHistoryError(404, "AI Agent 히스토리를 찾을 수 없습니다.", "AI_HISTORY_NOT_FOUND")
                return _row(row)

    def delete(self, history_id, env=None):
        history_id = _clean_text(history_id, 120)
        if not history_id:
            raise AIHistoryError(400, "history_id는 필수입니다.", "AI_HISTORY_ID_REQUIRED")
        self.ensure_table(env=env)
        with connect(env=env) as connection:
            with connection.cursor() as cursor:
                cursor.execute("DELETE FROM ai_agent_histories WHERE id = %s", (history_id,))
                return {"deleted": cursor.rowcount > 0, "deleted_count": cursor.rowcount}

    def delete_range(self, filters=None, env=None):
        filters = filters or {}
        if not any(filters.get(key) for key in ["start_date", "end_date", "start_at", "end_at"]):
            raise AIHistoryError(400, "삭제할 기간을 입력하세요.", "AI_HISTORY_DELETE_RANGE_REQUIRED")
        clauses, params = self._where(filters)
        if not clauses:
            raise AIHistoryError(400, "삭제 조건이 올바르지 않습니다.", "AI_HISTORY_DELETE_RANGE_REQUIRED")
        self.ensure_table(env=env)
        with connect(env=env) as connection:
            with connection.cursor() as cursor:
                cursor.execute("DELETE FROM ai_agent_histories WHERE " + " AND ".join(clauses), params)
                return {"deleted_count": cursor.rowcount}

    def export(self, filters=None, export_format="json", env=None):
        filters = dict(filters or {})
        filters["limit"] = min(_limit(filters.get("limit"), default=MAX_EXPORT_ROWS, maximum=MAX_EXPORT_ROWS), MAX_EXPORT_ROWS)
        filters["offset"] = 0
        rows = self.list(filters=filters, limit=filters["limit"], offset=0, env=env)["items"]
        export_format = _clean_text(export_format or filters.get("format") or "json", 20).lower()
        generated_at = _iso()
        if export_format == "csv":
            content = self._csv(rows)
            return {
                "content": content.encode("utf-8-sig"),
                "content_type": "text/csv; charset=utf-8",
                "filename": f"ai-agent-history-{generated_at[:10]}.csv",
            }
        payload = {"generated_at": generated_at, "count": len(rows), "items": rows}
        content = json.dumps(payload, ensure_ascii=False, indent=2)
        return {
            "content": content.encode("utf-8"),
            "content_type": "application/json; charset=utf-8",
            "filename": f"ai-agent-history-{generated_at[:10]}.json",
        }

    def _csv(self, rows):
        output = io.StringIO()
        fieldnames = [
            "id",
            "request_id",
            "session_id",
            "provider_session_id",
            "turn_index",
            "created_at",
            "agent_type",
            "agent_label",
            "model",
            "status",
            "duration_ms",
            "ip",
            "browser",
            "platform",
            "route",
            "context_summary",
            "request_message",
            "response_answer",
            "error_code",
            "error_message",
        ]
        writer = csv.DictWriter(output, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow({
                "id": row.get("id"),
                "request_id": row.get("request_id"),
                "session_id": row.get("session_id"),
                "provider_session_id": row.get("provider_session_id"),
                "turn_index": row.get("turn_index"),
                "created_at": row.get("created_at"),
                "agent_type": row.get("agent_type"),
                "agent_label": row.get("agent_label"),
                "model": row.get("model"),
                "status": row.get("status"),
                "duration_ms": row.get("duration_ms"),
                "ip": row.get("ip"),
                "browser": row.get("browser_label"),
                "platform": row.get("platform"),
                "route": row.get("route"),
                "context_summary": row.get("context_summary"),
                "request_message": row.get("request_message"),
                "response_answer": row.get("response_answer"),
                "error_code": row.get("error_code"),
                "error_message": row.get("error_message"),
            })
        return output.getvalue()


Model = AIHistory()
