import datetime
import json


connect = wiz.model("db/postgres").connect
local_executor = wiz.model("struct/local_executor")
compose_rules = wiz.model("struct/compose_rules")

PLACEMENT_WINDOW_MINUTES = 60
PLACEMENT_SAMPLE_LIMIT = 48
PLACEMENT_STAT_WEIGHTS = {"avg": 0.50, "max": 0.35, "min": 0.15}
RESOURCE_STAT_NAMES = ("min", "avg", "max", "last")


def _as_float(value, fallback=85.0):
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


def _percent(value, fallback=85.0):
    return max(0.0, min(100.0, _as_float(value, fallback)))


def _window_minutes(payload=None):
    payload = payload or {}
    return max(15, min(1440, _as_int(payload.get("placement_window_minutes") or payload.get("resource_window_minutes"), PLACEMENT_WINDOW_MINUTES)))


def _sample_limit(payload=None):
    payload = payload or {}
    return max(1, min(288, _as_int(payload.get("placement_sample_limit"), PLACEMENT_SAMPLE_LIMIT)))


def _age_minutes(value):
    if not value:
        return None
    if isinstance(value, datetime.datetime):
        dt = value
    else:
        try:
            dt = datetime.datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        except Exception:
            return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=datetime.timezone.utc)
    return max(0.0, (datetime.datetime.now(datetime.timezone.utc) - dt).total_seconds() / 60.0)


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


def _resource_window(metadata):
    metadata = metadata if isinstance(metadata, dict) else {}
    window = metadata.get("resource_window") or metadata.get("resource_stats") or {}
    return window if isinstance(window, dict) else {}


def _sample_count(row):
    row = row if isinstance(row, dict) else {}
    metadata = row.get("metadata") if isinstance(row.get("metadata"), dict) else {}
    for source in (row, metadata, _resource_window(row), _resource_window(metadata)):
        if isinstance(source, dict) and source.get("sample_count") not in (None, ""):
            return max(1, _as_int(source.get("sample_count"), 1))
    return 1


def _metric_fallback(row, metric_key):
    row = row if isinstance(row, dict) else {}
    if metric_key == "cpu_percent":
        return _percent(row.get("cpu_percent"))
    if metric_key == "memory_used_percent":
        memory = row.get("memory") if isinstance(row.get("memory"), dict) else {}
        return _percent(memory.get("used_percent"))
    if metric_key == "storage_used_percent":
        storage = row.get("storage") if isinstance(row.get("storage"), dict) else {}
        return _percent(storage.get("used_percent"))
    return _percent(row.get(metric_key))


def _row_metric_stats(row, metric_key):
    row = row if isinstance(row, dict) else {}
    fallback = _metric_fallback(row, metric_key)
    metadata = row.get("metadata") if isinstance(row.get("metadata"), dict) else {}
    window = _resource_window(metadata)
    payload = window.get(metric_key) if isinstance(window.get(metric_key), dict) else {}
    nested = {}
    nested_key = ""
    if metric_key == "memory_used_percent":
        nested = row.get("memory") if isinstance(row.get("memory"), dict) else {}
        nested_key = "used_percent"
    elif metric_key == "storage_used_percent":
        nested = row.get("storage") if isinstance(row.get("storage"), dict) else {}
        nested_key = "used_percent"
    stats = {}
    for stat in RESOURCE_STAT_NAMES:
        candidates = [
            row.get(f"{metric_key}_{stat}"),
            row.get(stat),
            nested.get(f"{nested_key}_{stat}") if nested_key else None,
            payload.get(stat),
        ]
        raw = next((item for item in candidates if item not in (None, "")), None)
        stats[stat] = _percent(raw, fallback) if raw is not None else fallback
    if stats["min"] > stats["max"]:
        stats["min"], stats["max"] = stats["max"], stats["min"]
    stats["avg"] = max(stats["min"], min(stats["max"], stats["avg"]))
    stats["last"] = max(stats["min"], min(stats["max"], stats["last"]))
    return stats


def _iso(value):
    if isinstance(value, datetime.datetime):
        parsed = value
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=datetime.timezone.utc)
        return parsed.astimezone(datetime.timezone.utc).isoformat().replace("+00:00", "Z")
    return str(value or "")


def _metric_rows(row):
    recent = row.get("recent_metrics") if isinstance(row.get("recent_metrics"), list) else []
    rows = [item for item in recent if isinstance(item, dict)]
    if rows:
        return sorted(rows, key=lambda item: _iso(item.get("reported_at")))
    if row.get("reported_at") is None and row.get("cpu_percent") is None and not row.get("memory"):
        return []
    return [{
        "cpu_percent": row.get("cpu_percent"),
        "memory": row.get("memory") or {},
        "storage": row.get("storage") or {},
        "containers": row.get("containers") or {},
        "metadata": row.get("metric_metadata") or {},
        "reported_at": row.get("reported_at"),
        "created_at": row.get("metric_created_at"),
    }]


def _window_metric_stats(rows, metric_key):
    rows = _metric_rows({"recent_metrics": rows}) if isinstance(rows, list) else []
    if not rows:
        stats = _row_metric_stats({}, metric_key)
        return {**stats, "sample_count": 0, "row_count": 0, "started_at": "", "ended_at": ""}
    weighted_avg = 0.0
    total_weight = 0
    mins = []
    maxes = []
    latest = rows[-1]
    for row in rows:
        stats = _row_metric_stats(row, metric_key)
        weight = _sample_count(row)
        weighted_avg += stats["avg"] * weight
        total_weight += weight
        mins.append(stats["min"])
        maxes.append(stats["max"])
    avg = weighted_avg / max(1, total_weight)
    first_window = _resource_window(rows[0].get("metadata") or {})
    last_window = _resource_window(latest.get("metadata") or {})
    return {
        "min": round(_percent(min(mins), avg), 2),
        "avg": round(_percent(avg), 2),
        "max": round(_percent(max(maxes), avg), 2),
        "last": round(_row_metric_stats(latest, metric_key)["last"], 2),
        "sample_count": total_weight,
        "row_count": len(rows),
        "started_at": first_window.get("started_at") or _iso(rows[0].get("reported_at")),
        "ended_at": last_window.get("ended_at") or _iso(latest.get("reported_at")),
    }


def _resource_stats(row):
    rows = _metric_rows(row)
    cpu = _window_metric_stats(rows, "cpu_percent")
    memory = _window_metric_stats(rows, "memory_used_percent")
    return {
        "cpu_percent": cpu,
        "memory_used_percent": memory,
        "window": {
            "sample_count": max(cpu.get("sample_count", 0), memory.get("sample_count", 0)),
            "row_count": max(cpu.get("row_count", 0), memory.get("row_count", 0)),
            "started_at": cpu.get("started_at") or memory.get("started_at") or "",
            "ended_at": cpu.get("ended_at") or memory.get("ended_at") or "",
        },
    }


def _weighted_pressure(stats):
    stats = stats or {}
    return _percent(
        _percent(stats.get("avg")) * PLACEMENT_STAT_WEIGHTS["avg"]
        + _percent(stats.get("max")) * PLACEMENT_STAT_WEIGHTS["max"]
        + _percent(stats.get("min")) * PLACEMENT_STAT_WEIGHTS["min"]
    )


def _public_stats(stats):
    return {
        "min": round(_percent((stats or {}).get("min")), 2),
        "avg": round(_percent((stats or {}).get("avg")), 2),
        "max": round(_percent((stats or {}).get("max")), 2),
        "last": round(_percent((stats or {}).get("last")), 2),
        "sample_count": _as_int((stats or {}).get("sample_count")),
        "row_count": _as_int((stats or {}).get("row_count")),
        "started_at": str((stats or {}).get("started_at") or ""),
        "ended_at": str((stats or {}).get("ended_at") or ""),
    }


def _node_summary(row):
    deployment_mode = "swarm" if str(row.get("swarm_node_id") or "").strip() else "compose"
    return {
        "id": str(row.get("id") or ""),
        "name": str(row.get("name") or ""),
        "host": str(row.get("host") or ""),
        "status": str(row.get("status") or ""),
        "swarm_node_id": str(row.get("swarm_node_id") or ""),
        "swarm_connected": bool(str(row.get("swarm_node_id") or "").strip()),
        "deployment_mode": deployment_mode,
        "network": compose_rules.default_network_name(deployment_mode),
        "swarm_hostname": str(row.get("swarm_hostname") or ""),
        "swarm_status": str(row.get("swarm_status") or ""),
        "swarm_availability": str(row.get("swarm_availability") or ""),
        "swarm_hostname_mismatch": bool(row.get("swarm_hostname_mismatch")),
        "is_local_master": bool(row.get("is_local_master")),
    }


class ServicesPlacement:
    def _swarm_nodes(self, env=None):
        result = local_executor.run("swarm.nodes", timeout_seconds=10, env=env)
        if result.get("status") != "ok":
            return {}
        rows = []
        for line in (result.get("stdout") or "").splitlines():
            try:
                row = json.loads(line)
            except Exception:
                continue
            if isinstance(row, dict):
                rows.append(row)
        by_id = {}
        for row in rows:
            node_id = str(row.get("ID") or "").strip()
            if not node_id:
                continue
            by_id[node_id] = row
            by_id[node_id[:12]] = row
        return by_id

    def _attach_swarm_state(self, rows, env=None):
        swarm = self._swarm_nodes(env=env)
        for row in rows:
            node_id = str(row.get("swarm_node_id") or "").strip()
            live = swarm.get(node_id) or swarm.get(node_id[:12])
            if not live:
                row["swarm_status"] = ""
                row["swarm_availability"] = ""
                row["swarm_hostname"] = ""
                row["swarm_ready"] = False
                row["swarm_hostname_mismatch"] = False
                continue
            hostname = str(live.get("Hostname") or "").strip()
            row["swarm_status"] = str(live.get("Status") or "").strip()
            row["swarm_availability"] = str(live.get("Availability") or "").strip()
            row["swarm_hostname"] = hostname
            row["swarm_ready"] = row["swarm_status"].lower() == "ready" and row["swarm_availability"].lower() == "active"
            registered_name = str(row.get("name") or "").strip()
            row["swarm_hostname_mismatch"] = bool(
                hostname
                and registered_name
                and registered_name != hostname
                and row.get("is_local_master") is not True
            )
        return rows

    def _latest_rows(self, payload=None, env=None):
        window_minutes = _window_minutes(payload)
        sample_limit = _sample_limit(payload)
        with connect(env=env) as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT
                        n.id,
                        n.name,
                        n.host,
                        n.status,
                        n.swarm_node_id,
                        n.is_local_master,
                        n.metadata,
                        n.created_at,
                        m.cpu_percent,
                        m.memory,
                        m.storage,
                        m.containers,
                        m.metadata AS metric_metadata,
                        m.reported_at,
                        m.created_at AS metric_created_at,
                        COALESCE(rm.recent_metrics, '[]'::jsonb) AS recent_metrics
                    FROM nodes n
                    LEFT JOIN LATERAL (
                        SELECT cpu_percent, memory, storage, containers, metadata, reported_at, created_at
                        FROM node_metrics
                        WHERE node_id = n.id
                        ORDER BY reported_at DESC, created_at DESC
                        LIMIT 1
                    ) m ON true
                    LEFT JOIN LATERAL (
                        SELECT COALESCE(
                            jsonb_agg(
                                jsonb_build_object(
                                    'cpu_percent', recent.cpu_percent,
                                    'memory', recent.memory,
                                    'storage', recent.storage,
                                    'containers', recent.containers,
                                    'metadata', recent.metadata,
                                    'reported_at', recent.reported_at,
                                    'created_at', recent.created_at
                                )
                                ORDER BY recent.reported_at ASC, recent.created_at ASC
                            ),
                            '[]'::jsonb
                        ) AS recent_metrics
                        FROM (
                            SELECT cpu_percent, memory, storage, containers, metadata, reported_at, created_at
                            FROM node_metrics
                            WHERE node_id = n.id
                              AND reported_at >= NOW() - (%s::int * interval '1 minute')
                            ORDER BY reported_at DESC, created_at DESC
                            LIMIT %s
                        ) recent
                    ) rm ON true
                    ORDER BY n.is_local_master DESC, n.created_at ASC, n.name ASC
                    """,
                    (window_minutes, sample_limit),
                )
                return self._attach_swarm_state([dict(row) for row in cursor.fetchall()], env=env)

    def _candidate(self, row, max_containers):
        storage = row.get("storage") or {}
        containers = _container_summary(row.get("containers") or {})
        resource_stats = _resource_stats(row)
        cpu_stats = resource_stats["cpu_percent"]
        memory_stats = resource_stats["memory_used_percent"]
        cpu_pressure = _weighted_pressure(cpu_stats)
        memory_pressure = _weighted_pressure(memory_stats)
        cpu_percent = _percent(cpu_stats.get("last"))
        memory_percent = _percent(memory_stats.get("last"))
        storage_percent = _percent(storage.get("used_percent"))
        container_pressure = min(100.0, containers["total"] * 100.0 / max(1, max_containers))
        age = _age_minutes(row.get("reported_at"))
        stale_penalty = 18.0 if age is None else min(18.0, age / 30.0)
        status = str(row.get("status") or "").lower()
        metadata = row.get("metadata") if isinstance(row.get("metadata"), dict) else {}
        last_check = metadata.get("last_check") if isinstance(metadata.get("last_check"), dict) else {}
        docker_check = last_check.get("docker") if isinstance(last_check.get("docker"), dict) else {}
        docker_check_status = str(docker_check.get("status") or "").lower()
        docker_unavailable = docker_check_status and docker_check_status != "ok"
        status_penalty = 0.0 if status in {"active", "ready", "running", "inactive"} and not docker_unavailable else 20.0
        swarm_connected = bool(str(row.get("swarm_node_id") or "").strip())
        live_swarm_penalty = 25.0 if swarm_connected and not row.get("swarm_ready") else 0.0
        hostname_penalty = 55.0 if swarm_connected and row.get("swarm_hostname_mismatch") else 0.0
        score = (
            cpu_pressure * 0.30
            + memory_pressure * 0.25
            + storage_percent * 0.25
            + container_pressure * 0.15
            + stale_penalty
            + status_penalty
            + live_swarm_penalty
            + hostname_penalty
        )
        selectable = status not in {"unreachable", "failed", "deleted", "error"} and not docker_unavailable
        if swarm_connected:
            selectable = selectable and bool(row.get("swarm_ready")) and not bool(row.get("swarm_hostname_mismatch"))
        return {
            "node": _node_summary(row),
            "score": round(score, 2),
            "cpu_percent": round(cpu_percent, 2),
            "memory_used_percent": round(memory_percent, 2),
            "cpu_pressure_percent": round(cpu_pressure, 2),
            "memory_pressure_percent": round(memory_pressure, 2),
            "cpu_stats": _public_stats(cpu_stats),
            "memory_stats": _public_stats(memory_stats),
            "resource_window": resource_stats["window"],
            "storage_used_percent": round(storage_percent, 2),
            "containers": containers,
            "container_pressure": round(container_pressure, 2),
            "metric_age_minutes": None if age is None else round(age, 1),
            "stale": age is None or age > 15,
            "swarm_status": str(row.get("swarm_status") or ""),
            "swarm_availability": str(row.get("swarm_availability") or ""),
            "swarm_hostname": str(row.get("swarm_hostname") or ""),
            "swarm_hostname_mismatch": bool(row.get("swarm_hostname_mismatch")),
            "selectable": selectable,
        }

    def recommend(self, payload=None, env=None):
        payload = payload or {}
        selected_node_id = str(payload.get("node_id") or "").strip()
        rows = self._latest_rows(payload=payload, env=env)
        if selected_node_id:
            rows = [row for row in rows if str(row.get("id")) == selected_node_id]
        max_containers = max([_container_summary(row.get("containers") or {}).get("total", 0) for row in rows] or [0])
        candidates = [self._candidate(row, max_containers=max_containers) for row in rows]
        selectable = [item for item in candidates if item["selectable"]]
        pool = selectable or candidates
        pool = sorted(pool, key=lambda item: (item["score"], not item["node"].get("is_local_master"), item["node"].get("name") or ""))
        selected = pool[0] if pool else None
        return {
            "strategy": "least_loaded_resource_score",
            "selected": selected,
            "candidates": sorted(candidates, key=lambda item: item["score"]),
            "weights": {"cpu": 0.30, "memory": 0.25, "storage": 0.25, "containers": 0.15},
            "stat_weights": dict(PLACEMENT_STAT_WEIGHTS),
            "metric_window_minutes": _window_minutes(payload),
        }


Model = ServicesPlacement()
