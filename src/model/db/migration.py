import hashlib
from dataclasses import dataclass
from pathlib import Path

try:
    connect = wiz.model("db/postgres").connect
except NameError:  # Direct CLI script execution.
    import importlib.util

    postgres_path = Path(__file__).resolve().with_name("postgres.py")
    spec = importlib.util.spec_from_file_location("docker_infra_postgres", postgres_path)
    postgres = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(postgres)
    connect = postgres.connect


MIGRATION_DIR = Path(__file__).resolve().parent / "migrations"


@dataclass(frozen=True)
class Migration:
    version: str
    name: str
    path: Path
    down_path: Path
    checksum: str


def _checksum(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def list_migrations():
    migrations = []
    for path in sorted(MIGRATION_DIR.glob("*.sql")):
        if path.name.endswith(".down.sql"):
            continue
        version, _, name = path.stem.partition("_")
        sql_text = path.read_text(encoding="utf-8")
        migrations.append(
            Migration(
                version=version,
                name=name or path.stem,
                path=path,
                down_path=path.with_name(f"{path.stem}.down.sql"),
                checksum=_checksum(sql_text),
            )
        )
    return migrations


def ensure_migration_table(connection):
    with connection.cursor() as cursor:
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS schema_migrations (
                version TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                checksum TEXT NOT NULL,
                applied_at TIMESTAMPTZ NOT NULL DEFAULT now()
            )
            """
        )


def applied_migrations(connection):
    ensure_migration_table(connection)
    with connection.cursor() as cursor:
        cursor.execute("SELECT version, name, checksum, applied_at FROM schema_migrations ORDER BY version")
        return {row["version"]: row for row in cursor.fetchall()}


def status(env=None):
    with connect(env=env) as connection:
        applied = applied_migrations(connection)
        rows = []
        for migration in list_migrations():
            applied_row = applied.get(migration.version)
            rows.append(
                {
                    "version": migration.version,
                    "name": migration.name,
                    "checksum": migration.checksum,
                    "applied": applied_row is not None,
                    "applied_at": None if applied_row is None else applied_row["applied_at"],
                    "checksum_matches": applied_row is None or applied_row["checksum"] == migration.checksum,
                }
            )
        return rows


def current_schema_version(env=None):
    with connect(env=env) as connection:
        ensure_migration_table(connection)
        with connection.cursor() as cursor:
            cursor.execute("SELECT version FROM schema_migrations ORDER BY version DESC LIMIT 1")
            row = cursor.fetchone()
            return None if row is None else row["version"]


def migrate_up(env=None):
    applied_versions = []
    with connect(env=env) as connection:
        ensure_migration_table(connection)
        applied = applied_migrations(connection)
        for migration in list_migrations():
            applied_row = applied.get(migration.version)
            if applied_row is not None:
                if applied_row["checksum"] != migration.checksum:
                    raise RuntimeError(f"Migration checksum changed after apply: {migration.version}")
                continue

            sql_text = migration.path.read_text(encoding="utf-8")
            with connection.cursor() as cursor:
                cursor.execute(sql_text)
                cursor.execute(
                    """
                    INSERT INTO schema_migrations(version, name, checksum)
                    VALUES (%s, %s, %s)
                    ON CONFLICT (version) DO NOTHING
                    """,
                    (migration.version, migration.name, migration.checksum),
                )
            applied_versions.append(migration.version)
    return applied_versions


def migrate_down(version=None, env=None):
    with connect(env=env) as connection:
        applied = applied_migrations(connection)
        if not applied:
            return []

        selected = version or sorted(applied)[-1]
        migrations = {migration.version: migration for migration in list_migrations()}
        if selected not in applied:
            raise RuntimeError(f"Migration is not applied: {selected}")
        if selected not in migrations:
            raise RuntimeError(f"Migration file is missing: {selected}")

        migration = migrations[selected]
        if not migration.down_path.is_file():
            raise RuntimeError(f"Down migration is missing: {migration.down_path.name}")

        with connection.cursor() as cursor:
            cursor.execute("DELETE FROM schema_migrations WHERE version = %s", (selected,))
            cursor.execute(migration.down_path.read_text(encoding="utf-8"))
        return [selected]


class MigrationRepository:
    list = staticmethod(list_migrations)
    ensure_table = staticmethod(ensure_migration_table)
    applied = staticmethod(applied_migrations)
    status = staticmethod(status)
    current_schema_version = staticmethod(current_schema_version)
    migrate_up = staticmethod(migrate_up)
    migrate_down = staticmethod(migrate_down)


Model = MigrationRepository()
