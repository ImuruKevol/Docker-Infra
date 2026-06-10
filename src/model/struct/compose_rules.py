import copy
import re

import yaml


NAMESPACE_PATTERN = re.compile(r"^[a-z0-9_]+$")
DEFAULT_FILENAME = "docker-compose.yaml"
ALLOWED_FILENAMES = {"docker-compose.yaml", "docker-compose.yml"}
OVERLAY_NETWORK = "docker_infra_overlay"
SERVICE_HOST_ENV_TOKENS = {
    "addr",
    "address",
    "addresses",
    "broker",
    "brokers",
    "contact",
    "contacts",
    "dsn",
    "endpoint",
    "endpoints",
    "host",
    "hostname",
    "hosts",
    "uri",
    "url",
}

DEFAULT_UPDATE_CONFIG = {
    "parallelism": 1,
    "delay": "10s",
    "failure_action": "rollback",
    "order": "start-first",
}
DEFAULT_ROLLBACK_CONFIG = {
    "parallelism": 1,
    "delay": "10s",
    "failure_action": "pause",
    "order": "stop-first",
}
DEFAULT_RESTART_POLICY = {
    "condition": "on-failure",
    "delay": "5s",
    "max_attempts": 3,
    "window": "120s",
}


class ComposeValidationError(Exception):
    def __init__(self, status_code, message, error_code, details=None, warning=False, can_continue=False):
        super().__init__(message)
        self.status_code = status_code
        self.message = message
        self.error_code = error_code
        self.details = details or []
        self.warning = warning
        self.can_continue = can_continue


def error(path, error_code, message, **extra):
    payload = {"path": path, "error_code": error_code, "message": message}
    payload.update(extra)
    return payload


def merge_defaults(value, defaults):
    if value is None:
        return copy.deepcopy(defaults)
    if not isinstance(value, dict):
        return None
    merged = copy.deepcopy(defaults)
    merged.update(value)
    return merged


def is_enabled_healthcheck(service):
    healthcheck = service.get("healthcheck")
    if not isinstance(healthcheck, dict):
        return False
    return healthcheck.get("disable") is not True


def has_health_check_override(payload):
    candidate = payload.get("health_check")
    if isinstance(candidate, bool):
        return candidate
    if isinstance(candidate, dict):
        return bool(candidate)
    return False


def format_path(parent, key):
    return str(key) if parent == "$" else f"{parent}.{key}"


def scan_duplicate_keys(node, path="$", errors=None):
    errors = errors if errors is not None else []
    if isinstance(node, yaml.MappingNode):
        seen = set()
        for key_node, value_node in node.value:
            key = key_node.value
            child_path = format_path(path, key)
            if key in seen:
                errors.append(error(child_path, "DUPLICATE_KEY", "YAML mapping key가 중복되었습니다."))
            seen.add(key)
            scan_duplicate_keys(value_node, child_path, errors)
    if isinstance(node, yaml.SequenceNode):
        for index, item in enumerate(node.value):
            scan_duplicate_keys(item, f"{path}[{index}]", errors)
    return errors


def load_compose(payload):
    errors = []
    if "compose" in payload:
        compose = payload.get("compose")
        if isinstance(compose, dict):
            return copy.deepcopy(compose), errors
        if isinstance(compose, str):
            content = compose
        else:
            return None, [error("compose", "INVALID_COMPOSE_DOCUMENT", "compose는 YAML 문자열 또는 object여야 합니다.")]
    else:
        content = payload.get("content")

    if not content:
        return None, [error("content", "COMPOSE_CONTENT_REQUIRED", "Compose YAML content는 필수입니다.")]
    if not isinstance(content, str):
        return None, [error("content", "INVALID_COMPOSE_CONTENT", "Compose YAML content는 문자열이어야 합니다.")]

    try:
        node = yaml.compose(content)
    except yaml.YAMLError as exc:
        return None, [error("content", "INVALID_YAML", "Compose YAML을 파싱할 수 없습니다.", reason=str(exc))]

    if node is None:
        return None, [error("content", "EMPTY_COMPOSE_DOCUMENT", "Compose YAML이 비어 있습니다.")]

    errors.extend(scan_duplicate_keys(node))
    if errors:
        return None, errors

    try:
        compose = yaml.safe_load(content)
    except yaml.YAMLError as exc:
        return None, [error("content", "INVALID_YAML", "Compose YAML을 파싱할 수 없습니다.", reason=str(exc))]
    return compose, errors


def network_names(value):
    if value is None:
        return []
    if isinstance(value, list):
        if not all(isinstance(item, str) for item in value):
            return None
        return value
    if isinstance(value, dict):
        return list(value.keys())
    return None


def is_internal_ref_env_key(key):
    normalized = re.sub(r"[^a-z0-9]+", "_", str(key or "").strip().lower()).strip("_")
    if not normalized:
        return False
    parts = {part for part in normalized.split("_") if part}
    if parts & SERVICE_HOST_ENV_TOKENS:
        return True
    return normalized in {"jdbc", "jdbc_connection_string", "connection_string", "database_connection_string"}


def _qualified_service_name(host, namespace, service_names):
    clean = str(host or "").strip().strip("[]")
    if not clean:
        return None
    for service_name in sorted([str(item) for item in service_names if str(item)], key=len, reverse=True):
        target = f"{namespace}_{service_name}"
        if clean == service_name or clean == target:
            return target
        if re.fullmatch(rf"[a-z0-9][a-z0-9_-]*_{re.escape(service_name)}", clean):
            return target
    return None


def qualify_internal_service_ref(value, namespace, service_names, enabled=True):
    text = str(value if value is not None else "")
    namespace = str(namespace or "").strip()
    if not namespace:
        return text
    text = text.replace("{{ namespace }}", namespace)
    if not enabled or "\n" in text or "\r" in text:
        return text

    names = [str(item) for item in service_names if str(item)]
    if not names:
        return text

    exact = re.fullmatch(r"(?P<host>[A-Za-z0-9_.-]+)(?P<port>:\d+)?", text)
    if exact:
        target = _qualified_service_name(exact.group("host"), namespace, names)
        if target:
            return f"{target}{exact.group('port') or ''}"

    def replace_url_host(match):
        target = _qualified_service_name(match.group("host"), namespace, names)
        if not target:
            return match.group(0)
        return f"{match.group('prefix')}{target}{match.group('port') or ''}"

    text = re.sub(
        r"(?P<prefix>://(?:[^/@\s]+@)?)(?P<host>[A-Za-z0-9_.-]+)(?P<port>:\d+)?",
        replace_url_host,
        text,
    )

    def replace_host_port(match):
        target = _qualified_service_name(match.group("host"), namespace, names)
        if not target:
            return match.group(0)
        return f"{match.group('prefix')}{target}{match.group('port')}"

    return re.sub(
        r"(?P<prefix>^|[,;\s])(?P<host>[A-Za-z0-9_.-]+)(?P<port>:\d+)(?=$|[,;\s])",
        replace_host_port,
        text,
    )


def qualify_environment_refs(environment, namespace, service_names):
    if isinstance(environment, dict):
        result = {}
        for key, value in environment.items():
            enabled = is_internal_ref_env_key(key)
            if not enabled and "{{ namespace }}" not in str(value if value is not None else ""):
                result[key] = value
                continue
            result[key] = qualify_internal_service_ref(value, namespace, service_names, enabled=enabled)
        return result
    if isinstance(environment, list):
        result = []
        for item in environment:
            if not isinstance(item, str) or "=" not in item:
                result.append(item)
                continue
            key, _, value = item.partition("=")
            result.append(
                f"{key}={qualify_internal_service_ref(value, namespace, service_names, enabled=is_internal_ref_env_key(key))}"
            )
        return result
    return environment


class ComposeRules:
    NAMESPACE_PATTERN = NAMESPACE_PATTERN
    DEFAULT_FILENAME = DEFAULT_FILENAME
    ALLOWED_FILENAMES = ALLOWED_FILENAMES
    OVERLAY_NETWORK = OVERLAY_NETWORK
    DEFAULT_UPDATE_CONFIG = DEFAULT_UPDATE_CONFIG
    DEFAULT_ROLLBACK_CONFIG = DEFAULT_ROLLBACK_CONFIG
    DEFAULT_RESTART_POLICY = DEFAULT_RESTART_POLICY
    ComposeValidationError = ComposeValidationError
    error = staticmethod(error)
    merge_defaults = staticmethod(merge_defaults)
    is_enabled_healthcheck = staticmethod(is_enabled_healthcheck)
    has_health_check_override = staticmethod(has_health_check_override)
    load_compose = staticmethod(load_compose)
    network_names = staticmethod(network_names)
    is_internal_ref_env_key = staticmethod(is_internal_ref_env_key)
    qualify_internal_service_ref = staticmethod(qualify_internal_service_ref)
    qualify_environment_refs = staticmethod(qualify_environment_refs)


Model = ComposeRules()
