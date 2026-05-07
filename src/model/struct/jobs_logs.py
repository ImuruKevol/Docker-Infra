from psycopg.types.json import Jsonb

connect = wiz.model("db/postgres").connect
secret_masking = wiz.model("struct/secret_masking")
mask_text = secret_masking.mask_text
shared = wiz.model("struct/jobs_shared")
JobError = shared.JobError
STREAMS = shared.STREAMS
_log_to_dict = shared.log_to_dict


class JobLogMixin:
    def append_log(self, job_id, message, stream="system", step_ref=None, metadata=None, secret_values=None, env=None):
        if stream not in STREAMS:
            raise JobError(400, "지원하지 않는 log stream입니다.", "INVALID_LOG_STREAM")
        if message is None:
            raise JobError(400, "log message는 필수입니다.", "LOG_MESSAGE_REQUIRED")
        metadata = dict(metadata or {})
        inline_secret_values = metadata.pop("secret_values", [])
        all_secret_values = []
        all_secret_values.extend(inline_secret_values or [])
        all_secret_values.extend(secret_values or [])
        with connect(env=env) as connection:
            with connection.cursor() as cursor:
                job = self._fetch_job(cursor, job_id)
                step_id = None
                if step_ref is not None:
                    step_id = self._fetch_step(cursor, job_id, step_ref)["id"]
                masked_message = mask_text(message, secret_values=all_secret_values, connection=connection, env=env)
                metadata.setdefault("masked", masked_message != str(message))
                cursor.execute(
                    """
                    INSERT INTO job_logs(job_id, step_id, stream, message, test_run_id, metadata)
                    VALUES (%s, %s, %s, %s, %s, %s)
                    RETURNING *
                    """,
                    (job_id, step_id, stream, masked_message, job["test_run_id"], Jsonb(metadata)),
                )
                return _log_to_dict(cursor.fetchone())

    def search_logs(self, job_id=None, query=None, stream=None, test_run_id=None, limit=100, env=None):
        if stream and stream not in STREAMS:
            raise JobError(400, "지원하지 않는 log stream입니다.", "INVALID_LOG_STREAM")
        limit = max(1, min(int(limit or 100), 500))
        clauses = []
        params = []
        with connect(env=env) as connection:
            with connection.cursor() as cursor:
                if job_id:
                    self._fetch_job(cursor, job_id)
                    clauses.append("job_id = %s")
                    params.append(job_id)
                if stream:
                    clauses.append("stream = %s")
                    params.append(stream)
                if test_run_id:
                    clauses.append("test_run_id = %s")
                    params.append(test_run_id)
                if query:
                    masked_query = mask_text(query, connection=connection, env=env)
                    clauses.append("message ILIKE %s")
                    params.append(f"%{masked_query}%")
                where = "" if not clauses else "WHERE " + " AND ".join(clauses)
                cursor.execute(
                    f"""
                    SELECT *
                    FROM job_logs
                    {where}
                    ORDER BY created_at DESC, id DESC
                    LIMIT %s
                    """,
                    [*params, limit],
                )
                return [_log_to_dict(row) for row in cursor.fetchall()]

    def download_logs(self, job_id, env=None):
        detail = self.detail(job_id, env=env)
        lines = []
        for log in detail["logs"]:
            timestamp = log["created_at"].isoformat() if hasattr(log["created_at"], "isoformat") else str(log["created_at"])
            step = "" if log["step_id"] is None else f" step={log['step_id']}"
            lines.append(f"{timestamp} {log['stream']}{step} {log['message']}")
        return {
            "job_id": detail["id"],
            "filename": f"job-{detail['id']}.log",
            "content_type": "text/plain; charset=utf-8",
            "content": "\n".join(lines) + ("\n" if lines else ""),
        }


Model = JobLogMixin
