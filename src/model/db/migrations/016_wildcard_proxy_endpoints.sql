ALTER TABLE ddns_endpoints
    ALTER COLUMN api_base_url DROP NOT NULL,
    ALTER COLUMN api_base_url SET DEFAULT '',
    ALTER COLUMN registration_path DROP NOT NULL,
    ALTER COLUMN registration_path SET DEFAULT '';

UPDATE ddns_endpoints
SET
    api_base_url = COALESCE(api_base_url, ''),
    registration_path = COALESCE(registration_path, ''),
    health_path = NULL,
    token_enc = NULL,
    tls_verify = true,
    metadata = metadata || '{"mode": "wildcard_proxy"}'::jsonb;
