DEFAULT_POLICY = {
    "name": "default",
    "keep_recent": 10,
    "keep_daily": 7,
    "keep_monthly": 12,
    "db_hook_mode": "none",
    "enabled": True,
    "placeholder": True,
}


class StorageSnapshotPolicies:
    def __init__(self, common=None):
        self.common = common or wiz.model("struct/storage_ceph")

    def list(self, env=None):
        return self.common.fetchall(
            """
            SELECT *
            FROM storage_snapshot_policies
            ORDER BY enabled DESC, name ASC
            """,
            env=env,
        )

    def default_policy(self, rows=None, env=None):
        rows = self.list(env=env) if rows is None else rows
        for row in rows or []:
            if row.get("name") == "default":
                return row
        return dict(DEFAULT_POLICY)

    def summary(self, rows):
        rows = rows or []
        return {
            "total": len(rows),
            "enabled": len([row for row in rows if row.get("enabled") is True]),
            "default": self.default_policy(rows=rows),
        }


Model = StorageSnapshotPolicies()
