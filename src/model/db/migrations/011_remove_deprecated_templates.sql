DELETE FROM template_versions
WHERE template_id IN (
    SELECT id
    FROM templates
    WHERE namespace IN ('gitlab_ce', 'harbor_registry')
);

DELETE FROM templates
WHERE namespace IN ('gitlab_ce', 'harbor_registry');
