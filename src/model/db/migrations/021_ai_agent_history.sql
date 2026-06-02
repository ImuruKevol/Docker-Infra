CREATE TABLE IF NOT EXISTS ai_agent_histories (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    request_id TEXT NOT NULL DEFAULT '',
    session_id TEXT NOT NULL DEFAULT '',
    provider_session_id TEXT NOT NULL DEFAULT '',
    session_title TEXT NOT NULL DEFAULT '',
    turn_index INTEGER NOT NULL DEFAULT 1,
    agent_type TEXT NOT NULL DEFAULT '',
    agent_label TEXT NOT NULL DEFAULT '',
    model TEXT NOT NULL DEFAULT '',
    status TEXT NOT NULL DEFAULT 'succeeded' CHECK (status IN ('succeeded', 'failed')),
    request_message TEXT NOT NULL DEFAULT '',
    response_answer TEXT NOT NULL DEFAULT '',
    response_summary TEXT NOT NULL DEFAULT '',
    request_payload JSONB NOT NULL DEFAULT '{}'::jsonb,
    response_payload JSONB NOT NULL DEFAULT '{}'::jsonb,
    test_run_id TEXT,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    error_code TEXT NOT NULL DEFAULT '',
    error_message TEXT NOT NULL DEFAULT '',
    started_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    finished_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

ALTER TABLE ai_agent_histories
    ADD COLUMN IF NOT EXISTS request_id TEXT NOT NULL DEFAULT '',
    ADD COLUMN IF NOT EXISTS session_id TEXT NOT NULL DEFAULT '',
    ADD COLUMN IF NOT EXISTS provider_session_id TEXT NOT NULL DEFAULT '',
    ADD COLUMN IF NOT EXISTS session_title TEXT NOT NULL DEFAULT '',
    ADD COLUMN IF NOT EXISTS turn_index INTEGER NOT NULL DEFAULT 1;

CREATE INDEX IF NOT EXISTS ai_agent_histories_created_at_idx
    ON ai_agent_histories(created_at DESC);
CREATE INDEX IF NOT EXISTS ai_agent_histories_agent_type_idx
    ON ai_agent_histories(agent_type, created_at DESC);
CREATE INDEX IF NOT EXISTS ai_agent_histories_status_idx
    ON ai_agent_histories(status, created_at DESC);
CREATE INDEX IF NOT EXISTS ai_agent_histories_session_idx
    ON ai_agent_histories(agent_type, session_id, created_at DESC);
CREATE INDEX IF NOT EXISTS ai_agent_histories_request_idx
    ON ai_agent_histories(agent_type, request_id)
    WHERE request_id <> '';
CREATE INDEX IF NOT EXISTS ai_agent_histories_provider_session_idx
    ON ai_agent_histories(agent_type, provider_session_id, created_at DESC)
    WHERE provider_session_id <> '';

DROP TRIGGER IF EXISTS ai_agent_histories_set_updated_at ON ai_agent_histories;
CREATE TRIGGER ai_agent_histories_set_updated_at
    BEFORE UPDATE ON ai_agent_histories
    FOR EACH ROW EXECUTE FUNCTION docker_infra_set_updated_at();
