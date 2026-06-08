import json

try:
    from psycopg import OperationalError as DatabaseOperationalError
except Exception:
    DatabaseOperationalError = RuntimeError


DATABASE_ERRORS = (RuntimeError, DatabaseOperationalError) if DatabaseOperationalError is not RuntimeError else (RuntimeError,)


def _is_service_error_like(exc):
    return all(hasattr(exc, key) for key in ("status_code", "message", "error_code"))


def _service_error_response(exc):
    payload = {
        "message": getattr(exc, "message", str(exc)),
        "error_code": getattr(exc, "error_code", "SERVICE_ERROR"),
        **(getattr(exc, "extra", {}) or {}),
    }
    if hasattr(exc, "details"):
        payload["details"] = getattr(exc, "details", []) or []
    if hasattr(exc, "warning"):
        payload["warning"] = bool(getattr(exc, "warning", False))
    if hasattr(exc, "can_continue"):
        payload["can_continue"] = bool(getattr(exc, "can_continue", False))
    return getattr(exc, "status_code", 500), payload


def _raise_unless_service_error_like(exc):
    if not _is_service_error_like(exc):
        raise exc
    return _service_error_response(exc)


def _request_payload():
    body = wiz.request.query()
    raw = body.get("payload") if isinstance(body, dict) else None
    if raw:
        return json.loads(raw)
    return body


def _truthy(value):
    if isinstance(value, bool):
        return value
    return str(value or "").strip().lower() in {"1", "true", "yes", "on"}


def _domain_match(domain, pattern):
    domain = str(domain or "").strip().lower().strip(".")
    pattern = str(pattern or "").strip().lower().strip(".")
    if not domain or not pattern:
        return False
    if pattern.startswith("*."):
        suffix = pattern[2:]
        if not suffix or not domain.endswith(f".{suffix}"):
            return False
        wildcard_label = domain[: -(len(suffix) + 1)]
        return bool(wildcard_label) and "." not in wildcard_label
    return domain == pattern


def _certificate_summary(certificates):
    summary = {
        "total": len(certificates),
        "valid": 0,
        "expiring": 0,
        "expired": 0,
        "error": 0,
        "disabled": 0,
        "missing": 0,
        "key_insecure": 0,
        "key_mismatch": 0,
    }
    for item in certificates:
        key = item.get("status") or "error"
        summary[key if key in summary else "error"] += 1
    return summary


def _zone_certificate_summary(certificate_cache, domain, zone_id=None):
    certificates = []
    for item in certificate_cache or []:
        if zone_id and str(item.get("zone_id") or "") == str(zone_id):
            certificates.append(item)
            continue
        names = [item.get("domain"), *((item.get("dns_names") or []))]
        if any(_domain_match(domain, hostname) for hostname in names):
            certificates.append(item)
    return _certificate_summary(certificates)


def _service_zone_options():
    domains_model = wiz.model("struct").domains
    webserver = wiz.model("struct/webserver")
    zones = []
    certificate_cache = None
    for zone in domains_model.service_options().get("zones", []):
        if zone.get("provider") == "ddns":
            zones.append(zone)
            continue
        if certificate_cache is None:
            certificate_cache = webserver.load().get("certificates") or []
        zones.append({
            **zone,
            "certificate_summary": _zone_certificate_summary(
                certificate_cache,
                zone.get("domain"),
                zone_id=zone.get("id"),
            ),
        })
    return {"zones": zones}


def _stream_events(events):
    flask = wiz.response._flask

    def encode(event):
        try:
            return json.dumps(event, ensure_ascii=False)
        except Exception as exc:
            return json.dumps({
                "type": "error",
                "message": "AI 스트림 이벤트를 직렬화할 수 없습니다: %s" % exc,
                "error_code": "AI_STREAM_EVENT_SERIALIZE_FAILED",
            }, ensure_ascii=False)

    def generate():
        yield ": stream-start\n\n"
        try:
            for event in events:
                yield "data: %s\n\n" % encode(event)
            yield ": stream-end\n\n"
        except GeneratorExit:
            return
        except (BrokenPipeError, ConnectionError):
            return
        except Exception as exc:
            yield "data: %s\n\n" % json.dumps({
                "type": "error",
                "message": getattr(exc, "message", str(exc)),
                "error_code": getattr(exc, "code", "AI_STREAM_INTERRUPTED"),
            }, ensure_ascii=False)

    resp = flask.Response(generate(), mimetype="text/event-stream")
    resp.headers["Cache-Control"] = "no-cache"
    resp.headers["X-Accel-Buffering"] = "no"
    wiz.response.response(resp)


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


def _with_detail_components(payload, expose_compose=True, include_flow=True):
    wizard = wiz.model("struct").services_wizard
    compose_content = payload.get("compose_content") or ""
    payload["components"] = _merge_wizard_components(
        wizard.components_from_content(compose_content),
        payload.get("service"),
    )
    if include_flow:
        flow_model = wiz.model("struct/services_flow")
        flow_source = {**payload, "compose_content": compose_content}
        payload["service_flow"] = flow_model.build(flow_source, payload["components"])
    if not expose_compose:
        payload.pop("compose_content", None)
    return payload


def _service_detail_payload(service_id):
    services_model = wiz.model("struct").services
    payload = _with_detail_components(services_model.detail(service_id), include_flow=False)
    payload["detail_sections"] = {"overview": True, "logs": True, "source": True, "files": True, "versions": True}
    return payload


def _service_overview_payload(service_id, lightweight=False):
    if lightweight:
        payload = wiz.model("struct/services_detail_fast").overview(service_id)
        payload["detail_sections"] = {"overview": True, "logs": False, "source": False, "files": True, "versions": False}
        return payload
    services_model = wiz.model("struct").services
    payload = services_model.detail_overview(
        service_id,
        include_certificates=not lightweight,
        include_operations=True,
        include_backup_system=not lightweight,
    )
    payload["detail_sections"] = {"overview": True, "logs": False, "source": False, "files": True, "versions": False}
    return payload


def _service_extras_payload(service_id):
    payload = wiz.model("struct/services_detail_fast").extras(service_id)
    payload["detail_sections"] = {"overview_extras": True, "certificates": True, "backup_system": True}
    return payload


def _service_advanced_payload(service_id):
    services_model = wiz.model("struct").services
    payload = _with_detail_components(services_model.detail_advanced(service_id), include_flow=False)
    payload["detail_sections"] = {"source": True, "versions": True}
    return payload


def load():
    catalog = wiz.model("struct/infra_catalog_registry")
    code = 200
    payload = {}

    try:
        payload = catalog.services()
    except DATABASE_ERRORS as exc:
        code = 503
        payload = {"message": str(exc), "error_code": "DATABASE_UNAVAILABLE"}

    wiz.response.status(code, **payload)


def support_options():
    nodes_model = wiz.model("struct").nodes
    code = 200
    payload = {}

    try:
        payload = {"nodes": nodes_model.list()}
    except DATABASE_ERRORS as exc:
        code = 503
        payload = {"message": str(exc), "error_code": "DATABASE_UNAVAILABLE"}

    wiz.response.status(code, **payload)


def edit_options():
    code = 200
    payload = {}

    try:
        payload = _service_zone_options()
    except DATABASE_ERRORS as exc:
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
    except DATABASE_ERRORS as exc:
        code = 503
        payload = {"message": str(exc), "error_code": "DATABASE_UNAVAILABLE"}

    wiz.response.status(code, **payload)


def ai_contract():
    ai_assistant = wiz.model("struct").ai_assistant
    wiz.response.status(200, contract=ai_assistant.service_contract())


def ai_model_options():
    ai_settings = wiz.model("struct").ai_settings
    code = 200
    payload = {}
    try:
        payload = ai_settings.model_options()
    except Exception as exc:
        code = getattr(exc, "status_code", 400)
        payload = {
            "message": getattr(exc, "message", str(exc)),
            "error_code": getattr(exc, "code", "AI_MODEL_OPTIONS_FAILED"),
        }
    wiz.response.status(code, **payload)


def generate_service_ai():
    ai_assistant = wiz.model("struct").ai_assistant
    code = 200
    payload = {}
    try:
        payload = ai_assistant.generate_service(wiz.request.query())
    except Exception as exc:
        code = getattr(exc, "status_code", 400)
        payload = {
            "message": getattr(exc, "message", str(exc)),
            "error_code": getattr(exc, "code", "AI_SERVICE_GENERATE_FAILED"),
            **getattr(exc, "details", {}),
        }
    wiz.response.status(code, **payload)


def stream_service_ai():
    ai_assistant = wiz.model("struct").ai_assistant
    try:
        payload = _request_payload()
        events = ai_assistant.stream_service(payload)
    except Exception as exc:
        events = [{
            "type": "error",
            "message": getattr(exc, "message", str(exc)),
            "error_code": getattr(exc, "code", "AI_SERVICE_STREAM_FAILED"),
        }]
    _stream_events(events)


def stream_runtime_ai_repair():
    ai_assistant = wiz.model("struct").ai_assistant
    try:
        payload = _request_payload()
        events = ai_assistant.stream_runtime_repair(payload)
    except Exception as exc:
        events = [{
            "type": "error",
            "message": getattr(exc, "message", str(exc)),
            "error_code": getattr(exc, "code", "AI_RUNTIME_REPAIR_STREAM_FAILED"),
        }]
    _stream_events(events)


def ai_runtime_repair():
    ai_assistant = wiz.model("struct").ai_assistant
    code = 200
    payload = {}
    try:
        result = ai_assistant.repair_runtime(wiz.request.query())
        service_id = (result.get("update_result") or {}).get("service", {}).get("id") or wiz.request.query().get("service_id")
        payload = {"result": result}
        if service_id:
            payload.update(_service_overview_payload(service_id))
    except Exception as exc:
        code = getattr(exc, "status_code", 400)
        payload = {
            "message": getattr(exc, "message", str(exc)),
            "error_code": getattr(exc, "code", None) or getattr(exc, "error_code", "AI_RUNTIME_REPAIR_FAILED"),
            **getattr(exc, "details", {}),
            **getattr(exc, "extra", {}),
        }
    wiz.response.status(code, **payload)


def start_runtime_ai_verification():
    ai_assistant = wiz.model("struct").ai_assistant
    code = 202
    payload = {}
    try:
        result = ai_assistant.start_runtime_verification(wiz.request.query())
        payload = {"result": result}
    except Exception as exc:
        code = getattr(exc, "status_code", 400)
        payload = {
            "message": getattr(exc, "message", str(exc)),
            "error_code": getattr(exc, "code", "AI_RUNTIME_VERIFY_START_FAILED"),
            **getattr(exc, "details", {}),
        }
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
    except DATABASE_ERRORS as exc:
        code = 503
        payload = {"message": str(exc), "error_code": "DATABASE_UNAVAILABLE"}

    wiz.response.status(code, **payload)


def deploy_service():
    services_model = wiz.model("struct").services
    code = 200
    payload = {}

    try:
        result = services_model.deploy(wiz.request.query())
        payload = {"result": result, **_service_overview_payload(result["service"]["id"])}
    except services_model.ServiceError as exc:
        code = exc.status_code
        payload = {"message": exc.message, "error_code": exc.error_code, **exc.extra}
    except DATABASE_ERRORS as exc:
        code = 503
        payload = {"message": str(exc), "error_code": "DATABASE_UNAVAILABLE"}
    except Exception as exc:
        code, payload = _raise_unless_service_error_like(exc)

    wiz.response.status(code, **payload)


def deploy_service_background():
    services_model = wiz.model("struct").services
    code = 202
    payload = {}

    try:
        result = services_model.deploy_background(wiz.request.query())
        payload = {"result": result, "operation": result.get("operation"), "service": result.get("service")}
    except services_model.ServiceError as exc:
        code = exc.status_code
        payload = {"message": exc.message, "error_code": exc.error_code, **exc.extra}
    except DATABASE_ERRORS as exc:
        code = 503
        payload = {"message": str(exc), "error_code": "DATABASE_UNAVAILABLE"}

    wiz.response.status(code, **payload)


def migrate_service():
    services_model = wiz.model("struct").services
    code = 202
    payload = {}

    try:
        result = services_model.migrate_background(wiz.request.query())
        payload = {
            "result": result,
            "operation": result.get("operation"),
            "service": result.get("service"),
            "target_node": result.get("target_node"),
        }
    except services_model.ServiceError as exc:
        code = exc.status_code
        payload = {"message": exc.message, "error_code": exc.error_code, **exc.extra}
    except DATABASE_ERRORS as exc:
        code = 503
        payload = {"message": str(exc), "error_code": "DATABASE_UNAVAILABLE"}

    wiz.response.status(code, **payload)


def release_service():
    services_model = wiz.model("struct").services
    code = 200
    payload = {}
    try:
        body = wiz.request.query()
        result = services_model.release(body)
        service_id = result["service"]["id"]
        payload = {"result": result, "operation": result.get("operation"), **_service_advanced_payload(service_id)}
        if _truthy(body.get("include_snapshots")):
            snapshot_result = services_model.snapshot_service_image_async({
                "service_id": service_id,
                "pause": body.get("snapshot_pause", True),
                "compose_version_id": result["compose_version"]["id"],
                "source": "manual_release_snapshot",
                "background": True,
            })
            payload["snapshot_result"] = snapshot_result
            payload["snapshot_operation"] = snapshot_result.get("operation")
            payload["operation"] = snapshot_result.get("operation") or payload.get("operation")
            code = 202
    except services_model.ComposeValidationError as exc:
        code = exc.status_code
        payload = {"message": exc.message, "error_code": exc.error_code, "details": exc.details}
    except services_model.ServiceError as exc:
        code = exc.status_code
        payload = {"message": exc.message, "error_code": exc.error_code, **exc.extra}
    except DATABASE_ERRORS as exc:
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
        payload = {"result": result}
        try:
            payload.update(catalog.services())
        except Exception as exc:
            payload["catalog_warning"] = {
                "message": str(exc),
                "error_code": "SERVICE_CATALOG_REFRESH_FAILED",
            }
    except services_model.ServiceError as exc:
        code = exc.status_code
        payload = {"message": exc.message, "error_code": exc.error_code, **exc.extra}
    except DATABASE_ERRORS as exc:
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
        payload = {"result": result, **_service_overview_payload(service_id, lightweight=True)}
    except services_model.ServiceError as exc:
        code = exc.status_code
        payload = {"message": exc.message, "error_code": exc.error_code, **exc.extra}
    except DATABASE_ERRORS as exc:
        code = 503
        payload = {"message": str(exc), "error_code": "DATABASE_UNAVAILABLE"}

    wiz.response.status(code, **payload)


def renew_service_certificate():
    services_model = wiz.model("struct").services
    body = wiz.request.query()
    code = 200
    payload = {}
    try:
        result = services_model.renew_certbot_certificate(body)
        service_id = body.get("service_id")
        payload = {"result": result, **_service_overview_payload(service_id)}
    except services_model.ServiceError as exc:
        code = exc.status_code
        payload = {"message": exc.message, "error_code": exc.error_code, **exc.extra}
    except DATABASE_ERRORS as exc:
        code = 503
        payload = {"message": str(exc), "error_code": "DATABASE_UNAVAILABLE"}

    wiz.response.status(code, **payload)


def ensure_service_certificate_renewal():
    services_model = wiz.model("struct").services
    body = wiz.request.query()
    code = 200
    payload = {}
    try:
        result = services_model.ensure_certbot_renewal(body)
        service_id = body.get("service_id")
        payload = {"result": result, **_service_overview_payload(service_id)}
    except services_model.ServiceError as exc:
        code = exc.status_code
        payload = {"message": exc.message, "error_code": exc.error_code, **exc.extra}
    except DATABASE_ERRORS as exc:
        code = 503
        payload = {"message": str(exc), "error_code": "DATABASE_UNAVAILABLE"}

    wiz.response.status(code, **payload)


def detail_service():
    body = wiz.request.query()
    service_id = body.get("service_id")
    if not service_id:
        wiz.response.status(400, message="service_id는 필수입니다.", error_code="SERVICE_ID_REQUIRED")
        return

    code = 200
    payload = {}
    try:
        payload = _service_overview_payload(service_id, lightweight=_truthy(body.get("lightweight") or body.get("basic")))
    except DATABASE_ERRORS as exc:
        code = 503
        payload = {"message": str(exc), "error_code": "DATABASE_UNAVAILABLE"}
    except Exception as exc:
        if _is_service_error_like(exc):
            code, payload = _service_error_response(exc)
        else:
            raise

    wiz.response.status(code, **payload)


def detail_service_logs():
    services_model = wiz.model("struct").services
    body = wiz.request.query()
    service_id = body.get("service_id")
    if not service_id:
        wiz.response.status(400, message="service_id는 필수입니다.", error_code="SERVICE_ID_REQUIRED")
        return

    code = 200
    payload = {}
    try:
        payload = services_model.detail_logs(service_id)
        payload["detail_sections"] = {"logs": True}
    except services_model.ServiceError as exc:
        code = exc.status_code
        payload = {"message": exc.message, "error_code": exc.error_code, **exc.extra}
    except DATABASE_ERRORS as exc:
        code = 503
        payload = {"message": str(exc), "error_code": "DATABASE_UNAVAILABLE"}

    wiz.response.status(code, **payload)


def detail_service_extras():
    body = wiz.request.query()
    service_id = body.get("service_id")
    if not service_id:
        wiz.response.status(400, message="service_id는 필수입니다.", error_code="SERVICE_ID_REQUIRED")
        return

    code = 200
    payload = {}
    try:
        payload = _service_extras_payload(service_id)
    except DATABASE_ERRORS as exc:
        code = 503
        payload = {"message": str(exc), "error_code": "DATABASE_UNAVAILABLE"}
    except Exception as exc:
        if _is_service_error_like(exc):
            code, payload = _service_error_response(exc)
        else:
            raise

    wiz.response.status(code, **payload)


def detail_service_backups():
    services_model = wiz.model("struct").services
    body = wiz.request.query()
    service_id = body.get("service_id")
    if not service_id:
        wiz.response.status(400, message="service_id는 필수입니다.", error_code="SERVICE_ID_REQUIRED")
        return

    code = 200
    payload = {}
    try:
        payload = services_model.detail_backups(service_id)
        payload["detail_sections"] = {"backups": True}
    except services_model.ServiceError as exc:
        code = exc.status_code
        payload = {"message": exc.message, "error_code": exc.error_code, **exc.extra}
    except DATABASE_ERRORS as exc:
        code = 503
        payload = {"message": str(exc), "error_code": "DATABASE_UNAVAILABLE"}

    wiz.response.status(code, **payload)


def detail_service_advanced():
    services_model = wiz.model("struct").services
    body = wiz.request.query()
    service_id = body.get("service_id")
    if not service_id:
        wiz.response.status(400, message="service_id는 필수입니다.", error_code="SERVICE_ID_REQUIRED")
        return

    code = 200
    payload = {}
    try:
        payload = _service_advanced_payload(service_id)
    except services_model.ServiceError as exc:
        code = exc.status_code
        payload = {"message": exc.message, "error_code": exc.error_code, **exc.extra}
    except DATABASE_ERRORS as exc:
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
        payload = {"result": result, **_service_advanced_payload(body.get("service_id"))}
    except services_model.ServiceError as exc:
        code = exc.status_code
        payload = {"message": exc.message, "error_code": exc.error_code, **exc.extra}
    except DATABASE_ERRORS as exc:
        code = 503
        payload = {"message": str(exc), "error_code": "DATABASE_UNAVAILABLE"}
    except Exception as exc:
        code, payload = _raise_unless_service_error_like(exc)
    wiz.response.status(code, **payload)


def save_compose_content():
    services_model = wiz.model("struct").services
    code = 200
    payload = {}
    try:
        body = wiz.request.query()
        result = services_model.update_compose_content(body)
        payload = {"result": result, **_service_advanced_payload(result["service"]["id"])}
    except services_model.ComposeValidationError as exc:
        code = exc.status_code
        payload = {"message": exc.message, "error_code": exc.error_code, "details": exc.details}
    except services_model.ServiceError as exc:
        code = exc.status_code
        payload = {"message": exc.message, "error_code": exc.error_code, **exc.extra}
    except DATABASE_ERRORS as exc:
        code = 503
        payload = {"message": str(exc), "error_code": "DATABASE_UNAVAILABLE"}
    except Exception as exc:
        code, payload = _raise_unless_service_error_like(exc)
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
        payload = {"result": result.get("result") or result, **_service_overview_payload(service_id)}
    except nodes_model.NodeError as exc:
        code = exc.status_code
        payload = {"message": exc.message, "error_code": exc.error_code, **exc.extra}
    except services_model.ServiceError as exc:
        code = exc.status_code
        payload = {"message": exc.message, "error_code": exc.error_code, **exc.extra}
    except DATABASE_ERRORS as exc:
        code = 503
        payload = {"message": str(exc), "error_code": "DATABASE_UNAVAILABLE"}
    wiz.response.status(code, **payload)


def _container_signal(container):
    state = str((container or {}).get("state") or "").lower()
    status = str((container or {}).get("status") or "").lower()
    if "unhealthy" in status:
        return "unhealthy"
    if "health: starting" in status:
        return "starting"
    if "healthy" in status:
        return "healthy"
    return state


def _can_run_container_action(container, action):
    allowed = {
        "start": {"created", "exited", "dead"},
        "restart": {"running", "healthy", "unhealthy", "starting", "paused", "created", "exited", "dead"},
        "stop": {"running", "healthy", "unhealthy", "starting", "paused", "restarting"},
    }
    return bool((container or {}).get("id") and (container or {}).get("node_id") and _container_signal(container) in allowed.get(action, set()))


def service_container_bulk_action():
    services_model = wiz.model("struct").services
    nodes_model = wiz.model("struct").nodes
    body = wiz.request.query()
    service_id = body.get("service_id")
    action = str(body.get("action") or "").strip().lower()
    if not service_id:
        wiz.response.status(400, message="service_id는 필수입니다.", error_code="SERVICE_ID_REQUIRED")
        return
    if action not in {"start", "stop", "restart"}:
        wiz.response.status(400, message="지원하지 않는 일괄 동작입니다.", error_code="INVALID_CONTAINER_BULK_ACTION")
        return

    code = 200
    payload = {}
    try:
        runtime = services_model.refresh_deploy_status(service_id).get("runtime_status") or {}
        containers = ((runtime.get("containers") or {}).get("containers") or [])
        targets = [item for item in containers if _can_run_container_action(item, action)]
        if not targets:
            raise services_model.ServiceError(409, "현재 상태에서 일괄 동작을 실행할 컨테이너가 없습니다.", "SERVICE_CONTAINER_BULK_EMPTY")
        results = []
        for target in targets:
            result = nodes_model.container_action(
                target.get("node_id"),
                {"container_id": target.get("id"), "action": action},
            )
            results.append({
                "container_id": target.get("id"),
                "name": target.get("name") or target.get("runtime_service_name"),
                "node_id": target.get("node_id"),
                "result": result.get("result") or result,
            })
        services_model.refresh_deploy_status(service_id)
        payload = {
            "result": {
                "action": action,
                "requested_count": len(targets),
                "succeeded_count": len(results),
                "items": results,
            },
            **_service_overview_payload(service_id),
        }
    except nodes_model.NodeError as exc:
        code = exc.status_code
        payload = {"message": exc.message, "error_code": exc.error_code, **exc.extra}
    except services_model.ServiceError as exc:
        code = exc.status_code
        payload = {"message": exc.message, "error_code": exc.error_code, **exc.extra}
    except DATABASE_ERRORS as exc:
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
        payload = {"result": result, **_service_overview_payload(result["service"]["id"])}
    except services_model.ComposeValidationError as exc:
        code = exc.status_code
        payload = {"message": exc.message, "error_code": exc.error_code, "details": exc.details}
    except services_model.ServiceError as exc:
        code = exc.status_code
        payload = {"message": exc.message, "error_code": exc.error_code, **exc.extra}
    except DATABASE_ERRORS as exc:
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
    except DATABASE_ERRORS as exc:
        code = 503
        payload = {"message": str(exc), "error_code": "DATABASE_UNAVAILABLE"}
    wiz.response.status(code, **payload)


def rollback_service():
    services_model = wiz.model("struct").services
    code = 200
    payload = {}
    try:
        result = services_model.rollback(wiz.request.query())
        service_id = result["service"]["id"]
        overview = _service_overview_payload(service_id)
        advanced = _service_advanced_payload(service_id)
        payload = {"result": result, **overview, **advanced}
        payload["detail_sections"] = {
            **(overview.get("detail_sections") or {}),
            **(advanced.get("detail_sections") or {}),
        }
    except services_model.ComposeValidationError as exc:
        code = exc.status_code
        payload = {"message": exc.message, "error_code": exc.error_code, "details": exc.details}
    except services_model.ServiceError as exc:
        code = exc.status_code
        payload = {"message": exc.message, "error_code": exc.error_code, **exc.extra}
    except DATABASE_ERRORS as exc:
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
    except DATABASE_ERRORS as exc:
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
    except DATABASE_ERRORS as exc:
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
    except DATABASE_ERRORS as exc:
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
    except DATABASE_ERRORS as exc:
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
    except DATABASE_ERRORS as exc:
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
    except DATABASE_ERRORS as exc:
        code = 503
        payload = {"message": str(exc), "error_code": "DATABASE_UNAVAILABLE"}

    wiz.response.status(code, **payload)


def snapshot_service_image():
    services_model = wiz.model("struct").services
    code = 200
    payload = {}
    try:
        body = wiz.request.query()
        if body.get("background"):
            payload = services_model.snapshot_service_image_async(body)
        else:
            payload = services_model.snapshot_service_image(body)
    except services_model.ServiceError as exc:
        code = exc.status_code
        payload = {"message": exc.message, "error_code": exc.error_code, **exc.extra}
    except DATABASE_ERRORS as exc:
        code = 503
        payload = {"message": str(exc), "error_code": "DATABASE_UNAVAILABLE"}
    except Exception as exc:
        if not _is_service_error_like(exc):
            raise
        code, payload = _service_error_response(exc)

    wiz.response.status(code, **payload)
