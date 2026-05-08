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

CREATE INDEX IF NOT EXISTS operation_logs_target_idx ON operation_logs(target_type, target_id, created_at DESC);
CREATE INDEX IF NOT EXISTS operation_logs_status_idx ON operation_logs(status, created_at DESC);
CREATE INDEX IF NOT EXISTS operation_logs_test_run_id_idx ON operation_logs(test_run_id);

DROP TRIGGER IF EXISTS operation_logs_set_updated_at ON operation_logs;
CREATE TRIGGER operation_logs_set_updated_at
BEFORE UPDATE ON operation_logs
FOR EACH ROW EXECUTE FUNCTION docker_infra_set_updated_at();

DROP TABLE IF EXISTS job_logs CASCADE;
DROP TABLE IF EXISTS job_steps CASCADE;
DROP TABLE IF EXISTS jobs CASCADE;
