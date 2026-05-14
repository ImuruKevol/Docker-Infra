CREATE INDEX IF NOT EXISTS services_created_idx
ON services(created_at DESC);

CREATE INDEX IF NOT EXISTS service_domains_service_created_idx
ON service_domains(service_id, created_at ASC);

CREATE INDEX IF NOT EXISTS service_domains_service_domain_idx
ON service_domains(service_id, domain ASC);

CREATE INDEX IF NOT EXISTS compose_versions_service_version_created_idx
ON compose_versions(service_id, version DESC, created_at DESC);

CREATE INDEX IF NOT EXISTS operation_logs_requested_service_id_idx
ON operation_logs((requested_payload->>'service_id'), created_at DESC);

CREATE INDEX IF NOT EXISTS operation_logs_metadata_service_id_idx
ON operation_logs((metadata->>'service_id'), created_at DESC);

CREATE INDEX IF NOT EXISTS operation_logs_requested_namespace_idx
ON operation_logs((requested_payload->>'namespace'), created_at DESC);

CREATE INDEX IF NOT EXISTS operation_logs_metadata_namespace_idx
ON operation_logs((metadata->>'namespace'), created_at DESC);
