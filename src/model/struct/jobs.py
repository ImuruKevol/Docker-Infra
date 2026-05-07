from psycopg.types.json import Jsonb

connect = wiz.model("db/postgres").connect
shared = wiz.model("struct/jobs_shared")
JobLogMixin = wiz.model("struct/jobs_logs")
JobLifecycleMixin = wiz.model("struct/jobs_lifecycle")
JOB_STATUSES = shared.JOB_STATUSES
STEP_STATUSES = shared.STEP_STATUSES
JOB_TRANSITIONS = shared.JOB_TRANSITIONS
STEP_TRANSITIONS = shared.STEP_TRANSITIONS
JobError = shared.JobError
_job_to_dict = shared.job_to_dict
_step_to_dict = shared.step_to_dict
_log_to_dict = shared.log_to_dict


class JobRepository(JobLogMixin, JobLifecycleMixin):
    JobError = JobError

    def create(self, type, steps=None, requested_payload=None, test_run_id=None, metadata=None, env=None):
        if not type:
            raise JobError(400, "job type은 필수입니다.", "JOB_TYPE_REQUIRED")
        steps = steps or []
        requested_payload = requested_payload or {}
        metadata = metadata or {}
        with connect(env=env) as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    INSERT INTO jobs(type, requested_payload, test_run_id, metadata)
                    VALUES (%s, %s, %s, %s)
                    RETURNING *
                    """,
                    (type, Jsonb(requested_payload), test_run_id, Jsonb(metadata)),
                )
                job = cursor.fetchone()
                for index, step in enumerate(steps, start=1):
                    name = step.get("name") if isinstance(step, dict) else str(step)
                    order_no = step.get("order_no", index) if isinstance(step, dict) else index
                    step_metadata = step.get("metadata", {}) if isinstance(step, dict) else {}
                    if not name:
                        raise JobError(400, "step name은 필수입니다.", "STEP_NAME_REQUIRED")
                    cursor.execute(
                        """
                        INSERT INTO job_steps(job_id, name, order_no, test_run_id, metadata)
                        VALUES (%s, %s, %s, %s, %s)
                        """,
                        (job["id"], name, order_no, test_run_id, Jsonb(step_metadata)),
                    )
                return self.detail(str(job["id"]), connection=connection)

    def list(self, status=None, test_run_id=None, limit=50, env=None):
        if status and status not in JOB_STATUSES:
            raise JobError(400, "지원하지 않는 job status입니다.", "INVALID_JOB_STATUS")
        limit = max(1, min(int(limit or 50), 200))
        clauses = []
        params = []
        if status:
            clauses.append("status = %s")
            params.append(status)
        if test_run_id:
            clauses.append("test_run_id = %s")
            params.append(test_run_id)
        where = "" if not clauses else "WHERE " + " AND ".join(clauses)
        with connect(env=env) as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    f"""
                    SELECT *
                    FROM jobs
                    {where}
                    ORDER BY created_at DESC
                    LIMIT %s
                    """,
                    [*params, limit],
                )
                return [_job_to_dict(row) for row in cursor.fetchall()]

    def _fetch_job(self, cursor, job_id):
        cursor.execute("SELECT * FROM jobs WHERE id = %s", (job_id,))
        row = cursor.fetchone()
        if row is None:
            raise JobError(404, "job을 찾을 수 없습니다.", "JOB_NOT_FOUND")
        return row

    def _fetch_step(self, cursor, job_id, step_ref):
        if isinstance(step_ref, int) or str(step_ref).isdigit():
            cursor.execute("SELECT * FROM job_steps WHERE job_id = %s AND order_no = %s", (job_id, int(step_ref)))
        else:
            cursor.execute("SELECT * FROM job_steps WHERE job_id = %s AND id = %s", (job_id, step_ref))
        row = cursor.fetchone()
        if row is None:
            raise JobError(404, "step을 찾을 수 없습니다.", "STEP_NOT_FOUND")
        return row

    def detail(self, job_id, connection=None, env=None):
        def read(conn):
            with conn.cursor() as cursor:
                job = self._fetch_job(cursor, job_id)
                cursor.execute("SELECT * FROM job_steps WHERE job_id = %s ORDER BY order_no", (job_id,))
                steps = [_step_to_dict(row) for row in cursor.fetchall()]
                cursor.execute("SELECT * FROM job_logs WHERE job_id = %s ORDER BY created_at, id", (job_id,))
                logs = [_log_to_dict(row) for row in cursor.fetchall()]
                result = _job_to_dict(job)
                result["steps"] = steps
                result["logs"] = logs
                return result

        if connection is not None:
            return read(connection)
        with connect(env=env) as conn:
            return read(conn)

    def transition_job(self, job_id, status, result_payload=None, env=None):
        if status not in JOB_STATUSES:
            raise JobError(400, "지원하지 않는 job status입니다.", "INVALID_JOB_STATUS")
        with connect(env=env) as connection:
            with connection.cursor() as cursor:
                job = self._fetch_job(cursor, job_id)
                if status != job["status"] and status not in JOB_TRANSITIONS[job["status"]]:
                    raise JobError(409, "허용되지 않는 job 상태 전이입니다.", "INVALID_JOB_TRANSITION")
                if result_payload is None:
                    cursor.execute(
                        """
                        UPDATE jobs
                        SET status = %s,
                            started_at = CASE WHEN %s = 'running' AND started_at IS NULL THEN now() ELSE started_at END,
                            finished_at = CASE WHEN %s IN ('succeeded', 'failed', 'canceled') THEN now() ELSE finished_at END
                        WHERE id = %s
                        RETURNING *
                        """,
                        (status, status, status, job_id),
                    )
                else:
                    cursor.execute(
                        """
                        UPDATE jobs
                        SET status = %s,
                            result_payload = %s,
                            started_at = CASE WHEN %s = 'running' AND started_at IS NULL THEN now() ELSE started_at END,
                            finished_at = CASE WHEN %s IN ('succeeded', 'failed', 'canceled') THEN now() ELSE finished_at END
                        WHERE id = %s
                        RETURNING *
                        """,
                        (status, Jsonb(result_payload), status, status, job_id),
                    )
                return self.detail(job_id, connection=connection)

    def update_step_status(self, job_id, step_ref, status, metadata=None, env=None):
        if status not in STEP_STATUSES:
            raise JobError(400, "지원하지 않는 step status입니다.", "INVALID_STEP_STATUS")
        with connect(env=env) as connection:
            with connection.cursor() as cursor:
                job = self._fetch_job(cursor, job_id)
                step = self._fetch_step(cursor, job_id, step_ref)
                if status != step["status"] and status not in STEP_TRANSITIONS[step["status"]]:
                    raise JobError(409, "허용되지 않는 step 상태 전이입니다.", "INVALID_STEP_TRANSITION")
                if job["status"] == "pending" and status == "running":
                    cursor.execute(
                        "UPDATE jobs SET status = 'running', started_at = COALESCE(started_at, now()) WHERE id = %s",
                        (job_id,),
                    )
                if metadata is None:
                    cursor.execute(
                        """
                        UPDATE job_steps
                        SET status = %s,
                            started_at = CASE WHEN %s = 'running' AND started_at IS NULL THEN now() ELSE started_at END,
                            finished_at = CASE WHEN %s IN ('succeeded', 'failed', 'skipped', 'canceled') THEN now() ELSE finished_at END
                        WHERE id = %s
                        RETURNING *
                        """,
                        (status, status, status, step["id"]),
                    )
                else:
                    cursor.execute(
                        """
                        UPDATE job_steps
                        SET status = %s,
                            metadata = %s,
                            started_at = CASE WHEN %s = 'running' AND started_at IS NULL THEN now() ELSE started_at END,
                            finished_at = CASE WHEN %s IN ('succeeded', 'failed', 'skipped', 'canceled') THEN now() ELSE finished_at END
                        WHERE id = %s
                        RETURNING *
                        """,
                        (status, Jsonb(metadata), status, status, step["id"]),
                    )
                updated = cursor.fetchone()
                self._sync_job_from_steps(cursor, job_id)
                result = self.detail(job_id, connection=connection)
                result["updated_step"] = _step_to_dict(updated)
                return result

    def _sync_job_from_steps(self, cursor, job_id):
        cursor.execute("SELECT status FROM job_steps WHERE job_id = %s ORDER BY order_no", (job_id,))
        statuses = [row["status"] for row in cursor.fetchall()]
        if not statuses:
            return
        next_status = None
        if any(status == "failed" for status in statuses):
            next_status = "failed"
        elif any(status == "canceled" for status in statuses):
            next_status = "canceled"
        elif all(status in {"succeeded", "skipped"} for status in statuses):
            next_status = "succeeded"
        if next_status:
            cursor.execute(
                """
                UPDATE jobs
                SET status = %s,
                    finished_at = now()
                WHERE id = %s AND status IN ('pending', 'running')
                """,
                (next_status, job_id),
            )

    def delete_by_test_run_id(self, test_run_id, env=None):
        with connect(env=env) as connection:
            with connection.cursor() as cursor:
                cursor.execute("DELETE FROM jobs WHERE test_run_id = %s", (test_run_id,))
                return cursor.rowcount


Model = JobRepository()
