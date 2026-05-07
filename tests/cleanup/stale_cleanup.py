import argparse
import datetime
import json
import shutil
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
TEST_RUNTIME_ROOT = ROOT / ".runtime" / "test"
MARKER_NAME = ".docker-infra-test-resource.json"


def _parse_timestamp(value):
    if value.endswith("Z"):
        value = value[:-1] + "+00:00"
    parsed = datetime.datetime.fromisoformat(value)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=datetime.timezone.utc)
    return parsed


def _is_allowed(path):
    resolved = path.resolve()
    allowed = TEST_RUNTIME_ROOT.resolve()
    return resolved == allowed or allowed in resolved.parents


def write_resource_marker(path, test_run_id, namespace, created_at=None):
    path.mkdir(parents=True, exist_ok=True)
    created_at = created_at or datetime.datetime.now(datetime.timezone.utc)
    marker = {
        "test_run_id": test_run_id,
        "namespace": namespace,
        "created_at": created_at.isoformat().replace("+00:00", "Z"),
    }
    (path / MARKER_NAME).write_text(json.dumps(marker, ensure_ascii=False, indent=2), encoding="utf-8")
    return marker


def find_stale_resources(root=TEST_RUNTIME_ROOT, older_than_hours=24, now=None):
    root = Path(root)
    now = now or datetime.datetime.now(datetime.timezone.utc)
    threshold = now - datetime.timedelta(hours=older_than_hours)
    stale = []

    if not root.exists():
        return stale

    for marker_path in root.rglob(MARKER_NAME):
        resource_root = marker_path.parent
        if not _is_allowed(resource_root):
            continue
        try:
            marker = json.loads(marker_path.read_text(encoding="utf-8"))
            created_at = _parse_timestamp(marker["created_at"])
        except Exception as exc:
            stale.append({"path": resource_root, "reason": f"invalid marker: {exc}"})
            continue
        if created_at <= threshold:
            stale.append({"path": resource_root, "reason": f"created_at={marker['created_at']}"})
    return stale


def cleanup_stale_resources(root=TEST_RUNTIME_ROOT, older_than_hours=24, dry_run=False, now=None):
    removed = []
    for item in find_stale_resources(root=root, older_than_hours=older_than_hours, now=now):
        path = item["path"]
        if not _is_allowed(path):
            continue
        removed.append({"path": str(path), "reason": item["reason"]})
        if not dry_run:
            if path.is_dir():
                shutil.rmtree(path)
            elif path.exists():
                path.unlink()
    return removed


def main():
    parser = argparse.ArgumentParser(description="Remove stale Docker Infra project-local test resources.")
    parser.add_argument("--older-than-hours", type=int, default=24)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    removed = cleanup_stale_resources(older_than_hours=args.older_than_hours, dry_run=args.dry_run)
    print(f"stale_resources={len(removed)} dry_run={args.dry_run}")


if __name__ == "__main__":
    main()
