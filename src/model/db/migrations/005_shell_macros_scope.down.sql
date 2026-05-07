DROP INDEX IF EXISTS shell_macros_node_name_unique;
DROP INDEX IF EXISTS shell_macros_global_name_unique;

ALTER TABLE shell_macros DROP CONSTRAINT IF EXISTS shell_macros_scope_type_check;

ALTER TABLE shell_macros
    DROP COLUMN IF EXISTS node_id,
    DROP COLUMN IF EXISTS scope_type;

ALTER TABLE shell_macros
    ADD CONSTRAINT shell_macros_name_key UNIQUE (name);
