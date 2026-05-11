DO $$
BEGIN
    IF to_regclass('public.system_settings') IS NOT NULL THEN
        UPDATE system_settings current_setting
        SET key = 'setup.service_root'
        WHERE current_setting.key = 'setup.template_root'
          AND NOT EXISTS (
              SELECT 1
              FROM system_settings existing
              WHERE existing.key = 'setup.service_root'
          );

        DELETE FROM system_settings
        WHERE key = 'setup.template_root';
    END IF;

    IF to_regclass('public.services') IS NOT NULL AND to_regclass('public.templates') IS NOT NULL THEN
        UPDATE services service_row
        SET metadata = jsonb_set(
            COALESCE(service_row.metadata, '{}'::jsonb),
            '{legacy_template}',
            jsonb_build_object(
                'id', template_row.id,
                'name', template_row.name,
                'namespace', template_row.namespace,
                'description', template_row.description
            ),
            true
        )
        FROM templates template_row
        WHERE COALESCE(service_row.metadata, '{}'::jsonb) #>> '{source_ref,template_id}' = template_row.id::text
          AND NOT (COALESCE(service_row.metadata, '{}'::jsonb) ? 'legacy_template');
    END IF;
END $$;

DROP TABLE IF EXISTS template_versions CASCADE;
DROP TABLE IF EXISTS templates CASCADE;
