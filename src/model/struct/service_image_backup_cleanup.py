import datetime
from pathlib import Path

import yaml
from psycopg.types.json import Jsonb


connect = wiz.model("db/postgres").connect
backup_system = wiz.model("struct/backup_system")
harbor = wiz.model("struct/images_harbor")
image_backups = wiz.model("struct/service_image_backups")
volume_backups = wiz.model("struct/service_volume_backups")
operations = wiz.model("struct/operations")
shared = wiz.model("struct/services_shared")
ServiceError = shared.ServiceError
_row = shared.row


def _ref_parts(ref):
    raw = str(ref or "").strip()
    parts = raw.split("/", 2)
    if len(parts) < 3 or ":" not in parts[2]:
        return None
    repository, tag = parts[2].rsplit(":", 1)
    return {"registry": parts[0], "project": parts[1], "repository": repository, "reference": tag}


def _images_from_compose(path):
    target = Path(str(path or "")).expanduser()
    if not target.is_file():
        return []
    try:
        compose = yaml.safe_load(target.read_text(encoding="utf-8")) or {}
    except Exception:
        return []
    return [str(item.get("image") or "").strip() for item in (compose.get("services") or {}).values() if item.get("image")]


class ServiceImageBackupCleanup:
    ServiceError = ServiceError

    def _current_refs(self, env=None):
        refs = set()
        with connect(env=env) as connection:
            with connection.cursor() as cursor:
                cursor.execute("SELECT compose_path FROM services")
                for row in cursor.fetchall():
                    refs.update(_images_from_compose(row["compose_path"]))
        return refs

    def _rows(self, env=None):
        image_backups.ensure_schema(env=env)
        with connect(env=env) as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT *
                    FROM service_image_backups
                    WHERE backup_status = 'backup_succeeded'
                      AND backup_ref IS NOT NULL
                    ORDER BY created_at DESC
                    """
                )
                return [_row(row) for row in cursor.fetchall()]

    def _volume_rows(self, env=None):
        volume_backups.ensure_schema(env=env)
        with connect(env=env) as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT *
                    FROM service_volume_backups
                    WHERE artifact_status = 'backup_succeeded'
                      AND artifact_ref IS NOT NULL
                    ORDER BY created_at DESC
                    """
                )
                return [_row(row) for row in cursor.fetchall()]

    def plan(self, payload=None, env=None):
        policy = backup_system.status(env=env).get("backup_policy") or {}
        keep = int((payload or {}).get("retention_keep_per_service") or policy.get("retention_keep_per_service") or 10)
        days = int((payload or {}).get("cleanup_unused_days") or policy.get("cleanup_unused_days") or 30)
        cutoff = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=days)
        current_refs = self._current_refs(env=env)
        grouped = {}
        candidates = []
        seen = set()
        for row in self._rows(env=env):
            key = ("image", row["service_id"], row["compose_service"])
            grouped.setdefault(key, []).append(row)
            reasons = []
            created = datetime.datetime.fromisoformat(str(row["created_at"]).replace("Z", "+00:00"))
            if len(grouped[key]) > keep:
                reasons.append("retention")
            if created < cutoff and row["backup_ref"] not in current_refs:
                reasons.append("unused_days")
            parts = _ref_parts(row["backup_ref"])
            if reasons and parts and row["id"] not in seen:
                seen.add(row["id"])
                candidates.append({**row, "backup_kind": "container_snapshot", "cleanup_reasons": reasons, "harbor": parts})
        for row in self._volume_rows(env=env):
            key = ("volume", row["service_id"], row["docker_volume"])
            grouped.setdefault(key, []).append(row)
            reasons = []
            if len(grouped[key]) > keep:
                reasons.append("retention")
            parts = _ref_parts(row["artifact_ref"])
            if reasons and parts and row["id"] not in seen:
                seen.add(row["id"])
                candidates.append({**row, "backup_kind": "named_volume_snapshot", "cleanup_reasons": reasons, "harbor": parts})
        total_size = sum(int((item.get("metadata") or {}).get("size") or 0) for item in candidates)
        return {"candidates": candidates[:200], "summary": {"count": len(candidates), "estimated_bytes": total_size, "keep": keep, "unused_days": days}}

    def cleanup(self, payload=None, env=None):
        plan = self.plan(payload, env=env)
        operation = operations.create(
            "service.image.backup.cleanup",
            target_type="backup_system",
            target_id="default",
            requested_payload={"summary": plan["summary"]},
            env=env,
        )
        deleted = []
        failures = []
        for item in plan["candidates"]:
            parts = item["harbor"]
            try:
                harbor.delete_tag(parts["project"], parts["repository"], parts["reference"], parts["reference"], env=env)
                deleted.append(item["id"])
                self._mark_deleted(item, operation["id"], env=env)
            except Exception as exc:
                failures.append({"id": item["id"], "message": str(exc)})
        status = "succeeded" if not failures else "failed"
        result = {"deleted_count": len(deleted), "failed_count": len(failures), "failures": failures}
        operation = operations.transition(operation["id"], status, result_payload=result, env=env)
        return {"summary": {**plan["summary"], **result}, "operation": operation}

    def _mark_deleted(self, item, operation_id, env=None):
        metadata = {
            "cleanup": {
                "operation_id": operation_id,
                "reasons": item.get("cleanup_reasons") or [],
                "deleted_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
            }
        }
        with connect(env=env) as connection:
            with connection.cursor() as cursor:
                if item.get("backup_kind") == "named_volume_snapshot":
                    cursor.execute(
                        """
                        UPDATE service_volume_backups
                        SET artifact_status = 'deleted',
                            metadata = metadata || %s::jsonb,
                            updated_at = now()
                        WHERE id = %s
                        """,
                        (Jsonb(metadata), item["id"]),
                    )
                else:
                    cursor.execute(
                        """
                        UPDATE service_image_backups
                        SET backup_status = 'deleted',
                            metadata = metadata || %s::jsonb,
                            updated_at = now()
                        WHERE id = %s
                        """,
                        (Jsonb(metadata), item["id"]),
                    )


Model = ServiceImageBackupCleanup()
