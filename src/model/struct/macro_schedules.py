import datetime
import hashlib
import hmac
import ipaddress
import json
import secrets
import shlex
import shutil
import uuid

from psycopg.types.json import Jsonb


config = wiz.config("docker_infra")
connect = wiz.model("db/postgres").connect
cron_files = wiz.model("struct/cron_files")
runner = wiz.model("struct/macros_runner")
shared = wiz.model("struct/macros_shared")

MacroError = shared.MacroError
SCOPE_GLOBAL = shared.SCOPE_GLOBAL

CRON_ROUTE = "/api/macros/schedules/run"
CRON_TOKEN_HEADER = "X-Docker-Infra-Cron-Token"
CRON_FILE_PREFIX = "docker-infra-macro-"
CRON_MARKER = "docker-infra-macro-schedule"
MAX_SCHEDULE_TARGETS = 50


def _utcnow():
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def _hash_token(token):
    return hashlib.sha256(str(token or "").encode("utf-8")).hexdigest()


def _bool_value(value, default=True):
    if value in (None, ""):
        return default
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"1", "true", "yes", "on"}


def _uuid_text(value, field_name, required=True):
    raw = str(value or "").strip()
    if not raw:
        if required:
            raise MacroError(400, f"{field_name}는 필수입니다.", f"{field_name.upper()}_REQUIRED")
        return ""
    try:
        return str(uuid.UUID(raw))
    except (TypeError, ValueError):
        raise MacroError(400, f"{field_name} 형식이 올바르지 않습니다.", f"{field_name.upper()}_INVALID")


def _clamp_int(value, default, minimum, maximum):
    try:
        number = int(value)
    except (TypeError, ValueError):
        number = default
    return max(minimum, min(maximum, number))


def _time_text(value, default="02:00"):
    text = str(value or "").strip()
    try:
        hour_text, minute_text = text.split(":", 1)
        hour = int(hour_text)
        minute = int(minute_text)
    except (TypeError, ValueError):
        return default
    if hour < 0 or hour > 23 or minute < 0 or minute > 59:
        return default
    return f"{hour:02d}:{minute:02d}"


def _schedule_type(value):
    return "monthly" if str(value or "").strip().lower() == "monthly" else "weekly"


def _cron_schedule(schedule):
    hour_text, minute_text = _time_text(schedule.get("schedule_time")).split(":", 1)
    hour = int(hour_text)
    minute = int(minute_text)
    if _schedule_type(schedule.get("schedule_type")) == "monthly":
        day = _clamp_int(schedule.get("schedule_month_day"), 1, 1, 31)
        return f"{minute} {hour} {day} * *"
    weekdays = _schedule_weekdays(schedule.get("schedule_weekdays"), fallback=schedule.get("schedule_weekday"))
    cron_weekdays = ",".join(str(0 if weekday == 6 else weekday + 1) for weekday in weekdays)
    return f"{minute} {hour} * * {cron_weekdays}"


def _base_url(env=None):
    values = config.runtime_env(env)
    base = (
        values.get("DOCKER_INFRA_MACRO_CRON_BASE_URL")
        or values.get("DOCKER_INFRA_INTERNAL_BASE_URL")
        or "http://127.0.0.1:3001"
    )
    return str(base).rstrip("/")


def _curl_command(schedule_id, token, env=None):
    curl = shutil.which("curl") or "/usr/bin/curl"
    url = f"{_base_url(env)}{CRON_ROUTE}"
    header = f"{CRON_TOKEN_HEADER}: {token}"
    data = f"schedule_id={schedule_id}"
    return f"{shlex.quote(curl)} -fsS -X POST -H {shlex.quote(header)} -d {shlex.quote(data)} {shlex.quote(url)} >/dev/null 2>&1"


def _json_list(value, message, error_code):
    if value in (None, ""):
        return []
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except Exception:
            raise MacroError(400, message, error_code)
    if not isinstance(value, list):
        raise MacroError(400, message, error_code)
    return value


def _schedule_weekdays(value, fallback=None):
    rows = []
    if value not in (None, ""):
        rows = _json_list(value, "실행 요일 목록이 올바르지 않습니다.", "MACRO_SCHEDULE_WEEKDAYS_INVALID")
    if not rows and fallback not in (None, ""):
        rows = [fallback]
    days = []
    seen = set()
    for raw in rows:
        day = _clamp_int(raw, 0, 0, 6)
        if day in seen:
            continue
        seen.add(day)
        days.append(day)
    return days or [0]


def _target_key(target_type, target):
    if target_type == "service":
        return f"service:{target.get('service_target_id') or target.get('id') or ''}"
    return f"server:{target.get('node_id') or ''}"


def _target_value(target_type, raw):
    if target_type == "service":
        return str(raw.get("service_target_id") or raw.get("id") or raw.get("value") or "").strip()
    return str(raw.get("node_id") or raw.get("id") or raw.get("value") or "").strip()


def _normal_targets(target_type, value):
    rows = _json_list(value, "실행 대상 목록이 올바르지 않습니다.", "MACRO_SCHEDULE_TARGETS_INVALID")
    targets = []
    seen = set()
    for raw in rows:
        if not isinstance(raw, dict):
            continue
        node_id = _uuid_text(raw.get("node_id"), "node_id")
        if target_type == "service":
            service_target_id = str(raw.get("service_target_id") or raw.get("id") or raw.get("value") or "").strip()
            if not service_target_id:
                raise MacroError(400, "서비스 실행 대상이 올바르지 않습니다.", "MACRO_SCHEDULE_SERVICE_TARGET_INVALID")
            item = {
                "target_type": "service",
                "node_id": node_id,
                "service_target_id": service_target_id,
                "service_id": str(raw.get("service_id") or "").strip(),
                "service_name": str(raw.get("service_name") or "").strip(),
                "service_namespace": str(raw.get("service_namespace") or "").strip(),
                "container_id": str(raw.get("container_id") or "").strip(),
                "container_name": str(raw.get("container_name") or "").strip(),
                "container_display_name": str(raw.get("container_display_name") or "").strip(),
                "label": str(raw.get("label") or raw.get("service_name") or "서비스").strip(),
            }
        else:
            item = {
                "target_type": "server",
                "node_id": node_id,
                "label": str(raw.get("label") or raw.get("node_name") or raw.get("name") or node_id).strip(),
            }
        key = _target_key(target_type, item)
        if key in seen:
            continue
        seen.add(key)
        targets.append(item)
    if not targets:
        raise MacroError(400, "실행 대상을 하나 이상 선택해주세요.", "MACRO_SCHEDULE_TARGET_REQUIRED")
    if len(targets) > MAX_SCHEDULE_TARGETS:
        raise MacroError(400, f"스케줄 대상은 최대 {MAX_SCHEDULE_TARGETS}개까지 선택할 수 있습니다.", "MACRO_SCHEDULE_TARGET_LIMIT")
    return targets


def _is_loopback(value):
    try:
        return ipaddress.ip_address(str(value or "").strip()).is_loopback
    except ValueError:
        return str(value or "").strip().lower() in {"localhost"}


class MacroSchedules:
    MacroError = MacroError
    CRON_TOKEN_HEADER = CRON_TOKEN_HEADER

    def ensure_schema(self, env=None):
        with connect(env=env) as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    CREATE TABLE IF NOT EXISTS shell_macro_schedules (
                        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                        macro_id UUID NOT NULL REFERENCES shell_macros(id) ON DELETE CASCADE,
                        name TEXT NOT NULL DEFAULT '',
                        enabled BOOLEAN NOT NULL DEFAULT true,
                        schedule_type TEXT NOT NULL DEFAULT 'weekly' CHECK (schedule_type IN ('weekly', 'monthly')),
                        schedule_weekday INTEGER NOT NULL DEFAULT 0 CHECK (schedule_weekday BETWEEN 0 AND 6),
                        schedule_weekdays JSONB NOT NULL DEFAULT '[0]'::jsonb,
                        schedule_month_day INTEGER NOT NULL DEFAULT 1 CHECK (schedule_month_day BETWEEN 1 AND 31),
                        schedule_time TEXT NOT NULL DEFAULT '02:00',
                        target_type TEXT NOT NULL DEFAULT 'server' CHECK (target_type IN ('server', 'service')),
                        targets JSONB NOT NULL DEFAULT '[]'::jsonb,
                        args TEXT NOT NULL DEFAULT '',
                        token_hash TEXT,
                        cron_file TEXT NOT NULL DEFAULT '',
                        last_run_at TIMESTAMPTZ,
                        last_result JSONB NOT NULL DEFAULT '{}'::jsonb,
                        test_run_id TEXT,
                        metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
                        created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
                        updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
                    )
                    """
                )
                cursor.execute("ALTER TABLE shell_macro_schedules ADD COLUMN IF NOT EXISTS schedule_weekdays JSONB NOT NULL DEFAULT '[0]'::jsonb")
                cursor.execute(
                    """
                    UPDATE shell_macro_schedules
                    SET schedule_weekdays = jsonb_build_array(COALESCE(schedule_weekday, 0))
                    WHERE schedule_weekdays IS NULL OR schedule_weekdays = '[]'::jsonb
                    """
                )
                cursor.execute("CREATE INDEX IF NOT EXISTS shell_macro_schedules_macro_idx ON shell_macro_schedules(macro_id, created_at DESC)")
                cursor.execute("CREATE INDEX IF NOT EXISTS shell_macro_schedules_enabled_idx ON shell_macro_schedules(enabled, schedule_type)")
                cursor.execute(
                    """
                    CREATE INDEX IF NOT EXISTS operation_logs_macro_schedule_idx
                        ON operation_logs((metadata->>'schedule_id'), created_at DESC)
                        WHERE type = 'macro.run'
                    """
                )
                cursor.execute("DROP TRIGGER IF EXISTS shell_macro_schedules_set_updated_at ON shell_macro_schedules")
                cursor.execute(
                    """
                    CREATE TRIGGER shell_macro_schedules_set_updated_at
                        BEFORE UPDATE ON shell_macro_schedules
                        FOR EACH ROW EXECUTE FUNCTION docker_infra_set_updated_at()
                    """
                )

    def _fetch_macro(self, cursor, macro_id):
        cursor.execute("SELECT id, name, scope_type, node_id FROM shell_macros WHERE id = %s", (macro_id,))
        row = cursor.fetchone()
        if row is None:
            raise MacroError(404, "매크로를 찾을 수 없습니다.", "MACRO_NOT_FOUND")
        if row["scope_type"] != SCOPE_GLOBAL or row["node_id"] is not None:
            raise MacroError(409, "전역 매크로만 스케줄을 등록할 수 있습니다.", "GLOBAL_MACRO_REQUIRED")
        return row

    def _select_sql(self):
        return """
            SELECT ms.*, COALESCE(h.history, '[]'::jsonb) AS history
            FROM shell_macro_schedules ms
            LEFT JOIN LATERAL (
                SELECT jsonb_agg(
                    jsonb_build_object(
                        'id', ol.id::text,
                        'status', ol.status,
                        'message', ol.message,
                        'target_id', ol.target_id,
                        'requested_payload', ol.requested_payload,
                        'result_payload', ol.result_payload,
                        'output', ol.output,
                        'metadata', ol.metadata,
                        'started_at', ol.started_at,
                        'finished_at', ol.finished_at,
                        'created_at', ol.created_at,
                        'updated_at', ol.updated_at
                    )
                    ORDER BY ol.created_at DESC
                ) AS history
                FROM (
                    SELECT *
                    FROM operation_logs ol
                    WHERE ol.type = 'macro.run'
                      AND ol.metadata->>'schedule_id' = ms.id::text
                    ORDER BY ol.created_at DESC
                    LIMIT 10
                ) ol
            ) h ON true
        """

    def _fetch(self, cursor, schedule_id, macro_id=None):
        query = self._select_sql() + " WHERE ms.id = %s"
        params = [schedule_id]
        if macro_id:
            query += " AND ms.macro_id = %s"
            params.append(macro_id)
        cursor.execute(query, params)
        row = cursor.fetchone()
        if row is None:
            raise MacroError(404, "매크로 스케줄을 찾을 수 없습니다.", "MACRO_SCHEDULE_NOT_FOUND")
        return row

    def _validate_nodes(self, cursor, targets):
        node_ids = sorted({target["node_id"] for target in targets})
        cursor.execute("SELECT id::text AS id FROM nodes WHERE id = ANY(%s::uuid[])", (node_ids,))
        found = {row["id"] for row in cursor.fetchall()}
        missing = [node_id for node_id in node_ids if node_id not in found]
        if missing:
            raise MacroError(404, "선택한 서버를 찾을 수 없습니다.", "MACRO_SCHEDULE_NODE_NOT_FOUND", node_ids=missing)

    def _sync_cron_file(self, schedule, token, env=None):
        schedule = dict(schedule or {})
        file_name = f"{CRON_FILE_PREFIX}{str(schedule['id']).replace('-', '')}"
        if not schedule.get("enabled"):
            cron_files.remove(file_name, env=env, directory_env="DOCKER_INFRA_MACRO_CRON_DIR", prefix=CRON_FILE_PREFIX)
            return {"cron_file": ""}
        if not token:
            raise MacroError(500, "매크로 스케줄 cron 토큰을 만들 수 없습니다.", "MACRO_SCHEDULE_TOKEN_REQUIRED")
        try:
            result = cron_files.write(
                file_name,
                _cron_schedule(schedule),
                _curl_command(schedule["id"], token, env=env),
                f"{CRON_MARKER} {schedule['id']}",
                env=env,
                directory_env="DOCKER_INFRA_MACRO_CRON_DIR",
                user_env="DOCKER_INFRA_MACRO_CRON_USER",
                prefix=CRON_FILE_PREFIX,
            )
        except cron_files.CronFileError as exc:
            raise MacroError(exc.status_code, exc.message, exc.error_code, **exc.extra)
        return {"cron_file": result.get("path") or ""}

    def list(self, macro_id=None, env=None):
        self.ensure_schema(env=env)
        where = []
        params = []
        if macro_id:
            where.append("ms.macro_id = %s")
            params.append(_uuid_text(macro_id, "macro_id"))
        sql = self._select_sql()
        if where:
            sql += " WHERE " + " AND ".join(where)
        sql += " ORDER BY ms.enabled DESC, ms.created_at DESC"
        with connect(env=env) as connection:
            with connection.cursor() as cursor:
                cursor.execute(sql, params)
                return [shared.macro_schedule_row(row) for row in cursor.fetchall()]

    def save(self, payload=None, env=None):
        payload = payload or {}
        macro_id = _uuid_text(payload.get("macro_id"), "macro_id")
        schedule_id = _uuid_text(payload.get("id") or payload.get("schedule_id"), "schedule_id", required=False)
        target_type = "service" if str(payload.get("target_type") or "").strip().lower() == "service" else "server"
        targets = _normal_targets(target_type, payload.get("targets"))
        enabled = _bool_value(payload.get("enabled"), True)
        token = secrets.token_urlsafe(32) if enabled else None
        schedule_weekdays = _schedule_weekdays(payload.get("schedule_weekdays"), fallback=payload.get("schedule_weekday"))
        schedule_values = {
            "name": str(payload.get("name") or "").strip(),
            "enabled": enabled,
            "schedule_type": _schedule_type(payload.get("schedule_type")),
            "schedule_weekday": schedule_weekdays[0],
            "schedule_weekdays": schedule_weekdays,
            "schedule_month_day": _clamp_int(payload.get("schedule_month_day"), 1, 1, 31),
            "schedule_time": _time_text(payload.get("schedule_time")),
            "target_type": target_type,
            "targets": targets,
            "args": str(payload.get("args") or "").strip(),
            "token_hash": _hash_token(token) if token else None,
            "test_run_id": str(payload.get("test_run_id") or "").strip() or None,
        }

        self.ensure_schema(env=env)
        with connect(env=env) as connection:
            with connection.cursor() as cursor:
                self._fetch_macro(cursor, macro_id)
                self._validate_nodes(cursor, targets)
                if schedule_id:
                    self._fetch(cursor, schedule_id, macro_id=macro_id)
                    cursor.execute(
                        """
                        UPDATE shell_macro_schedules
                        SET name = %s,
                            enabled = %s,
                            schedule_type = %s,
                            schedule_weekday = %s,
                            schedule_weekdays = %s,
                            schedule_month_day = %s,
                            schedule_time = %s,
                            target_type = %s,
                            targets = %s,
                            args = %s,
                            token_hash = %s,
                            test_run_id = COALESCE(%s, test_run_id),
                            metadata = metadata || %s,
                            updated_at = now()
                        WHERE id = %s AND macro_id = %s
                        RETURNING *
                        """,
                        (
                            schedule_values["name"],
                            schedule_values["enabled"],
                            schedule_values["schedule_type"],
                            schedule_values["schedule_weekday"],
                            Jsonb(schedule_values["schedule_weekdays"]),
                            schedule_values["schedule_month_day"],
                            schedule_values["schedule_time"],
                            schedule_values["target_type"],
                            Jsonb(schedule_values["targets"]),
                            schedule_values["args"],
                            schedule_values["token_hash"],
                            schedule_values["test_run_id"],
                            Jsonb({"source": "web_ui", "cron_route": CRON_ROUTE, "updated_at": _utcnow()}),
                            schedule_id,
                            macro_id,
                        ),
                    )
                else:
                    cursor.execute(
                        """
                        INSERT INTO shell_macro_schedules(
                            macro_id, name, enabled, schedule_type, schedule_weekday, schedule_weekdays, schedule_month_day,
                            schedule_time, target_type, targets, args, token_hash, test_run_id, metadata
                        )
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                        RETURNING *
                        """,
                        (
                            macro_id,
                            schedule_values["name"],
                            schedule_values["enabled"],
                            schedule_values["schedule_type"],
                            schedule_values["schedule_weekday"],
                            Jsonb(schedule_values["schedule_weekdays"]),
                            schedule_values["schedule_month_day"],
                            schedule_values["schedule_time"],
                            schedule_values["target_type"],
                            Jsonb(schedule_values["targets"]),
                            schedule_values["args"],
                            schedule_values["token_hash"],
                            schedule_values["test_run_id"],
                            Jsonb({"source": "web_ui", "cron_route": CRON_ROUTE, "created_at": _utcnow()}),
                        ),
                    )
                row = cursor.fetchone()
                cron_result = self._sync_cron_file(row, token, env=env)
                cursor.execute(
                    """
                    UPDATE shell_macro_schedules
                    SET cron_file = %s,
                        metadata = metadata || %s,
                        updated_at = now()
                    WHERE id = %s
                    RETURNING *
                    """,
                    (cron_result["cron_file"], Jsonb({"cron_file": cron_result["cron_file"]}), row["id"]),
                )
                return shared.macro_schedule_row(cursor.fetchone())

    def delete(self, schedule_id, macro_id=None, env=None):
        schedule_id = _uuid_text(schedule_id, "schedule_id")
        macro_id = _uuid_text(macro_id, "macro_id", required=False) if macro_id else ""
        self.ensure_schema(env=env)
        with connect(env=env) as connection:
            with connection.cursor() as cursor:
                row = self._fetch(cursor, schedule_id, macro_id=macro_id or None)
                self._sync_cron_file({"id": row["id"], "enabled": False}, None, env=env)
                cursor.execute("DELETE FROM shell_macro_schedules WHERE id = %s", (schedule_id,))
                return {"deleted": True, "schedule": shared.macro_schedule_row(row)}

    def delete_for_macro(self, macro_id, env=None):
        macro_id = _uuid_text(macro_id, "macro_id")
        schedules = self.list(macro_id=macro_id, env=env)
        for schedule in schedules:
            self.delete(schedule["id"], macro_id=macro_id, env=env)
        return {"deleted": len(schedules)}

    def verify_token(self, schedule_id, token, env=None):
        if not schedule_id or not token:
            return False
        schedule_id = _uuid_text(schedule_id, "schedule_id", required=False)
        if not schedule_id:
            return False
        self.ensure_schema(env=env)
        with connect(env=env) as connection:
            with connection.cursor() as cursor:
                cursor.execute("SELECT token_hash, enabled FROM shell_macro_schedules WHERE id = %s", (schedule_id,))
                row = cursor.fetchone()
        expected = row["token_hash"] if row else None
        return bool(row and row["enabled"] and expected) and hmac.compare_digest(str(expected), _hash_token(token))

    def request_allowed(self, request):
        forwarded = (request.headers.get("X-Forwarded-For") or "").split(",", 1)[0].strip()
        remote = forwarded or request.remote_addr
        return _is_loopback(remote)

    def run(self, schedule_id, env=None):
        schedule_id = _uuid_text(schedule_id, "schedule_id")
        self.ensure_schema(env=env)
        with connect(env=env) as connection:
            with connection.cursor() as cursor:
                schedule = shared.macro_schedule_row(self._fetch(cursor, schedule_id))

        if not schedule.get("enabled"):
            raise MacroError(409, "비활성화된 매크로 스케줄입니다.", "MACRO_SCHEDULE_DISABLED")

        operations = []
        errors = []
        for target in schedule.get("targets") or []:
            payload = {
                "macro_id": schedule["macro_id"],
                "node_id": target.get("node_id"),
                "args": schedule.get("args") or "",
                "target_type": target.get("target_type") or schedule.get("target_type"),
                "schedule_id": schedule["id"],
                "schedule_name": schedule.get("name") or "",
                "service_target_id": target.get("service_target_id"),
                "service_id": target.get("service_id"),
                "service_name": target.get("service_name"),
                "service_namespace": target.get("service_namespace"),
                "container_id": target.get("container_id"),
                "container_name": target.get("container_name"),
                "container_display_name": target.get("container_display_name"),
            }
            try:
                operations.append(runner.run(payload, env=env))
            except MacroError as exc:
                errors.append({"target": target, "message": exc.message, "error_code": exc.error_code})
            except Exception as exc:
                errors.append({"target": target, "message": str(exc), "error_code": "MACRO_SCHEDULE_RUN_FAILED"})

        result = {
            "processed": len(schedule.get("targets") or []),
            "scheduled": len(operations),
            "failed": len(errors),
            "operation_ids": [item.get("id") for item in operations if item.get("id")],
            "errors": errors,
        }
        with connect(env=env) as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    UPDATE shell_macro_schedules
                    SET last_run_at = now(),
                        last_result = %s,
                        updated_at = now()
                    WHERE id = %s
                    RETURNING *
                    """,
                    (Jsonb(result), schedule_id),
                )
                updated = shared.macro_schedule_row(cursor.fetchone())
        return {"scheduled": bool(operations), "schedule": updated, "operations": operations, "errors": errors, "result": result}


Model = MacroSchedules()
