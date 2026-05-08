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

DROP TRIGGER IF EXISTS integration_gitlab_set_updated_at ON integration_gitlab;
CREATE TRIGGER integration_gitlab_set_updated_at
BEFORE UPDATE ON integration_gitlab
FOR EACH ROW EXECUTE FUNCTION docker_infra_set_updated_at();

DROP TRIGGER IF EXISTS image_builds_set_updated_at ON image_builds;
CREATE TRIGGER image_builds_set_updated_at
BEFORE UPDATE ON image_builds
FOR EACH ROW EXECUTE FUNCTION docker_infra_set_updated_at();
