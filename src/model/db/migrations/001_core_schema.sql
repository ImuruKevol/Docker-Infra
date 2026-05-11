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

CREATE TABLE IF NOT EXISTS integration_harbor (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    url TEXT NOT NULL,
    username TEXT,
    password_enc TEXT,
    enabled BOOLEAN NOT NULL DEFAULT false,
    project TEXT,
    test_run_id TEXT,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS integration_gitlab (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    url TEXT NOT NULL,
    token_enc TEXT,
    enabled BOOLEAN NOT NULL DEFAULT false,
    test_run_id TEXT,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS cloudflare_zones (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    domain TEXT NOT NULL UNIQUE,
    zone_id TEXT NOT NULL,
    api_token_enc TEXT,
    usable_for_service BOOLEAN NOT NULL DEFAULT true,
    enabled BOOLEAN NOT NULL DEFAULT false,
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

CREATE UNIQUE INDEX IF NOT EXISTS nodes_one_local_master_idx ON nodes (is_local_master) WHERE is_local_master = true;

CREATE TABLE IF NOT EXISTS node_credentials (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    node_id UUID NOT NULL REFERENCES nodes(id) ON DELETE CASCADE,
    username TEXT NOT NULL,
    password_enc TEXT,
    private_key_enc TEXT,
    passphrase_enc TEXT,
    ssh_fingerprint TEXT,
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

CREATE TABLE IF NOT EXISTS image_builds (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    service_id UUID REFERENCES services(id) ON DELETE SET NULL,
    gitlab_project_id TEXT,
    compose_file_path TEXT NOT NULL,
    build_node_id UUID REFERENCES nodes(id) ON DELETE SET NULL,
    status TEXT NOT NULL DEFAULT 'pending',
    image_id UUID REFERENCES images(id) ON DELETE SET NULL,
    test_run_id TEXT,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS jobs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    type TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'running', 'succeeded', 'failed', 'canceled')),
    requested_payload JSONB NOT NULL DEFAULT '{}'::jsonb,
    result_payload JSONB NOT NULL DEFAULT '{}'::jsonb,
    test_run_id TEXT,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    started_at TIMESTAMPTZ,
    finished_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS job_steps (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    job_id UUID NOT NULL REFERENCES jobs(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'running', 'succeeded', 'failed', 'skipped', 'canceled')),
    order_no INTEGER NOT NULL,
    test_run_id TEXT,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    started_at TIMESTAMPTZ,
    finished_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE(job_id, order_no)
);

CREATE TABLE IF NOT EXISTS job_logs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    job_id UUID NOT NULL REFERENCES jobs(id) ON DELETE CASCADE,
    step_id UUID REFERENCES job_steps(id) ON DELETE SET NULL,
    stream TEXT NOT NULL CHECK (stream IN ('stdout', 'stderr', 'system')),
    message TEXT NOT NULL,
    test_run_id TEXT,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
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

CREATE INDEX IF NOT EXISTS system_settings_test_run_id_idx ON system_settings(test_run_id);
CREATE INDEX IF NOT EXISTS nodes_test_run_id_idx ON nodes(test_run_id);
CREATE INDEX IF NOT EXISTS services_test_run_id_idx ON services(test_run_id);
CREATE INDEX IF NOT EXISTS jobs_test_run_id_idx ON jobs(test_run_id);
CREATE INDEX IF NOT EXISTS job_logs_job_id_idx ON job_logs(job_id);
CREATE INDEX IF NOT EXISTS node_metrics_node_reported_idx ON node_metrics(node_id, reported_at DESC);

DO $$
DECLARE
    table_name TEXT;
BEGIN
    FOREACH table_name IN ARRAY ARRAY[
        'system_settings', 'integration_harbor', 'integration_gitlab', 'cloudflare_zones',
        'nodes', 'node_credentials', 'node_metrics',
        'services', 'service_domains', 'compose_versions', 'images', 'image_builds',
        'jobs', 'job_steps', 'job_logs', 'proxy_configs', 'certificates', 'electron_setting_backups'
    ] LOOP
        EXECUTE format('DROP TRIGGER IF EXISTS %I_set_updated_at ON %I', table_name, table_name);
        EXECUTE format(
            'CREATE TRIGGER %I_set_updated_at BEFORE UPDATE ON %I FOR EACH ROW EXECUTE FUNCTION docker_infra_set_updated_at()',
            table_name,
            table_name
        );
    END LOOP;
END $$;
