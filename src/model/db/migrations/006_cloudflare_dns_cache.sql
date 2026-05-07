ALTER TABLE cloudflare_zones
    ADD COLUMN IF NOT EXISTS last_sync_at TIMESTAMPTZ,
    ADD COLUMN IF NOT EXISTS last_sync_status TEXT NOT NULL DEFAULT 'never',
    ADD COLUMN IF NOT EXISTS last_sync_message TEXT,
    ADD COLUMN IF NOT EXISTS record_count INTEGER NOT NULL DEFAULT 0;

CREATE TABLE IF NOT EXISTS cloudflare_dns_records (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    zone_config_id UUID NOT NULL REFERENCES cloudflare_zones(id) ON DELETE CASCADE,
    cloudflare_record_id TEXT NOT NULL,
    record_type TEXT NOT NULL,
    record_name TEXT NOT NULL,
    content TEXT,
    proxied BOOLEAN,
    ttl INTEGER,
    priority INTEGER,
    comment TEXT,
    test_run_id TEXT,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    last_synced_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE(zone_config_id, cloudflare_record_id)
);

CREATE INDEX IF NOT EXISTS cloudflare_dns_records_zone_idx
    ON cloudflare_dns_records(zone_config_id, record_name, record_type);

DROP TRIGGER IF EXISTS cloudflare_dns_records_set_updated_at ON cloudflare_dns_records;
CREATE TRIGGER cloudflare_dns_records_set_updated_at
    BEFORE UPDATE ON cloudflare_dns_records
    FOR EACH ROW
    EXECUTE FUNCTION docker_infra_set_updated_at();
