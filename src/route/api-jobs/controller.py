jobs = wiz.model("struct").jobs
method = wiz.request.method().upper()

if method not in ["GET", "POST"]:
    wiz.response.status(405, message="지원하지 않는 method입니다.", error_code="METHOD_NOT_ALLOWED")

code = 200
payload = {}

try:
    if method == "GET":
        payload = {
            "jobs": jobs.list(
                status=wiz.request.query("status", None),
                test_run_id=wiz.request.query("test_run_id", None),
                limit=wiz.request.query("limit", 50),
            )
        }
    else:
        body = wiz.request.query()
        payload = {
            "job": jobs.create(
                type=body.get("type"),
                steps=body.get("steps") or [],
                requested_payload=body.get("requested_payload") or {},
                test_run_id=body.get("test_run_id"),
                metadata=body.get("metadata") or {},
            )
        }
except jobs.JobError as exc:
    code = exc.status_code
    payload = {"message": exc.message, "error_code": exc.error_code, **exc.extra}
except RuntimeError as exc:
    code = 503
    payload = {"message": str(exc), "error_code": "DATABASE_UNAVAILABLE"}

wiz.response.status(code, **payload)
