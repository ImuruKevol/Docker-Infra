ALTER TABLE node_credentials
ADD COLUMN IF NOT EXISTS key_file TEXT;

UPDATE node_credentials
SET key_file = metadata->>'key_file'
WHERE key_file IS NULL
  AND metadata ? 'key_file';
