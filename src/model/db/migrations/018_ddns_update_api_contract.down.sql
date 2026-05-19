ALTER TABLE ddns_endpoints
    ALTER COLUMN registration_path SET DEFAULT '/api/ddns/records';

UPDATE ddns_endpoints
SET registration_path = '/api/ddns/records'
WHERE registration_path = '/api/ddns/update';
