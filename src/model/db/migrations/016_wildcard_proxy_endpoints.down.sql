UPDATE ddns_endpoints
SET
    api_base_url = COALESCE(NULLIF(api_base_url, ''), 'http://localhost'),
    registration_path = COALESCE(NULLIF(registration_path, ''), '/api/ddns/services');

ALTER TABLE ddns_endpoints
    ALTER COLUMN api_base_url SET NOT NULL,
    ALTER COLUMN api_base_url DROP DEFAULT,
    ALTER COLUMN registration_path SET NOT NULL,
    ALTER COLUMN registration_path SET DEFAULT '/api/ddns/services';
