import hashlib
import json
import re
import shutil
from pathlib import Path

import yaml
from psycopg.types.json import Jsonb


connect = wiz.model("db/postgres").connect
config = wiz.config("docker_infra")
validator = wiz.model("struct/compose_validator")
shared = wiz.model("struct/templates_shared")
TemplateError = shared.TemplateError
_row = shared.row
_json_text = shared.json_text

FILES = ("docker-compose.yaml", "values.default.yaml", "values.schema.json", "README.md")


def _normalize_namespace(value):
    return re.sub(r"_+", "_", re.sub(r"[^a-z0-9_]+", "_", str(value or "").strip().lower())).strip("_")


def _render_text(text, values):
    payload = values or {}
    def replace(match):
        key = match.group(1).strip()
        value = payload.get(key, "")
        if isinstance(value, bool):
            return "true" if value else "false"
        if isinstance(value, (dict, list)):
            return json.dumps(value, ensure_ascii=False)
        return str(value if value is not None else "")
    return re.sub(r"\{\{\s*([^}]+?)\s*\}\}", replace, text or "")


def _text_content(value):
    if isinstance(value, (dict, list)):
        return json.dumps(value, indent=2, ensure_ascii=False)
    return str(value or "")


class TemplateStore:
    TemplateError = TemplateError

    def template_root(self):
        root = Path(config.data_dir()) / "templates"
        root.mkdir(parents=True, exist_ok=True)
        return root

    def template_dir(self, namespace):
        return self.template_root() / namespace

    def overview(self, env=None):
        with connect(env=env) as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT t.*, COALESCE(v.version_count, 0) AS version_count, v.latest_version
                    FROM templates t
                    LEFT JOIN (
                        SELECT template_id, count(*) AS version_count, max(version) AS latest_version
                        FROM template_versions
                        GROUP BY template_id
                    ) v ON v.template_id = t.id
                    ORDER BY t.created_at ASC, t.name ASC
                    """
                )
                templates = [_row(item) for item in cursor.fetchall()]
        return {"template_root": str(self.template_root()), "templates": templates}

    def detail(self, template_id, env=None):
        with connect(env=env) as connection:
            with connection.cursor() as cursor:
                cursor.execute("SELECT * FROM templates WHERE id = %s", (template_id,))
                template = _row(cursor.fetchone())
                if template is None:
                    raise TemplateError(404, "템플릿을 찾을 수 없습니다.", "TEMPLATE_NOT_FOUND")
                cursor.execute("SELECT * FROM template_versions WHERE template_id = %s ORDER BY version DESC, created_at DESC", (template_id,))
                versions = [_row(item) for item in cursor.fetchall()]
        files = self.read_files(template["path"])
        rendered = self.render_preview(files["docker-compose.yaml"], files["values.default.yaml"], template["namespace"])
        return {"template": template, "files": files, "versions": versions, "preview": rendered}

    def version_detail(self, version_id, env=None):
        with connect(env=env) as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT v.*, t.id AS template_id, t.name AS template_name, t.namespace AS template_namespace
                    FROM template_versions v
                    JOIN templates t ON t.id = v.template_id
                    WHERE v.id = %s
                    """,
                    (version_id,),
                )
                row = cursor.fetchone()
                version = _row(row)
                if version is None:
                    raise TemplateError(404, "템플릿 버전을 찾을 수 없습니다.", "TEMPLATE_VERSION_NOT_FOUND")
        files = self.read_files(version["path"])
        rendered = self.render_preview(files["docker-compose.yaml"], files["values.default.yaml"], version["template_namespace"])
        return {
            "version": version,
            "template": {
                "id": version["template_id"],
                "name": version["template_name"],
                "namespace": version["template_namespace"],
            },
            "files": files,
            "preview": rendered,
        }

    def preview(self, payload, env=None):
        body = payload or {}
        namespace = _normalize_namespace(body.get("namespace"))
        if not namespace:
            raise TemplateError(400, "템플릿 ID가 필요합니다.", "TEMPLATE_NAMESPACE_REQUIRED")
        compose_text = str(body.get("compose") or "")
        values_default_text = str(body.get("values_default") or "")
        if not compose_text.strip():
            raise TemplateError(400, "Compose 본문이 비어 있습니다.", "TEMPLATE_COMPOSE_REQUIRED")
        return self.render_preview(compose_text, values_default_text, namespace)

    def save(self, payload, env=None):
        body = payload or {}
        requested_id = body.get("id")
        requested_name = str(body.get("name") or "").strip()
        if not requested_name:
            raise TemplateError(400, "템플릿 이름이 필요합니다.", "TEMPLATE_NAME_REQUIRED")
        files = {
            "docker-compose.yaml": _text_content(body.get("compose")).rstrip() + "\n",
            "values.default.yaml": _text_content(body.get("values_default")).rstrip() + "\n",
            "values.schema.json": _text_content(body.get("values_schema")).rstrip() + "\n",
            "README.md": _text_content(body.get("readme")).rstrip() + "\n",
        }
        template = None
        namespace = ""
        with connect(env=env) as connection:
            with connection.cursor() as cursor:
                current = None
                if requested_id:
                    cursor.execute("SELECT * FROM templates WHERE id = %s", (requested_id,))
                    current = cursor.fetchone()
                namespace = _normalize_namespace((current or {}).get("namespace") if current else body.get("namespace") or requested_name)
                if not namespace:
                    namespace = "template"
                if current is None:
                    namespace = self._unique_namespace(cursor, namespace)
                self._validate_files(namespace, files)
                target_dir = self.template_dir(namespace)
                target_dir.mkdir(parents=True, exist_ok=True)
                for file_name, content in files.items():
                    (target_dir / file_name).write_text(content, encoding="utf-8")
                if current is None:
                    cursor.execute(
                        """
                        INSERT INTO templates(name, namespace, path, description, enabled, metadata)
                        VALUES (%s, %s, %s, %s, %s, %s)
                        RETURNING *
                        """,
                        (requested_name, namespace, str(target_dir), str(body.get("description") or "").strip(), body.get("enabled") is not False, Jsonb(body.get("metadata") or {})),
                    )
                    template = _row(cursor.fetchone())
                else:
                    cursor.execute(
                        """
                        UPDATE templates
                        SET name = %s, namespace = %s, path = %s, description = %s, enabled = %s, metadata = %s
                        WHERE id = %s
                        RETURNING *
                        """,
                        (requested_name, namespace, str(target_dir), str(body.get("description") or "").strip(), body.get("enabled") is not False, Jsonb(body.get("metadata") or {}), current["id"]),
                    )
                    template = _row(cursor.fetchone())
        return {"template": template, "preview": self.render_preview(files["docker-compose.yaml"], files["values.default.yaml"], namespace)}

    def release(self, payload, env=None):
        result = self.save(payload, env=env)
        template = result["template"]
        with connect(env=env) as connection:
            with connection.cursor() as cursor:
                version = self._create_version_snapshot(cursor, template, {"source": (payload or {}).get("source") or "templates_ui_release"})
        return {"template": template, "version": version, "preview": result["preview"]}

    def delete(self, template_id, env=None):
        detail = self.detail(template_id, env=env)
        path = Path(detail["template"]["path"]).expanduser()
        if path.is_dir():
            shutil.rmtree(path)
        with connect(env=env) as connection:
            with connection.cursor() as cursor:
                cursor.execute("DELETE FROM templates WHERE id = %s", (template_id,))
        return True

    def read_files(self, template_path):
        root = Path(template_path).expanduser()
        return {file_name: (root / file_name).read_text(encoding="utf-8") if (root / file_name).exists() else "" for file_name in FILES}

    def render_preview(self, compose_text, values_default_text, namespace):
        values = yaml.safe_load(values_default_text or "{}") or {}
        rendered = _render_text(compose_text or "", values)
        validation = validator.validate({"namespace": namespace, "filename": "docker-compose.yaml", "content": rendered})
        return {"values": values, "rendered_compose": rendered, "validation": validation}

    def has_templates(self, env=None):
        with connect(env=env) as connection:
            with connection.cursor() as cursor:
                cursor.execute("SELECT count(*) AS count FROM templates")
                return int(cursor.fetchone()["count"]) > 0

    def namespaces(self, env=None):
        with connect(env=env) as connection:
            with connection.cursor() as cursor:
                cursor.execute("SELECT namespace FROM templates")
                return {str(item["namespace"] or "").strip() for item in cursor.fetchall()}

    def migrate_storage_root(self, env=None):
        new_root = self.template_root().resolve()
        with connect(env=env) as connection:
            with connection.cursor() as cursor:
                cursor.execute("SELECT id, namespace, path FROM templates")
                rows = [_row(item) for item in cursor.fetchall()]
                for item in rows:
                    current = Path(item["path"]).expanduser()
                    target = (new_root / item["namespace"]).resolve()
                    try:
                        already_managed = current.resolve().is_relative_to(new_root)
                    except Exception:
                        already_managed = False
                    if already_managed:
                        continue
                    if current.is_dir():
                        target.parent.mkdir(parents=True, exist_ok=True)
                        shutil.copytree(current, target, dirs_exist_ok=True)
                    else:
                        target.mkdir(parents=True, exist_ok=True)
                    cursor.execute("UPDATE templates SET path = %s WHERE id = %s", (str(target), item["id"]))

    def _unique_namespace(self, cursor, namespace):
        base = namespace or "template"
        candidate = base
        index = 2
        while True:
            cursor.execute("SELECT 1 FROM templates WHERE namespace = %s LIMIT 1", (candidate,))
            if cursor.fetchone() is None:
                return candidate
            candidate = f"{base}_{index}"
            index += 1

    def _create_version_snapshot(self, cursor, template, metadata=None):
        root = Path(template["path"]).expanduser()
        files = self.read_files(str(root))
        checksum = hashlib.sha256("".join(files[name] for name in FILES).encode("utf-8")).hexdigest()
        cursor.execute("SELECT COALESCE(max(version), 0) AS version FROM template_versions WHERE template_id = %s", (template["id"],))
        version = int(cursor.fetchone()["version"]) + 1
        snapshot_dir = root / ".versions" / f"v{version:04d}"
        snapshot_dir.mkdir(parents=True, exist_ok=True)
        for file_name in FILES:
            shutil.copy2(root / file_name, snapshot_dir / file_name)
        cursor.execute(
            """
            INSERT INTO template_versions(template_id, version, path, checksum, metadata)
            VALUES (%s, %s, %s, %s, %s)
            RETURNING *
            """,
            (template["id"], version, str(snapshot_dir), checksum, Jsonb(metadata or {})),
        )
        return _row(cursor.fetchone())

    def _validate_files(self, namespace, files):
        try:
            values = yaml.safe_load(files["values.default.yaml"] or "{}") or {}
        except Exception as exc:
            raise TemplateError(400, f"values.default.yaml을 읽을 수 없습니다. {exc}", "TEMPLATE_VALUES_DEFAULT_INVALID")
        try:
            schema = json.loads(files["values.schema.json"] or "{}")
        except Exception as exc:
            raise TemplateError(400, f"values.schema.json을 읽을 수 없습니다. {exc}", "TEMPLATE_VALUES_SCHEMA_INVALID")
        if not isinstance(values, dict) or not isinstance(schema, dict):
            raise TemplateError(400, "기본값과 스키마는 object여야 합니다.", "TEMPLATE_VALUES_INVALID")
        try:
            self.render_preview(files["docker-compose.yaml"], yaml.safe_dump(values, sort_keys=False, allow_unicode=False), namespace)
        except validator.ComposeValidationError as exc:
            raise TemplateError(exc.status_code, exc.message, exc.error_code, details=exc.details)


Model = TemplateStore()
