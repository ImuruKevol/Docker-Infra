CREATE TABLE IF NOT EXISTS ceph_clusters (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    fsid TEXT NOT NULL DEFAULT '',
    status TEXT NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'bootstrapping', 'running', 'degraded', 'failed')),
    health TEXT NOT NULL DEFAULT 'HEALTH_UNKNOWN' CHECK (health IN ('HEALTH_UNKNOWN', 'HEALTH_OK', 'HEALTH_WARN', 'HEALTH_ERR')),
    ceph_image TEXT NOT NULL DEFAULT 'quay.io/ceph/ceph:v19',
    public_network TEXT NOT NULL DEFAULT '',
    cluster_network TEXT NOT NULL DEFAULT '',
    mount_root TEXT NOT NULL DEFAULT '/srv/docker-infra/storage/cephfs',
    test_run_id TEXT,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS ceph_nodes (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    cluster_id UUID NOT NULL REFERENCES ceph_clusters(id) ON DELETE CASCADE,
    node_id UUID NOT NULL REFERENCES nodes(id) ON DELETE CASCADE,
    ceph_hostname TEXT NOT NULL DEFAULT '',
    ip_address TEXT NOT NULL DEFAULT '',
    roles JSONB NOT NULL DEFAULT '[]'::jsonb,
    mount_status TEXT NOT NULL DEFAULT 'unmounted' CHECK (mount_status IN ('mounted', 'unmounted', 'failed', 'unknown')),
    status TEXT NOT NULL DEFAULT 'ready' CHECK (status IN ('pending', 'ready', 'warning', 'failed')),
    test_run_id TEXT,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE(cluster_id, node_id)
);

CREATE TABLE IF NOT EXISTS ceph_osd_slots (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    cluster_id UUID NOT NULL REFERENCES ceph_clusters(id) ON DELETE CASCADE,
    node_id UUID NOT NULL REFERENCES nodes(id) ON DELETE CASCADE,
    slot_name TEXT NOT NULL,
    size_gb INTEGER NOT NULL CHECK (size_gb > 0),
    backing_type TEXT NOT NULL CHECK (backing_type IN ('gpt_partition', 'lvm_lv', 'managed_loop')),
    backing_path TEXT NOT NULL DEFAULT '',
    device_stable_id TEXT NOT NULL DEFAULT '',
    ceph_device_path TEXT NOT NULL DEFAULT '',
    ceph_lvm_artifact JSONB NOT NULL DEFAULT '{}'::jsonb,
    osd_id INTEGER,
    osd_fsid TEXT NOT NULL DEFAULT '',
    status TEXT NOT NULL DEFAULT 'allocated' CHECK (status IN ('allocated', 'prepared', 'active', 'out', 'removed', 'failed')),
    test_run_id TEXT,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE(cluster_id, slot_name)
);

CREATE TABLE IF NOT EXISTS storage_snapshot_policies (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name TEXT NOT NULL UNIQUE,
    keep_recent INTEGER NOT NULL DEFAULT 10 CHECK (keep_recent >= 0),
    keep_daily INTEGER NOT NULL DEFAULT 7 CHECK (keep_daily >= 0),
    keep_monthly INTEGER NOT NULL DEFAULT 12 CHECK (keep_monthly >= 0),
    db_hook_mode TEXT NOT NULL DEFAULT 'none' CHECK (db_hook_mode IN ('none', 'postgres', 'mysql', 'custom')),
    enabled BOOLEAN NOT NULL DEFAULT true,
    test_run_id TEXT,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS storage_mounts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    service_id UUID NOT NULL REFERENCES services(id) ON DELETE CASCADE,
    compose_version_id UUID REFERENCES compose_versions(id) ON DELETE SET NULL,
    mount_name TEXT NOT NULL,
    backend TEXT NOT NULL DEFAULT 'cephfs' CHECK (backend IN ('cephfs', 'local_bind')),
    original_source TEXT NOT NULL DEFAULT '',
    host_path TEXT NOT NULL DEFAULT '',
    container_path TEXT NOT NULL DEFAULT '',
    quota_bytes BIGINT CHECK (quota_bytes IS NULL OR quota_bytes >= 0),
    snapshot_policy_id UUID REFERENCES storage_snapshot_policies(id) ON DELETE SET NULL,
    status TEXT NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'warning', 'failed', 'deleted')),
    test_run_id TEXT,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE(service_id, mount_name, host_path)
);

CREATE TABLE IF NOT EXISTS storage_snapshots (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    mount_id UUID NOT NULL REFERENCES storage_mounts(id) ON DELETE CASCADE,
    service_id UUID NOT NULL REFERENCES services(id) ON DELETE CASCADE,
    compose_version_id UUID REFERENCES compose_versions(id) ON DELETE SET NULL,
    snapshot_name TEXT NOT NULL,
    snapshot_path TEXT NOT NULL DEFAULT '',
    source TEXT NOT NULL DEFAULT 'manual' CHECK (source IN ('release', 'manual', 'policy', 'pre_rollback')),
    status TEXT NOT NULL DEFAULT 'creating' CHECK (status IN ('creating', 'ready', 'restoring', 'failed', 'deleted')),
    size_bytes BIGINT CHECK (size_bytes IS NULL OR size_bytes >= 0),
    test_run_id TEXT,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE(mount_id, snapshot_name)
);

CREATE INDEX IF NOT EXISTS ceph_clusters_status_idx
    ON ceph_clusters(status, created_at DESC);
CREATE INDEX IF NOT EXISTS ceph_nodes_cluster_status_idx
    ON ceph_nodes(cluster_id, status, mount_status);
CREATE INDEX IF NOT EXISTS ceph_nodes_node_idx
    ON ceph_nodes(node_id);
CREATE INDEX IF NOT EXISTS ceph_osd_slots_cluster_status_idx
    ON ceph_osd_slots(cluster_id, status);
CREATE INDEX IF NOT EXISTS ceph_osd_slots_node_idx
    ON ceph_osd_slots(node_id, status);
CREATE INDEX IF NOT EXISTS storage_mounts_service_idx
    ON storage_mounts(service_id, status);
CREATE INDEX IF NOT EXISTS storage_mounts_backend_idx
    ON storage_mounts(backend, status);
CREATE INDEX IF NOT EXISTS storage_snapshots_mount_idx
    ON storage_snapshots(mount_id, created_at DESC);
CREATE INDEX IF NOT EXISTS storage_snapshots_service_idx
    ON storage_snapshots(service_id, created_at DESC);
CREATE INDEX IF NOT EXISTS storage_snapshots_status_idx
    ON storage_snapshots(status, created_at DESC);

DROP TRIGGER IF EXISTS ceph_clusters_set_updated_at ON ceph_clusters;
CREATE TRIGGER ceph_clusters_set_updated_at
    BEFORE UPDATE ON ceph_clusters
    FOR EACH ROW EXECUTE FUNCTION docker_infra_set_updated_at();

DROP TRIGGER IF EXISTS ceph_nodes_set_updated_at ON ceph_nodes;
CREATE TRIGGER ceph_nodes_set_updated_at
    BEFORE UPDATE ON ceph_nodes
    FOR EACH ROW EXECUTE FUNCTION docker_infra_set_updated_at();

DROP TRIGGER IF EXISTS ceph_osd_slots_set_updated_at ON ceph_osd_slots;
CREATE TRIGGER ceph_osd_slots_set_updated_at
    BEFORE UPDATE ON ceph_osd_slots
    FOR EACH ROW EXECUTE FUNCTION docker_infra_set_updated_at();

DROP TRIGGER IF EXISTS storage_mounts_set_updated_at ON storage_mounts;
CREATE TRIGGER storage_mounts_set_updated_at
    BEFORE UPDATE ON storage_mounts
    FOR EACH ROW EXECUTE FUNCTION docker_infra_set_updated_at();

DROP TRIGGER IF EXISTS storage_snapshots_set_updated_at ON storage_snapshots;
CREATE TRIGGER storage_snapshots_set_updated_at
    BEFORE UPDATE ON storage_snapshots
    FOR EACH ROW EXECUTE FUNCTION docker_infra_set_updated_at();

DROP TRIGGER IF EXISTS storage_snapshot_policies_set_updated_at ON storage_snapshot_policies;
CREATE TRIGGER storage_snapshot_policies_set_updated_at
    BEFORE UPDATE ON storage_snapshot_policies
    FOR EACH ROW EXECUTE FUNCTION docker_infra_set_updated_at();
