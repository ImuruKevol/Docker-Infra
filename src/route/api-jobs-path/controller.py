from flask import request

jobs = wiz.model("struct").jobs
method = wiz.request.method().upper()
parts = [part for part in request.path.replace("/api/jobs/", "", 1).split("/") if part]

if not parts:
    wiz.response.status(404, message="job path를 찾을 수 없습니다.", error_code="JOB_PATH_NOT_FOUND")

job_id = parts[0]
body = wiz.request.query()
code = 200
payload = {}

try:
    if len(parts) == 1:
        if method != "GET":
            code = 405
            payload = {"message": "지원하지 않는 method입니다.", "error_code": "METHOD_NOT_ALLOWED"}
        else:
            payload = {"job": jobs.detail(job_id)}
    else:
        action = parts[1]
        if action == "status" and method in ["POST", "PATCH"]:
            payload = {
                "job": jobs.transition_job(
                    job_id,
                    body.get("status"),
                    result_payload=body.get("result_payload"),
                )
            }
        elif action == "steps" and len(parts) >= 4 and parts[3] == "status" and method in ["POST", "PATCH"]:
            payload = {
                "job": jobs.update_step_status(
                    job_id,
                    parts[2],
                    body.get("status"),
                    metadata=body.get("metadata"),
                )
            }
        elif action == "logs" and len(parts) >= 3 and parts[2] == "search" and method in ["GET", "POST"]:
            payload = {
                "logs": jobs.search_logs(
                    job_id=job_id,
                    query=body.get("query"),
                    stream=body.get("stream"),
                    limit=body.get("limit", 100),
                )
            }
        elif action == "logs" and len(parts) >= 3 and parts[2] == "download" and method == "GET":
            payload = {"download": jobs.download_logs(job_id)}
        elif action == "logs" and method == "POST":
            payload = {
                "log": jobs.append_log(
                    job_id,
                    body.get("message"),
                    stream=body.get("stream", "system"),
                    step_ref=body.get("step_id") or body.get("order_no"),
                    metadata=body.get("metadata") or {},
                    secret_values=body.get("secret_values") or [],
                )
            }
        elif action == "cancel" and method == "POST":
            payload = {"job": jobs.cancel(job_id)}
        elif action == "retry" and method == "POST":
            payload = jobs.retry(job_id)
        else:
            code = 404
            payload = {"message": "job action을 찾을 수 없습니다.", "error_code": "JOB_ACTION_NOT_FOUND"}
except jobs.JobError as exc:
    code = exc.status_code
    payload = {"message": exc.message, "error_code": exc.error_code, **exc.extra}
except RuntimeError as exc:
    code = 503
    payload = {"message": str(exc), "error_code": "DATABASE_UNAVAILABLE"}

wiz.response.status(code, **payload)
