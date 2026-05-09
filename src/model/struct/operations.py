import datetime
import decimal
import uuid

from psycopg.types.json import Jsonb


connect = wiz.model("db/postgres").connect

STATUSES = {"pending", "running", "succeeded", "failed", "canceled"}
STREAMS = {"stdout", "stderr", "system"}


class OperationError(Exception):
    def __init__(self, status_code, message, error_code, **extra):
        super().__init__(message)
        self.status_code = status_code
        self.message = message
        self.error_code = error_code
        self.extra = extra


def _serialize(value):
    if isinstance(value, (datetime.datetime, datetime.date)):
        return value.isoformat()
    if isinstance(value, uuid.UUID):
        return str(value)
    if isinstance(value, decimal.Decimal):
        return float(value)
    if isinstance(value, list):
        return [_serialize(item) for item in value]
    if isinstance(value, dict):
        return {key: _serialize(item) for key, item in value.items()}
    return value


def _row(row):
    return _serialize(dict(row)) if row is not None else None


def _utc_now():
    return datetime.datetime.now(datetime.timezone.utc).isoformat().replace("+00:00", "Z")


class OperationRepository:
    OperationError = OperationError

    def _fetch(self, cursor, operation_id):
        cursor.execute("SELECT * FROM operation_logs WHERE id = %s", (operation_id,))
        row = cursor.fetchone()
        if row is None:
            raise OperationError(404, "operation을 찾을 수 없습니다.", "OPERATION_NOT_FOUND")
        return row

    def create(
        self,
        operation_type,
        target_type=None,
        target_id=None,
        message="",
        status="running",
        requested_payload=None,
        result_payload=None,
        metadata=None,
        test_run_id=None,
        env=None,
    ):
        if not operation_type:
            raise OperationError(400, "operation type은 필수입니다.", "OPERATION_TYPE_REQUIRED")
        if status not in STATUSES:
            raise OperationError(400, "지원하지 않는 operation status입니다.", "INVALID_OPERATION_STATUS")
        started_at = "now()" if status in {"running", "succeeded", "failed", "canceled"} else "NULL"
        finished_at = "now()" if status in {"succeeded", "failed", "canceled"} else "NULL"
        with connect(env=env) as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    f"""
                    INSERT INTO operation_logs(
                        type, target_type, target_id, status, message,
                        requested_payload, result_payload, output, test_run_id, metadata, started_at, finished_at
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, %s, '[]'::jsonb, %s, %s, {started_at}, {finished_at})
                    RETURNING *
                    """,
                    (
                        operation_type,
                        target_type,
                        str(target_id) if target_id is not None else None,
                        status,
                        message or "",
                        Jsonb(_serialize(requested_payload or {})),
                        Jsonb(_serialize(result_payload or {})),
                        test_run_id,
                        Jsonb(_serialize(metadata or {})),
                    ),
                )
                return _row(cursor.fetchone())

    def detail(self, operation_id, env=None):
        with connect(env=env) as connection:
            with connection.cursor() as cursor:
                return _row(self._fetch(cursor, operation_id))

    def list(self, filters=None, limit=50, env=None):
        filters = filters or {}
        clauses = []
        params = []
        for key in ["target_type", "target_id", "type", "status", "test_run_id"]:
            value = filters.get(key)
            if value in (None, ""):
                continue
            clauses.append(f"{key} = %s")
            params.append(str(value))
        sql = "SELECT * FROM operation_logs"
        if clauses:
            sql += " WHERE " + " AND ".join(clauses)
        sql += " ORDER BY created_at DESC LIMIT %s"
        params.append(max(1, min(int(limit or 50), 200)))
        with connect(env=env) as connection:
            with connection.cursor() as cursor:
                cursor.execute(sql, params)
                return [_row(row) for row in cursor.fetchall()]

    def status_counts(self, env=None):
        with connect(env=env) as connection:
            with connection.cursor() as cursor:
                cursor.execute("SELECT status, count(*) AS count FROM operation_logs GROUP BY status")
                return {row["status"]: int(row["count"]) for row in cursor.fetchall()}

    def transition(self, operation_id, status, message=None, result_payload=None, metadata=None, env=None):
        if status not in STATUSES:
            raise OperationError(400, "지원하지 않는 operation status입니다.", "INVALID_OPERATION_STATUS")
        terminal = status in {"succeeded", "failed", "canceled"}
        with connect(env=env) as connection:
            with connection.cursor() as cursor:
                self._fetch(cursor, operation_id)
                cursor.execute(
                    """
                    UPDATE operation_logs
                    SET status = %s,
                        message = COALESCE(%s, message),
                        result_payload = COALESCE(%s, result_payload),
                        metadata = metadata || COALESCE(%s, '{}'::jsonb),
                        finished_at = CASE WHEN %s THEN COALESCE(finished_at, now()) ELSE finished_at END,
                        started_at = CASE WHEN status = 'pending' AND %s = 'running' THEN COALESCE(started_at, now()) ELSE started_at END
                    WHERE id = %s
                    RETURNING *
                    """,
                    (
                        status,
                        message,
                        Jsonb(_serialize(result_payload)) if result_payload is not None else None,
                        Jsonb(_serialize(metadata)) if metadata is not None else None,
                        terminal,
                        status,
                        operation_id,
                    ),
                )
                return _row(cursor.fetchone())

    def append_output(self, operation_id, message, stream="system", metadata=None, secret_values=None, env=None):
        if stream not in STREAMS:
            raise OperationError(400, "지원하지 않는 output stream입니다.", "INVALID_OPERATION_STREAM")
        text = str(message or "")
        for secret in secret_values or []:
            if secret:
                text = text.replace(str(secret), "********")
        entry = {
            "stream": stream,
            "message": text,
            "metadata": _serialize(metadata or {}),
            "created_at": _utc_now(),
        }
        with connect(env=env) as connection:
            with connection.cursor() as cursor:
                self._fetch(cursor, operation_id)
                cursor.execute(
                    """
                    UPDATE operation_logs
                    SET output = output || %s::jsonb
                    WHERE id = %s
                    RETURNING *
                    """,
                    (Jsonb([entry]), operation_id),
                )
                return _row(cursor.fetchone())

    def delete_by_test_run_id(self, test_run_id, env=None):
        with connect(env=env) as connection:
            with connection.cursor() as cursor:
                cursor.execute("DELETE FROM operation_logs WHERE test_run_id = %s", (test_run_id,))
                return cursor.rowcount


Model = OperationRepository()
