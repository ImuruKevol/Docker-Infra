class StorageCephOsdRetry:
    def __init__(self, common=None):
        self.common = common or wiz.model("struct/storage_ceph")

    def prepared_slots(self, cluster, node, limit=0, env=None):
        if not cluster or not node or limit <= 0:
            return []
        return self.common.fetchall(
            """
            SELECT *
            FROM ceph_osd_slots
            WHERE cluster_id = %s
              AND node_id = %s
              AND status = 'prepared'
            ORDER BY osd_id ASC NULLS LAST, created_at ASC
            LIMIT %s
            """,
            [cluster["id"], node["id"], int(limit)],
            env=env,
        )

    def service_plan(self, plan, slot):
        return {
            **(plan or {}),
            "slot_name": slot.get("slot_name") or "",
            "osd_id_hint": slot.get("osd_id"),
            "osd_fsid": slot.get("osd_fsid") or "",
        }


Model = StorageCephOsdRetry()
