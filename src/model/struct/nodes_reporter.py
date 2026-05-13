import datetime
import secrets

from psycopg.types.json import Jsonb

auth = wiz.model("struct/auth")
connect = wiz.model("db/postgres").connect
shared = wiz.model("struct/nodes_shared")
metric_history = wiz.model("struct/nodes_metric_history")
token_hash = auth.token_hash
REPORTER_TOKEN_TYPE = shared.REPORTER_TOKEN_TYPE
METRIC_DEDUPLICATE_WINDOW_SECONDS = 10
NodeError = shared.NodeError
_node_to_dict = shared.node_to_dict
_reporter_to_public = shared.reporter_to_public
_metric_to_dict = shared.metric_to_dict
_parse_reported_at = shared.parse_reported_at
_container_items = shared.container_items


class NodeReporterMixin:
    def _reporter_status(self, cursor, node_id):
        cursor.execute(
            """
            SELECT *
            FROM node_credentials
            WHERE node_id = %s AND metadata->>'type' = %s
            ORDER BY created_at DESC
            LIMIT 1
            """,
            (node_id, REPORTER_TOKEN_TYPE),
        )
        return _reporter_to_public(cursor.fetchone())

    def _latest_metric(self, cursor, node_id):
        cursor.execute(
            """
            SELECT *
            FROM node_metrics
            WHERE node_id = %s
            ORDER BY reported_at DESC, created_at DESC
            LIMIT 1
            """,
            (node_id,),
        )
        return _metric_to_dict(cursor.fetchone())

    def _upsert_metric(self, cursor, node, payload, memory, storage, containers, reported_at, metadata):
        cursor.execute("SELECT pg_advisory_xact_lock(hashtext(%s))", (f"node_metrics:{node['id']}",))
        cursor.execute(
            """
            SELECT *
            FROM node_metrics
            WHERE node_id = %s
              AND reported_at >= %s::timestamptz - (%s::int * interval '1 second')
              AND reported_at <= %s::timestamptz + (%s::int * interval '1 second')
            ORDER BY ABS(EXTRACT(EPOCH FROM (reported_at - %s::timestamptz))) ASC, created_at DESC
            LIMIT 1
            """,
            (
                node["id"],
                reported_at,
                METRIC_DEDUPLICATE_WINDOW_SECONDS,
                reported_at,
                METRIC_DEDUPLICATE_WINDOW_SECONDS,
                reported_at,
            ),
        )
        existing = cursor.fetchone()
        if existing is not None:
            cursor.execute(
                """
                UPDATE node_metrics
                SET cpu_percent = %s,
                    memory = %s,
                    storage = %s,
                    containers = %s,
                    reported_at = %s,
                    test_run_id = COALESCE(%s, test_run_id),
                    metadata = COALESCE(metadata, '{}'::jsonb) || %s
                WHERE id = %s
                RETURNING *
                """,
                (
                    payload.get("cpu_percent"),
                    Jsonb(memory),
                    Jsonb(storage),
                    Jsonb(containers),
                    reported_at,
                    node["test_run_id"],
                    Jsonb(metadata),
                    existing["id"],
                ),
            )
            return cursor.fetchone()
        cursor.execute(
            """
            INSERT INTO node_metrics(
                node_id, cpu_percent, memory, storage, containers,
                reported_at, test_run_id, metadata
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING *
            """,
            (
                node["id"],
                payload.get("cpu_percent"),
                Jsonb(memory),
                Jsonb(storage),
                Jsonb(containers),
                reported_at,
                node["test_run_id"],
                Jsonb(metadata),
            ),
        )
        return cursor.fetchone()

    def issue_reporter_token(self, node_id, env=None):
        token = secrets.token_urlsafe(32)
        issued_at = datetime.datetime.now(datetime.timezone.utc).isoformat().replace("+00:00", "Z")
        with connect(env=env) as connection:
            with connection.cursor() as cursor:
                node = _node_to_dict(self._fetch_node(cursor, node_id))
                cursor.execute(
                    "DELETE FROM node_credentials WHERE node_id = %s AND metadata->>'type' = %s",
                    (node_id, REPORTER_TOKEN_TYPE),
                )
                cursor.execute(
                    """
                    INSERT INTO node_credentials(node_id, username, ssh_fingerprint, test_run_id, metadata)
                    VALUES (%s, 'node-reporter', NULL, %s, %s)
                    RETURNING *
                    """,
                    (
                        node_id,
                        node["test_run_id"],
                        Jsonb({
                            "type": REPORTER_TOKEN_TYPE,
                            "token_hash": token_hash(token),
                            "issued_at": issued_at,
                            "last_used_at": None,
                        }),
                    ),
                )
                return {"node": node, "reporter": _reporter_to_public(cursor.fetchone()), "token": token}

    def _fetch_reporter_credential(self, cursor, token, node_id=None):
        if not token:
            raise NodeError(401, "reporter token이 필요합니다.", "REPORTER_TOKEN_REQUIRED")
        hashed = token_hash(token)
        if node_id:
            cursor.execute(
                """
                SELECT *
                FROM node_credentials
                WHERE node_id = %s
                  AND metadata->>'type' = %s
                  AND metadata->>'token_hash' = %s
                ORDER BY created_at DESC
                LIMIT 1
                """,
                (node_id, REPORTER_TOKEN_TYPE, hashed),
            )
        else:
            cursor.execute(
                """
                SELECT *
                FROM node_credentials
                WHERE metadata->>'type' = %s
                  AND metadata->>'token_hash' = %s
                ORDER BY created_at DESC
                LIMIT 1
                """,
                (REPORTER_TOKEN_TYPE, hashed),
            )
        credential = cursor.fetchone()
        if credential is None:
            raise NodeError(401, "reporter token이 올바르지 않습니다.", "INVALID_REPORTER_TOKEN")
        return credential

    def ingest_metric(self, reporter_token, payload=None, env=None):
        payload = payload or {}
        node_id = payload.get("node_id")
        reported_at = _parse_reported_at(payload.get("reported_at"))
        memory = payload.get("memory") or {}
        storage = payload.get("storage") or {}
        containers = payload.get("containers") or {"items": []}
        metadata = payload.get("metadata") or {}
        if isinstance(metadata, dict) is False:
            metadata = {}
        metadata = {**metadata, "source": metadata.get("source") or "reporter_ingest"}
        if isinstance(memory, dict) is False or isinstance(storage, dict) is False:
            raise NodeError(400, "memory와 storage는 object여야 합니다.", "INVALID_METRIC_PAYLOAD")
        if isinstance(containers, (dict, list)) is False:
            raise NodeError(400, "containers는 object 또는 array여야 합니다.", "INVALID_METRIC_PAYLOAD")

        with connect(env=env) as connection:
            with connection.cursor() as cursor:
                credential = self._fetch_reporter_credential(cursor, reporter_token, node_id=node_id)
                node = _node_to_dict(self._fetch_node(cursor, credential["node_id"]))
                metric = _metric_to_dict(self._upsert_metric(cursor, node, payload, memory, storage, containers, reported_at, metadata))
                try:
                    metric_history.append(node["id"], metric, source=metadata.get("source"))
                except Exception:
                    pass
                now = datetime.datetime.now(datetime.timezone.utc).isoformat().replace("+00:00", "Z")
                cursor.execute(
                    """
                    UPDATE node_credentials
                    SET metadata = metadata || %s
                    WHERE id = %s
                    RETURNING *
                    """,
                    (Jsonb({"last_used_at": now}), credential["id"]),
                )
                reporter = _reporter_to_public(cursor.fetchone())
                cursor.execute(
                    """
                    UPDATE nodes
                    SET status = 'active',
                        metadata = metadata || %s
                    WHERE id = %s
                    RETURNING *
                    """,
                    (Jsonb({"last_reported_at": metric["reported_at"].isoformat()}), node["id"]),
                )
                node = _node_to_dict(cursor.fetchone())
                return {"node": node, "metric": metric, "reporter": reporter}

    def latest_metric(self, node_id, env=None):
        with connect(env=env) as connection:
            with connection.cursor() as cursor:
                self._fetch_node(cursor, node_id)
                return self._latest_metric(cursor, node_id)

    def metrics(self, node_id, limit=50, env=None):
        limit = max(1, min(int(limit or 50), 200))
        with connect(env=env) as connection:
            with connection.cursor() as cursor:
                self._fetch_node(cursor, node_id)
                cursor.execute(
                    """
                    SELECT *
                    FROM node_metrics
                    WHERE node_id = %s
                    ORDER BY reported_at DESC, created_at DESC
                    LIMIT %s
                    """,
                    (node_id, limit),
                )
                return [_metric_to_dict(row) for row in cursor.fetchall()]

    def containers(self, node_id, env=None):
        metric = self.latest_metric(node_id, env=env)
        containers = [] if metric is None else _container_items(metric["containers"])
        return {"node_id": node_id, "latest_metric": metric, "containers": containers}


Model = NodeReporterMixin
