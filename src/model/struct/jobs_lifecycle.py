from psycopg.types.json import Jsonb

connect = wiz.model("db/postgres").connect
shared = wiz.model("struct/jobs_shared")
JobError = shared.JobError


class JobLifecycleMixin:
    def cancel(self, job_id, env=None):
        with connect(env=env) as connection:
            with connection.cursor() as cursor:
                job = self._fetch_job(cursor, job_id)
                if job["status"] not in {"pending", "running"}:
                    raise JobError(409, "완료된 job은 cancel할 수 없습니다.", "JOB_ALREADY_TERMINAL")
                cursor.execute(
                    """
                    UPDATE jobs
                    SET status = 'canceled', finished_at = now()
                    WHERE id = %s
                    """,
                    (job_id,),
                )
                cursor.execute(
                    """
                    UPDATE job_steps
                    SET status = 'canceled', finished_at = now()
                    WHERE job_id = %s AND status IN ('pending', 'running')
                    """,
                    (job_id,),
                )
                cursor.execute(
                    """
                    INSERT INTO job_logs(job_id, stream, message, test_run_id, metadata)
                    VALUES (%s, 'system', 'job canceled', %s, %s)
                    """,
                    (job_id, job["test_run_id"], Jsonb({"event": "cancel"})),
                )
                return self.detail(job_id, connection=connection)

    def retry(self, job_id, env=None):
        with connect(env=env) as connection:
            with connection.cursor() as cursor:
                job = self._fetch_job(cursor, job_id)
                if job["status"] != "failed":
                    raise JobError(409, "failed job만 retry할 수 있습니다.", "JOB_RETRY_NOT_ALLOWED")
                cursor.execute("SELECT * FROM job_steps WHERE job_id = %s ORDER BY order_no", (job_id,))
                steps = cursor.fetchall()
                retry_attempt = int((job["metadata"] or {}).get("retry_attempt", 0)) + 1
                metadata = dict(job["metadata"] or {})
                metadata.update({"retry_of": str(job["id"]), "retry_attempt": retry_attempt})
                cursor.execute(
                    """
                    INSERT INTO jobs(type, requested_payload, test_run_id, metadata)
                    VALUES (%s, %s, %s, %s)
                    RETURNING *
                    """,
                    (job["type"], Jsonb(job["requested_payload"]), job["test_run_id"], Jsonb(metadata)),
                )
                retried = cursor.fetchone()
                for step in steps:
                    step_metadata = dict(step["metadata"] or {})
                    step_metadata.update({"retry_of_step": str(step["id"])})
                    cursor.execute(
                        """
                        INSERT INTO job_steps(job_id, name, order_no, test_run_id, metadata)
                        VALUES (%s, %s, %s, %s, %s)
                        """,
                        (retried["id"], step["name"], step["order_no"], job["test_run_id"], Jsonb(step_metadata)),
                    )
                cursor.execute(
                    """
                    INSERT INTO job_logs(job_id, stream, message, test_run_id, metadata)
                    VALUES (%s, 'system', 'job retry created', %s, %s)
                    """,
                    (retried["id"], job["test_run_id"], Jsonb({"retry_of": str(job["id"])})),
                )
                return {
                    "original_job_id": str(job["id"]),
                    "retried_job": self.detail(str(retried["id"]), connection=connection),
                }


Model = JobLifecycleMixin
