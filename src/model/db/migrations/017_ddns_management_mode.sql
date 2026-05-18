UPDATE ddns_endpoints
SET
    registration_path = COALESCE(NULLIF(registration_path, ''), '/api/ddns/records'),
    metadata = COALESCE(metadata, '{}'::jsonb) || '{"mode": "ddns_management"}'::jsonb;
