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

CREATE INDEX IF NOT EXISTS jobs_test_run_id_idx ON jobs(test_run_id);
CREATE INDEX IF NOT EXISTS job_logs_job_id_idx ON job_logs(job_id);

DROP TRIGGER IF EXISTS jobs_set_updated_at ON jobs;
CREATE TRIGGER jobs_set_updated_at
BEFORE UPDATE ON jobs
FOR EACH ROW EXECUTE FUNCTION docker_infra_set_updated_at();

DROP TRIGGER IF EXISTS job_steps_set_updated_at ON job_steps;
CREATE TRIGGER job_steps_set_updated_at
BEFORE UPDATE ON job_steps
FOR EACH ROW EXECUTE FUNCTION docker_infra_set_updated_at();

DROP TRIGGER IF EXISTS job_logs_set_updated_at ON job_logs;
CREATE TRIGGER job_logs_set_updated_at
BEFORE UPDATE ON job_logs
FOR EACH ROW EXECUTE FUNCTION docker_infra_set_updated_at();

DROP TABLE IF EXISTS operation_logs CASCADE;
