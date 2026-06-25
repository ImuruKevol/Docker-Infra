ALTER TABLE ceph_osd_slots
    DROP CONSTRAINT IF EXISTS ceph_osd_slots_backing_type_check;

ALTER TABLE ceph_osd_slots
    ADD CONSTRAINT ceph_osd_slots_backing_type_check
    CHECK (backing_type IN ('gpt_partition', 'lvm_lv', 'managed_loop'));
