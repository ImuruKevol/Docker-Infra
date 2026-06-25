import re


_RANDOM_CONTAINER_NAME_RE = re.compile(r"^[a-f0-9]{12,}$", re.IGNORECASE)


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


def _node_label(node):
    name = str((node or {}).get("name") or "").strip()
    host = str((node or {}).get("host") or (node or {}).get("private_host") or "").strip()
    if name and host and name != host:
        return f"{name} ({host})"
    return name or host or str((node or {}).get("id") or "")


def _public_node(node):
    return {
        "id": node.get("id"),
        "name": node.get("name"),
        "host": node.get("host"),
        "private_host": node.get("private_host"),
        "status": node.get("status"),
        "is_local_master": bool(node.get("is_local_master")),
        "runtime_summary": node.get("runtime_summary") or {},
    }


def _clean_container_name(value):
    return str(value or "").strip().lstrip("/")


def _service_key(service):
    return str((service or {}).get("id") or (service or {}).get("namespace") or (service or {}).get("name") or "").strip()


def _container_is_running(container):
    state = str((container or {}).get("state") or "").strip().lower()
    status = str((container or {}).get("status") or "").strip().lower()
    return state == "running" or status.startswith("up")


def _is_random_container_name(value):
    name = _clean_container_name(value)
    if not name:
        return True
    compact = name.replace("-", "").replace("_", "").replace(".", "")
    return len(compact) >= 12 and _RANDOM_CONTAINER_NAME_RE.match(compact) is not None


def _container_component_label(container, service):
    runtime_name = _clean_container_name((container or {}).get("runtime_service_name"))
    namespace = str((service or {}).get("namespace") or "").strip()
    if namespace and runtime_name.startswith(f"{namespace}_"):
        runtime_name = runtime_name[len(namespace) + 1:]
    elif namespace and runtime_name.startswith(f"{namespace}-"):
        runtime_name = runtime_name[len(namespace) + 1:]
    if not runtime_name:
        return ""

    parts = [part for part in runtime_name.split(".") if part]
    if not parts:
        return runtime_name
    if len(parts) > 1 and parts[1].isdigit():
        return f"{parts[0]} #{parts[1]}"
    return parts[0]


def _friendly_container_name(container, service, index):
    component_label = _container_component_label(container, service)
    if component_label:
        return component_label

    raw_name = _clean_container_name((container or {}).get("name"))
    namespace = str((service or {}).get("namespace") or "").strip()
    if raw_name:
        if namespace and raw_name.startswith(f"{namespace}_"):
            trimmed = raw_name[len(namespace) + 1:]
            if trimmed and not _is_random_container_name(trimmed):
                return trimmed
        if not _is_random_container_name(raw_name):
            return raw_name

    service_label = str((service or {}).get("name") or (service or {}).get("namespace") or "서비스").strip()
    return f"{service_label} 컨테이너 {index + 1}"


def _service_targets(nodes_model, nodes):
    targets = []
    seen = set()
    for node in nodes:
        try:
            panel = nodes_model.cached_containers_panel(node["id"])
        except Exception:
            continue
        node_name = _node_label(node)
        for group in panel.get("service_groups") or []:
            service = group.get("service") or {}
            for index, container in enumerate(group.get("containers") or []):
                if not _container_is_running(container):
                    continue
                container_ref = container.get("id") or container.get("name") or str(index)
                service_key = _service_key(service)
                container_raw_name = _clean_container_name(container.get("name"))
                container_name = container_raw_name or (str(container.get("id") or "")[:12] if container.get("id") else "")
                target_id = f"{node['id']}:{service_key or 'service'}:{container_ref}"
                if target_id in seen:
                    continue
                seen.add(target_id)
                targets.append({
                    "id": target_id,
                    "node_id": node.get("id"),
                    "node_name": node_name,
                    "node_host": node.get("host") or node.get("private_host"),
                    "service_key": service_key,
                    "service_id": service.get("id"),
                    "service_name": service.get("name") or service.get("namespace"),
                    "service_namespace": service.get("namespace"),
                    "container_id": container.get("id"),
                    "container_name": container_name,
                    "container_raw_name": container_raw_name,
                    "container_display_name": _friendly_container_name(container, service, index),
                    "container_state": container.get("state"),
                    "container_status": container.get("status"),
                    "runtime_service_name": container.get("runtime_service_name"),
                })
    return targets


def load():
    macros_model = wiz.model("struct").macros
    nodes_model = wiz.model("struct").nodes
    code = 200
    payload = {}

    try:
        macros = macros_model.list({"scope_type": macros_model.SCOPE_GLOBAL})
        nodes = nodes_model.list_with_runtime_summary()
        payload = {
            "macros": macros,
            "nodes": [_public_node(node) for node in nodes],
            "service_targets": _service_targets(nodes_model, nodes),
        }
    except macros_model.MacroError as exc:
        code = exc.status_code
        payload = {"message": exc.message, "error_code": exc.error_code, **exc.extra}
    except nodes_model.NodeError as exc:
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
                "enabled": True,
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


def save_schedule():
    macros_model = wiz.model("struct").macros
    body = wiz.request.query()
    macro_id = body.get("macro_id")
    if not macro_id:
        wiz.response.status(400, message="macro_id는 필수입니다.", error_code="MACRO_ID_REQUIRED")
        return

    code = 200
    payload = {}
    try:
        schedule = macros_model.save_schedule(body)
        payload = {
            "schedule": schedule,
            "schedules": macros_model.list_schedules(macro_id=macro_id),
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


def delete_schedule():
    macros_model = wiz.model("struct").macros
    body = wiz.request.query()
    schedule_id = body.get("schedule_id")
    macro_id = body.get("macro_id")
    if not schedule_id:
        wiz.response.status(400, message="schedule_id는 필수입니다.", error_code="MACRO_SCHEDULE_ID_REQUIRED")
        return

    code = 200
    payload = {}
    try:
        deleted = macros_model.delete_schedule(schedule_id, macro_id=macro_id)
        payload = {
            **deleted,
            "schedules": macros_model.list_schedules(macro_id=macro_id) if macro_id else [],
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


def schedule_history():
    macros_model = wiz.model("struct").macros
    body = wiz.request.query()
    schedule_id = body.get("schedule_id")
    if not schedule_id:
        wiz.response.status(400, message="schedule_id는 필수입니다.", error_code="MACRO_SCHEDULE_ID_REQUIRED")
        return

    code = 200
    payload = {}
    try:
        payload = macros_model.schedule_history(
            schedule_id,
            macro_id=body.get("macro_id"),
            page=body.get("page") or 1,
            limit=body.get("limit") or 10,
        )
    except macros_model.MacroError as exc:
        code = exc.status_code
        payload = {"message": exc.message, "error_code": exc.error_code, **exc.extra}
    except RuntimeError as exc:
        code = 503
        payload = {"message": str(exc), "error_code": "DATABASE_UNAVAILABLE"}
    except Exception as exc:
        code, payload = _error_payload(exc)

    wiz.response.status(code, **payload)


def run_macro():
    macros_model = wiz.model("struct").macros
    nodes_model = wiz.model("struct").nodes
    body = wiz.request.query()
    macro_id = body.get("macro_id")
    if not macro_id:
        wiz.response.status(400, message="macro_id는 필수입니다.", error_code="MACRO_ID_REQUIRED")
        return

    code = 200
    payload = {}
    try:
        global_macros = macros_model.list({"scope_type": macros_model.SCOPE_GLOBAL})
        if not any(str(item.get("id")) == str(macro_id) for item in global_macros):
            wiz.response.status(409, message="매크로 화면에서는 선택한 매크로를 실행할 수 없습니다.", error_code="GLOBAL_MACRO_REQUIRED")
            return
        payload = {"operation": macros_model.run(body)}
    except macros_model.MacroError as exc:
        code = exc.status_code
        payload = {"message": exc.message, "error_code": exc.error_code, **exc.extra}
    except nodes_model.NodeError as exc:
        code = exc.status_code
        payload = {"message": exc.message, "error_code": exc.error_code, **exc.extra}
    except RuntimeError as exc:
        code = 503
        payload = {"message": str(exc), "error_code": "DATABASE_UNAVAILABLE"}
    except Exception as exc:
        code, payload = _error_payload(exc)

    wiz.response.status(code, **payload)


def operation_status():
    operations_model = wiz.model("struct").operations
    body = wiz.request.query()
    operation_id = body.get("operation_id")
    if not operation_id:
        wiz.response.status(400, message="operation_id는 필수입니다.", error_code="OPERATION_ID_REQUIRED")
        return

    code = 200
    payload = {}
    try:
        payload = {"operation": operations_model.detail(operation_id)}
    except operations_model.OperationError as exc:
        code = exc.status_code
        payload = {"message": exc.message, "error_code": exc.error_code, **exc.extra}
    except RuntimeError as exc:
        code = 503
        payload = {"message": str(exc), "error_code": "DATABASE_UNAVAILABLE"}
    except Exception as exc:
        code, payload = _error_payload(exc)

    wiz.response.status(code, **payload)


def download_macro_file():
    macros_model = wiz.model("struct").macros
    body = wiz.request.query()
    file_id = body.get("file_id")
    if not file_id:
        wiz.response.status(400, message="file_id는 필수입니다.", error_code="MACRO_FILE_ID_REQUIRED")
        return

    code = 200
    payload = {}
    try:
        payload = macros_model.download_file(file_id, macro_id=body.get("macro_id"))
    except macros_model.MacroError as exc:
        code = exc.status_code
        payload = {"message": exc.message, "error_code": exc.error_code, **exc.extra}
    except RuntimeError as exc:
        code = 503
        payload = {"message": str(exc), "error_code": "DATABASE_UNAVAILABLE"}
    except Exception as exc:
        code, payload = _error_payload(exc)

    wiz.response.status(code, **payload)


def delete_macro_file():
    macros_model = wiz.model("struct").macros
    body = wiz.request.query()
    file_id = body.get("file_id")
    if not file_id:
        wiz.response.status(400, message="file_id는 필수입니다.", error_code="MACRO_FILE_ID_REQUIRED")
        return

    code = 200
    payload = {}
    try:
        payload = macros_model.delete_file(file_id, macro_id=body.get("macro_id"))
    except macros_model.MacroError as exc:
        code = exc.status_code
        payload = {"message": exc.message, "error_code": exc.error_code, **exc.extra}
    except RuntimeError as exc:
        code = 503
        payload = {"message": str(exc), "error_code": "DATABASE_UNAVAILABLE"}
    except Exception as exc:
        code, payload = _error_payload(exc)

    wiz.response.status(code, **payload)
