CREATE EXTENSION IF NOT EXISTS pgcrypto;

CREATE TABLE IF NOT EXISTS schema_migrations (
    version TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    checksum TEXT NOT NULL,
    applied_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE OR REPLACE FUNCTION docker_infra_set_updated_at()
RETURNS trigger AS $$
BEGIN
    NEW.updated_at = now();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TABLE IF NOT EXISTS system_settings (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    key TEXT NOT NULL UNIQUE,
    value_json JSONB,
    secret_enc TEXT,
    value_type TEXT NOT NULL DEFAULT 'string',
    is_secret BOOLEAN NOT NULL DEFAULT false,
    description TEXT,
    test_run_id TEXT,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT system_settings_secret_shape CHECK (
        (is_secret = true AND secret_enc IS NOT NULL AND value_json IS NULL)
        OR (is_secret = false AND secret_enc IS NULL)
    )
);

CREATE TABLE IF NOT EXISTS cloudflare_zones (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    domain TEXT NOT NULL UNIQUE,
    zone_id TEXT NOT NULL,
    api_token_enc TEXT,
    usable_for_service BOOLEAN NOT NULL DEFAULT true,
    enabled BOOLEAN NOT NULL DEFAULT false,
    last_sync_at TIMESTAMPTZ,
    last_sync_status TEXT NOT NULL DEFAULT 'never',
    last_sync_message TEXT,
    record_count INTEGER NOT NULL DEFAULT 0,
    test_run_id TEXT,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS nodes (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name TEXT NOT NULL,
    role TEXT NOT NULL CHECK (role IN ('local_master', 'manager', 'worker')),
    host TEXT NOT NULL,
    ssh_port INTEGER,
    auth_type TEXT,
    status TEXT NOT NULL DEFAULT 'pending',
    swarm_node_id TEXT,
    is_local_master BOOLEAN NOT NULL DEFAULT false,
    labels JSONB NOT NULL DEFAULT '{}'::jsonb,
    test_run_id TEXT,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE UNIQUE INDEX IF NOT EXISTS nodes_one_local_master_idx
    ON nodes (is_local_master)
    WHERE is_local_master = true;

CREATE TABLE IF NOT EXISTS node_credentials (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    node_id UUID NOT NULL REFERENCES nodes(id) ON DELETE CASCADE,
    username TEXT NOT NULL,
    password_enc TEXT,
    private_key_enc TEXT,
    passphrase_enc TEXT,
    ssh_fingerprint TEXT,
    key_file TEXT,
    test_run_id TEXT,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS node_metrics (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    node_id UUID NOT NULL REFERENCES nodes(id) ON DELETE CASCADE,
    cpu_percent NUMERIC(6, 2),
    memory JSONB NOT NULL DEFAULT '{}'::jsonb,
    storage JSONB NOT NULL DEFAULT '{}'::jsonb,
    containers JSONB NOT NULL DEFAULT '{}'::jsonb,
    reported_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    test_run_id TEXT,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS services (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    namespace TEXT NOT NULL UNIQUE,
    name TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'draft',
    compose_path TEXT,
    stack_name TEXT,
    target_node_policy JSONB NOT NULL DEFAULT '{}'::jsonb,
    test_run_id TEXT,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS service_domains (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    service_id UUID NOT NULL REFERENCES services(id) ON DELETE CASCADE,
    domain TEXT NOT NULL,
    port INTEGER NOT NULL,
    proxy_type TEXT NOT NULL DEFAULT 'nginx',
    ssl_mode TEXT NOT NULL DEFAULT 'none',
    test_run_id TEXT,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE(service_id, domain)
);

CREATE TABLE IF NOT EXISTS compose_versions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    service_id UUID NOT NULL REFERENCES services(id) ON DELETE CASCADE,
    version INTEGER NOT NULL,
    path TEXT NOT NULL,
    checksum TEXT NOT NULL,
    test_run_id TEXT,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE(service_id, version)
);

CREATE TABLE IF NOT EXISTS images (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    registry TEXT NOT NULL,
    project TEXT,
    name TEXT NOT NULL,
    tag TEXT NOT NULL,
    digest TEXT,
    source TEXT NOT NULL DEFAULT 'local',
    test_run_id TEXT,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE(registry, name, tag)
);

CREATE TABLE IF NOT EXISTS proxy_configs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    service_id UUID REFERENCES services(id) ON DELETE CASCADE,
    proxy_type TEXT NOT NULL,
    config_path TEXT NOT NULL,
    content TEXT NOT NULL,
    active BOOLEAN NOT NULL DEFAULT false,
    checksum TEXT NOT NULL,
    test_run_id TEXT,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS certificates (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    service_domain_id UUID REFERENCES service_domains(id) ON DELETE CASCADE,
    mode TEXT NOT NULL,
    cert_path TEXT NOT NULL,
    key_path TEXT NOT NULL,
    expires_at TIMESTAMPTZ,
    status TEXT NOT NULL DEFAULT 'pending',
    test_run_id TEXT,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS electron_setting_backups (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name TEXT NOT NULL,
    payload_enc TEXT NOT NULL,
    test_run_id TEXT,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS operator_auth (
    singleton_key TEXT PRIMARY KEY DEFAULT 'operator',
    password_hash TEXT NOT NULL,
    password_changed_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    test_run_id TEXT,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT operator_auth_singleton CHECK (singleton_key = 'operator')
);

CREATE TABLE IF NOT EXISTS auth_sessions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    token_hash TEXT NOT NULL UNIQUE,
    expires_at TIMESTAMPTZ NOT NULL,
    revoked_at TIMESTAMPTZ,
    last_seen_at TIMESTAMPTZ,
    remote_addr TEXT,
    user_agent TEXT,
    test_run_id TEXT,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS auth_login_attempts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    scope TEXT NOT NULL,
    success BOOLEAN NOT NULL DEFAULT false,
    locked_until TIMESTAMPTZ,
    attempted_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    remote_addr TEXT,
    user_agent TEXT,
    test_run_id TEXT,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS shell_macros (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name TEXT NOT NULL,
    description TEXT NOT NULL DEFAULT '',
    script TEXT NOT NULL,
    enabled BOOLEAN NOT NULL DEFAULT true,
    scope_type TEXT NOT NULL DEFAULT 'global',
    node_id UUID REFERENCES nodes(id) ON DELETE CASCADE,
    test_run_id TEXT,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS shell_macro_files (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    macro_id UUID NOT NULL REFERENCES shell_macros(id) ON DELETE CASCADE,
    filename TEXT NOT NULL,
    content_type TEXT NOT NULL DEFAULT '',
    size_bytes BIGINT NOT NULL DEFAULT 0,
    content BYTEA NOT NULL,
    test_run_id TEXT,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

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

CREATE TABLE IF NOT EXISTS operation_logs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    type TEXT NOT NULL,
    target_type TEXT,
    target_id TEXT,
    status TEXT NOT NULL DEFAULT 'running' CHECK (status IN ('pending', 'running', 'succeeded', 'failed', 'canceled')),
    message TEXT NOT NULL DEFAULT '',
    requested_payload JSONB NOT NULL DEFAULT '{}'::jsonb,
    result_payload JSONB NOT NULL DEFAULT '{}'::jsonb,
    output JSONB NOT NULL DEFAULT '[]'::jsonb,
    test_run_id TEXT,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    started_at TIMESTAMPTZ,
    finished_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS backup_system_settings (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    singleton_key TEXT NOT NULL DEFAULT 'default' UNIQUE,
    enabled BOOLEAN NOT NULL DEFAULT false,
    status TEXT NOT NULL DEFAULT 'disabled' CHECK (status IN ('disabled', 'pending_install', 'running', 'stopped', 'failed')),
    data_path TEXT NOT NULL,
    harbor_url TEXT,
    admin_username TEXT,
    admin_password_enc TEXT,
    used_bytes BIGINT NOT NULL DEFAULT 0,
    available_bytes BIGINT NOT NULL DEFAULT 0,
    total_bytes BIGINT NOT NULL DEFAULT 0,
    last_error TEXT,
    last_checked_at TIMESTAMPTZ,
    test_run_id TEXT,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS ddns_endpoints (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name TEXT NOT NULL,
    domain_suffix TEXT NOT NULL UNIQUE,
    api_base_url TEXT DEFAULT '',
    registration_path TEXT DEFAULT '/api/ddns/update',
    health_path TEXT,
    token_enc TEXT,
    enabled BOOLEAN NOT NULL DEFAULT false,
    tls_verify BOOLEAN NOT NULL DEFAULT true,
    last_check_at TIMESTAMPTZ,
    last_check_status TEXT NOT NULL DEFAULT 'never',
    last_check_message TEXT,
    test_run_id TEXT,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS ddns_registrations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    endpoint_id UUID NOT NULL REFERENCES ddns_endpoints(id) ON DELETE CASCADE,
    service_id UUID REFERENCES services(id) ON DELETE CASCADE,
    service_domain_id UUID REFERENCES service_domains(id) ON DELETE CASCADE,
    domain TEXT NOT NULL,
    target_scheme TEXT NOT NULL DEFAULT 'http',
    target_host TEXT NOT NULL,
    target_port INTEGER NOT NULL,
    remote_record_id TEXT,
    status TEXT NOT NULL DEFAULT 'pending',
    last_sync_at TIMESTAMPTZ,
    last_sync_message TEXT,
    test_run_id TEXT,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE(endpoint_id, domain)
);

ALTER TABLE cloudflare_zones
    ADD COLUMN IF NOT EXISTS last_sync_at TIMESTAMPTZ,
    ADD COLUMN IF NOT EXISTS last_sync_status TEXT DEFAULT 'never',
    ADD COLUMN IF NOT EXISTS last_sync_message TEXT,
    ADD COLUMN IF NOT EXISTS record_count INTEGER DEFAULT 0;

UPDATE cloudflare_zones
SET
    last_sync_status = COALESCE(NULLIF(last_sync_status, ''), 'never'),
    record_count = COALESCE(record_count, 0);

ALTER TABLE cloudflare_zones
    ALTER COLUMN last_sync_status SET DEFAULT 'never',
    ALTER COLUMN last_sync_status SET NOT NULL,
    ALTER COLUMN record_count SET DEFAULT 0,
    ALTER COLUMN record_count SET NOT NULL;

ALTER TABLE node_credentials
    ADD COLUMN IF NOT EXISTS key_file TEXT;

UPDATE node_credentials
SET key_file = metadata->>'key_file'
WHERE key_file IS NULL
  AND metadata ? 'key_file';

ALTER TABLE shell_macros DROP CONSTRAINT IF EXISTS shell_macros_name_key;
ALTER TABLE shell_macros
    ADD COLUMN IF NOT EXISTS scope_type TEXT DEFAULT 'global',
    ADD COLUMN IF NOT EXISTS node_id UUID;

UPDATE shell_macros
SET scope_type = 'global'
WHERE scope_type IS NULL OR scope_type = '';

ALTER TABLE shell_macros
    ALTER COLUMN scope_type SET DEFAULT 'global',
    ALTER COLUMN scope_type SET NOT NULL;

ALTER TABLE shell_macros DROP CONSTRAINT IF EXISTS shell_macros_scope_type_check;
ALTER TABLE shell_macros
    ADD CONSTRAINT shell_macros_scope_type_check CHECK (scope_type IN ('global', 'node'));

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM pg_constraint
        WHERE conname = 'shell_macros_node_id_fkey'
          AND conrelid = 'shell_macros'::regclass
    ) THEN
        ALTER TABLE shell_macros
            ADD CONSTRAINT shell_macros_node_id_fkey
            FOREIGN KEY (node_id) REFERENCES nodes(id) ON DELETE CASCADE;
    END IF;
END $$;

ALTER TABLE ddns_endpoints
    ALTER COLUMN api_base_url DROP NOT NULL,
    ALTER COLUMN api_base_url SET DEFAULT '',
    ALTER COLUMN registration_path DROP NOT NULL,
    ALTER COLUMN registration_path SET DEFAULT '/api/ddns/update';

UPDATE ddns_endpoints
SET
    api_base_url = COALESCE(api_base_url, ''),
    registration_path = '/api/ddns/update'
WHERE COALESCE(NULLIF(registration_path, ''), '/api/ddns/update') IN (
    '/api/ddns/services',
    '/api/ddns/records',
    '/api/ddns/update'
);

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM schema_migrations WHERE version = '016') THEN
        UPDATE ddns_endpoints
        SET
            health_path = NULL,
            token_enc = NULL,
            tls_verify = true;
    END IF;

    IF NOT EXISTS (SELECT 1 FROM schema_migrations WHERE version = '017') THEN
        UPDATE ddns_endpoints
        SET
            metadata = COALESCE(metadata, '{}'::jsonb) || '{"mode": "ddns_management"}'::jsonb;
    END IF;
END $$;

DO $$
BEGIN
    IF to_regclass('system_settings') IS NOT NULL THEN
        UPDATE system_settings current_setting
        SET key = 'setup.service_root'
        WHERE current_setting.key = 'setup.template_root'
          AND NOT EXISTS (
              SELECT 1
              FROM system_settings existing
              WHERE existing.key = 'setup.service_root'
          );

        DELETE FROM system_settings
        WHERE key = 'setup.template_root'
           OR key LIKE 'integration.harbor.%';
    END IF;

    IF to_regclass('services') IS NOT NULL AND to_regclass('templates') IS NOT NULL THEN
        UPDATE services service_row
        SET metadata = jsonb_set(
            COALESCE(service_row.metadata, '{}'::jsonb),
            '{legacy_template}',
            jsonb_build_object(
                'id', template_row.id,
                'name', template_row.name,
                'namespace', template_row.namespace,
                'description', template_row.description
            ),
            true
        )
        FROM templates template_row
        WHERE COALESCE(service_row.metadata, '{}'::jsonb) #>> '{source_ref,template_id}' = template_row.id::text
          AND NOT (COALESCE(service_row.metadata, '{}'::jsonb) ? 'legacy_template');
    END IF;
END $$;

DROP TABLE IF EXISTS image_builds CASCADE;
DROP TABLE IF EXISTS integration_gitlab CASCADE;
DROP TABLE IF EXISTS job_logs CASCADE;
DROP TABLE IF EXISTS job_steps CASCADE;
DROP TABLE IF EXISTS jobs CASCADE;
DROP TABLE IF EXISTS integration_harbor CASCADE;
DROP TABLE IF EXISTS template_versions CASCADE;
DROP TABLE IF EXISTS templates CASCADE;

CREATE INDEX IF NOT EXISTS system_settings_test_run_id_idx
    ON system_settings(test_run_id);
CREATE INDEX IF NOT EXISTS nodes_test_run_id_idx
    ON nodes(test_run_id);
CREATE INDEX IF NOT EXISTS services_test_run_id_idx
    ON services(test_run_id);
CREATE INDEX IF NOT EXISTS node_metrics_node_reported_idx
    ON node_metrics(node_id, reported_at DESC);

CREATE INDEX IF NOT EXISTS auth_sessions_active_idx
    ON auth_sessions(token_hash, expires_at)
    WHERE revoked_at IS NULL;
CREATE INDEX IF NOT EXISTS auth_sessions_test_run_id_idx
    ON auth_sessions(test_run_id);
CREATE INDEX IF NOT EXISTS auth_login_attempts_scope_attempted_idx
    ON auth_login_attempts(scope, attempted_at DESC);
CREATE INDEX IF NOT EXISTS auth_login_attempts_test_run_id_idx
    ON auth_login_attempts(test_run_id);

CREATE INDEX IF NOT EXISTS shell_macro_files_macro_id_idx
    ON shell_macro_files(macro_id);
CREATE UNIQUE INDEX IF NOT EXISTS shell_macro_files_macro_filename_unique
    ON shell_macro_files(macro_id, filename);
CREATE UNIQUE INDEX IF NOT EXISTS shell_macros_global_name_unique
    ON shell_macros(lower(name))
    WHERE scope_type = 'global' AND node_id IS NULL;
CREATE UNIQUE INDEX IF NOT EXISTS shell_macros_node_name_unique
    ON shell_macros(node_id, lower(name))
    WHERE scope_type = 'node';

CREATE INDEX IF NOT EXISTS cloudflare_dns_records_zone_idx
    ON cloudflare_dns_records(zone_config_id, record_name, record_type);

CREATE INDEX IF NOT EXISTS operation_logs_target_idx
    ON operation_logs(target_type, target_id, created_at DESC);
CREATE INDEX IF NOT EXISTS operation_logs_status_idx
    ON operation_logs(status, created_at DESC);
CREATE INDEX IF NOT EXISTS operation_logs_test_run_id_idx
    ON operation_logs(test_run_id);
CREATE INDEX IF NOT EXISTS operation_logs_requested_service_id_idx
    ON operation_logs((requested_payload->>'service_id'), created_at DESC);
CREATE INDEX IF NOT EXISTS operation_logs_metadata_service_id_idx
    ON operation_logs((metadata->>'service_id'), created_at DESC);
CREATE INDEX IF NOT EXISTS operation_logs_requested_namespace_idx
    ON operation_logs((requested_payload->>'namespace'), created_at DESC);
CREATE INDEX IF NOT EXISTS operation_logs_metadata_namespace_idx
    ON operation_logs((metadata->>'namespace'), created_at DESC);

CREATE INDEX IF NOT EXISTS backup_system_settings_test_run_id_idx
    ON backup_system_settings(test_run_id);

CREATE INDEX IF NOT EXISTS services_created_idx
    ON services(created_at DESC);
CREATE INDEX IF NOT EXISTS service_domains_service_created_idx
    ON service_domains(service_id, created_at ASC);
CREATE INDEX IF NOT EXISTS service_domains_service_domain_idx
    ON service_domains(service_id, domain ASC);
CREATE INDEX IF NOT EXISTS compose_versions_service_version_created_idx
    ON compose_versions(service_id, version DESC, created_at DESC);

CREATE INDEX IF NOT EXISTS ddns_endpoints_suffix_idx
    ON ddns_endpoints(domain_suffix);
CREATE INDEX IF NOT EXISTS ddns_registrations_service_domain_idx
    ON ddns_registrations(service_domain_id);
CREATE INDEX IF NOT EXISTS ddns_registrations_status_idx
    ON ddns_registrations(endpoint_id, status);

DO $$
DECLARE
    table_name TEXT;
BEGIN
    FOREACH table_name IN ARRAY ARRAY[
        'system_settings', 'cloudflare_zones', 'nodes', 'node_credentials', 'node_metrics',
        'services', 'service_domains', 'compose_versions', 'images', 'proxy_configs',
        'certificates', 'electron_setting_backups', 'operator_auth', 'auth_sessions',
        'auth_login_attempts', 'cloudflare_dns_records', 'operation_logs',
        'backup_system_settings', 'ddns_endpoints', 'ddns_registrations'
    ] LOOP
        EXECUTE format('DROP TRIGGER IF EXISTS %I_set_updated_at ON %I', table_name, table_name);
        EXECUTE format(
            'CREATE TRIGGER %I_set_updated_at BEFORE UPDATE ON %I FOR EACH ROW EXECUTE FUNCTION docker_infra_set_updated_at()',
            table_name,
            table_name
        );
    END LOOP;
END $$;

DELETE FROM schema_migrations
WHERE version <> '019';
