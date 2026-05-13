def _error_payload(exc, default_code=500, default_error="UNEXPECTED_ERROR"):
    if hasattr(exc, "status_code") and hasattr(exc, "message") and hasattr(exc, "error_code"):
        extra = getattr(exc, "extra", {}) or {}
        return exc.status_code, {"message": exc.message, "error_code": exc.error_code, **extra}
    return default_code, {"message": str(exc), "error_code": default_error}


def _macro_request():
    from flask import request

    if request.form or request.files:
        return request.form.to_dict(flat=True), request.files.getlist("files")
    return wiz.request.query(), []


def load():
    macros_model = wiz.model("struct").macros
    code = 200
    payload = {}

    try:
        macros = macros_model.list({"scope_type": macros_model.SCOPE_GLOBAL})
        payload = {
            "macros": macros,
            "summary": {
                "total": len(macros),
                "enabled": len([item for item in macros if item.get("enabled")]),
                "disabled": len([item for item in macros if not item.get("enabled")]),
            },
        }
    except macros_model.MacroError as exc:
        code = exc.status_code
        payload = {"message": exc.message, "error_code": exc.error_code, **exc.extra}
    except RuntimeError as exc:
        code = 503
        payload = {"message": str(exc), "error_code": "DATABASE_UNAVAILABLE"}
    except Exception as exc:
        code, payload = _error_payload(exc)

    wiz.response.status(code, **payload)


def save_macro():
    macros_model = wiz.model("struct").macros
    body, files = _macro_request()
    code = 200
    payload = {}

    try:
        payload = {
            "macro": macros_model.save({
                **body,
                "scope_type": macros_model.SCOPE_GLOBAL,
                "node_id": None,
            }, file_storages=files)
        }
    except macros_model.MacroError as exc:
        code = exc.status_code
        payload = {"message": exc.message, "error_code": exc.error_code, **exc.extra}
    except RuntimeError as exc:
        code = 503
        payload = {"message": str(exc), "error_code": "DATABASE_UNAVAILABLE"}
    except Exception as exc:
        code, payload = _error_payload(exc)

    wiz.response.status(code, **payload)


def delete_macro():
    macros_model = wiz.model("struct").macros
    body = wiz.request.query()
    macro_id = body.get("macro_id")
    if not macro_id:
        wiz.response.status(400, message="macro_id는 필수입니다.", error_code="MACRO_ID_REQUIRED")
        return

    code = 200
    payload = {}
    try:
        payload = macros_model.delete(macro_id)
    except macros_model.MacroError as exc:
        code = exc.status_code
        payload = {"message": exc.message, "error_code": exc.error_code, **exc.extra}
    except RuntimeError as exc:
        code = 503
        payload = {"message": str(exc), "error_code": "DATABASE_UNAVAILABLE"}
    except Exception as exc:
        code, payload = _error_payload(exc)

    wiz.response.status(code, **payload)
