import datetime
import hashlib
import shutil
from pathlib import Path

import yaml
from psycopg.types.json import Jsonb


connect = wiz.model("db/postgres").connect
validator = wiz.model("struct/compose_validator")
operations = wiz.model("struct/operations")
image_backups = wiz.model("struct/service_image_backups")
shared = wiz.model("struct/services_shared")
ServiceError = shared.ServiceError
_row = shared.row


def _utc_id():
    return datetime.datetime.utcnow().strftime("%Y%m%d_%H%M%S")


def _checksum(content):
    return hashlib.sha256(str(content or "").encode("utf-8")).hexdigest()


def _safe_int(value):
    try:
        return int(value)
    except Exception:
        return None


def _port(raw):
    protocol = "tcp"
    target = None
    published = None
    if isinstance(raw, dict):
        target = _safe_int(raw.get("target") or raw.get("published"))
        published = _safe_int(raw.get("published") or target)
        protocol = str(raw.get("protocol") or "tcp")
    else:
        text = str(raw or "").strip().strip('"')
        base, _, proto = text.partition("/")
        chunks = base.split(":")
        target = _safe_int(chunks[-1]) if chunks else None
        published = _safe_int(chunks[-2]) if len(chunks) >= 2 else target
        protocol = proto or "tcp"
    label = f"{published or '-'} -> {target or '-'}/{protocol}"
    return {"published": published, "target": target, "protocol": protocol, "label": label}


def _compose_summary(compose):
    result = {}
    for name, service in ((compose or {}).get("services") or {}).items():
        service = service if isinstance(service, dict) else {}
        env = service.get("environment") or {}
        if isinstance(env, list):
            env_keys = [str(item).split("=", 1)[0] for item in env]
        else:
            env_keys = sorted([str(key) for key in env.keys()])
        ports = [_port(item) for item in service.get("ports") or []]
        result[str(name)] = {
            "image": str(service.get("image") or ""),
            "ports": ports,
            "port_labels": [item["label"] for item in ports],
            "env_keys": env_keys,
            "volume_count": len(service.get("volumes") or []),
        }
    return result


def _load_yaml(content):
    try:
        return yaml.safe_load(content or "{}") or {}
    except yaml.YAMLError as exc:
        raise ServiceError(400, f"Compose를 읽을 수 없습니다: {exc}", "COMPOSE_PARSE_FAILED")


class ServiceRollbackMixin:
    def _version_row(self, cursor, service_id, version_id):
        cursor.execute(
            "SELECT * FROM compose_versions WHERE id = %s AND service_id = %s",
            (version_id, service_id),
        )
        row = cursor.fetchone()
        if row is None:
            raise ServiceError(404, "Compose 버전을 찾을 수 없습니다.", "COMPOSE_VERSION_NOT_FOUND")
        return _row(row)

    def _rollback_target(self, service_id, version_id, env=None):
        with connect(env=env) as connection:
            with connection.cursor() as cursor:
                service = self._service_row(cursor, service_id)
                version = self._version_row(cursor, service_id, version_id)
                cursor.execute(
                    "SELECT * FROM service_domains WHERE service_id = %s ORDER BY created_at ASC",
                    (service_id,),
                )
                domains = [_row(row) for row in cursor.fetchall()]
        path = Path(version["path"]).expanduser()
        if not path.is_file():
            raise ServiceError(404, "선택한 버전의 Compose 파일을 찾을 수 없습니다.", "COMPOSE_VERSION_FILE_NOT_FOUND")
        target_content = path.read_text(encoding="utf-8")
        validation = validator.validate({
            "namespace": service["namespace"],
            "filename": Path(service.get("compose_path") or "docker-compose.yaml").name,
            "content": target_content,
        })
        return service, version, domains, target_content, validation

    def rollback_plan(self, payload, env=None):
        payload = payload or {}
        service_id = payload.get("service_id")
        version_id = payload.get("version_id")
        if not service_id:
            raise ServiceError(400, "service_id는 필수입니다.", "SERVICE_ID_REQUIRED")
        if not version_id:
            raise ServiceError(400, "version_id는 필수입니다.", "COMPOSE_VERSION_ID_REQUIRED")

        service, version, domains, target_content, validation = self._rollback_target(service_id, version_id, env=env)
        compose_path = Path(service["compose_path"]).expanduser()
        current_content = compose_path.read_text(encoding="utf-8") if compose_path.is_file() else ""
        current = _compose_summary(_load_yaml(current_content))
        target = _compose_summary(validation["normalized"])

        added = sorted([name for name in target.keys() if name not in current])
        removed = sorted([name for name in current.keys() if name not in target])
        image_changes = []
        port_changes = []
        for name in sorted(set(current.keys()) & set(target.keys())):
            if current[name]["image"] != target[name]["image"]:
                image_changes.append({"service": name, "from": current[name]["image"], "to": target[name]["image"]})
            if current[name]["port_labels"] != target[name]["port_labels"]:
                port_changes.append({"service": name, "from": current[name]["port_labels"], "to": target[name]["port_labels"]})

        target_ports = {
            item["target"]
            for service in target.values()
            for item in service["ports"]
            if item.get("target") is not None
        }
        domain_impacts = []
        for domain in domains:
            port = _safe_int(domain.get("port"))
            matched = port is None or port in target_ports
            domain_impacts.append({
                "domain": domain.get("domain"),
                "port": port,
                "status": "matched" if matched else "warning",
                "message": "연결 포트가 복원할 Compose에 있습니다." if matched else "현재 도메인 연결 포트가 복원할 Compose에 없습니다.",
            })

        return {
            "service": service,
            "target_version": version,
            "summary": {
                "same_content": _checksum(current_content) == _checksum(target_content),
                "services": len(target),
                "added_services": len(added),
                "removed_services": len(removed),
                "image_changes": len(image_changes),
                "port_changes": len(port_changes),
                "domain_warnings": len([item for item in domain_impacts if item["status"] == "warning"]),
            },
            "changes": {
                "added_services": added,
                "removed_services": removed,
                "image_changes": image_changes,
                "port_changes": port_changes,
                "domain_impacts": domain_impacts,
            },
        }

    def rollback(self, payload, env=None):
        payload = payload or {}
        service_id = payload.get("service_id")
        version_id = payload.get("version_id")
        plan = self.rollback_plan(payload, env=env)
        service, version, _domains, target_content, validation = self._rollback_target(service_id, version_id, env=env)
        compose_path = Path(service["compose_path"]).expanduser()
        compose_path.parent.mkdir(parents=True, exist_ok=True)
        history_id = f"rollback_{_utc_id()}"
        history_dir = compose_path.parent / ".history" / history_id
        history_dir.mkdir(parents=True, exist_ok=True)
        previous_path = history_dir / f"previous-{compose_path.name}"
        if compose_path.exists():
            shutil.copy2(compose_path, previous_path)
        compose_path.write_text(target_content, encoding="utf-8")
        applied_path = history_dir / compose_path.name
        shutil.copy2(compose_path, applied_path)
        checksum = _checksum(target_content)

        metadata = dict(service.get("metadata") or {})
        metadata["last_rollback"] = {
            "history_id": history_id,
            "target_version_id": version["id"],
            "target_version": version["version"],
            "previous_path": str(previous_path) if previous_path.exists() else "",
        }
        with connect(env=env) as connection:
            with connection.cursor() as cursor:
                cursor.execute("SELECT COALESCE(max(version), 0) + 1 AS next_version FROM compose_versions WHERE service_id = %s", (service_id,))
                next_version = int(cursor.fetchone()["next_version"])
                cursor.execute(
                    "UPDATE services SET status = 'draft', metadata = %s, updated_at = now() WHERE id = %s RETURNING *",
                    (Jsonb(metadata), service_id),
                )
                updated_service = _row(cursor.fetchone())
                cursor.execute(
                    """
                    INSERT INTO compose_versions(service_id, version, path, checksum, test_run_id, metadata)
                    VALUES (%s, %s, %s, %s, %s, %s)
                    RETURNING *
                    """,
                    (
                        service_id,
                        next_version,
                        str(applied_path),
                        checksum,
                        service.get("test_run_id"),
                        Jsonb({"source": "compose_rollback", "history_id": history_id, "target_version_id": version["id"], "target_version": version["version"]}),
                    ),
                )
                compose_version = _row(cursor.fetchone())

        image_rows = image_backups.record(
            updated_service,
            validation["normalized"],
            compose_version_id=compose_version["id"],
            source="compose_rollback",
            test_run_id=updated_service.get("test_run_id"),
            metadata={"namespace": updated_service.get("namespace"), "target_version": version["version"]},
            env=env,
        )
        operation = operations.create(
            "service.compose.rollback",
            target_type="service",
            target_id=service_id,
            status="succeeded",
            message=f"Compose 버전 {version['version']} 기준으로 되돌림",
            requested_payload={"service_id": service_id, "version_id": version_id},
            result_payload={"compose_version": compose_version["version"], "target_version": version["version"]},
            metadata={"service_id": service_id, "namespace": updated_service.get("namespace")},
            env=env,
        )
        return {
            "service": updated_service,
            "compose_version": compose_version,
            "image_backups": image_rows,
            "operation": operation,
            "plan": plan,
        }


Model = ServiceRollbackMixin
