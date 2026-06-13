import base64
import json
from pathlib import PurePosixPath

from psycopg.types.json import Jsonb

connect = wiz.model("db/postgres").connect
shared = wiz.model("struct/macros_shared")
MacroError = shared.MacroError
macro_row = shared.macro_row
normalize_enabled = shared.normalize_enabled
normalize_script_text = shared.normalize_script_text
normalize_scope_type = shared.normalize_scope_type
MAX_MACRO_FILES = shared.MAX_MACRO_FILES
MAX_MACRO_FILE_BYTES = shared.MAX_MACRO_FILE_BYTES
MAX_MACRO_TOTAL_FILE_BYTES = shared.MAX_MACRO_TOTAL_FILE_BYTES
SCOPE_GLOBAL = shared.SCOPE_GLOBAL
SCOPE_NODE = shared.SCOPE_NODE


class MacroStore:
    MacroError = MacroError

    def _select_sql(self):
        return """
            SELECT m.*, n.name AS node_name, n.host AS node_host, COALESCE(f.files, '[]'::jsonb) AS files
            FROM shell_macros m
            LEFT JOIN nodes n ON n.id = m.node_id
            LEFT JOIN LATERAL (
                SELECT jsonb_agg(
                    jsonb_build_object(
                        'id', mf.id::text,
                        'filename', mf.filename,
                        'content_type', mf.content_type,
                        'size_bytes', mf.size_bytes,
                        'created_at', mf.created_at
                    )
                    ORDER BY lower(mf.filename), mf.created_at
                ) AS files
                FROM shell_macro_files mf
                WHERE mf.macro_id = m.id
            ) f ON true
        """

    def _fetch(self, cursor, macro_id):
        cursor.execute(
            self._select_sql() + " WHERE m.id = %s",
            (macro_id,),
        )
        row = cursor.fetchone()
        if row is None:
            raise MacroError(404, "매크로를 찾을 수 없습니다.", "MACRO_NOT_FOUND")
        return row

    def _normalize_keep_file_ids(self, value):
        if value in (None, ""):
            return None
        if isinstance(value, str):
            try:
                value = json.loads(value)
            except Exception:
                raise MacroError(400, "첨부 파일 유지 목록이 올바르지 않습니다.", "MACRO_FILE_KEEP_INVALID")
        if not isinstance(value, list):
            raise MacroError(400, "첨부 파일 유지 목록이 올바르지 않습니다.", "MACRO_FILE_KEEP_INVALID")
        return [str(item).strip() for item in value if str(item or "").strip()]

    def _safe_filename(self, value):
        raw = str(value or "").replace("\\", "/").strip()
        name = PurePosixPath(raw).name.strip()
        if not name or name in {".", ".."}:
            raise MacroError(400, "첨부 파일 이름이 올바르지 않습니다.", "MACRO_FILE_NAME_INVALID")
        if len(name) > 255:
            raise MacroError(400, "첨부 파일 이름은 255자 이하여야 합니다.", "MACRO_FILE_NAME_TOO_LONG")
        return name

    def _normalize_uploads(self, file_storages):
        uploads = []
        for storage in file_storages or []:
            filename = self._safe_filename(getattr(storage, "filename", ""))
            content = storage.read()
            if isinstance(content, str):
                content = content.encode("utf-8")
            content = content or b""
            if len(content) > MAX_MACRO_FILE_BYTES:
                raise MacroError(400, f"첨부 파일은 파일당 {MAX_MACRO_FILE_BYTES // 1024 // 1024}MB 이하여야 합니다.", "MACRO_FILE_TOO_LARGE")
            uploads.append(
                {
                    "filename": filename,
                    "content_type": str(getattr(storage, "content_type", "") or ""),
                    "content": content,
                    "size_bytes": len(content),
                }
            )
        return uploads

    def _sync_files(self, cursor, macro_id, file_storages=None, keep_file_ids=None, test_run_id=None):
        uploads = self._normalize_uploads(file_storages)
        if keep_file_ids is None and not uploads:
            return

        cursor.execute("SELECT id::text AS id, filename, size_bytes FROM shell_macro_files WHERE macro_id = %s", (macro_id,))
        existing = cursor.fetchall()
        existing_by_id = {row["id"]: row for row in existing}

        if keep_file_ids is not None:
            invalid = [file_id for file_id in keep_file_ids if file_id not in existing_by_id]
            if invalid:
                raise MacroError(400, "유지할 첨부 파일을 찾을 수 없습니다.", "MACRO_FILE_KEEP_NOT_FOUND")
            if keep_file_ids:
                cursor.execute(
                    "DELETE FROM shell_macro_files WHERE macro_id = %s AND NOT (id = ANY(%s::uuid[]))",
                    (macro_id, keep_file_ids),
                )
            else:
                cursor.execute("DELETE FROM shell_macro_files WHERE macro_id = %s", (macro_id,))
            existing = [row for row in existing if row["id"] in set(keep_file_ids)]

        filenames = {row["filename"] for row in existing}
        for upload in uploads:
            if upload["filename"] in filenames:
                raise MacroError(409, "이미 같은 이름의 첨부 파일이 있습니다.", "MACRO_FILE_NAME_EXISTS")
            filenames.add(upload["filename"])

        total_count = len(existing) + len(uploads)
        total_size = sum(int(row["size_bytes"] or 0) for row in existing) + sum(item["size_bytes"] for item in uploads)
        if total_count > MAX_MACRO_FILES:
            raise MacroError(400, f"첨부 파일은 매크로당 최대 {MAX_MACRO_FILES}개까지 저장할 수 있습니다.", "MACRO_FILE_COUNT_EXCEEDED")
        if total_size > MAX_MACRO_TOTAL_FILE_BYTES:
            raise MacroError(400, f"첨부 파일 총 용량은 {MAX_MACRO_TOTAL_FILE_BYTES // 1024 // 1024}MB 이하여야 합니다.", "MACRO_FILE_TOTAL_TOO_LARGE")

        for upload in uploads:
            cursor.execute(
                """
                INSERT INTO shell_macro_files(macro_id, filename, content_type, size_bytes, content, test_run_id, metadata)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    macro_id,
                    upload["filename"],
                    upload["content_type"],
                    upload["size_bytes"],
                    upload["content"],
                    test_run_id,
                    Jsonb({"source": "web_ui"}),
                ),
            )

    def _validate_node_scope(self, cursor, scope_type, node_id):
        if scope_type != SCOPE_NODE:
            return None
        node_id = str(node_id or "").strip()
        if not node_id:
            raise MacroError(400, "서버 전용 매크로는 node_id가 필요합니다.", "MACRO_NODE_ID_REQUIRED")
        cursor.execute("SELECT id, name, host FROM nodes WHERE id = %s", (node_id,))
        row = cursor.fetchone()
        if row is None:
            raise MacroError(404, "매크로를 연결할 서버를 찾을 수 없습니다.", "MACRO_NODE_NOT_FOUND")
        return row

    def _check_duplicate(self, cursor, macro_id, name, scope_type, node_id):
        if scope_type == SCOPE_GLOBAL:
            query = """
                SELECT id FROM shell_macros
                WHERE lower(name) = lower(%s)
                  AND scope_type = %s
                  AND node_id IS NULL
            """
            params = [name, scope_type]
        else:
            query = """
                SELECT id FROM shell_macros
                WHERE lower(name) = lower(%s)
                  AND scope_type = %s
                  AND node_id = %s
            """
            params = [name, scope_type, node_id]
        if macro_id:
            query += " AND id <> %s"
            params.append(macro_id)
        cursor.execute(query, params)
        if cursor.fetchone() is not None:
            raise MacroError(409, "이미 같은 이름의 매크로가 있습니다.", "MACRO_NAME_EXISTS")

    def list(self, payload=None, env=None):
        payload = payload or {}
        scope_type = str(payload.get("scope_type") or "").strip().lower()
        node_id = str(payload.get("node_id") or "").strip()
        available_for_node = str(payload.get("available_for_node") or "").strip()
        search = str(payload.get("search") or "").strip().lower()

        where = []
        params = []
        if available_for_node:
            where.append("((m.scope_type = %s AND m.node_id IS NULL) OR (m.scope_type = %s AND m.node_id = %s))")
            params.extend([SCOPE_GLOBAL, SCOPE_NODE, available_for_node])
        elif scope_type:
            scope_type = normalize_scope_type(scope_type)
            if scope_type == SCOPE_GLOBAL:
                where.append("m.scope_type = %s AND m.node_id IS NULL")
                params.append(scope_type)
            else:
                if not node_id:
                    raise MacroError(400, "node_id는 필수입니다.", "MACRO_NODE_ID_REQUIRED")
                where.append("m.scope_type = %s AND m.node_id = %s")
                params.extend([scope_type, node_id])
        elif node_id:
            where.append("m.node_id = %s")
            params.append(node_id)
        if search:
            where.append("(lower(m.name) LIKE %s OR lower(m.description) LIKE %s)")
            params.extend([f"%{search}%", f"%{search}%"])

        sql = self._select_sql()
        if where:
            sql += " WHERE " + " AND ".join(where)
        sql += " ORDER BY CASE WHEN m.scope_type = 'node' THEN 0 ELSE 1 END, lower(m.name) ASC, m.created_at DESC"

        with connect(env=env) as connection:
            with connection.cursor() as cursor:
                cursor.execute(sql, params)
                return [macro_row(item) for item in cursor.fetchall()]

    def save(self, payload, file_storages=None, env=None):
        payload = payload or {}
        macro_id = payload.get("id")
        name = str(payload.get("name") or "").strip()
        script = normalize_script_text(payload.get("script")).strip()
        description = str(payload.get("description") or "").strip()
        enabled = normalize_enabled(payload.get("enabled"))
        test_run_id = payload.get("test_run_id")
        scope_type = normalize_scope_type(payload.get("scope_type"), default=SCOPE_GLOBAL)
        keep_file_ids = self._normalize_keep_file_ids(payload.get("keep_file_ids")) if "keep_file_ids" in payload else None

        if not name:
            raise MacroError(400, "매크로 이름을 입력해주세요.", "MACRO_NAME_REQUIRED")
        if not script:
            raise MacroError(400, "실행할 스크립트를 입력해주세요.", "MACRO_SCRIPT_REQUIRED")

        with connect(env=env) as connection:
            with connection.cursor() as cursor:
                linked_node = self._validate_node_scope(cursor, scope_type, payload.get("node_id"))
                node_id = linked_node["id"] if linked_node is not None else None
                self._check_duplicate(cursor, macro_id, name, scope_type, node_id)
                if macro_id:
                    self._fetch(cursor, macro_id)
                    cursor.execute(
                        """
                        UPDATE shell_macros
                        SET name = %s,
                            description = %s,
                            script = %s,
                            enabled = %s,
                            scope_type = %s,
                            node_id = %s,
                            metadata = metadata || %s,
                            updated_at = now()
                        WHERE id = %s
                        RETURNING id
                        """,
                        (name, description, script, enabled, scope_type, node_id, Jsonb({"source": "web_ui"}), macro_id),
                    )
                    saved_id = cursor.fetchone()["id"]
                else:
                    cursor.execute(
                        """
                        INSERT INTO shell_macros(name, description, script, enabled, scope_type, node_id, test_run_id, metadata)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                        RETURNING id
                        """,
                        (name, description, script, enabled, scope_type, node_id, test_run_id, Jsonb({"source": "web_ui"})),
                    )
                    saved_id = cursor.fetchone()["id"]
                self._sync_files(cursor, saved_id, file_storages=file_storages, keep_file_ids=keep_file_ids, test_run_id=test_run_id)
                return macro_row(self._fetch(cursor, saved_id))

    def delete(self, macro_id, env=None):
        with connect(env=env) as connection:
            with connection.cursor() as cursor:
                macro = macro_row(self._fetch(cursor, macro_id))
                cursor.execute("DELETE FROM shell_macros WHERE id = %s", (macro_id,))
                return {"deleted": True, "macro": macro}

    def download_file(self, file_id, macro_id=None, env=None):
        file_id = str(file_id or "").strip()
        macro_id = str(macro_id or "").strip()
        if not file_id:
            raise MacroError(400, "file_id는 필수입니다.", "MACRO_FILE_ID_REQUIRED")

        query = """
            SELECT id, macro_id, filename, content_type, size_bytes, content, created_at
            FROM shell_macro_files
            WHERE id = %s
        """
        params = [file_id]
        if macro_id:
            query += " AND macro_id = %s"
            params.append(macro_id)
        with connect(env=env) as connection:
            with connection.cursor() as cursor:
                cursor.execute(query, params)
                row = cursor.fetchone()
        if row is None:
            raise MacroError(404, "첨부 파일을 찾을 수 없습니다.", "MACRO_FILE_NOT_FOUND")
        content = bytes(row["content"] or b"")
        return {
            "id": str(row["id"]),
            "macro_id": str(row["macro_id"]),
            "filename": row["filename"],
            "content_type": row["content_type"] or "application/octet-stream",
            "size_bytes": int(row["size_bytes"] or len(content)),
            "created_at": row["created_at"],
            "content_base64": base64.b64encode(content).decode("ascii"),
        }


Model = MacroStore()
