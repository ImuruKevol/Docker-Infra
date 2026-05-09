import datetime

from psycopg.types.json import Jsonb


class BackupSystemPolicyMixin:
    def save_policy(self, payload=None, env=None):
        payload = payload or {}
        with self.connect(env=env) as connection:
            with connection.cursor() as cursor:
                row = self._fetch(cursor, decrypt=False, env=env)
                if row is None:
                    status = self.configure({"enabled": False}, env=env)
                    metadata = dict(status.get("metadata") or {})
                else:
                    metadata = dict(row["metadata"] or {})
                current = self._backup_policy(metadata.get("backup_policy"))
                metadata["backup_policy"] = self._backup_policy(payload, base=current)
                cursor.execute(
                    """
                    UPDATE backup_system_settings
                    SET metadata = %s,
                        updated_at = now()
                    WHERE singleton_key = 'default'
                    RETURNING *
                    """,
                    (Jsonb(metadata),),
                )
                updated = cursor.fetchone()
        return self._row(updated, env=env)

    def mark_policy_run(self, result=None, env=None):
        result = result or {}
        with self.connect(env=env) as connection:
            with connection.cursor() as cursor:
                row = self._fetch(cursor, decrypt=False, env=env)
                if row is None:
                    return self.status(env=env)
                metadata = dict(row["metadata"] or {})
                policy = self._backup_policy(metadata.get("backup_policy"))
                policy["last_run_at"] = datetime.datetime.now(datetime.timezone.utc).isoformat()
                policy["last_result"] = {
                    "processed": int(result.get("processed") or 0),
                    "succeeded": int(result.get("succeeded") or 0),
                    "failed": int(result.get("failed") or 0),
                    "skipped": int(result.get("skipped") or 0),
                    "snapshots": int(result.get("snapshots") or 0),
                }
                metadata["backup_policy"] = policy
                cursor.execute(
                    "UPDATE backup_system_settings SET metadata = %s, updated_at = now() WHERE singleton_key = 'default' RETURNING *",
                    (Jsonb(metadata),),
                )
                updated = cursor.fetchone()
        return self._row(updated, env=env)


Model = BackupSystemPolicyMixin
