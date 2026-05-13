from flask import request


def _request_base_url():
    forwarded_proto = (request.headers.get("X-Forwarded-Proto") or "").split(",")[0].strip()
    forwarded_host = (request.headers.get("X-Forwarded-Host") or "").split(",")[0].strip()
    proto = forwarded_proto or request.scheme
    host = forwarded_host or request.headers.get("Host")
    if host:
        return f"{proto}://{host}".rstrip("/")
    return request.url_root.rstrip("/")


def _error_payload(exc, default_code=500, default_error="UNEXPECTED_ERROR"):
    if hasattr(exc, "status_code") and hasattr(exc, "message") and hasattr(exc, "error_code"):
        extra = getattr(exc, "extra", {}) or {}
        return exc.status_code, {"message": exc.message, "error_code": exc.error_code, **extra}
    return default_code, {"message": str(exc), "error_code": default_error}


def _macro_request():
    if request.form or request.files:
        return request.form.to_dict(flat=True), request.files.getlist("files")
    return wiz.request.query(), []


def _with_monitoring_state(payload, monitoring):
    payload = payload or {}
    payload["monitoring"] = monitoring.state()
    return payload


def load():
    nodes_model = wiz.model("struct").nodes
    monitoring = wiz.model("struct").nodes_monitoring
    body = wiz.request.query()
    code = 200
    payload = {}

    try:
        payload = _with_monitoring_state(nodes_model.overview_summary(selected_id=body.get("selected_id"), auto_sync_local_master=False), monitoring)
    except nodes_model.NodeError as exc:
        code = exc.status_code
        payload = {"message": exc.message, "error_code": exc.error_code, **exc.extra}
    except nodes_model.LocalCommandError as exc:
        code = exc.status_code
        payload = {"message": exc.message, "error_code": exc.error_code, **exc.extra}
    except RuntimeError as exc:
        code = 503
        payload = {"message": str(exc), "error_code": "DATABASE_UNAVAILABLE"}
    except Exception as exc:
        code, payload = _error_payload(exc)

    wiz.response.status(code, **payload)


def overview():
    nodes_model = wiz.model("struct").nodes
    monitoring = wiz.model("struct").nodes_monitoring
    body = wiz.request.query()
    code = 200
    payload = {}

    try:
        payload = _with_monitoring_state(nodes_model.overview_summary(selected_id=body.get("selected_id"), auto_sync_local_master=False), monitoring)
    except nodes_model.NodeError as exc:
        code = exc.status_code
        payload = {"message": exc.message, "error_code": exc.error_code, **exc.extra}
    except nodes_model.LocalCommandError as exc:
        code = exc.status_code
        payload = {"message": exc.message, "error_code": exc.error_code, **exc.extra}
    except RuntimeError as exc:
        code = 503
        payload = {"message": str(exc), "error_code": "DATABASE_UNAVAILABLE"}
    except Exception as exc:
        code, payload = _error_payload(exc)

    wiz.response.status(code, **payload)


def ensure_monitoring_agent():
    monitoring = wiz.model("struct").nodes_monitoring
    nodes_model = wiz.model("struct").nodes
    operations_model = wiz.model("struct").operations
    body = wiz.request.query()
    code = 200
    payload = {}

    try:
        body["reporter_base_url"] = body.get("reporter_base_url") or _request_base_url()
        result = monitoring.ensure_exporters(body)
        payload = {
            **result,
            **nodes_model.overview_summary(selected_id=body.get("node_id"), auto_sync_local_master=False),
        }
        payload = _with_monitoring_state(payload, monitoring)
    except nodes_model.NodeError as exc:
        code = exc.status_code
        payload = {"message": exc.message, "error_code": exc.error_code, **exc.extra}
    except operations_model.OperationError as exc:
        code = exc.status_code
        payload = {"message": exc.message, "error_code": exc.error_code, **exc.extra}
    except RuntimeError as exc:
        code = 503
        payload = {"message": str(exc), "error_code": "DATABASE_UNAVAILABLE"}
    except Exception as exc:
        code, payload = _error_payload(exc)

    wiz.response.status(code, **payload)


def ensure_local_master():
    nodes_model = wiz.model("struct").nodes
    monitoring = wiz.model("struct").nodes_monitoring
    body = wiz.request.query()
    code = 200
    payload = {}

    try:
        result = nodes_model.ensure_local_master(body)
        monitoring_result = None
        selected = result["local_master"]
        if selected:
            try:
                monitoring_result = monitoring.ensure_exporters({"node_id": selected["id"], "reporter_base_url": _request_base_url()})
                selected = nodes_model.detail(selected["id"])
                result["local_master"] = selected
            except Exception as exc:
                monitoring_result = {"status": "failed", "message": str(exc)}
        nodes = nodes_model.list()
        containers = nodes_model.containers(selected["id"])["containers"] if selected else []
        payload = _with_monitoring_state(
            {"result": result, "monitoring_auto_configure": monitoring_result, "nodes": nodes, "selected": selected, "containers": containers},
            monitoring,
        )
    except nodes_model.NodeError as exc:
        code = exc.status_code
        payload = {"message": exc.message, "error_code": exc.error_code, **exc.extra}
    except nodes_model.LocalCommandError as exc:
        code = exc.status_code
        payload = {"message": exc.message, "error_code": exc.error_code, **exc.extra}
    except RuntimeError as exc:
        code = 503
        payload = {"message": str(exc), "error_code": "DATABASE_UNAVAILABLE"}
    except Exception as exc:
        code, payload = _error_payload(exc)

    wiz.response.status(code, **payload)


def register_slave():
    nodes_model = wiz.model("struct").nodes
    monitoring = wiz.model("struct").nodes_monitoring
    body = wiz.request.query()
    code = 200
    payload = {}

    try:
        is_new = not body.get("node_id")
        node = nodes_model.save_slave(body)
        monitoring_result = None
        if is_new:
            try:
                monitoring_result = monitoring.ensure_exporters({"node_id": node["id"], "reporter_base_url": _request_base_url()})
                node = nodes_model.detail(node["id"])
            except Exception as exc:
                monitoring_result = {"status": "failed", "message": str(exc)}
        payload = _with_monitoring_state(
            {
                "node": node,
                "monitoring_auto_configure": monitoring_result,
                **nodes_model.overview(selected_id=node["id"], auto_sync_local_master=False),
            },
            monitoring,
        )
    except nodes_model.NodeError as exc:
        code = exc.status_code
        payload = {"message": exc.message, "error_code": exc.error_code, **exc.extra}
    except RuntimeError as exc:
        code = 503
        payload = {"message": str(exc), "error_code": "DATABASE_UNAVAILABLE"}
    except Exception as exc:
        code, payload = _error_payload(exc)

    wiz.response.status(code, **payload)


def check_node():
    nodes_model = wiz.model("struct").nodes
    body = wiz.request.query()
    node_id = body.get("node_id")
    code = 200
    payload = {}

    try:
        if not node_id:
            code = 400
            payload = {"message": "node_id는 필수입니다.", "error_code": "NODE_ID_REQUIRED"}
        else:
            payload = nodes_model.check_slave(node_id)
            payload.update(nodes_model.overview(selected_id=node_id, auto_sync_local_master=False))
    except nodes_model.NodeError as exc:
        code = exc.status_code
        payload = {"message": exc.message, "error_code": exc.error_code, **exc.extra}
    except RuntimeError as exc:
        code = 503
        payload = {"message": str(exc), "error_code": "DATABASE_UNAVAILABLE"}
    except Exception as exc:
        code, payload = _error_payload(exc)

    wiz.response.status(code, **payload)


def join_node():
    nodes_model = wiz.model("struct").nodes
    body = wiz.request.query()
    node_id = body.get("node_id")
    code = 200
    payload = {}

    try:
        if not node_id:
            code = 400
            payload = {"message": "node_id는 필수입니다.", "error_code": "NODE_ID_REQUIRED"}
        else:
            payload = nodes_model.join_slave(node_id, body)
            payload.update(nodes_model.overview(selected_id=node_id, auto_sync_local_master=False))
    except nodes_model.NodeError as exc:
        code = exc.status_code
        payload = {"message": exc.message, "error_code": exc.error_code, **exc.extra}
    except nodes_model.LocalCommandError as exc:
        code = exc.status_code
        payload = {"message": exc.message, "error_code": exc.error_code, **exc.extra}
    except RuntimeError as exc:
        code = 503
        payload = {"message": str(exc), "error_code": "DATABASE_UNAVAILABLE"}
    except Exception as exc:
        code, payload = _error_payload(exc)

    wiz.response.status(code, **payload)


def issue_reporter_token():
    nodes_model = wiz.model("struct").nodes
    body = wiz.request.query()
    node_id = body.get("node_id")
    code = 200
    payload = {}

    try:
        if not node_id:
            code = 400
            payload = {"message": "node_id는 필수입니다.", "error_code": "NODE_ID_REQUIRED"}
        else:
            payload = nodes_model.issue_reporter_token(node_id)
    except nodes_model.NodeError as exc:
        code = exc.status_code
        payload = {"message": exc.message, "error_code": exc.error_code, **exc.extra}
    except RuntimeError as exc:
        code = 503
        payload = {"message": str(exc), "error_code": "DATABASE_UNAVAILABLE"}
    except Exception as exc:
        code, payload = _error_payload(exc)

    wiz.response.status(code, **payload)


def detail():
    nodes_model = wiz.model("struct").nodes
    body = wiz.request.query()
    node_id = body.get("node_id")
    if not node_id:
        wiz.response.status(400, message="node_id는 필수입니다.", error_code="NODE_ID_REQUIRED")
        return

    code = 200
    payload = {}
    try:
        payload = nodes_model.metric_snapshot(node_id) if body.get("refresh") else nodes_model.server_detail(node_id)
    except nodes_model.NodeError as exc:
        code = exc.status_code
        payload = {"message": exc.message, "error_code": exc.error_code, **exc.extra}
    except RuntimeError as exc:
        code = 503
        payload = {"message": str(exc), "error_code": "DATABASE_UNAVAILABLE"}
    except Exception as exc:
        code, payload = _error_payload(exc)

    wiz.response.status(code, **payload)


def cached_detail():
    nodes_model = wiz.model("struct").nodes
    monitoring = wiz.model("struct").nodes_monitoring
    body = wiz.request.query()
    node_id = body.get("node_id")
    if not node_id:
        wiz.response.status(400, message="node_id는 필수입니다.", error_code="NODE_ID_REQUIRED")
        return

    code = 200
    payload = {}
    try:
        payload = _with_monitoring_state(nodes_model.cached_detail(node_id), monitoring)
    except nodes_model.NodeError as exc:
        code = exc.status_code
        payload = {"message": exc.message, "error_code": exc.error_code, **exc.extra}
    except RuntimeError as exc:
        code = 503
        payload = {"message": str(exc), "error_code": "DATABASE_UNAVAILABLE"}
    except Exception as exc:
        code, payload = _error_payload(exc)

    wiz.response.status(code, **payload)


def refresh_metrics():
    nodes_model = wiz.model("struct").nodes
    monitoring = wiz.model("struct").nodes_monitoring
    body = wiz.request.query()
    node_id = body.get("node_id")
    if not node_id:
        wiz.response.status(400, message="node_id는 필수입니다.", error_code="NODE_ID_REQUIRED")
        return

    code = 200
    payload = {}
    try:
        persist = str(body.get("persist") or body.get("record") or "").strip().lower() in {"1", "true", "yes", "on"}
        payload = nodes_model.metric_snapshot(node_id) if persist else nodes_model.live_metric(node_id)
        payload = _with_monitoring_state(payload, monitoring)
    except nodes_model.NodeError as exc:
        code = exc.status_code
        payload = {"message": exc.message, "error_code": exc.error_code, **exc.extra}
    except RuntimeError as exc:
        code = 503
        payload = {"message": str(exc), "error_code": "DATABASE_UNAVAILABLE"}
    except Exception as exc:
        code, payload = _error_payload(exc)

    wiz.response.status(code, **payload)


def resource_history():
    history_model = wiz.model("struct/nodes_metric_history")
    body = wiz.request.query()
    node_id = body.get("node_id")
    if not node_id:
        wiz.response.status(400, message="node_id는 필수입니다.", error_code="NODE_ID_REQUIRED")
        return

    code = 200
    payload = {}
    try:
        chart_args = {
            "node_id": node_id,
            "start_date": body.get("start_date"),
            "end_date": body.get("end_date"),
            "start_at": body.get("start_at"),
            "end_at": body.get("end_at"),
            "limit": body.get("limit") or 1440,
        }
        if hasattr(history_model, "node_chart"):
            payload = history_model.node_chart(**chart_args)
        else:
            payload = history_model.query(**chart_args)
            payload["source"] = payload.get("source") or "csv"
            payload["source_count"] = payload.get("source_count") or payload.get("count", 0)
    except Exception as exc:
        code, payload = _error_payload(exc)

    wiz.response.status(code, **payload)


def delete_resource_history():
    history_model = wiz.model("struct/nodes_metric_history")
    body = wiz.request.query()
    node_id = body.get("node_id")
    if not node_id:
        wiz.response.status(400, message="node_id는 필수입니다.", error_code="NODE_ID_REQUIRED")
        return

    code = 200
    payload = {}
    try:
        payload = history_model.delete_range(
            node_id=node_id,
            start_date=body.get("start_date"),
            end_date=body.get("end_date"),
            start_at=body.get("start_at"),
            end_at=body.get("end_at"),
        )
    except Exception as exc:
        code, payload = _error_payload(exc)

    wiz.response.status(code, **payload)


def refresh_containers():
    nodes_model = wiz.model("struct").nodes
    monitoring = wiz.model("struct").nodes_monitoring
    body = wiz.request.query()
    node_id = body.get("node_id")
    if not node_id:
        wiz.response.status(400, message="node_id는 필수입니다.", error_code="NODE_ID_REQUIRED")
        return

    code = 200
    payload = {}
    try:
        payload = _with_monitoring_state(nodes_model.refresh_containers_panel(node_id), monitoring)
    except nodes_model.NodeError as exc:
        code = exc.status_code
        payload = {"message": exc.message, "error_code": exc.error_code, **exc.extra}
    except RuntimeError as exc:
        code = 503
        payload = {"message": str(exc), "error_code": "DATABASE_UNAVAILABLE"}
    except Exception as exc:
        code, payload = _error_payload(exc)

    wiz.response.status(code, **payload)


def container_action():
    nodes_model = wiz.model("struct").nodes
    body = wiz.request.query()
    node_id = body.get("node_id")
    if not node_id:
        wiz.response.status(400, message="node_id는 필수입니다.", error_code="NODE_ID_REQUIRED")
        return

    code = 200
    payload = {}
    try:
        payload = nodes_model.container_action(node_id, body)
    except nodes_model.NodeError as exc:
        code = exc.status_code
        payload = {"message": exc.message, "error_code": exc.error_code, **exc.extra}
    except nodes_model.LocalCommandError as exc:
        code = exc.status_code
        payload = {"message": exc.message, "error_code": exc.error_code, **exc.extra}
    except RuntimeError as exc:
        code = 503
        payload = {"message": str(exc), "error_code": "DATABASE_UNAVAILABLE"}
    except Exception as exc:
        code, payload = _error_payload(exc)

    wiz.response.status(code, **payload)


def service_action():
    nodes_model = wiz.model("struct").nodes
    body = wiz.request.query()
    node_id = body.get("node_id")
    if not node_id:
        wiz.response.status(400, message="node_id는 필수입니다.", error_code="NODE_ID_REQUIRED")
        return

    code = 200
    payload = {}
    try:
        payload = nodes_model.service_action(node_id, body)
    except nodes_model.NodeError as exc:
        code = exc.status_code
        payload = {"message": exc.message, "error_code": exc.error_code, **exc.extra}
    except nodes_model.LocalCommandError as exc:
        code = exc.status_code
        payload = {"message": exc.message, "error_code": exc.error_code, **exc.extra}
    except RuntimeError as exc:
        code = 503
        payload = {"message": str(exc), "error_code": "DATABASE_UNAVAILABLE"}
    except Exception as exc:
        code, payload = _error_payload(exc)

    wiz.response.status(code, **payload)


def browse_files():
    nodes_model = wiz.model("struct").nodes
    body = wiz.request.query()
    node_id = body.get("node_id")
    if not node_id:
        wiz.response.status(400, message="node_id는 필수입니다.", error_code="NODE_ID_REQUIRED")
        return

    code = 200
    payload = {}
    try:
        payload = nodes_model.browse_files(node_id, body)
    except nodes_model.NodeError as exc:
        code = exc.status_code
        payload = {"message": exc.message, "error_code": exc.error_code, **exc.extra}
    except nodes_model.LocalCommandError as exc:
        code = exc.status_code
        payload = {"message": exc.message, "error_code": exc.error_code, **exc.extra}
    except RuntimeError as exc:
        code = 503
        payload = {"message": str(exc), "error_code": "DATABASE_UNAVAILABLE"}
    except Exception as exc:
        code, payload = _error_payload(exc)

    wiz.response.status(code, **payload)


def import_compose_service():
    nodes_model = wiz.model("struct").nodes
    services_model = wiz.model("struct").services
    body = wiz.request.query()
    node_id = body.get("node_id")
    path = body.get("path")
    if not node_id:
        wiz.response.status(400, message="node_id는 필수입니다.", error_code="NODE_ID_REQUIRED")
        return
    if not path:
        wiz.response.status(400, message="path는 필수입니다.", error_code="NODE_PATH_REQUIRED")
        return

    code = 200
    payload = {}
    try:
        content = nodes_model.read_file_text(node_id, path)
        filename = path.split("/")[-1]
        result = services_model.import_compose(
            {
                "node_id": node_id,
                "content": content,
                "filename": filename,
                "source_path": path,
                "suggested_namespace": body.get("suggested_namespace"),
                "name": body.get("suggested_name"),
                "allow_warnings": body.get("allow_warnings"),
                "source_ref": {"node_id": node_id, "path": path},
            }
        )
        payload = {"imported_service": result, **nodes_model.refresh_containers_panel(node_id)}
    except nodes_model.NodeError as exc:
        code = exc.status_code
        payload = {"message": exc.message, "error_code": exc.error_code, **exc.extra}
    except services_model.ComposeValidationError as exc:
        code = exc.status_code
        payload = {
            "message": exc.message,
            "error_code": exc.error_code,
            "details": exc.details,
            "warning": getattr(exc, "warning", False),
            "can_continue": getattr(exc, "can_continue", False),
        }
    except services_model.ServiceError as exc:
        code = exc.status_code
        payload = {"message": exc.message, "error_code": exc.error_code, **exc.extra}
    except nodes_model.LocalCommandError as exc:
        code = exc.status_code
        payload = {"message": exc.message, "error_code": exc.error_code, **exc.extra}
    except RuntimeError as exc:
        code = 503
        payload = {"message": str(exc), "error_code": "DATABASE_UNAVAILABLE"}
    except Exception as exc:
        code, payload = _error_payload(exc)

    wiz.response.status(code, **payload)


def list_macros():
    macros_model = wiz.model("struct").macros
    body = wiz.request.query()
    node_id = body.get("node_id")
    code = 200
    payload = {}

    try:
        payload = {
            "global_macros": macros_model.list({"scope_type": macros_model.SCOPE_GLOBAL}),
            "node_macros": macros_model.list({"scope_type": macros_model.SCOPE_NODE, "node_id": node_id}) if node_id else [],
            "available_macros": macros_model.list({"available_for_node": node_id}) if node_id else macros_model.list({"scope_type": macros_model.SCOPE_GLOBAL}),
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
                "scope_type": macros_model.SCOPE_NODE,
                "node_id": body.get("node_id"),
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


def run_macro():
    macros_model = wiz.model("struct").macros
    nodes_model = wiz.model("struct").nodes
    code = 200
    payload = {}

    try:
        payload = {"operation": macros_model.run(wiz.request.query())}
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
