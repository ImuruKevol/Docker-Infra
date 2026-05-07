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

CREATE INDEX IF NOT EXISTS auth_sessions_active_idx ON auth_sessions(token_hash, expires_at) WHERE revoked_at IS NULL;
CREATE INDEX IF NOT EXISTS auth_sessions_test_run_id_idx ON auth_sessions(test_run_id);
CREATE INDEX IF NOT EXISTS auth_login_attempts_scope_attempted_idx ON auth_login_attempts(scope, attempted_at DESC);
CREATE INDEX IF NOT EXISTS auth_login_attempts_test_run_id_idx ON auth_login_attempts(test_run_id);

DO $$
DECLARE
    table_name TEXT;
BEGIN
    FOREACH table_name IN ARRAY ARRAY[
        'operator_auth', 'auth_sessions', 'auth_login_attempts'
    ] LOOP
        EXECUTE format('DROP TRIGGER IF EXISTS %I_set_updated_at ON %I', table_name, table_name);
        EXECUTE format(
            'CREATE TRIGGER %I_set_updated_at BEFORE UPDATE ON %I FOR EACH ROW EXECUTE FUNCTION docker_infra_set_updated_at()',
            table_name,
            table_name
        );
    END LOOP;
END $$;
