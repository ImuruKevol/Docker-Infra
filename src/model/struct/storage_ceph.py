from datetime import date, datetime


def _connect(env=None):
    return wiz.model("db/postgres").connect(env=env)


def _json_safe(value):
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    return value


def _row(row):
    if row is None:
        return None
    data = {}
    for key, value in dict(row).items():
        if value is not None and (key == "id" or key.endswith("_id")):
            data[key] = str(value)
        else:
            data[key] = _json_safe(value)
    return data


class StorageCeph:
    def connect(self, env=None):
        return _connect(env=env)

    def rows(self, rows):
        return [_row(row) for row in rows or []]

    def row(self, row):
        return _row(row)

    def fetchall(self, query, params=None, env=None):
        with _connect(env=env) as connection:
            with connection.cursor() as cursor:
                cursor.execute(query, params or ())
                return self.rows(cursor.fetchall())

    def fetchone(self, query, params=None, env=None):
        with _connect(env=env) as connection:
            with connection.cursor() as cursor:
                cursor.execute(query, params or ())
                return self.row(cursor.fetchone())

    def tables_ready(self, table_names, env=None):
        missing = []
        with _connect(env=env) as connection:
            with connection.cursor() as cursor:
                for table_name in table_names:
                    cursor.execute("SELECT to_regclass(%s) AS relation_name", (table_name,))
                    if cursor.fetchone()["relation_name"] is None:
                        missing.append(table_name)
        return {"ready": not missing, "missing": missing}


Model = StorageCeph()
