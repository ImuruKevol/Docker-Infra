import csv
import datetime
from pathlib import Path


config = wiz.config("docker_infra")

RESOURCE_CHART_BUCKET_MINUTES = 10
RESOURCE_METRIC_KEYS = ("cpu_percent", "memory_used_percent", "storage_used_percent")
MEMORY_STACK_KEYS = ("memory_used_percent", "memory_cache_percent", "memory_free_percent")
MEMORY_COMPONENT_STAT_KEYS = ("memory_cache_percent", "memory_free_percent")
RESOURCE_STAT_NAMES = ("min", "max", "last", "avg")
RESOURCE_STAT_FIELDS = [f"{metric}_{stat}" for metric in RESOURCE_METRIC_KEYS for stat in RESOURCE_STAT_NAMES]
MEMORY_COMPONENT_STAT_FIELDS = [f"{metric}_{stat}" for metric in MEMORY_COMPONENT_STAT_KEYS for stat in RESOURCE_STAT_NAMES]

HEADER = [
    "reported_at",
    "node_id",
    "cpu_percent",
    "memory_used_percent",
    "memory_used_bytes",
    "memory_cache_percent",
    "memory_cache_bytes",
    "memory_free_percent",
    "memory_free_bytes",
    "memory_total_bytes",
    "storage_used_percent",
    "storage_used_bytes",
    "storage_total_bytes",
    "containers_total",
    "containers_running",
    "containers_stopped",
    *RESOURCE_STAT_FIELDS,
    *MEMORY_COMPONENT_STAT_FIELDS,
    "sample_count",
    "source",
]

DEDUPLICATE_WINDOW_SECONDS = 10


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


def _percent(value, fallback=0.0):
    return max(0.0, min(100.0, _as_float(value, fallback)))


def _stat_payload(metadata, metric_key):
    if not isinstance(metadata, dict):
        return {}
    window = metadata.get("resource_window") or metadata.get("resource_stats") or {}
    if not isinstance(window, dict):
        return {}
    payload = window.get(metric_key) or {}
    return payload if isinstance(payload, dict) else {}


def _metric_stats(value, direct=None, nested=None, metadata=None, metric_key=None, nested_prefix="used_percent"):
    fallback = _percent(value)
    direct = direct if isinstance(direct, dict) else {}
    nested = nested if isinstance(nested, dict) else {}
    payload = _stat_payload(metadata, metric_key) if metric_key else {}
    stats = {}
    for stat in RESOURCE_STAT_NAMES:
        candidates = [
            direct.get(f"{metric_key}_{stat}") if metric_key else None,
            direct.get(stat),
            nested.get(f"{nested_prefix}_{stat}"),
            payload.get(stat),
        ]
        raw = next((item for item in candidates if item not in (None, "")), None)
        if raw is None:
            raw = fallback
        stats[stat] = _percent(raw, fallback)
    if stats["min"] > stats["max"]:
        stats["min"], stats["max"] = stats["max"], stats["min"]
    stats["last"] = max(stats["min"], min(stats["max"], stats["last"]))
    stats["avg"] = max(stats["min"], min(stats["max"], stats["avg"]))
    return stats


def _stats_fields(metric_key, stats):
    return {f"{metric_key}_{stat}": round(_percent(stats.get(stat)), 2) for stat in RESOURCE_STAT_NAMES}


def _row_metric_stats(row, metric_key):
    return _metric_stats(
        row.get(metric_key),
        direct=row,
        metadata=row.get("metadata") or {},
        metric_key=metric_key,
    )


def _sample_count(row):
    row = row if isinstance(row, dict) else {}
    if row.get("sample_count") not in (None, ""):
        return max(1, _as_int(row.get("sample_count"), 1))
    metadata = row.get("metadata") or {}
    if isinstance(metadata, dict) and metadata.get("sample_count") not in (None, ""):
        return max(1, _as_int(metadata.get("sample_count"), 1))
    window = row.get("resource_window") or row.get("resource_stats") or {}
    if isinstance(window, dict) and window.get("sample_count") not in (None, ""):
        return max(1, _as_int(window.get("sample_count"), 1))
    if isinstance(metadata, dict):
        window = metadata.get("resource_window") or metadata.get("resource_stats") or {}
        if isinstance(window, dict) and window.get("sample_count") not in (None, ""):
            return max(1, _as_int(window.get("sample_count"), 1))
    return 1


def _memory_percent(memory, key, byte_key=None):
    memory = memory if isinstance(memory, dict) else {}
    if memory.get(key) not in (None, ""):
        return _percent(memory.get(key))
    total = _as_float(memory.get("total"))
    raw_bytes = _as_float(memory.get(byte_key or key.replace("_percent", "")))
    if total <= 0:
        return 0.0
    return _percent(raw_bytes * 100.0 / total)


def _iso(value=None):
    if value is None:
        return datetime.datetime.now(datetime.timezone.utc).isoformat().replace("+00:00", "Z")
    if isinstance(value, datetime.datetime):
        parsed = value
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=datetime.timezone.utc)
        return parsed.astimezone(datetime.timezone.utc).isoformat().replace("+00:00", "Z")
    if isinstance(value, str):
        parsed = _parse_reported_at(value)
        if parsed is not None:
            return parsed.isoformat().replace("+00:00", "Z")
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


def _reported_delta_seconds(left, right):
    left_dt = _parse_reported_at(left)
    right_dt = _parse_reported_at(right)
    if left_dt is None or right_dt is None:
        return None
    return abs((left_dt - right_dt).total_seconds())


def _deduplicate_metric_rows(rows, window_seconds=DEDUPLICATE_WINDOW_SECONDS):
    deduplicated = []
    for row in sorted(rows or [], key=lambda item: item.get("reported_at") or ""):
        replacement_index = None
        replacement_delta = None
        for index, existing in enumerate(deduplicated):
            if str(existing.get("node_id") or "") != str(row.get("node_id") or ""):
                continue
            delta = _reported_delta_seconds(existing.get("reported_at"), row.get("reported_at"))
            if delta is None or delta > window_seconds:
                continue
            if replacement_delta is None or delta < replacement_delta:
                replacement_index = index
                replacement_delta = delta
        if replacement_index is None:
            deduplicated.append(row)
        else:
            deduplicated[replacement_index] = row
    return sorted(deduplicated, key=lambda item: item.get("reported_at") or "")


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


def _bucket_time(value, minutes=RESOURCE_CHART_BUCKET_MINUTES):
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
        if not isinstance(metadata, dict):
            metadata = {}
        cpu_stats = _metric_stats(metric.get("cpu_percent"), direct=metric, metadata=metadata, metric_key="cpu_percent")
        memory_stats = _metric_stats(memory.get("used_percent"), nested=memory, metadata=metadata, metric_key="memory_used_percent")
        memory_cache_stats = _metric_stats(
            _memory_percent(memory, "cache_percent", byte_key="cache"),
            nested=memory,
            metadata=metadata,
            metric_key="memory_cache_percent",
            nested_prefix="cache_percent",
        )
        memory_free_stats = _metric_stats(
            _memory_percent(memory, "free_percent", byte_key="free"),
            nested=memory,
            metadata=metadata,
            metric_key="memory_free_percent",
            nested_prefix="free_percent",
        )
        storage_stats = _metric_stats(storage.get("used_percent"), nested=storage, metadata=metadata, metric_key="storage_used_percent")
        path = self.path_for(node_id, reported_at=reported_at, env=env)
        path.parent.mkdir(parents=True, exist_ok=True)
        row = {
            "reported_at": _iso(reported_at),
            "node_id": str(node_id or ""),
            "cpu_percent": cpu_stats["last"],
            "memory_used_percent": memory_stats["last"],
            "memory_used_bytes": _as_int(memory.get("used")),
            "memory_cache_percent": memory_cache_stats["last"],
            "memory_cache_bytes": _as_int(memory.get("cache")),
            "memory_free_percent": memory_free_stats["last"],
            "memory_free_bytes": _as_int(memory.get("free")),
            "memory_total_bytes": _as_int(memory.get("total")),
            "storage_used_percent": storage_stats["last"],
            "storage_used_bytes": _as_int(storage.get("used")),
            "storage_total_bytes": _as_int(storage.get("total")),
            "containers_total": summary["total"],
            "containers_running": summary["running"],
            "containers_stopped": summary["stopped"],
            **_stats_fields("cpu_percent", cpu_stats),
            **_stats_fields("memory_used_percent", memory_stats),
            **_stats_fields("storage_used_percent", storage_stats),
            **_stats_fields("memory_cache_percent", memory_cache_stats),
            **_stats_fields("memory_free_percent", memory_free_stats),
            "sample_count": _sample_count(metadata),
            "source": source or metadata.get("source") or "",
        }
        existing_rows = self._read_rows(path)
        replacement_index = None
        replacement_delta = None
        for index, existing in enumerate(existing_rows):
            if str(existing.get("node_id") or "") != row["node_id"]:
                continue
            delta = _reported_delta_seconds(existing.get("reported_at"), row.get("reported_at"))
            if delta is None or delta > DEDUPLICATE_WINDOW_SECONDS:
                continue
            if replacement_delta is None or delta < replacement_delta:
                replacement_index = index
                replacement_delta = delta
        if replacement_index is not None:
            existing_rows[replacement_index] = {**existing_rows[replacement_index], **row}
            existing_rows.sort(key=lambda item: item.get("reported_at") or "")
            self._write_rows(path, existing_rows)
            return {"path": str(path), "row": row, "deduplicated": True}

        existing_rows.append(row)
        existing_rows.sort(key=lambda item: item.get("reported_at") or "")
        self._write_rows(path, existing_rows)
        return {"path": str(path), "row": row, "deduplicated": False}

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
        row = row or {}
        cpu_stats = _row_metric_stats(row, "cpu_percent")
        memory_stats = _row_metric_stats(row, "memory_used_percent")
        memory_cache_stats = _row_metric_stats(row, "memory_cache_percent")
        memory_free_value = row.get("memory_free_percent")
        if memory_free_value in (None, ""):
            memory_free_value = max(0.0, 100.0 - memory_stats["last"] - memory_cache_stats["last"])
        memory_free_stats = _metric_stats(memory_free_value, direct=row, metadata=row.get("metadata") or {}, metric_key="memory_free_percent")
        storage_stats = _row_metric_stats(row, "storage_used_percent")
        return {
            "reported_at": row.get("reported_at") or "",
            "node_id": row.get("node_id") or "",
            "cpu_percent": cpu_stats["last"],
            "memory_used_percent": memory_stats["last"],
            "memory_used_bytes": _as_int(row.get("memory_used_bytes")),
            "memory_cache_percent": memory_cache_stats["last"],
            "memory_cache_bytes": _as_int(row.get("memory_cache_bytes")),
            "memory_free_percent": memory_free_stats["last"],
            "memory_free_bytes": _as_int(row.get("memory_free_bytes")),
            "memory_total_bytes": _as_int(row.get("memory_total_bytes")),
            "storage_used_percent": storage_stats["last"],
            "storage_used_bytes": _as_int(row.get("storage_used_bytes")),
            "storage_total_bytes": _as_int(row.get("storage_total_bytes")),
            "containers_total": _as_int(row.get("containers_total")),
            "containers_running": _as_int(row.get("containers_running")),
            "containers_stopped": _as_int(row.get("containers_stopped")),
            **_stats_fields("cpu_percent", cpu_stats),
            **_stats_fields("memory_used_percent", memory_stats),
            **_stats_fields("storage_used_percent", storage_stats),
            **_stats_fields("memory_cache_percent", memory_cache_stats),
            **_stats_fields("memory_free_percent", memory_free_stats),
            "sample_count": _sample_count(row),
            "source": row.get("source") or "",
        }

    def _normalize_metric_row(self, row):
        row = row or {}
        memory = row.get("memory") or {}
        storage = row.get("storage") or {}
        summary = _container_summary(row.get("containers") or {})
        metadata = row.get("metadata") or {}
        if not isinstance(metadata, dict):
            metadata = {}
        cpu_stats = _metric_stats(row.get("cpu_percent"), direct=row, metadata=metadata, metric_key="cpu_percent")
        memory_stats = _metric_stats(memory.get("used_percent"), nested=memory, metadata=metadata, metric_key="memory_used_percent")
        memory_cache_stats = _metric_stats(
            _memory_percent(memory, "cache_percent", byte_key="cache"),
            nested=memory,
            metadata=metadata,
            metric_key="memory_cache_percent",
            nested_prefix="cache_percent",
        )
        memory_free_stats = _metric_stats(
            _memory_percent(memory, "free_percent", byte_key="free"),
            nested=memory,
            metadata=metadata,
            metric_key="memory_free_percent",
            nested_prefix="free_percent",
        )
        storage_stats = _metric_stats(storage.get("used_percent"), nested=storage, metadata=metadata, metric_key="storage_used_percent")
        return {
            "reported_at": _iso(row.get("reported_at")),
            "node_id": str(row.get("node_id") or ""),
            "cpu_percent": cpu_stats["last"],
            "memory_used_percent": memory_stats["last"],
            "memory_used_bytes": _as_int(memory.get("used")),
            "memory_cache_percent": memory_cache_stats["last"],
            "memory_cache_bytes": _as_int(memory.get("cache")),
            "memory_free_percent": memory_free_stats["last"],
            "memory_free_bytes": _as_int(memory.get("free")),
            "memory_total_bytes": _as_int(memory.get("total")),
            "storage_used_percent": storage_stats["last"],
            "storage_used_bytes": _as_int(storage.get("used")),
            "storage_total_bytes": _as_int(storage.get("total")),
            "containers_total": summary["total"],
            "containers_running": summary["running"],
            "containers_stopped": summary["stopped"],
            **_stats_fields("cpu_percent", cpu_stats),
            **_stats_fields("memory_used_percent", memory_stats),
            **_stats_fields("storage_used_percent", storage_stats),
            **_stats_fields("memory_cache_percent", memory_cache_stats),
            **_stats_fields("memory_free_percent", memory_free_stats),
            "sample_count": _sample_count(metadata),
            "source": metadata.get("source") or row.get("source") or "database",
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
        def average(metric_key):
            return round(sum(_row_metric_stats(row, metric_key)["avg"] for row in rows) / len(rows), 2)

        def minimum(metric_key):
            return round(min(_row_metric_stats(row, metric_key)["min"] for row in rows), 2)

        def maximum(metric_key):
            return round(max(_row_metric_stats(row, metric_key)["max"] for row in rows), 2)

        return {
            "latest": latest,
            "count": len(rows),
            "avg_cpu_percent": average("cpu_percent"),
            "avg_memory_used_percent": average("memory_used_percent"),
            "avg_storage_used_percent": average("storage_used_percent"),
            "min_cpu_percent": minimum("cpu_percent"),
            "max_cpu_percent": maximum("cpu_percent"),
            "min_memory_used_percent": minimum("memory_used_percent"),
            "max_memory_used_percent": maximum("memory_used_percent"),
            "min_storage_used_percent": minimum("storage_used_percent"),
            "max_storage_used_percent": maximum("storage_used_percent"),
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
        rows = _deduplicate_metric_rows(rows)
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

    def _dashboard_chart_payload(self, data, rows, limit=288, source="csv", node_id=None):
        buckets = {}
        for row in rows or []:
            key = _bucket_time(row.get("reported_at"), minutes=RESOURCE_CHART_BUCKET_MINUTES)
            if not key:
                continue
            node_key = str(row.get("node_id") or node_id or "unknown")
            bucket = buckets.setdefault(key, {"reported_at": key, "nodes": {}, "count": 0, "sample_count": 0})
            node_bucket = bucket["nodes"].setdefault(node_key, {
                "metrics": {
                    metric_key: {
                        "min": None,
                        "max": None,
                        "avg_sum": 0.0,
                        "avg_weight": 0,
                        "last": None,
                        "last_at": None,
                    }
                    for metric_key in RESOURCE_METRIC_KEYS
                },
                "count": 0,
                "sample_count": 0,
                "containers_total_sum": 0.0,
                "containers_running_sum": 0.0,
                "memory_components": {key: {"sum": 0.0, "weight": 0} for key in MEMORY_STACK_KEYS},
            })
            reported_at = row.get("reported_at")
            reported_dt = _parse_reported_at(reported_at)
            weight = _sample_count(row)
            bucket["count"] += 1
            bucket["sample_count"] += weight
            node_bucket["count"] += 1
            node_bucket["sample_count"] += weight
            node_bucket["containers_total_sum"] += _as_float(row.get("containers_total"))
            node_bucket["containers_running_sum"] += _as_float(row.get("containers_running"))
            for component_key in MEMORY_STACK_KEYS:
                stats = _row_metric_stats(row, component_key)
                component = node_bucket["memory_components"][component_key]
                component["sum"] += stats["avg"] * weight
                component["weight"] += weight
            for metric_key in RESOURCE_METRIC_KEYS:
                stats = _row_metric_stats(row, metric_key)
                metric = node_bucket["metrics"][metric_key]
                metric["min"] = stats["min"] if metric["min"] is None else min(metric["min"], stats["min"])
                metric["max"] = stats["max"] if metric["max"] is None else max(metric["max"], stats["max"])
                metric["avg_sum"] += stats["avg"] * weight
                metric["avg_weight"] += weight
                if metric["last_at"] is None or (reported_dt is not None and reported_dt >= metric["last_at"]):
                    metric["last"] = stats["last"]
                    metric["last_at"] = reported_dt

        chart_rows = []
        for key in sorted(buckets):
            bucket = buckets[key]
            node_values = []
            for node_key, node_bucket in bucket["nodes"].items():
                metric_values = {}
                for metric_key, metric in node_bucket["metrics"].items():
                    avg_weight = max(1, metric["avg_weight"])
                    avg = metric["avg_sum"] / avg_weight
                    metric_values[metric_key] = {
                        "min": _percent(metric["min"], avg),
                        "max": _percent(metric["max"], avg),
                        "avg": _percent(avg),
                        "last": _percent(metric["last"], avg),
                    }
                count = max(1, node_bucket["count"])
                node_values.append({
                    "node_id": node_key,
                    "metrics": metric_values,
                    "memory_components": {
                        key: component["sum"] / max(1, component["weight"])
                        for key, component in node_bucket["memory_components"].items()
                    },
                    "containers_total": node_bucket["containers_total_sum"] / count,
                    "containers_running": node_bucket["containers_running_sum"] / count,
                })
            if not node_values:
                continue
            chart_row = {
                "reported_at": bucket["reported_at"],
                "node_count": len([item for item in node_values if item.get("node_id") != "unknown"]),
                "sample_count": bucket["sample_count"],
                "source_row_count": bucket["count"],
                "containers_total": round(sum(item["containers_total"] for item in node_values) / len(node_values), 2),
                "containers_running": round(sum(item["containers_running"] for item in node_values) / len(node_values), 2),
            }
            for metric_key in RESOURCE_METRIC_KEYS:
                metric_items = [item["metrics"][metric_key] for item in node_values]
                stats = {
                    "min": min(item["min"] for item in metric_items),
                    "max": max(item["max"] for item in metric_items),
                    "avg": sum(item["avg"] for item in metric_items) / len(metric_items),
                    "last": sum(item["last"] for item in metric_items) / len(metric_items),
                }
                chart_row[metric_key] = round(stats["avg"], 2)
                chart_row.update(_stats_fields(metric_key, stats))
            for component_key in MEMORY_STACK_KEYS:
                chart_row[component_key] = round(
                    sum(item["memory_components"].get(component_key, 0.0) for item in node_values) / len(node_values),
                    2,
                )
            chart_rows.append(chart_row)
        row_limit = _limit_value(limit, default=288, maximum=10000)
        if len(chart_rows) > row_limit:
            chart_rows = chart_rows[-row_limit:]
        return {
            **{key: data.get(key) for key in ["root", "start_date", "end_date", "start_at", "end_at"]},
            "node_id": str(node_id) if node_id else None,
            "bucket_minutes": RESOURCE_CHART_BUCKET_MINUTES,
            "count": len(chart_rows),
            "rows": chart_rows,
            "summary": self._summary(chart_rows),
            "source_count": data.get("count", len(rows or [])),
            "source": source,
        }

    def dashboard_chart(self, start_date=None, end_date=None, start_at=None, end_at=None, limit=288, env=None):
        if not start_date and not end_date and not start_at and not end_at:
            end_at = datetime.datetime.now(datetime.timezone.utc)
            start_at = end_at - datetime.timedelta(hours=24)
        data = self.query(node_id=None, start_date=start_date, end_date=end_date, start_at=start_at, end_at=end_at, limit=10000, env=env)
        return self._dashboard_chart_payload(data, data.get("rows") or [], limit=limit, source="csv")

    def node_chart(self, node_id, start_date=None, end_date=None, start_at=None, end_at=None, limit=288, env=None):
        if not start_date and not end_date and not start_at and not end_at:
            end_at = datetime.datetime.now(datetime.timezone.utc)
            start_at = end_at - datetime.timedelta(hours=24)
        data = self.query(node_id=node_id, start_date=start_date, end_date=end_date, start_at=start_at, end_at=end_at, limit=10000, env=env)
        return self._dashboard_chart_payload(data, data.get("rows") or [], limit=limit, source="csv", node_id=node_id)

    def dashboard_node_charts(self, node_ids, start_date=None, end_date=None, start_at=None, end_at=None, limit=288, env=None):
        return [
            self.node_chart(
                node_id,
                start_date=start_date,
                end_date=end_date,
                start_at=start_at,
                end_at=end_at,
                limit=limit,
                env=env,
            )
            for node_id in (node_ids or [])
        ]

    def dashboard_chart_from_metrics(self, rows, start_date=None, end_date=None, start_at=None, end_at=None, limit=288, env=None, node_id=None):
        if not start_date and not end_date and not start_at and not end_at:
            end_at = datetime.datetime.now(datetime.timezone.utc)
            start_at = end_at - datetime.timedelta(hours=24)
        start, end, start_dt, end_dt = _range_bounds(start_date=start_date, end_date=end_date, start_at=start_at, end_at=end_at)
        normalized = []
        for row in rows or []:
            normalized_row = self._normalize_metric_row(row)
            if node_id and str(normalized_row.get("node_id") or "") != str(node_id):
                continue
            if start_dt and end_dt:
                row_dt = _parse_reported_at(normalized_row.get("reported_at"))
                include = row_dt is not None and start_dt <= row_dt <= end_dt
            else:
                row_date = self._row_date(normalized_row)
                include = start.isoformat() <= row_date <= end.isoformat()
            if include:
                normalized.append(normalized_row)
        normalized = _deduplicate_metric_rows(normalized)
        data = {
            "root": str(self.root(env=env)),
            "start_date": start.isoformat(),
            "end_date": end.isoformat(),
            "start_at": start_dt.isoformat().replace("+00:00", "Z") if start_dt else None,
            "end_at": end_dt.isoformat().replace("+00:00", "Z") if end_dt else None,
            "count": len(normalized),
        }
        return self._dashboard_chart_payload(data, normalized, limit=limit, source="database", node_id=node_id)

    def dashboard_node_charts_from_metrics(self, node_ids, rows, start_date=None, end_date=None, start_at=None, end_at=None, limit=288, env=None):
        return [
            self.dashboard_chart_from_metrics(
                rows,
                start_date=start_date,
                end_date=end_date,
                start_at=start_at,
                end_at=end_at,
                limit=limit,
                env=env,
                node_id=node_id,
            )
            for node_id in (node_ids or [])
        ]

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
