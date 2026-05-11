DO $$
BEGIN
    IF to_regclass('public.templates') IS NULL OR to_regclass('public.template_versions') IS NULL THEN
        RETURN;
    END IF;

    DELETE FROM template_versions
    WHERE template_id IN (
        SELECT id
        FROM templates
        WHERE namespace IN ('gitlab_ce', 'harbor_registry')
    );

    DELETE FROM templates
    WHERE namespace IN ('gitlab_ce', 'harbor_registry');
END $$;
