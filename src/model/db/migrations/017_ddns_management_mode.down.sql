UPDATE ddns_endpoints
SET metadata = COALESCE(metadata, '{}'::jsonb) || '{"mode": "wildcard_proxy"}'::jsonb;
