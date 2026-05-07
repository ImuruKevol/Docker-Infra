#!/usr/bin/env python3
import argparse
import importlib.util
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MIGRATION_MODEL = ROOT / "src" / "model" / "db" / "migration.py"

spec = importlib.util.spec_from_file_location("docker_infra_migration", MIGRATION_MODEL)
migration = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = migration
spec.loader.exec_module(migration)


def main():
    parser = argparse.ArgumentParser(description="Run Docker Infra PostgreSQL migrations.")
    subcommands = parser.add_subparsers(dest="command", required=True)
    subcommands.add_parser("up", help="Apply pending migrations")
    down = subcommands.add_parser("down", help="Rollback one migration")
    down.add_argument("--version", help="Migration version to roll back. Defaults to latest applied migration.")
    subcommands.add_parser("status", help="Show migration status")
    args = parser.parse_args()

    if args.command == "up":
        applied = migration.migrate_up()
        print(json.dumps({"applied": applied}, ensure_ascii=False))
        return 0
    if args.command == "down":
        rolled_back = migration.migrate_down(version=args.version)
        print(json.dumps({"rolled_back": rolled_back}, ensure_ascii=False))
        return 0
    if args.command == "status":
        rows = migration.status()
        print(json.dumps({"migrations": rows}, ensure_ascii=False, default=str))
        return 0
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
