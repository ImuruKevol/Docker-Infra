CREATE TABLE IF NOT EXISTS shell_macro_schedules (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    macro_id UUID NOT NULL REFERENCES shell_macros(id) ON DELETE CASCADE,
    name TEXT NOT NULL DEFAULT '',
    enabled BOOLEAN NOT NULL DEFAULT true,
    schedule_type TEXT NOT NULL DEFAULT 'weekly' CHECK (schedule_type IN ('weekly', 'monthly')),
    schedule_weekday INTEGER NOT NULL DEFAULT 0 CHECK (schedule_weekday BETWEEN 0 AND 6),
    schedule_weekdays JSONB NOT NULL DEFAULT '[0]'::jsonb,
    schedule_month_day INTEGER NOT NULL DEFAULT 1 CHECK (schedule_month_day BETWEEN 1 AND 31),
    schedule_time TEXT NOT NULL DEFAULT '02:00',
    target_type TEXT NOT NULL DEFAULT 'server' CHECK (target_type IN ('server', 'service')),
    targets JSONB NOT NULL DEFAULT '[]'::jsonb,
    args TEXT NOT NULL DEFAULT '',
    token_hash TEXT,
    cron_file TEXT NOT NULL DEFAULT '',
    last_run_at TIMESTAMPTZ,
    last_result JSONB NOT NULL DEFAULT '{}'::jsonb,
    test_run_id TEXT,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

ALTER TABLE shell_macro_schedules
    ADD COLUMN IF NOT EXISTS schedule_weekdays JSONB NOT NULL DEFAULT '[0]'::jsonb;

UPDATE shell_macro_schedules
SET schedule_weekdays = jsonb_build_array(COALESCE(schedule_weekday, 0))
WHERE schedule_weekdays IS NULL OR schedule_weekdays = '[]'::jsonb;

CREATE INDEX IF NOT EXISTS shell_macro_schedules_macro_idx
    ON shell_macro_schedules(macro_id, created_at DESC);
CREATE INDEX IF NOT EXISTS shell_macro_schedules_enabled_idx
    ON shell_macro_schedules(enabled, schedule_type);
CREATE INDEX IF NOT EXISTS operation_logs_macro_schedule_idx
    ON operation_logs((metadata->>'schedule_id'), created_at DESC)
    WHERE type = 'macro.run';

DROP TRIGGER IF EXISTS shell_macro_schedules_set_updated_at ON shell_macro_schedules;
CREATE TRIGGER shell_macro_schedules_set_updated_at
    BEFORE UPDATE ON shell_macro_schedules
    FOR EACH ROW EXECUTE FUNCTION docker_infra_set_updated_at();
