import argparse
import shutil
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
TEST_RUNTIME_ROOT = ROOT / ".runtime" / "test"
DEFAULT_TEST_ROOTS = [
    TEST_RUNTIME_ROOT / "templates",
    TEST_RUNTIME_ROOT / "artifacts",
    TEST_RUNTIME_ROOT / "logs",
    TEST_RUNTIME_ROOT / "proxy" / "nginx",
    TEST_RUNTIME_ROOT / "proxy" / "apache2",
]


def _is_allowed(path):
    resolved = path.resolve()
    allowed = TEST_RUNTIME_ROOT.resolve()
    return resolved == allowed or allowed in resolved.parents


def cleanup_test_roots(paths=None, dry_run=False):
    roots = [Path(path) for path in (paths or DEFAULT_TEST_ROOTS)]
    removed = []
    skipped = []

    for root in roots:
        if not _is_allowed(root):
            skipped.append(str(root))
            continue
        if not root.exists():
            continue
        removed.append(str(root))
        if not dry_run:
            if root.is_dir():
                shutil.rmtree(root)
            else:
                root.unlink()

    return {"removed": removed, "skipped": skipped}


def main():
    parser = argparse.ArgumentParser(description="Reset Docker Infra project-local test runtime roots.")
    parser.add_argument("--dry-run", action="store_true", help="Report paths without deleting them.")
    args = parser.parse_args()
    result = cleanup_test_roots(dry_run=args.dry_run)
    print(f"removed={len(result['removed'])} skipped={len(result['skipped'])}")


if __name__ == "__main__":
    main()
