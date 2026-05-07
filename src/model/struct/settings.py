from psycopg.types.json import Jsonb

connect = wiz.model("db/postgres").connect
config = wiz.config("docker_infra")


MASKED_SECRET = "********"


def _secret_key(env=None):
    return config.secret_key(env)


def _row_to_setting(row):
    if row is None:
        return None

    value = row["value_json"]
    secret = None
    if row["is_secret"]:
        value = None
        secret = {
            "is_configured": row["secret_enc"] is not None,
            "masked_value": MASKED_SECRET if row["secret_enc"] is not None else "",
            "last_updated_at": row["updated_at"],
        }

    return {
        "id": str(row["id"]),
        "key": row["key"],
        "value": value,
        "value_type": row["value_type"],
        "is_secret": row["is_secret"],
        "secret": secret,
        "description": row["description"],
        "test_run_id": row["test_run_id"],
        "metadata": row["metadata"],
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
    }


class SettingsRepository:
    MASKED_SECRET = MASKED_SECRET

    def secret_key(self, env=None):
        return _secret_key(env)

    def list(self, env=None, test_run_id=None):
        with connect(env=env) as connection:
            with connection.cursor() as cursor:
                if test_run_id:
                    cursor.execute(
                        "SELECT * FROM system_settings WHERE test_run_id = %s ORDER BY key",
                        (test_run_id,),
                    )
                else:
                    cursor.execute("SELECT * FROM system_settings ORDER BY key")
                return [_row_to_setting(row) for row in cursor.fetchall()]

    def get(self, key, env=None):
        with connect(env=env) as connection:
            with connection.cursor() as cursor:
                cursor.execute("SELECT * FROM system_settings WHERE key = %s", (key,))
                return _row_to_setting(cursor.fetchone())

    def upsert(
        self,
        key,
        value=None,
        value_type="string",
        is_secret=False,
        description=None,
        test_run_id=None,
        metadata=None,
        env=None,
    ):
        metadata = metadata or {}
        with connect(env=env) as connection:
            with connection.cursor() as cursor:
                if is_secret:
                    cursor.execute(
                        """
                        INSERT INTO system_settings(
                            key, value_json, secret_enc, value_type, is_secret, description, test_run_id, metadata
                        )
                        VALUES (
                            %s, NULL, encode(pgp_sym_encrypt(%s, %s), 'base64'), %s, true, %s, %s, %s
                        )
                        ON CONFLICT (key) DO UPDATE SET
                            value_json = NULL,
                            secret_enc = EXCLUDED.secret_enc,
                            value_type = EXCLUDED.value_type,
                            is_secret = true,
                            description = EXCLUDED.description,
                            test_run_id = EXCLUDED.test_run_id,
                            metadata = EXCLUDED.metadata
                        RETURNING *
                        """,
                        (
                            key,
                            "" if value is None else str(value),
                            _secret_key(env),
                            value_type,
                            description,
                            test_run_id,
                            Jsonb(metadata),
                        ),
                    )
                else:
                    cursor.execute(
                        """
                        INSERT INTO system_settings(
                            key, value_json, secret_enc, value_type, is_secret, description, test_run_id, metadata
                        )
                        VALUES (%s, %s, NULL, %s, false, %s, %s, %s)
                        ON CONFLICT (key) DO UPDATE SET
                            value_json = EXCLUDED.value_json,
                            secret_enc = NULL,
                            value_type = EXCLUDED.value_type,
                            is_secret = false,
                            description = EXCLUDED.description,
                            test_run_id = EXCLUDED.test_run_id,
                            metadata = EXCLUDED.metadata
                        RETURNING *
                        """,
                        (key, Jsonb(value), value_type, description, test_run_id, Jsonb(metadata)),
                    )
                return _row_to_setting(cursor.fetchone())

    def delete(self, key, env=None):
        with connect(env=env) as connection:
            with connection.cursor() as cursor:
                cursor.execute("DELETE FROM system_settings WHERE key = %s RETURNING key", (key,))
                return cursor.fetchone() is not None

    def delete_by_test_run_id(self, test_run_id, env=None):
        with connect(env=env) as connection:
            with connection.cursor() as cursor:
                cursor.execute("DELETE FROM system_settings WHERE test_run_id = %s", (test_run_id,))
                return cursor.rowcount


Model = SettingsRepository()
