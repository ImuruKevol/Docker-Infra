from flask import request


domains = wiz.model("struct").domains
method = wiz.request.method().upper()
code = 200
payload = {}

if method != "POST":
    wiz.response.status(405, message="지원하지 않는 method입니다.", error_code="METHOD_NOT_ALLOWED")
else:
    try:
        payload = domains.upload_certificate(
            zone_id=request.form.get("zone_id"),
            label=request.form.get("label"),
            cert_file=request.files.get("cert_file"),
            key_file=request.files.get("key_file"),
            chain_file=request.files.get("chain_file"),
            test_run_id=request.form.get("test_run_id"),
        )
    except domains.DomainError as exc:
        code = exc.status_code
        payload = {"message": exc.message, "error_code": exc.error_code, **exc.extra}
    except ValueError as exc:
        code = 400
        payload = {"message": str(exc), "error_code": "CERTIFICATE_UPLOAD_FAILED"}
    except RuntimeError as exc:
        code = 503
        payload = {"message": str(exc), "error_code": "DATABASE_UNAVAILABLE"}
    wiz.response.status(code, **payload)
