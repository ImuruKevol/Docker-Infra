from contextlib import contextmanager
from pathlib import Path
from types import SimpleNamespace

try:
    import psycopg
    from psycopg import sql
    from psycopg.rows import dict_row
except Exception:  # pragma: no cover - exercised only when dependency is absent
    psycopg = None
    sql = None
    dict_row = None


def _load_config():
    try:
        return wiz.config("docker_infra")
    except NameError:
        config_path = Path(__file__).resolve().parents[3] / "config" / "docker_infra.py"
        env = {"__file__": str(config_path), "__name__": "docker_infra_config"}
        exec(compile(config_path.read_text(encoding="utf-8"), str(config_path), "exec"), env)
        return SimpleNamespace(**{key: value for key, value in env.items() if not key.startswith("__")})


config = _load_config()


def database_url(env=None):
    return config.database_url(env)


def schema(env=None):
    return config.database_schema(env)


def require_driver():
    if psycopg is None:
        raise RuntimeError("psycopg is required for PostgreSQL access")


def has_database_config(env=None):
    return config.has_database_config(env)


@contextmanager
def connect(env=None):
    require_driver()
    url = database_url(env)
    if not url:
        raise RuntimeError("Docker Infra database config is not configured")

    db_schema = schema(env)
    with psycopg.connect(url, row_factory=dict_row) as connection:
        if db_schema != "public":
            with connection.cursor() as cursor:
                cursor.execute(sql.SQL("CREATE SCHEMA IF NOT EXISTS {}").format(sql.Identifier(db_schema)))
                cursor.execute(sql.SQL("SET search_path TO {}, public").format(sql.Identifier(db_schema)))
        yield connection


class Postgres:
    database_url = staticmethod(database_url)
    schema = staticmethod(schema)
    require_driver = staticmethod(require_driver)
    has_database_config = staticmethod(has_database_config)
    connect = staticmethod(connect)


Model = Postgres()
