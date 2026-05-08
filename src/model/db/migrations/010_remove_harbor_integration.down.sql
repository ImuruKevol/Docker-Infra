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

DROP TRIGGER IF EXISTS integration_harbor_set_updated_at ON integration_harbor;
CREATE TRIGGER integration_harbor_set_updated_at
BEFORE UPDATE ON integration_harbor
FOR EACH ROW EXECUTE FUNCTION docker_infra_set_updated_at();
