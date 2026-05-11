CREATE TABLE IF NOT EXISTS templates (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name TEXT NOT NULL,
    namespace TEXT NOT NULL UNIQUE,
    path TEXT NOT NULL,
    description TEXT,
    enabled BOOLEAN NOT NULL DEFAULT true,
    test_run_id TEXT,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS template_versions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    template_id UUID NOT NULL REFERENCES templates(id) ON DELETE CASCADE,
    version INTEGER NOT NULL,
    path TEXT NOT NULL,
    checksum TEXT NOT NULL,
    test_run_id TEXT,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE(template_id, version)
);

DO $$
BEGIN
    IF to_regclass('public.system_settings') IS NOT NULL THEN
        UPDATE system_settings current_setting
        SET key = 'setup.template_root'
        WHERE current_setting.key = 'setup.service_root'
          AND NOT EXISTS (
              SELECT 1
              FROM system_settings existing
              WHERE existing.key = 'setup.template_root'
          );
    END IF;
END $$;
