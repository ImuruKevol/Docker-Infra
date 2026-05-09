def _merge_wizard_components(components, service):
    metadata = (service or {}).get("metadata") or {}
    saved = (metadata.get("wizard") or {}).get("components") or []
    saved_by_key = {str(item.get("key") or ""): item for item in saved if item.get("key")}
    result = []
    for component in components or []:
        item = {**component}
        previous = saved_by_key.get(str(item.get("key") or ""))
        if previous:
            if previous.get("label"):
                item["label"] = previous.get("label")
            if previous.get("role"):
                item["role"] = previous.get("role")
            previous_ports = {
                (int(port.get("target") or 0), str(port.get("protocol") or "tcp")): port
                for port in previous.get("ports") or []
            }
            next_ports = []
            for port in item.get("ports") or []:
                key = (int(port.get("target") or 0), str(port.get("protocol") or "tcp"))
                next_ports.append({**port, "public_endpoint": bool(previous_ports.get(key, {}).get("public_endpoint"))})
            item["ports"] = next_ports
        result.append(item)
    return result


def _service_detail_payload(service_id):
    services_model = wiz.model("struct").services
    wizard = wiz.model("struct").services_wizard
    flow_model = wiz.model("struct/services_flow")
    payload = services_model.detail(service_id)
    payload["components"] = _merge_wizard_components(
        wizard.components_from_content(payload.get("compose_content")),
        payload.get("service"),
    )
    payload["service_flow"] = flow_model.build(payload, payload["components"])
    return payload


def load():
    catalog = wiz.model("struct/infra_catalog_registry")
    monitoring = wiz.model("struct").nodes_monitoring
    code = 200
    payload = {}

    try:
        monitoring.tick()
        payload = catalog.services()
    except RuntimeError as exc:
        code = 503
        payload = {"message": str(exc), "error_code": "DATABASE_UNAVAILABLE"}

    wiz.response.status(code, **payload)


def edit_options():
    domains_model = wiz.model("struct").domains
    webserver = wiz.model("struct/webserver")
    code = 200
    payload = {}

    try:
        zones = []
        for zone in domains_model.load().get("zones", []):
            if zone.get("usable_for_service") is False or zone.get("enabled") is False:
                continue
            certs = webserver.certificates_for_domain(zone.get("domain"), zone_id=zone.get("id"))
            zones.append({**zone, "certificate_summary": certs.get("summary") or {}})
        payload = {"zones": zones}
    except RuntimeError as exc:
        code = 503
        payload = {"message": str(exc), "error_code": "DATABASE_UNAVAILABLE"}

    wiz.response.status(code, **payload)


def compose_conflicts():
    service_compose = wiz.model("struct/services_compose")
    code = 200
    payload = {}
    try:
        payload = service_compose.conflicts(wiz.request.query())
    except service_compose.ComposeValidationError as exc:
        code = exc.status_code
        payload = {"message": exc.message, "error_code": exc.error_code, "details": exc.details}
    except Exception as exc:
        code = 400
        payload = {"message": str(exc), "error_code": "COMPOSE_CONFLICT_CHECK_FAILED"}
    wiz.response.status(code, **payload)


def validate_compose():
    validator = wiz.model("struct").compose_validator
    code = 200
    payload = {}

    try:
        payload = {"validation": validator.validate(wiz.request.query())}
    except validator.ComposeValidationError as exc:
        code = exc.status_code
        payload = {"message": exc.message, "error_code": exc.error_code, "details": exc.details}
    except RuntimeError as exc:
        code = 503
        payload = {"message": str(exc), "error_code": "DATABASE_UNAVAILABLE"}

    wiz.response.status(code, **payload)


def template_detail():
    templates_model = wiz.model("struct").templates
    template_id = str(wiz.request.query().get("template_id") or "").strip()
    if not template_id:
        wiz.response.status(400, message="template_id가 필요합니다.", error_code="TEMPLATE_ID_REQUIRED")
        return

    code = 200
    payload = {}
    try:
        payload = templates_model.detail(template_id)
    except templates_model.TemplateError as exc:
        code = exc.status_code
        payload = {"message": exc.message, "error_code": exc.error_code, **exc.extra}
    except RuntimeError as exc:
        code = 503
        payload = {"message": str(exc), "error_code": "DATABASE_UNAVAILABLE"}

    wiz.response.status(code, **payload)


def create_service():
    services_model = wiz.model("struct").services
    catalog = wiz.model("struct/infra_catalog_registry")
    code = 200
    payload = {}

    try:
        result = services_model.create(wiz.request.query())
        payload = {"result": result, **catalog.services()}
    except services_model.ComposeValidationError as exc:
        code = exc.status_code
        payload = {"message": exc.message, "error_code": exc.error_code, "details": exc.details}
    except services_model.ServiceError as exc:
        code = exc.status_code
        payload = {"message": exc.message, "error_code": exc.error_code, **exc.extra}
    except RuntimeError as exc:
        code = 503
        payload = {"message": str(exc), "error_code": "DATABASE_UNAVAILABLE"}

    wiz.response.status(code, **payload)


def deploy_service():
    services_model = wiz.model("struct").services
    code = 200
    payload = {}

    try:
        result = services_model.deploy(wiz.request.query())
        payload = {"result": result, **services_model.detail(result["service"]["id"])}
    except services_model.ServiceError as exc:
        code = exc.status_code
        payload = {"message": exc.message, "error_code": exc.error_code, **exc.extra}
    except RuntimeError as exc:
        code = 503
        payload = {"message": str(exc), "error_code": "DATABASE_UNAVAILABLE"}

    wiz.response.status(code, **payload)


def deploy_service_background():
    services_model = wiz.model("struct").services
    code = 202
    payload = {}

    try:
        result = services_model.deploy_background(wiz.request.query())
        payload = {"result": result}
    except services_model.ServiceError as exc:
        code = exc.status_code
        payload = {"message": exc.message, "error_code": exc.error_code, **exc.extra}
    except RuntimeError as exc:
        code = 503
        payload = {"message": str(exc), "error_code": "DATABASE_UNAVAILABLE"}

    wiz.response.status(code, **payload)


def delete_service():
    services_model = wiz.model("struct").services
    catalog = wiz.model("struct/infra_catalog_registry")
    code = 200
    payload = {}
    try:
        result = services_model.delete(wiz.request.query())
        payload = {"result": result, **catalog.services()}
    except services_model.ServiceError as exc:
        code = exc.status_code
        payload = {"message": exc.message, "error_code": exc.error_code, **exc.extra}
    except RuntimeError as exc:
        code = 503
        payload = {"message": str(exc), "error_code": "DATABASE_UNAVAILABLE"}
    wiz.response.status(code, **payload)


def refresh_deploy_status():
    services_model = wiz.model("struct").services
    body = wiz.request.query()
    service_id = body.get("service_id")
    if not service_id:
        wiz.response.status(400, message="service_id는 필수입니다.", error_code="SERVICE_ID_REQUIRED")
        return

    code = 200
    payload = {}
    try:
        result = services_model.refresh_deploy_status(service_id)
        payload = {"result": result, **_service_detail_payload(service_id)}
    except services_model.ServiceError as exc:
        code = exc.status_code
        payload = {"message": exc.message, "error_code": exc.error_code, **exc.extra}
    except RuntimeError as exc:
        code = 503
        payload = {"message": str(exc), "error_code": "DATABASE_UNAVAILABLE"}

    wiz.response.status(code, **payload)


def detail_service():
    services_model = wiz.model("struct").services
    body = wiz.request.query()
    service_id = body.get("service_id")
    if not service_id:
        wiz.response.status(400, message="service_id는 필수입니다.", error_code="SERVICE_ID_REQUIRED")
        return

    code = 200
    payload = {}
    try:
        payload = _service_detail_payload(service_id)
    except services_model.ServiceError as exc:
        code = exc.status_code
        payload = {"message": exc.message, "error_code": exc.error_code, **exc.extra}
    except RuntimeError as exc:
        code = 503
        payload = {"message": str(exc), "error_code": "DATABASE_UNAVAILABLE"}

    wiz.response.status(code, **payload)


def save_nginx_config():
    services_model = wiz.model("struct").services
    body = wiz.request.query()
    code = 200
    payload = {}
    try:
        result = services_model.update_nginx_config(body)
        payload = {"result": result, **_service_detail_payload(body.get("service_id"))}
    except services_model.ServiceError as exc:
        code = exc.status_code
        payload = {"message": exc.message, "error_code": exc.error_code, **exc.extra}
    except RuntimeError as exc:
        code = 503
        payload = {"message": str(exc), "error_code": "DATABASE_UNAVAILABLE"}
    wiz.response.status(code, **payload)


def save_compose_content():
    services_model = wiz.model("struct").services
    code = 200
    payload = {}
    try:
        body = wiz.request.query()
        result = services_model.update_compose_content(body)
        payload = {"result": result, **_service_detail_payload(result["service"]["id"])}
    except services_model.ComposeValidationError as exc:
        code = exc.status_code
        payload = {"message": exc.message, "error_code": exc.error_code, "details": exc.details}
    except services_model.ServiceError as exc:
        code = exc.status_code
        payload = {"message": exc.message, "error_code": exc.error_code, **exc.extra}
    except RuntimeError as exc:
        code = 503
        payload = {"message": str(exc), "error_code": "DATABASE_UNAVAILABLE"}
    wiz.response.status(code, **payload)


def _container_id_matches(actual, requested):
    actual = str(actual or "").strip()
    requested = str(requested or "").strip()
    if not actual or not requested:
        return False
    return actual == requested or actual.startswith(requested) or requested.startswith(actual)


def service_container_action():
    services_model = wiz.model("struct").services
    nodes_model = wiz.model("struct").nodes
    body = wiz.request.query()
    service_id = body.get("service_id")
    container_id = str(body.get("container_id") or "").strip()
    action = str(body.get("action") or "").strip().lower()
    if not service_id:
        wiz.response.status(400, message="service_id는 필수입니다.", error_code="SERVICE_ID_REQUIRED")
        return
    if not container_id:
        wiz.response.status(400, message="container_id는 필수입니다.", error_code="CONTAINER_ID_REQUIRED")
        return

    code = 200
    payload = {}
    try:
        runtime = services_model.refresh_deploy_status(service_id).get("runtime_status") or {}
        containers = ((runtime.get("containers") or {}).get("containers") or [])
        requested_node_id = str(body.get("node_id") or "").strip()
        target = next(
            (
                item for item in containers
                if _container_id_matches(item.get("id"), container_id)
                and (not requested_node_id or str(item.get("node_id") or "") == requested_node_id)
            ),
            None,
        )
        if target is None:
            raise services_model.ServiceError(404, "선택한 서비스의 컨테이너를 찾을 수 없습니다.", "SERVICE_CONTAINER_NOT_FOUND")
        target_node_id = str(target.get("node_id") or "").strip()
        if not target_node_id:
            raise services_model.ServiceError(409, "컨테이너가 실행 중인 서버를 확인할 수 없습니다.", "SERVICE_CONTAINER_NODE_MISSING")
        result = nodes_model.container_action(target_node_id, {"container_id": target.get("id") or container_id, "action": action})
        services_model.refresh_deploy_status(service_id)
        payload = {"result": result.get("result") or result, **_service_detail_payload(service_id)}
    except nodes_model.NodeError as exc:
        code = exc.status_code
        payload = {"message": exc.message, "error_code": exc.error_code, **exc.extra}
    except services_model.ServiceError as exc:
        code = exc.status_code
        payload = {"message": exc.message, "error_code": exc.error_code, **exc.extra}
    except RuntimeError as exc:
        code = 503
        payload = {"message": str(exc), "error_code": "DATABASE_UNAVAILABLE"}
    wiz.response.status(code, **payload)


def update_service():
    services_model = wiz.model("struct").services
    wizard = wiz.model("struct").services_wizard
    code = 200
    payload = {}
    try:
        body = wiz.request.query()
        if not body.get("content"):
            body["content"] = wizard.render(body)
        result = services_model.update_wizard(body)
        payload = {"result": result, **_service_detail_payload(result["service"]["id"])}
    except services_model.ComposeValidationError as exc:
        code = exc.status_code
        payload = {"message": exc.message, "error_code": exc.error_code, "details": exc.details}
    except services_model.ServiceError as exc:
        code = exc.status_code
        payload = {"message": exc.message, "error_code": exc.error_code, **exc.extra}
    except RuntimeError as exc:
        code = 503
        payload = {"message": str(exc), "error_code": "DATABASE_UNAVAILABLE"}
    wiz.response.status(code, **payload)


def rollback_plan():
    services_model = wiz.model("struct").services
    code = 200
    payload = {}
    try:
        payload = services_model.rollback_plan(wiz.request.query())
    except services_model.ComposeValidationError as exc:
        code = exc.status_code
        payload = {"message": exc.message, "error_code": exc.error_code, "details": exc.details}
    except services_model.ServiceError as exc:
        code = exc.status_code
        payload = {"message": exc.message, "error_code": exc.error_code, **exc.extra}
    except RuntimeError as exc:
        code = 503
        payload = {"message": str(exc), "error_code": "DATABASE_UNAVAILABLE"}
    wiz.response.status(code, **payload)


def rollback_service():
    services_model = wiz.model("struct").services
    wizard = wiz.model("struct").services_wizard
    code = 200
    payload = {}
    try:
        result = services_model.rollback(wiz.request.query())
        payload = {"result": result, **services_model.detail(result["service"]["id"])}
        payload["components"] = _merge_wizard_components(
            wizard.components_from_content(payload.get("compose_content")),
            payload.get("service"),
        )
    except services_model.ComposeValidationError as exc:
        code = exc.status_code
        payload = {"message": exc.message, "error_code": exc.error_code, "details": exc.details}
    except services_model.ServiceError as exc:
        code = exc.status_code
        payload = {"message": exc.message, "error_code": exc.error_code, **exc.extra}
    except RuntimeError as exc:
        code = 503
        payload = {"message": str(exc), "error_code": "DATABASE_UNAVAILABLE"}
    wiz.response.status(code, **payload)


def operation_detail():
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
    wiz.response.status(code, **payload)


def browse_files():
    services_model = wiz.model("struct").services
    body = wiz.request.query()
    service_id = body.get("service_id")
    if not service_id:
        wiz.response.status(400, message="service_id는 필수입니다.", error_code="SERVICE_ID_REQUIRED")
        return

    code = 200
    payload = {}
    try:
        payload = services_model.browse_files(service_id, body.get("path"))
    except services_model.ServiceError as exc:
        code = exc.status_code
        payload = {"message": exc.message, "error_code": exc.error_code, **exc.extra}
    except RuntimeError as exc:
        code = 503
        payload = {"message": str(exc), "error_code": "DATABASE_UNAVAILABLE"}

    wiz.response.status(code, **payload)


def read_file():
    services_model = wiz.model("struct").services
    body = wiz.request.query()
    service_id = body.get("service_id")
    path = body.get("path")
    if not service_id:
        wiz.response.status(400, message="service_id는 필수입니다.", error_code="SERVICE_ID_REQUIRED")
        return
    if not path:
        wiz.response.status(400, message="path는 필수입니다.", error_code="SERVICE_FILE_PATH_REQUIRED")
        return

    code = 200
    payload = {}
    try:
        payload = services_model.read_file(service_id, path)
    except services_model.ServiceError as exc:
        code = exc.status_code
        payload = {"message": exc.message, "error_code": exc.error_code, **exc.extra}
    except RuntimeError as exc:
        code = 503
        payload = {"message": str(exc), "error_code": "DATABASE_UNAVAILABLE"}

    wiz.response.status(code, **payload)


def refresh_image_records():
    services_model = wiz.model("struct").services
    code = 200
    payload = {}
    try:
        payload = services_model.refresh_image_records(wiz.request.query())
    except services_model.ServiceError as exc:
        code = exc.status_code
        payload = {"message": exc.message, "error_code": exc.error_code, **exc.extra}
    except RuntimeError as exc:
        code = 503
        payload = {"message": str(exc), "error_code": "DATABASE_UNAVAILABLE"}

    wiz.response.status(code, **payload)


def restore_image_backup():
    services_model = wiz.model("struct").services
    code = 200
    payload = {}
    try:
        payload = services_model.restore_image_backup(wiz.request.query())
    except services_model.ServiceError as exc:
        code = exc.status_code
        payload = {"message": exc.message, "error_code": exc.error_code, **exc.extra}
    except RuntimeError as exc:
        code = 503
        payload = {"message": str(exc), "error_code": "DATABASE_UNAVAILABLE"}

    wiz.response.status(code, **payload)


def backup_service_image():
    services_model = wiz.model("struct").services
    code = 200
    payload = {}
    try:
        payload = services_model.backup_service_image(wiz.request.query())
    except services_model.ServiceError as exc:
        code = exc.status_code
        payload = {"message": exc.message, "error_code": exc.error_code, **exc.extra}
    except RuntimeError as exc:
        code = 503
        payload = {"message": str(exc), "error_code": "DATABASE_UNAVAILABLE"}

    wiz.response.status(code, **payload)


def snapshot_service_image():
    services_model = wiz.model("struct").services
    code = 200
    payload = {}
    try:
        payload = services_model.snapshot_service_image(wiz.request.query())
    except services_model.ServiceError as exc:
        code = exc.status_code
        payload = {"message": exc.message, "error_code": exc.error_code, **exc.extra}
    except RuntimeError as exc:
        code = 503
        payload = {"message": str(exc), "error_code": "DATABASE_UNAVAILABLE"}

    wiz.response.status(code, **payload)
