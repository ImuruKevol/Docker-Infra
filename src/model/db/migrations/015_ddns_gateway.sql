CREATE TABLE IF NOT EXISTS ddns_endpoints (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name TEXT NOT NULL,
    domain_suffix TEXT NOT NULL UNIQUE,
    api_base_url TEXT NOT NULL,
    registration_path TEXT NOT NULL DEFAULT '/api/ddns/services',
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

CREATE INDEX IF NOT EXISTS ddns_endpoints_suffix_idx
    ON ddns_endpoints(domain_suffix);

CREATE INDEX IF NOT EXISTS ddns_registrations_service_domain_idx
    ON ddns_registrations(service_domain_id);

CREATE INDEX IF NOT EXISTS ddns_registrations_status_idx
    ON ddns_registrations(endpoint_id, status);

DROP TRIGGER IF EXISTS ddns_endpoints_set_updated_at ON ddns_endpoints;
CREATE TRIGGER ddns_endpoints_set_updated_at
    BEFORE UPDATE ON ddns_endpoints
    FOR EACH ROW
    EXECUTE FUNCTION docker_infra_set_updated_at();

DROP TRIGGER IF EXISTS ddns_registrations_set_updated_at ON ddns_registrations;
CREATE TRIGGER ddns_registrations_set_updated_at
    BEFORE UPDATE ON ddns_registrations
    FOR EACH ROW
    EXECUTE FUNCTION docker_infra_set_updated_at();
