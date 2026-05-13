CREATE TABLE IF NOT EXISTS shell_macro_files (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    macro_id UUID NOT NULL REFERENCES shell_macros(id) ON DELETE CASCADE,
    filename TEXT NOT NULL,
    content_type TEXT NOT NULL DEFAULT '',
    size_bytes BIGINT NOT NULL DEFAULT 0,
    content BYTEA NOT NULL,
    test_run_id TEXT,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS shell_macro_files_macro_id_idx
    ON shell_macro_files (macro_id);

CREATE UNIQUE INDEX IF NOT EXISTS shell_macro_files_macro_filename_unique
    ON shell_macro_files (macro_id, filename);
