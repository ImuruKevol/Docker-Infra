DROP TRIGGER IF EXISTS cloudflare_dns_records_set_updated_at ON cloudflare_dns_records;
DROP TABLE IF EXISTS cloudflare_dns_records CASCADE;

ALTER TABLE cloudflare_zones
    DROP COLUMN IF EXISTS last_sync_at,
    DROP COLUMN IF EXISTS last_sync_status,
    DROP COLUMN IF EXISTS last_sync_message,
    DROP COLUMN IF EXISTS record_count;
