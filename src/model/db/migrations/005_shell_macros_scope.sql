ALTER TABLE shell_macros DROP CONSTRAINT IF EXISTS shell_macros_name_key;

ALTER TABLE shell_macros
    ADD COLUMN IF NOT EXISTS scope_type TEXT NOT NULL DEFAULT 'global',
    ADD COLUMN IF NOT EXISTS node_id UUID REFERENCES nodes(id) ON DELETE CASCADE;

UPDATE shell_macros
SET scope_type = 'global'
WHERE scope_type IS NULL OR scope_type = '';

ALTER TABLE shell_macros DROP CONSTRAINT IF EXISTS shell_macros_scope_type_check;
ALTER TABLE shell_macros
    ADD CONSTRAINT shell_macros_scope_type_check CHECK (scope_type IN ('global', 'node'));

CREATE UNIQUE INDEX IF NOT EXISTS shell_macros_global_name_unique
    ON shell_macros (lower(name))
    WHERE scope_type = 'global' AND node_id IS NULL;

CREATE UNIQUE INDEX IF NOT EXISTS shell_macros_node_name_unique
    ON shell_macros (node_id, lower(name))
    WHERE scope_type = 'node';
