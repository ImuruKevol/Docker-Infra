import datetime
import shutil
from pathlib import Path

import yaml
from psycopg.types.json import Jsonb


connect = wiz.model("db/postgres").connect
validator = wiz.model("struct/compose_validator")
preflight_model = wiz.model("struct/services_preflight")
webserver = wiz.model("struct/webserver")
ddns_model = wiz.model("struct/domains_ddns")
shared = wiz.model("struct/services_shared")
ServiceError = shared.ServiceError
_row = shared.row


def _safe_int(value, fallback):
    try:
        return int(value)
    except Exception:
        return fallback


def _history_id():
    return datetime.datetime.utcnow().strftime("%Y%m%d_%H%M%S")


class ServiceUpdateMixin:
    def _domain_payload(self, payload, domain, port, env=None):
        metadata = dict(payload.get("domain_metadata") or {})
        metadata["source"] = "service_update"
        zone_id = payload.get("zone_id") or metadata.get("zone_id")
        normalized = ddns_model.normalize_service_domain(
            domain,
            endpoint_id=zone_id,
            prefix=payload.get("domain_prefix") or metadata.get("domain_prefix"),
            fallback_prefix=payload.get("name") or payload.get("namespace") or metadata.get("compose_service"),
            env=env,
        )
        domain = normalized.get("domain") or domain
        ddns_endpoint = normalized.get("endpoint") or (ddns_model.match_domain(domain, endpoint_id=zone_id, env=env) if zone_id else ddns_model.match_domain(domain, env=env))
        if not ddns_endpoint:
            raise ServiceError(400, "서비스 도메인은 DDNS 관리 서버에 등록된 suffix 하위 주소만 사용할 수 있습니다.", "DDNS_ENDPOINT_REQUIRED", domain=domain)
        metadata.pop("zone_id", None)
        metadata.update({
            "dns_provider": "ddns",
            "routing_provider": "nginx",
            "ddns_endpoint_id": str(ddns_endpoint["id"]),
            "ddns_domain_suffix": ddns_endpoint.get("domain_suffix"),
            "domain_prefix": normalized.get("prefix"),
            "ddns_mode": "ddns_management",
        })
        ssl_mode = "none"
        if domain:
            certs = webserver.certificates_for_domain(domain, zone_id=None, env=env)
            ssl_mode = "existing" if int((certs.get("summary") or {}).get("valid") or 0) > 0 else "certbot"
        return ssl_mode, metadata

    def _replace_domain(self, cursor, service_id, payload, env=None):
        domain_rows = self._domain_rows_from_payload(payload, env=env)
        if not domain_rows:
            cursor.execute("DELETE FROM service_domains WHERE service_id = %s", (service_id,))
            return None
        keep = [item["domain"] for item in domain_rows]
        cursor.execute("DELETE FROM service_domains WHERE service_id = %s AND NOT (lower(domain) = ANY(%s))", (service_id, keep))
        saved = []
        for item in domain_rows:
            domain = item["domain"]
            port = item["port"]
            ssl_mode = item["ssl_mode"]
            metadata = item["metadata"]
            cursor.execute(
                """
                INSERT INTO service_domains(service_id, domain, port, proxy_type, ssl_mode, test_run_id, metadata)
                VALUES (%s, %s, %s, 'nginx', %s, %s, %s)
                ON CONFLICT (service_id, domain)
                DO UPDATE SET port = EXCLUDED.port, proxy_type = 'nginx', ssl_mode = EXCLUDED.ssl_mode, metadata = EXCLUDED.metadata, updated_at = now()
                RETURNING *
                """,
                (service_id, domain, port, ssl_mode, payload.get("test_run_id"), Jsonb(metadata)),
            )
            saved.append(_row(cursor.fetchone()))
        return saved[0] if saved else None

    def _domain_rows_from_payload(self, payload, env=None):
        payload = payload or {}
        raw_domains = payload.get("domains") if isinstance(payload.get("domains"), list) else []
        rows = []
        for item in raw_domains:
            if not isinstance(item, dict):
                continue
            domain = str(item.get("domain") or "").strip().lower()
            if not domain:
                continue
            port = _safe_int(item.get("port") or item.get("domain_target_port") or item.get("target_port") or payload.get("domain_target_port"), 80)
            metadata = dict(item.get("metadata") or {})
            metadata.update({
                "source": metadata.get("source") or "service_update",
                "compose_service": item.get("compose_service") or item.get("service_key") or metadata.get("compose_service"),
                "target_port": port,
                "published_port": _safe_int(item.get("published_port") or metadata.get("published_port") or port, port),
            })
            zone_id = item.get("zone_id") or payload.get("zone_id") or metadata.get("zone_id")
            normalized = ddns_model.normalize_service_domain(
                domain,
                endpoint_id=zone_id,
                prefix=item.get("domain_prefix") or item.get("prefix") or payload.get("domain_prefix") or metadata.get("domain_prefix"),
                fallback_prefix=payload.get("name") or payload.get("namespace") or metadata.get("compose_service"),
                env=env,
            )
            domain = normalized.get("domain") or domain
            ddns_endpoint = normalized.get("endpoint") or (ddns_model.match_domain(domain, endpoint_id=zone_id, env=env) if zone_id else ddns_model.match_domain(domain, env=env))
            if not ddns_endpoint:
                raise ServiceError(400, "서비스 도메인은 DDNS 관리 서버에 등록된 suffix 하위 주소만 사용할 수 있습니다.", "DDNS_ENDPOINT_REQUIRED", domain=domain)
            metadata.pop("zone_id", None)
            metadata.update({
                "dns_provider": "ddns",
                "routing_provider": "nginx",
                "ddns_endpoint_id": str(ddns_endpoint["id"]),
                "ddns_domain_suffix": ddns_endpoint.get("domain_suffix"),
                "domain_prefix": normalized.get("prefix"),
                "ddns_mode": "ddns_management",
            })
            ssl_mode = item.get("ssl_mode")
            if not ssl_mode:
                ssl_mode, metadata = self._domain_payload({**payload, "domain_metadata": metadata, "zone_id": zone_id}, domain, port, env=env)
            rows.append({"domain": domain, "port": port, "ssl_mode": ssl_mode, "metadata": metadata})
        if not rows and str(payload.get("domain") or "").strip():
            domain = str(payload.get("domain") or "").strip().lower()
            port = _safe_int(payload.get("port") or payload.get("domain_target_port"), 80)
            normalized = ddns_model.normalize_service_domain(
                domain,
                endpoint_id=payload.get("zone_id") or (payload.get("domain_metadata") or {}).get("zone_id"),
                prefix=payload.get("domain_prefix"),
                fallback_prefix=payload.get("name") or payload.get("namespace"),
                env=env,
            )
            domain = normalized.get("domain") or domain
            ssl_mode, metadata = self._domain_payload(payload, domain, port, env=env)
            rows.append({"domain": domain, "port": port, "ssl_mode": ssl_mode, "metadata": metadata})
        deduped = []
        seen = set()
        for item in rows:
            if item["domain"] in seen:
                continue
            seen.add(item["domain"])
            deduped.append(item)
        return deduped

    def update_wizard(self, payload, env=None):
        payload = payload or {}
        service_id = payload.get("service_id")
        if not service_id:
            raise ServiceError(400, "service_id는 필수입니다.", "SERVICE_ID_REQUIRED")
        name = str(payload.get("name") or "").strip()
        if not name:
            raise ServiceError(400, "서비스 이름을 입력해주세요.", "SERVICE_NAME_REQUIRED")
        content = payload.get("content")
        if not content:
            raise ServiceError(400, "수정할 Compose 내용이 필요합니다.", "SERVICE_CONTENT_REQUIRED")

        with connect(env=env) as connection:
            with connection.cursor() as cursor:
                service = self._service_row(cursor, service_id)

        namespace = service["namespace"]
        validation = validator.validate({"namespace": namespace, "filename": "docker-compose.yaml", "content": content})
        preflight = preflight_model.check({**payload, "service_id": service_id}, content, namespace, validation=validation, env=env)
        if preflight.get("ok") is not True:
            raise ServiceError(409, "서비스 수정 전에 해결해야 할 항목이 있습니다.", "SERVICE_PREFLIGHT_BLOCKED", preflight=preflight)

        normalized_content = yaml.safe_dump(validation["normalized"], sort_keys=False, allow_unicode=False)
        compose_path = Path(service["compose_path"]).expanduser()
        compose_path.parent.mkdir(parents=True, exist_ok=True)
        history_id = _history_id()
        history_dir = compose_path.parent / ".history" / history_id
        history_dir.mkdir(parents=True, exist_ok=True)
        if compose_path.exists():
            shutil.copy2(compose_path, history_dir / f"previous-{compose_path.name}")
        compose_path.write_text(normalized_content, encoding="utf-8")
        shutil.copy2(compose_path, history_dir / compose_path.name)

        metadata = dict(service.get("metadata") or {})
        metadata.update({
            "description": str(payload.get("description") or "").strip(),
            "source": metadata.get("source") or "ui_wizard",
            "last_update": {"history_id": history_id, "source": "service_update"},
            "wizard": payload.get("wizard") or {"components": payload.get("components") or [], "domain_mode": payload.get("domain_mode")},
        })
        if payload.get("operator_comment") is not None:
            operator_comment = str(payload.get("operator_comment") or "").strip()
            if operator_comment:
                metadata["operator_comment"] = operator_comment
            else:
                metadata.pop("operator_comment", None)

        with connect(env=env) as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    UPDATE services
                    SET name = %s, status = 'draft', metadata = %s, updated_at = now()
                    WHERE id = %s
                    RETURNING *
                    """,
                    (name, Jsonb(metadata), service_id),
                )
                service = _row(cursor.fetchone())
                domain = self._replace_domain(cursor, service_id, payload, env=env)
        return {"service": service, "domain": domain, "validation": validation, "preflight": preflight, "history_id": history_id}

    def update_basic(self, payload, env=None):
        payload = payload or {}
        service_id = payload.get("service_id")
        if not service_id:
            raise ServiceError(400, "service_id는 필수입니다.", "SERVICE_ID_REQUIRED")
        name = str(payload.get("name") or "").strip()
        if not name:
            raise ServiceError(400, "서비스 이름을 입력해주세요.", "SERVICE_NAME_REQUIRED")

        include_domain = bool(payload.get("include_domain"))
        if include_domain and payload.get("domain_mode") == "registered" and not str(payload.get("domain") or "").strip():
            raise ServiceError(400, "DDNS 도메인을 입력해주세요.", "SERVICE_DOMAIN_REQUIRED")

        with connect(env=env) as connection:
            with connection.cursor() as cursor:
                service = self._service_row(cursor, service_id)
                metadata = dict(service.get("metadata") or {})
                metadata["description"] = str(payload.get("description") or "").strip()
                if payload.get("operator_comment") is not None:
                    operator_comment = str(payload.get("operator_comment") or "").strip()
                    if operator_comment:
                        metadata["operator_comment"] = operator_comment
                    else:
                        metadata.pop("operator_comment", None)
                metadata["last_basic_update"] = {
                    "source": "service_basic_update",
                    "updated_at": datetime.datetime.utcnow().isoformat() + "Z",
                    "domain_included": include_domain,
                }
                cursor.execute(
                    """
                    UPDATE services
                    SET name = %s, metadata = %s, updated_at = now()
                    WHERE id = %s
                    RETURNING *
                    """,
                    (name, Jsonb(metadata), service_id),
                )
                service = _row(cursor.fetchone())
                domain = self._replace_domain(cursor, service_id, payload, env=env) if include_domain else None
        return {"service": service, "domain": domain, "domain_updated": include_domain}

    def update_compose_content(self, payload, env=None):
        payload = payload or {}
        service_id = payload.get("service_id")
        if not service_id:
            raise ServiceError(400, "service_id는 필수입니다.", "SERVICE_ID_REQUIRED")
        content = payload.get("content")
        if not content:
            raise ServiceError(400, "수정할 Compose 내용이 필요합니다.", "SERVICE_CONTENT_REQUIRED")

        with connect(env=env) as connection:
            with connection.cursor() as cursor:
                service = self._service_row(cursor, service_id)

        namespace = service["namespace"]
        validation = validator.validate({"namespace": namespace, "filename": "docker-compose.yaml", "content": content})
        preflight = preflight_model.check({**payload, "service_id": service_id}, content, namespace, validation=validation, env=env)
        if preflight.get("ok") is not True:
            raise ServiceError(409, "Compose 원문을 저장하기 전에 해결해야 할 항목이 있습니다.", "SERVICE_PREFLIGHT_BLOCKED", preflight=preflight)

        normalized_content = yaml.safe_dump(validation["normalized"], sort_keys=False, allow_unicode=False)
        compose_path = Path(service["compose_path"]).expanduser()
        compose_path.parent.mkdir(parents=True, exist_ok=True)
        history_id = _history_id()
        history_dir = compose_path.parent / ".history" / history_id
        history_dir.mkdir(parents=True, exist_ok=True)
        if compose_path.exists():
            shutil.copy2(compose_path, history_dir / f"previous-{compose_path.name}")
        compose_path.write_text(normalized_content, encoding="utf-8")
        shutil.copy2(compose_path, history_dir / compose_path.name)

        metadata = dict(service.get("metadata") or {})
        if payload.get("description") is not None:
            metadata["description"] = str(payload.get("description") or "").strip()
        metadata.update({
            "source": metadata.get("source") or "ui_wizard",
            "last_update": {"history_id": history_id, "source": "compose_raw_update"},
        })

        name = str(payload.get("name") or service.get("name") or "").strip()
        with connect(env=env) as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    UPDATE services
                    SET name = %s, status = 'draft', metadata = %s, updated_at = now()
                    WHERE id = %s
                    RETURNING *
                    """,
                    (name, Jsonb(metadata), service_id),
                )
                service = _row(cursor.fetchone())
        return {"service": service, "validation": validation, "preflight": preflight, "history_id": history_id}


Model = ServiceUpdateMixin
