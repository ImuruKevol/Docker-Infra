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

CREATE INDEX IF NOT EXISTS backup_system_settings_test_run_id_idx ON backup_system_settings(test_run_id);

DROP TRIGGER IF EXISTS backup_system_settings_set_updated_at ON backup_system_settings;
CREATE TRIGGER backup_system_settings_set_updated_at
BEFORE UPDATE ON backup_system_settings
FOR EACH ROW EXECUTE FUNCTION docker_infra_set_updated_at();
