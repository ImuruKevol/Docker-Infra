JOB_STATUSES = {"pending", "running", "succeeded", "failed", "canceled"}
STEP_STATUSES = {"pending", "running", "succeeded", "failed", "skipped", "canceled"}
STREAMS = {"stdout", "stderr", "system"}

JOB_TRANSITIONS = {
    "pending": {"running", "canceled"},
    "running": {"succeeded", "failed", "canceled"},
    "succeeded": set(),
    "failed": set(),
    "canceled": set(),
}
STEP_TRANSITIONS = {
    "pending": {"running", "skipped", "canceled"},
    "running": {"succeeded", "failed", "canceled"},
    "succeeded": set(),
    "failed": set(),
    "skipped": set(),
    "canceled": set(),
}


class JobError(Exception):
    def __init__(self, status_code, message, error_code, **extra):
        super().__init__(message)
        self.status_code = status_code
        self.message = message
        self.error_code = error_code
        self.extra = extra


def job_to_dict(row):
    if row is None:
        return None
    return {
        "id": str(row["id"]),
        "type": row["type"],
        "status": row["status"],
        "requested_payload": row["requested_payload"],
        "result_payload": row["result_payload"],
        "test_run_id": row["test_run_id"],
        "metadata": row["metadata"],
        "started_at": row["started_at"],
        "finished_at": row["finished_at"],
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
    }


def step_to_dict(row):
    if row is None:
        return None
    return {
        "id": str(row["id"]),
        "job_id": str(row["job_id"]),
        "name": row["name"],
        "status": row["status"],
        "order_no": row["order_no"],
        "test_run_id": row["test_run_id"],
        "metadata": row["metadata"],
        "started_at": row["started_at"],
        "finished_at": row["finished_at"],
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
    }


def log_to_dict(row):
    if row is None:
        return None
    return {
        "id": str(row["id"]),
        "job_id": str(row["job_id"]),
        "step_id": None if row["step_id"] is None else str(row["step_id"]),
        "stream": row["stream"],
        "message": row["message"],
        "test_run_id": row["test_run_id"],
        "metadata": row["metadata"],
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
    }


class JobsShared:
    JOB_STATUSES = JOB_STATUSES
    STEP_STATUSES = STEP_STATUSES
    STREAMS = STREAMS
    JOB_TRANSITIONS = JOB_TRANSITIONS
    STEP_TRANSITIONS = STEP_TRANSITIONS
    JobError = JobError
    job_to_dict = staticmethod(job_to_dict)
    step_to_dict = staticmethod(step_to_dict)
    log_to_dict = staticmethod(log_to_dict)


Model = JobsShared()
