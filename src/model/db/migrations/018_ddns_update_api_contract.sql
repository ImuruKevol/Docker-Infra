ALTER TABLE ddns_endpoints
    ALTER COLUMN registration_path SET DEFAULT '/api/ddns/update';

UPDATE ddns_endpoints
SET registration_path = '/api/ddns/update'
WHERE COALESCE(NULLIF(registration_path, ''), '/api/ddns/update') IN (
    '/api/ddns/services',
    '/api/ddns/records',
    '/api/ddns/update'
);
