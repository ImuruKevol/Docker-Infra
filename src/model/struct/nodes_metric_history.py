import csv
import datetime
from pathlib import Path


config = wiz.config("docker_infra")

HEADER = [
    "reported_at",
    "node_id",
    "cpu_percent",
    "memory_used_percent",
    "memory_used_bytes",
    "memory_total_bytes",
    "storage_used_percent",
    "storage_used_bytes",
    "storage_total_bytes",
    "containers_total",
    "containers_running",
    "containers_stopped",
    "source",
]


class MetricHistoryError(Exception):
    def __init__(self, status_code, message, error_code, **extra):
        super().__init__(message)
        self.status_code = status_code
        self.message = message
        self.error_code = error_code
        self.extra = extra


def _as_float(value, fallback=0.0):
    try:
        if value is None:
            return fallback
        return float(value)
    except Exception:
        return fallback


def _as_int(value, fallback=0):
    try:
        if value is None:
            return fallback
        return int(float(value))
    except Exception:
        return fallback


def _iso(value=None):
    if value is None:
        return datetime.datetime.now(datetime.timezone.utc).isoformat().replace("+00:00", "Z")
    if isinstance(value, datetime.datetime):
        return value.isoformat().replace("+00:00", "Z")
    return str(value)


def _date_key(value=None):
    if isinstance(value, datetime.datetime):
        return value.date().isoformat()
    raw = str(value or "")
    return raw[:10] if len(raw) >= 10 else datetime.date.today().isoformat()


def _parse_date(value, default=None, field="date"):
    if value in (None, ""):
        if default is not None:
            return default
        return datetime.date.today()
    if isinstance(value, datetime.datetime):
        return value.date()
    if isinstance(value, datetime.date):
        return value
    raw = str(value).strip()
    try:
        return datetime.date.fromisoformat(raw[:10])
    except Exception:
        raise MetricHistoryError(400, f"{field} 형식은 YYYY-MM-DD여야 합니다.", "INVALID_METRIC_HISTORY_DATE", field=field)


def _date_range(start_date, end_date):
    _validate_date_range(start_date, end_date)
    current = start_date
    while current <= end_date:
        yield current
        current = current + datetime.timedelta(days=1)


def _validate_date_range(start_date, end_date):
    if start_date > end_date:
        raise MetricHistoryError(400, "조회 시작일은 종료일보다 늦을 수 없습니다.", "INVALID_METRIC_HISTORY_DATE_RANGE")
    if (end_date - start_date).days > 366:
        raise MetricHistoryError(400, "한 번에 조회할 수 있는 기간은 최대 366일입니다.", "METRIC_HISTORY_RANGE_TOO_LARGE")


def _limit_value(value, default=1440, maximum=10000):
    try:
        limit = int(value)
    except Exception:
        limit = default
    return max(1, min(limit, maximum))


def _parse_reported_at(value):
    raw = str(value or "").strip()
    if not raw:
        return None
    normalized = raw.replace("Z", "+00:00")
    try:
        parsed = datetime.datetime.fromisoformat(normalized)
    except Exception:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=datetime.timezone.utc)
    return parsed.astimezone(datetime.timezone.utc)


def _parse_datetime(value, field="datetime"):
    if value in (None, ""):
        return None
    if isinstance(value, datetime.datetime):
        parsed = value
    else:
        raw = str(value).strip()
        try:
            parsed = datetime.datetime.fromisoformat(raw.replace("Z", "+00:00"))
        except Exception:
            raise MetricHistoryError(400, f"{field} 형식이 올바르지 않습니다.", "INVALID_METRIC_HISTORY_DATETIME", field=field)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=datetime.timezone.utc)
    return parsed.astimezone(datetime.timezone.utc)


def _range_bounds(start_date=None, end_date=None, start_at=None, end_at=None):
    start_dt = _parse_datetime(start_at, field="start_at")
    end_dt = _parse_datetime(end_at, field="end_at")
    if start_dt or end_dt:
        if start_dt is None:
            start_dt = _parse_datetime(f"{_parse_date(start_date, field='start_date').isoformat()}T00:00:00+00:00", field="start_at")
        if end_dt is None:
            end_dt = _parse_datetime(f"{_parse_date(end_date, default=start_dt.date(), field='end_date').isoformat()}T23:59:59.999999+00:00", field="end_at")
        if start_dt > end_dt:
            raise MetricHistoryError(400, "조회 시작 시각은 종료 시각보다 늦을 수 없습니다.", "INVALID_METRIC_HISTORY_DATE_RANGE")
        start = start_dt.date()
        end = end_dt.date()
        _validate_date_range(start, end)
        return start, end, start_dt, end_dt
    end = _parse_date(end_date, field="end_date")
    start = _parse_date(start_date, default=end, field="start_date")
    _validate_date_range(start, end)
    return start, end, None, None


def _bucket_time(value, minutes=5):
    parsed = _parse_reported_at(value)
    if parsed is None:
        return str(value or "")
    minute = parsed.minute - (parsed.minute % minutes)
    bucket = parsed.replace(minute=minute, second=0, microsecond=0)
    return bucket.isoformat().replace("+00:00", "Z")


def _container_summary(containers):
    if isinstance(containers, dict):
        summary = containers.get("summary") or {}
        if summary:
            return {
                "total": _as_int(summary.get("total")),
                "running": _as_int(summary.get("running")),
                "stopped": _as_int(summary.get("stopped")),
            }
        items = containers.get("items") or []
    elif isinstance(containers, list):
        items = containers
    else:
        items = []
    running = len([item for item in items if str(item.get("state") or "").lower() == "running"])
    return {"total": len(items), "running": running, "stopped": max(0, len(items) - running)}


class NodesMetricHistory:
    MetricHistoryError = MetricHistoryError

    def root(self, env=None):
        return Path(config.data_dir(env)) / "node-metrics"

    def path_for(self, node_id, reported_at=None, env=None):
        date_key = _date_key(reported_at)
        safe_node_id = str(node_id or "unknown").replace("/", "_")
        return self.root(env=env) / date_key / f"{safe_node_id}.csv"

    def append(self, node_id, metric, source=None, env=None):
        metric = metric or {}
        reported_at = metric.get("reported_at") or metric.get("created_at")
        memory = metric.get("memory") or {}
        storage = metric.get("storage") or {}
        containers = metric.get("containers") or {}
        summary = _container_summary(containers)
        metadata = metric.get("metadata") or {}
        path = self.path_for(node_id, reported_at=reported_at, env=env)
        path.parent.mkdir(parents=True, exist_ok=True)
        write_header = not path.exists() or path.stat().st_size == 0
        row = {
            "reported_at": _iso(reported_at),
            "node_id": str(node_id or ""),
            "cpu_percent": _as_float(metric.get("cpu_percent")),
            "memory_used_percent": _as_float(memory.get("used_percent")),
            "memory_used_bytes": _as_int(memory.get("used")),
            "memory_total_bytes": _as_int(memory.get("total")),
            "storage_used_percent": _as_float(storage.get("used_percent")),
            "storage_used_bytes": _as_int(storage.get("used")),
            "storage_total_bytes": _as_int(storage.get("total")),
            "containers_total": summary["total"],
            "containers_running": summary["running"],
            "containers_stopped": summary["stopped"],
            "source": source or metadata.get("source") or "",
        }
        with path.open("a", newline="", encoding="utf-8") as stream:
            writer = csv.DictWriter(stream, fieldnames=HEADER)
            if write_header:
                writer.writeheader()
            writer.writerow(row)
        return {"path": str(path), "row": row}

    def append_db_row(self, row, source=None, env=None):
        if row is None:
            return None
        metric = {
            "cpu_percent": row.get("cpu_percent"),
            "memory": row.get("memory") or {},
            "storage": row.get("storage") or {},
            "containers": row.get("containers") or {},
            "reported_at": row.get("reported_at"),
            "metadata": row.get("metadata") or {},
            "created_at": row.get("created_at"),
        }
        return self.append(row.get("node_id"), metric, source=source, env=env)

    def _files_for_dates(self, start_date, end_date, node_id=None, env=None):
        root = self.root(env=env)
        if not root.exists():
            return []
        files = []
        safe_node_id = str(node_id or "").replace("/", "_")
        for date_item in _date_range(start_date, end_date):
            date_dir = root / date_item.isoformat()
            if not date_dir.exists():
                continue
            if safe_node_id:
                path = date_dir / f"{safe_node_id}.csv"
                if path.exists():
                    files.append(path)
            else:
                files.extend(sorted(date_dir.glob("*.csv")))
        return sorted(files)

    def _row_date(self, row, path=None):
        raw = str((row or {}).get("reported_at") or "")
        if len(raw) >= 10:
            return raw[:10]
        if path is not None:
            return Path(path).parent.name
        return datetime.date.today().isoformat()

    def _normalize_row(self, row):
        return {
            "reported_at": row.get("reported_at") or "",
            "node_id": row.get("node_id") or "",
            "cpu_percent": _as_float(row.get("cpu_percent")),
            "memory_used_percent": _as_float(row.get("memory_used_percent")),
            "memory_used_bytes": _as_int(row.get("memory_used_bytes")),
            "memory_total_bytes": _as_int(row.get("memory_total_bytes")),
            "storage_used_percent": _as_float(row.get("storage_used_percent")),
            "storage_used_bytes": _as_int(row.get("storage_used_bytes")),
            "storage_total_bytes": _as_int(row.get("storage_total_bytes")),
            "containers_total": _as_int(row.get("containers_total")),
            "containers_running": _as_int(row.get("containers_running")),
            "containers_stopped": _as_int(row.get("containers_stopped")),
            "source": row.get("source") or "",
        }

    def _read_rows(self, path):
        if not path.exists() or path.stat().st_size == 0:
            return []
        with path.open("r", newline="", encoding="utf-8") as stream:
            reader = csv.DictReader(stream)
            return [dict(row) for row in reader if row]

    def _write_rows(self, path, rows):
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", newline="", encoding="utf-8") as stream:
            writer = csv.DictWriter(stream, fieldnames=HEADER)
            writer.writeheader()
            for row in rows:
                writer.writerow({key: row.get(key, "") for key in HEADER})

    def _summary(self, rows):
        if not rows:
            return {}
        latest = rows[-1]
        return {
            "latest": latest,
            "count": len(rows),
            "avg_cpu_percent": round(sum(_as_float(row.get("cpu_percent")) for row in rows) / len(rows), 2),
            "avg_memory_used_percent": round(sum(_as_float(row.get("memory_used_percent")) for row in rows) / len(rows), 2),
            "avg_storage_used_percent": round(sum(_as_float(row.get("storage_used_percent")) for row in rows) / len(rows), 2),
        }

    def query(self, node_id=None, start_date=None, end_date=None, start_at=None, end_at=None, limit=1440, env=None):
        start, end, start_dt, end_dt = _range_bounds(start_date=start_date, end_date=end_date, start_at=start_at, end_at=end_at)
        row_limit = _limit_value(limit)
        rows = []
        for path in self._files_for_dates(start, end, node_id=node_id, env=env):
            for row in self._read_rows(path):
                if node_id and str(row.get("node_id") or "") != str(node_id):
                    continue
                include = False
                if start_dt and end_dt:
                    row_dt = _parse_reported_at(row.get("reported_at"))
                    include = row_dt is not None and start_dt <= row_dt <= end_dt
                else:
                    row_date = self._row_date(row, path)
                    include = start.isoformat() <= row_date <= end.isoformat()
                if include:
                    rows.append(self._normalize_row(row))
        rows.sort(key=lambda row: row.get("reported_at") or "")
        if len(rows) > row_limit:
            rows = rows[-row_limit:]
        return {
            "root": str(self.root(env=env)),
            "node_id": node_id or None,
            "start_date": start.isoformat(),
            "end_date": end.isoformat(),
            "start_at": start_dt.isoformat().replace("+00:00", "Z") if start_dt else None,
            "end_at": end_dt.isoformat().replace("+00:00", "Z") if end_dt else None,
            "count": len(rows),
            "rows": rows,
            "summary": self._summary(rows),
        }

    def dashboard_chart(self, start_date=None, end_date=None, limit=288, env=None):
        start_at = None
        end_at = None
        if not start_date and not end_date:
            end_at = datetime.datetime.now(datetime.timezone.utc)
            start_at = end_at - datetime.timedelta(hours=24)
        data = self.query(node_id=None, start_date=start_date, end_date=end_date, start_at=start_at, end_at=end_at, limit=10000, env=env)
        buckets = {}
        for row in data.get("rows") or []:
            key = _bucket_time(row.get("reported_at"))
            if not key:
                continue
            bucket = buckets.setdefault(key, {"reported_at": key, "nodes": set(), "count": 0, "cpu": 0.0, "memory": 0.0, "storage": 0.0, "containers_total": 0.0, "containers_running": 0.0})
            bucket["nodes"].add(row.get("node_id"))
            bucket["count"] += 1
            bucket["cpu"] += _as_float(row.get("cpu_percent"))
            bucket["memory"] += _as_float(row.get("memory_used_percent"))
            bucket["storage"] += _as_float(row.get("storage_used_percent"))
            bucket["containers_total"] += _as_float(row.get("containers_total"))
            bucket["containers_running"] += _as_float(row.get("containers_running"))

        rows = []
        for key in sorted(buckets):
            bucket = buckets[key]
            count = max(1, bucket["count"])
            rows.append({
                "reported_at": bucket["reported_at"],
                "node_count": len([node for node in bucket["nodes"] if node]),
                "sample_count": bucket["count"],
                "cpu_percent": round(bucket["cpu"] / count, 2),
                "memory_used_percent": round(bucket["memory"] / count, 2),
                "storage_used_percent": round(bucket["storage"] / count, 2),
                "containers_total": round(bucket["containers_total"] / count, 2),
                "containers_running": round(bucket["containers_running"] / count, 2),
            })
        row_limit = _limit_value(limit, default=288, maximum=10000)
        if len(rows) > row_limit:
            rows = rows[-row_limit:]
        return {
            **{key: data.get(key) for key in ["root", "start_date", "end_date"]},
            "node_id": None,
            "count": len(rows),
            "rows": rows,
            "summary": self._summary(rows),
            "source_count": data.get("count", 0),
        }

    def delete_range(self, node_id=None, start_date=None, end_date=None, start_at=None, end_at=None, env=None):
        if (not start_date or not end_date) and (not start_at or not end_at):
            raise MetricHistoryError(400, "삭제할 시작일과 종료일이 필요합니다.", "METRIC_HISTORY_DELETE_RANGE_REQUIRED")
        start, end, start_dt, end_dt = _range_bounds(start_date=start_date, end_date=end_date, start_at=start_at, end_at=end_at)
        files_removed = 0
        files_rewritten = 0
        rows_removed = 0
        for path in self._files_for_dates(start, end, node_id=node_id, env=env):
            rows = self._read_rows(path)
            kept = []
            removed = []
            for row in rows:
                matches_node = not node_id or str(row.get("node_id") or "") == str(node_id)
                if start_dt and end_dt:
                    row_dt = _parse_reported_at(row.get("reported_at"))
                    matches_range = row_dt is not None and start_dt <= row_dt <= end_dt
                else:
                    row_date = self._row_date(row, path)
                    matches_range = start.isoformat() <= row_date <= end.isoformat()
                if matches_node and matches_range:
                    removed.append(row)
                else:
                    kept.append(row)
            if not removed:
                continue
            rows_removed += len(removed)
            if kept:
                self._write_rows(path, kept)
                files_rewritten += 1
            else:
                path.unlink(missing_ok=True)
                files_removed += 1
                try:
                    path.parent.rmdir()
                except OSError:
                    pass
        return {
            "node_id": node_id or None,
            "start_date": start.isoformat(),
            "end_date": end.isoformat(),
            "start_at": start_dt.isoformat().replace("+00:00", "Z") if start_dt else None,
            "end_at": end_dt.isoformat().replace("+00:00", "Z") if end_dt else None,
            "rows_removed": rows_removed,
            "files_removed": files_removed,
            "files_rewritten": files_rewritten,
        }

    def dashboard_summary(self, env=None):
        root = self.root(env=env)
        if not root.exists():
            return {"root": str(root), "files": 0, "latest_file": None}
        files = sorted(root.glob("*/*.csv"), key=lambda item: item.stat().st_mtime, reverse=True)
        return {
            "root": str(root),
            "files": len(files),
            "latest_file": str(files[0]) if files else None,
        }


Model = NodesMetricHistory()
