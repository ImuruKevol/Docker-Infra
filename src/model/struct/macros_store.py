from psycopg.types.json import Jsonb

connect = wiz.model("db/postgres").connect
shared = wiz.model("struct/macros_shared")
MacroError = shared.MacroError
macro_row = shared.macro_row
normalize_enabled = shared.normalize_enabled
normalize_scope_type = shared.normalize_scope_type
SCOPE_GLOBAL = shared.SCOPE_GLOBAL
SCOPE_NODE = shared.SCOPE_NODE


class MacroStore:
    MacroError = MacroError

    def _fetch(self, cursor, macro_id):
        cursor.execute(
            """
            SELECT m.*, n.name AS node_name, n.host AS node_host
            FROM shell_macros m
            LEFT JOIN nodes n ON n.id = m.node_id
            WHERE m.id = %s
            """,
            (macro_id,),
        )
        row = cursor.fetchone()
        if row is None:
            raise MacroError(404, "매크로를 찾을 수 없습니다.", "MACRO_NOT_FOUND")
        return row

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

        sql = """
            SELECT m.*, n.name AS node_name, n.host AS node_host
            FROM shell_macros m
            LEFT JOIN nodes n ON n.id = m.node_id
        """
        if where:
            sql += " WHERE " + " AND ".join(where)
        sql += " ORDER BY CASE WHEN m.scope_type = 'node' THEN 0 ELSE 1 END, m.enabled DESC, lower(m.name) ASC, m.created_at DESC"

        with connect(env=env) as connection:
            with connection.cursor() as cursor:
                cursor.execute(sql, params)
                return [macro_row(item) for item in cursor.fetchall()]

    def save(self, payload, env=None):
        payload = payload or {}
        macro_id = payload.get("id")
        name = str(payload.get("name") or "").strip()
        script = str(payload.get("script") or "").strip()
        description = str(payload.get("description") or "").strip()
        enabled = normalize_enabled(payload.get("enabled"))
        test_run_id = payload.get("test_run_id")
        scope_type = normalize_scope_type(payload.get("scope_type"), default=SCOPE_GLOBAL)

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
                return macro_row(self._fetch(cursor, saved_id))

    def delete(self, macro_id, env=None):
        with connect(env=env) as connection:
            with connection.cursor() as cursor:
                macro = macro_row(self._fetch(cursor, macro_id))
                cursor.execute("DELETE FROM shell_macros WHERE id = %s", (macro_id,))
                return {"deleted": True, "macro": macro}


Model = MacroStore()
