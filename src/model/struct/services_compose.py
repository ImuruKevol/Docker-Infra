import yaml


validator = wiz.model("struct/compose_validator")


def _safe_int(value, fallback):
    try:
        return int(value)
    except Exception:
        return fallback


def _dict_items(items):
    return [item for item in (items or []) if isinstance(item, dict)]


class ServiceCompose:
    ComposeValidationError = validator.ComposeValidationError

    def default_compose(self, namespace, service_name="web", image="nginx:alpine", port=80, env_vars=None, volumes=None):
        service_name = service_name or "web"
        port = _safe_int(port, 80)
        service = {
            "image": image or "nginx:alpine",
            "ports": [{
                "target": port,
                "published": port,
                "protocol": "tcp",
                "mode": "host",
            }],
            "healthcheck": {
                "test": ["CMD", "wget", "-qO-", f"http://127.0.0.1:{port}"],
                "interval": "30s",
                "timeout": "5s",
                "retries": 3,
            },
        }

        environment = {
            str(item.get("key")).strip(): str(item.get("value") or "")
            for item in _dict_items(env_vars)
            if str(item.get("key") or "").strip()
        }
        if environment:
            service["environment"] = environment

        normalized_volumes = [
            f"{str(item.get('source') or '').strip()}:{str(item.get('target') or '').strip()}"
            for item in _dict_items(volumes)
            if str(item.get("source") or "").strip() and str(item.get("target") or "").strip()
        ]
        if normalized_volumes:
            service["volumes"] = normalized_volumes

        compose = {"services": {service_name: service}}
        named_volumes = [
            str(item.get("source") or "").strip()
            for item in _dict_items(volumes)
            if str(item.get("source") or "").strip()
            and not str(item.get("source") or "").strip().startswith("/")
            and ":" not in str(item.get("source") or "").strip()
            and "\\" not in str(item.get("source") or "").strip()
        ]
        if named_volumes:
            compose["volumes"] = {name: {} for name in sorted(set(named_volumes))}

        result = validator.validate({
            "namespace": namespace,
            "filename": "docker-compose.yaml",
            "compose": compose,
        })
        return yaml.safe_dump(result["normalized"], sort_keys=False, allow_unicode=False)

    def _port_matches(self, ports, expected):
        expected = str(expected)
        for item in ports or []:
            raw = str(item).split("/", 1)[0].strip().strip('"')
            host_target = raw.rsplit(":", 1)[-1] if ":" in raw else raw
            if host_target == expected:
                return True
        return False

    def conflicts(self, payload):
        payload = payload or {}
        validation = validator.validate({
            "namespace": payload.get("namespace"),
            "filename": payload.get("filename") or "docker-compose.yaml",
            "content": payload.get("content"),
            "allow_warnings": True,
            "warning_codes": ["FORBIDDEN_CONTAINER_NAME"],
        })
        compose = validation["normalized"]
        services = compose.get("services") or {}
        service_name = str(payload.get("service_name") or "web").strip()
        image = str(payload.get("image") or "").strip()
        port = payload.get("port")
        conflicts = []

        service = services.get(service_name)
        if service is None:
            conflicts.append({"field": "service_name", "message": f"Compose에 {service_name} 서비스가 없습니다."})
            service = next(iter(services.values())) if services else {}

        if image and str(service.get("image") or "").strip() != image:
            conflicts.append({"field": "image", "message": "폼의 이미지와 Compose 이미지가 다릅니다."})
        if port and not self._port_matches(service.get("ports") or [], port):
            conflicts.append({"field": "port", "message": f"Compose ports에 내부 port {port} 연결이 없습니다."})

        environment = service.get("environment") or {}
        if isinstance(environment, list):
            parsed = {}
            for item in environment:
                key, _, value = str(item).partition("=")
                parsed[key] = value
            environment = parsed
        for item in payload.get("env_vars") or []:
            key = str(item.get("key") or "").strip()
            if key and str(environment.get(key, "")) != str(item.get("value") or ""):
                conflicts.append({"field": f"environment.{key}", "message": f"{key} 환경변수 값이 폼과 다릅니다."})

        compose_volumes = {str(item) for item in service.get("volumes") or []}
        for item in payload.get("volumes") or []:
            source = str(item.get("source") or "").strip()
            target = str(item.get("target") or "").strip()
            if source and target and f"{source}:{target}" not in compose_volumes:
                conflicts.append({"field": f"volumes.{target}", "message": f"{target} 볼륨 연결이 Compose와 다릅니다."})

        return {"valid": True, "conflicts": conflicts, "validation": validation}


Model = ServiceCompose()
