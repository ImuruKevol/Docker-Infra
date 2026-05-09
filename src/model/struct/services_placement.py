import datetime


connect = wiz.model("db/postgres").connect


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


def _node_summary(row):
    return {
        "id": str(row.get("id") or ""),
        "name": str(row.get("name") or ""),
        "host": str(row.get("host") or ""),
        "status": str(row.get("status") or ""),
        "swarm_node_id": str(row.get("swarm_node_id") or ""),
        "is_local_master": bool(row.get("is_local_master")),
    }


class ServicesPlacement:
    def _latest_rows(self, env=None):
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
                        n.created_at,
                        m.cpu_percent,
                        m.memory,
                        m.storage,
                        m.containers,
                        m.reported_at
                    FROM nodes n
                    LEFT JOIN LATERAL (
                        SELECT cpu_percent, memory, storage, containers, reported_at
                        FROM node_metrics
                        WHERE node_id = n.id
                        ORDER BY reported_at DESC, created_at DESC
                        LIMIT 1
                    ) m ON true
                    ORDER BY n.is_local_master DESC, n.created_at ASC, n.name ASC
                    """
                )
                return [dict(row) for row in cursor.fetchall()]

    def _candidate(self, row, max_containers):
        memory = row.get("memory") or {}
        storage = row.get("storage") or {}
        containers = _container_summary(row.get("containers") or {})
        cpu_percent = _as_float(row.get("cpu_percent"))
        memory_percent = _as_float(memory.get("used_percent"))
        storage_percent = _as_float(storage.get("used_percent"))
        container_pressure = min(100.0, containers["total"] * 100.0 / max(1, max_containers))
        age = _age_minutes(row.get("reported_at"))
        stale_penalty = 18.0 if age is None else min(18.0, age / 30.0)
        status = str(row.get("status") or "").lower()
        status_penalty = 0.0 if status in {"active", "reachable", "ready"} else 20.0
        swarm_penalty = 0.0 if str(row.get("swarm_node_id") or "").strip() else 35.0
        score = (
            cpu_percent * 0.30
            + memory_percent * 0.25
            + storage_percent * 0.25
            + container_pressure * 0.15
            + stale_penalty
            + status_penalty
            + swarm_penalty
        )
        return {
            "node": _node_summary(row),
            "score": round(score, 2),
            "cpu_percent": round(cpu_percent, 2),
            "memory_used_percent": round(memory_percent, 2),
            "storage_used_percent": round(storage_percent, 2),
            "containers": containers,
            "container_pressure": round(container_pressure, 2),
            "metric_age_minutes": None if age is None else round(age, 1),
            "stale": age is None or age > 15,
            "selectable": bool(row.get("swarm_node_id")) and status not in {"unreachable", "failed", "deleted"},
        }

    def recommend(self, payload=None, env=None):
        payload = payload or {}
        selected_node_id = str(payload.get("node_id") or "").strip()
        rows = self._latest_rows(env=env)
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
        }


Model = ServicesPlacement()
