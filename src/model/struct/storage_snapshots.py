class StorageSnapshots:
    def __init__(self, common=None):
        self.common = common or wiz.model("struct/storage_ceph")

    def list_recent(self, service_id=None, mount_id=None, limit=50, env=None):
        query = """
            SELECT
                snapshot.*,
                mount.mount_name AS mount_name,
                service.namespace AS service_namespace,
                service.name AS service_name
            FROM storage_snapshots snapshot
            LEFT JOIN storage_mounts mount ON mount.id = snapshot.mount_id
            LEFT JOIN services service ON service.id = snapshot.service_id
        """
        clauses = []
        params = []
        if service_id:
            clauses.append("snapshot.service_id = %s")
            params.append(service_id)
        if mount_id:
            clauses.append("snapshot.mount_id = %s")
            params.append(mount_id)
        if clauses:
            query += " WHERE " + " AND ".join(clauses)
        query += " ORDER BY snapshot.created_at DESC LIMIT %s"
        params.append(int(limit or 50))
        return self.common.fetchall(query, params, env=env)

    def summary(self, rows):
        by_status = {}
        by_source = {}
        size_bytes = 0
        for row in rows or []:
            status = str(row.get("status") or "unknown")
            source = str(row.get("source") or "unknown")
            by_status[status] = by_status.get(status, 0) + 1
            by_source[source] = by_source.get(source, 0) + 1
            size_bytes += int(row.get("size_bytes") or 0)
        return {
            "total": len(rows or []),
            "ready": by_status.get("ready", 0),
            "failed": by_status.get("failed", 0),
            "size_bytes": size_bytes,
            "by_status": by_status,
            "by_source": by_source,
        }


Model = StorageSnapshots()
