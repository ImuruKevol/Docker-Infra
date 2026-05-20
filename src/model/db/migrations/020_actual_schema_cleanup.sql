CREATE TABLE IF NOT EXISTS service_image_backups (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    service_id UUID NOT NULL REFERENCES services(id) ON DELETE CASCADE,
    compose_version_id UUID REFERENCES compose_versions(id) ON DELETE SET NULL,
    compose_service TEXT NOT NULL,
    image_ref TEXT NOT NULL,
    registry TEXT,
    repository TEXT,
    tag TEXT,
    digest TEXT,
    backup_ref TEXT,
    backup_status TEXT NOT NULL DEFAULT 'recorded',
    backup_error TEXT,
    source TEXT NOT NULL DEFAULT 'compose',
    test_run_id TEXT,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS service_image_backups_service_idx
    ON service_image_backups(service_id, created_at DESC);
CREATE INDEX IF NOT EXISTS service_image_backups_digest_idx
    ON service_image_backups(digest)
    WHERE digest IS NOT NULL;

DROP TRIGGER IF EXISTS service_image_backups_set_updated_at ON service_image_backups;
CREATE TRIGGER service_image_backups_set_updated_at
    BEFORE UPDATE ON service_image_backups
    FOR EACH ROW EXECUTE FUNCTION docker_infra_set_updated_at();

ALTER TABLE cloudflare_dns_records
    DROP COLUMN IF EXISTS test_run_id;

ALTER TABLE images
    DROP COLUMN IF EXISTS test_run_id;

DROP TABLE IF EXISTS proxy_configs CASCADE;
DROP TABLE IF EXISTS certificates CASCADE;
DROP TABLE IF EXISTS electron_setting_backups CASCADE;
