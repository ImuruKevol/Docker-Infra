import datetime
import json
import re
import uuid
from pathlib import Path

import yaml


config = wiz.config("docker_infra")
seed = wiz.model("struct/templates_seed")
services_wizard = wiz.model("struct/services_wizard")
validator = wiz.model("struct/compose_validator")

TEMPLATE_FILES = {
    "compose": "docker-compose.yaml",
    "values_default": "values.default.yaml",
    "values_schema": "values.schema.json",
    "readme": "README.md",
}

_SEED_TEMPLATE_CACHE = None
_SUMMARY_CACHE = {}
_DETAIL_CACHE = {}


def _seed_templates():
    global _SEED_TEMPLATE_CACHE
    if _SEED_TEMPLATE_CACHE is None:
        _SEED_TEMPLATE_CACHE = seed.default_templates()
    return _SEED_TEMPLATE_CACHE


def _mtime_ns(path):
    try:
        return path.stat().st_mtime_ns
    except Exception:
        return 0


def _template_dirs(root):
    return [
        directory
        for directory in sorted(root.iterdir(), key=lambda item: item.name)
        if directory.is_dir() and (directory / TEMPLATE_FILES["compose"]).exists()
    ]


def _summary_signature(root):
    return tuple(
        (
            directory.name,
            _mtime_ns(directory / "template.json"),
            _mtime_ns(directory / TEMPLATE_FILES["readme"]),
            _mtime_ns(directory / TEMPLATE_FILES["compose"]),
        )
        for directory in _template_dirs(root)
    )


def _detail_signature(directory):
    return (
        _mtime_ns(directory / "template.json"),
        *(_mtime_ns(directory / filename) for filename in TEMPLATE_FILES.values()),
    )


def _invalidate_cache(namespace=None, env=None):
    root = str(_template_root(env))
    for key in list(_SUMMARY_CACHE.keys()):
        if key[0] == root:
            _SUMMARY_CACHE.pop(key, None)
    if namespace is None:
        for key in list(_DETAIL_CACHE.keys()):
            if key[0] == root:
                _DETAIL_CACHE.pop(key, None)
        return
    namespace = _namespace(namespace)
    for key in list(_DETAIL_CACHE.keys()):
        if key[0] == root and key[1] == namespace:
            _DETAIL_CACHE.pop(key, None)


class TemplateError(Exception):
    def __init__(self, status_code, message, error_code, **extra):
        super().__init__(message)
        self.status_code = status_code
        self.message = message
        self.error_code = error_code
        self.extra = extra


def _now():
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def _namespace(value):
    clean = re.sub(r"_+", "_", re.sub(r"[^a-z0-9_]+", "_", str(value or "").strip().lower())).strip("_")
    return clean or f"template_{uuid.uuid4().hex[:8]}"


def _template_root(env=None):
    return Path(config.data_dir(env)) / "templates"


def _read_text(path, fallback=""):
    try:
        return path.read_text(encoding="utf-8")
    except Exception:
        return fallback


def _file_text(value):
    if isinstance(value, (dict, list)):
        return json.dumps(value, ensure_ascii=False, indent=2)
    return str(value or "")


def _safe_json(value, fallback=None):
    if isinstance(value, dict):
        return value
    try:
        return json.loads(value or "{}")
    except Exception:
        return fallback if fallback is not None else {}


def _safe_yaml(value):
    try:
        loaded = yaml.safe_load(value or "{}")
        return loaded if isinstance(loaded, dict) else {}
    except Exception:
        return {}


def _normalize_tags(value):
    raw = value if isinstance(value, list) else str(value or "").split(",")
    tags = []
    for item in raw:
        tag = str(item or "").strip()
        if tag and tag not in tags:
            tags.append(tag)
    return tags


def _normalize_metadata(value):
    metadata = value if isinstance(value, dict) else {}
    tags = _normalize_tags(metadata.get("tags"))
    if not tags:
        tags = _normalize_tags(metadata.get("category"))
    cleaned = {key: val for key, val in metadata.items() if key not in {"category", "primary_image"}}
    cleaned["tags"] = tags
    return cleaned


def _readme_excerpt(value):
    for line in str(value or "").splitlines():
        clean = line.strip().lstrip("#").strip()
        if clean:
            return clean[:140]
    return ""


def _is_secret_field(name, schema=None):
    if schema and schema.get("secret") is True:
        return True
    key = str(name or "").lower()
    return any(token in key for token in ["password", "passwd", "secret", "token", "api_key", "private_key"])


def _generated_secret():
    return uuid.uuid4().hex + uuid.uuid4().hex[:8]


def _render_template(content, values):
    def replace(match):
        key = match.group(1).strip()
        value = values.get(key, "")
        if value is None:
            return ""
        if isinstance(value, bool):
            return "true" if value else "false"
        return str(value)

    return re.sub(r"{{\s*([a-zA-Z0-9_.-]+)\s*}}", replace, content or "")


def _fields_from_schema(schema, values):
    properties = schema.get("properties") if isinstance(schema.get("properties"), dict) else {}
    required = set(schema.get("required") if isinstance(schema.get("required"), list) else [])
    names = list(properties.keys())
    for key in values.keys():
        if key not in names:
            names.append(key)
    fields = []
    for name in names:
        prop = properties.get(name) or {}
        fields.append(
            {
                "name": name,
                "title": prop.get("title") or name,
                "type": prop.get("type") or ("integer" if isinstance(values.get(name), int) else "string"),
                "description": prop.get("description") or "",
                "default": prop.get("default", values.get(name)),
                "required": name in required,
                "secret": _is_secret_field(name, prop),
                "enum": prop.get("enum") or [],
            }
        )
    return fields


class Templates:
    TemplateError = TemplateError
    ComposeValidationError = validator.ComposeValidationError

    def root(self, env=None):
        root = _template_root(env)
        root.mkdir(parents=True, exist_ok=True)
        return root

    def _dir(self, namespace, env=None):
        return self.root(env=env) / _namespace(namespace)

    def _record_path(self, namespace, env=None):
        return self._dir(namespace, env=env) / "template.json"

    def ensure_defaults(self, env=None):
        root = self.root(env=env)
        for item in _seed_templates():
            namespace = _namespace(item.get("namespace"))
            directory = root / namespace
            record_path = directory / "template.json"
            if record_path.exists():
                continue
            directory.mkdir(parents=True, exist_ok=True)
            files = item.get("files") or {}
            readme_text = _file_text(files.get("README.md") or files.get("readme"))
            if not readme_text.strip():
                raise TemplateError(400, "README.md는 필수입니다.", "TEMPLATE_README_REQUIRED")
            for key, filename in TEMPLATE_FILES.items():
                (directory / filename).write_text(_file_text(files.get(filename) or files.get(key)), encoding="utf-8")
            record = {
                "id": namespace,
                "namespace": namespace,
                "name": item.get("name") or namespace,
                "description": "",
                "enabled": item.get("enabled", True),
                "metadata": {**_normalize_metadata(item.get("metadata") or {}), "source": "seed"},
                "created_at": _now(),
                "updated_at": _now(),
            }
            record_path.write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8")

    def _read(self, namespace, include_files=False, env=None):
        directory = self._dir(namespace, env=env)
        if not directory.exists():
            raise TemplateError(404, "템플릿을 찾을 수 없습니다.", "TEMPLATE_NOT_FOUND")
        record = _safe_json(_read_text(directory / "template.json"), {})
        schema = _safe_json(_read_text(directory / TEMPLATE_FILES["values_schema"]), {})
        values = _safe_yaml(_read_text(directory / TEMPLATE_FILES["values_default"]))
        metadata = _normalize_metadata(record.get("metadata"))
        readme_text = _read_text(directory / TEMPLATE_FILES["readme"])
        if not record:
            record = {
                "id": directory.name,
                "namespace": directory.name,
                "name": schema.get("title") or directory.name,
                "description": "",
                "enabled": True,
                "metadata": metadata,
                "created_at": "",
                "updated_at": "",
            }
        record = {**record, "id": record.get("id") or directory.name, "namespace": directory.name}
        record["description"] = ""
        record["metadata"] = metadata
        record["fields"] = _fields_from_schema(schema, values)
        record["values"] = values
        record["readme_excerpt"] = _readme_excerpt(readme_text)
        if include_files:
            record["files"] = {key: _read_text(directory / filename) for key, filename in TEMPLATE_FILES.items()}
            record["schema"] = schema
        return record

    def _read_summary(self, namespace, env=None):
        directory = self._dir(namespace, env=env)
        if not directory.exists():
            raise TemplateError(404, "템플릿을 찾을 수 없습니다.", "TEMPLATE_NOT_FOUND")
        record = _safe_json(_read_text(directory / "template.json"), {})
        metadata = _normalize_metadata(record.get("metadata") if record else {})
        readme_text = _read_text(directory / TEMPLATE_FILES["readme"])
        if not record:
            record = {
                "id": directory.name,
                "namespace": directory.name,
                "name": directory.name,
                "description": "",
                "enabled": True,
                "metadata": metadata,
                "created_at": "",
                "updated_at": "",
            }
        record = {**record, "id": record.get("id") or directory.name, "namespace": directory.name}
        record["description"] = ""
        record["metadata"] = metadata
        record["readme_excerpt"] = _readme_excerpt(readme_text)
        return record

    def load(self, env=None):
        self.ensure_defaults(env=env)
        rows = []
        for directory in _template_dirs(self.root(env=env)):
            rows.append(self._read(directory.name, env=env))
        enabled = [item for item in rows if item.get("enabled") is not False]
        return {"templates": rows, "enabled_templates": enabled, "template_root": str(self.root(env=env))}

    def load_summaries(self, env=None):
        self.ensure_defaults(env=env)
        root = self.root(env=env)
        signature = _summary_signature(root)
        cache_key = (str(root), signature)
        cached = _SUMMARY_CACHE.get(cache_key)
        if cached is not None:
            return cached
        rows = [self._read_summary(directory.name, env=env) for directory in _template_dirs(root)]
        enabled = [item for item in rows if item.get("enabled") is not False]
        payload = {"templates": rows, "enabled_templates": enabled, "template_root": str(root)}
        _SUMMARY_CACHE.clear()
        _SUMMARY_CACHE[cache_key] = payload
        return payload

    def detail(self, template_id, env=None):
        self.ensure_defaults(env=env)
        namespace = _namespace(template_id)
        directory = self._dir(namespace, env=env)
        signature = _detail_signature(directory)
        cache_key = (str(self.root(env=env)), namespace, signature)
        cached = _DETAIL_CACHE.get(cache_key)
        if cached is not None:
            return cached
        payload = {"template": self._read(namespace, include_files=True, env=env)}
        _DETAIL_CACHE.clear()
        _DETAIL_CACHE[cache_key] = payload
        return payload

    def save(self, payload, env=None):
        body = payload or {}
        namespace = _namespace(body.get("namespace") or body.get("id") or body.get("name"))
        directory = self._dir(namespace, env=env)
        is_new = not (directory / "template.json").exists()
        directory.mkdir(parents=True, exist_ok=True)
        files = body.get("files") if isinstance(body.get("files"), dict) else {}
        readme_text = _file_text(files.get("readme") or body.get("readme"))
        if not readme_text.strip():
            raise TemplateError(400, "README.md는 필수입니다.", "TEMPLATE_README_REQUIRED")
        for key, filename in TEMPLATE_FILES.items():
            (directory / filename).write_text(_file_text(files.get(key) or body.get(key)), encoding="utf-8")
        metadata = _normalize_metadata(body.get("metadata"))
        record = {
            "id": namespace,
            "namespace": namespace,
            "name": str(body.get("name") or namespace).strip(),
            "description": "",
            "enabled": body.get("enabled") is not False,
            "metadata": metadata,
            "created_at": body.get("created_at") or _now(),
            "updated_at": _now(),
        }
        if is_new:
            record["created_at"] = _now()
        (directory / "template.json").write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8")
        _invalidate_cache(namespace, env=env)
        return {"template": self._read(namespace, include_files=True, env=env)}

    def delete(self, template_id, env=None):
        directory = self._dir(template_id, env=env)
        if not directory.exists():
            raise TemplateError(404, "템플릿을 찾을 수 없습니다.", "TEMPLATE_NOT_FOUND")
        for path in sorted(directory.rglob("*"), reverse=True):
            path.unlink() if path.is_file() else path.rmdir()
        directory.rmdir()
        _invalidate_cache(template_id, env=env)
        return {"deleted": True}

    def render(self, payload, env=None):
        body = payload or {}
        template_id = body.get("template_id") or body.get("id")
        detail = self._read(template_id, include_files=True, env=env)
        values = {**(detail.get("values") or {}), **(body.get("values") or {})}
        service_name = str(body.get("name") or values.get("service_name") or detail.get("name") or "").strip()
        values["service_name"] = service_name
        values["namespace"] = _namespace(service_name or values.get("namespace") or detail.get("namespace"))
        generated = []
        for field in detail.get("fields") or []:
            name = field["name"]
            current = str(values.get(name) or "").strip()
            if _is_secret_field(name, field) and (not current or current in {"change_me", "changeme"} or current.endswith("_change_me")):
                values[name] = _generated_secret()
                generated.append(name)
        rendered = _render_template((detail.get("files") or {}).get("compose"), values)
        return {"template": detail, "values": values, "rendered": rendered, "generated_secret_keys": generated}

    def preview(self, payload, env=None):
        rendered = self.render(payload, env=env)
        namespace = rendered["values"].get("namespace") or "template_preview"
        validation = validator.validate(
            {
                "namespace": namespace,
                "filename": "docker-compose.yaml",
                "content": rendered["rendered"],
                "allow_warnings": True,
                "warning_codes": ["FORBIDDEN_CONTAINER_NAME", "HEALTHCHECK_REQUIRED"],
            }
        )
        return {**rendered, "validation": validation}

    def prepare_service_draft(self, payload, env=None):
        rendered = self.preview(payload, env=env)
        template = rendered["template"]
        metadata = template.get("metadata") or {}
        components = services_wizard.components_from_content(rendered["rendered"], metadata=metadata)
        return {
            "filename": "docker-compose.yaml",
            "content": rendered["rendered"],
            "components": components,
            "suggested_name": payload.get("name") or template.get("name"),
            "generated_secret_keys": rendered.get("generated_secret_keys") or [],
            "source": "compose_template",
            "source_ref": {
                "source": "compose_template",
                "template_id": template.get("id"),
                "template_namespace": template.get("namespace"),
                "template_name": template.get("name"),
            },
            "summary": {
                "template": template.get("name"),
                "services": len(components),
                "ports": sum(len(item.get("ports") or []) for item in components),
            },
            "template": {"id": template.get("id"), "name": template.get("name"), "namespace": template.get("namespace")},
            "values": rendered.get("values") or {},
        }


Model = Templates()
