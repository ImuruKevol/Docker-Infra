DELETE FROM system_settings WHERE key LIKE 'integration.harbor.%';
DROP TABLE IF EXISTS integration_harbor CASCADE;
