SYSTEM_METRICS_SCRIPT = r"""
state_file="${DOCKER_INFRA_METRICS_STATE_FILE:-/tmp/docker-infra-system-metrics.prev}"
read cpu user nice system idle iowait irq softirq steal rest < /proc/stat
total=$((user + nice + system + idle + iowait + irq + softirq + steal))
idle_now=$((idle + iowait))
prev_total=""
prev_idle=""
if [ -r "$state_file" ]; then
  read prev_total prev_idle < "$state_file" || true
fi
umask 077
printf '%s %s\n' "$total" "$idle_now" > "$state_file" 2>/dev/null || true
valid_prev=0
case "$prev_total" in
  ""|*[!0-9]*) valid_prev=0 ;;
  *)
    case "$prev_idle" in
      ""|*[!0-9]*) valid_prev=0 ;;
      *) valid_prev=1 ;;
    esac
    ;;
esac
if [ "$valid_prev" = "1" ] && [ "$total" -gt "$prev_total" ]; then
  total_delta=$((total - prev_total))
  idle_delta=$((idle_now - prev_idle))
  if [ "$idle_delta" -lt 0 ]; then
    idle_delta=0
  fi
  cpu_percent=$(awk -v total="$total_delta" -v idle="$idle_delta" 'BEGIN { if (total <= 0) print "0.0"; else { used = total - idle; if (used < 0) used = 0; percent = used * 100 / total; if (percent > 100) percent = 100; printf "%.2f", percent } }')
else
  cpu_percent="0.0"
fi
mem_values=$(awk '
  /MemTotal:/ { total = $2 * 1024 }
  /MemFree:/ { free = $2 * 1024 }
  /MemAvailable:/ { available = $2 * 1024 }
  /^Buffers:/ { buffers = $2 * 1024 }
  /^Cached:/ { cached = $2 * 1024 }
  /^SReclaimable:/ { sreclaimable = $2 * 1024 }
  /^Shmem:/ { shmem = $2 * 1024 }
  END {
    cache = buffers + cached + sreclaimable - shmem
    if (cache < 0) cache = 0
    used = total - free - cache
    if (used < 0) used = 0
    if (total <= 0) total = 0
    used_percent = total > 0 ? used * 100 / total : 0
    cache_percent = total > 0 ? cache * 100 / total : 0
    free_percent = total > 0 ? free * 100 / total : 0
    available_percent = total > 0 ? available * 100 / total : 0
    printf "%.0f %.0f %.0f %.0f %.0f %.2f %.2f %.2f %.2f", total, used, cache, free, available, used_percent, cache_percent, free_percent, available_percent
  }
' /proc/meminfo)
read mem_total mem_used mem_cache mem_free mem_available mem_percent mem_cache_percent mem_free_percent mem_available_percent <<EOF
$mem_values
EOF
storage_json=$(df -Pk / | awk 'NR==2 { gsub("%", "", $5); printf "\"total\":%d,\"used\":%d,\"available\":%d,\"used_percent\":%.2f", $2 * 1024, $3 * 1024, $4 * 1024, $5 }')
printf '{"cpu_percent":%s,"memory":{"total":%s,"used":%s,"cache":%s,"free":%s,"available":%s,"used_percent":%s,"cache_percent":%s,"free_percent":%s,"available_percent":%s},"storage":{%s}}\n' "$cpu_percent" "$mem_total" "$mem_used" "$mem_cache" "$mem_free" "$mem_available" "$mem_percent" "$mem_cache_percent" "$mem_free_percent" "$mem_available_percent" "$storage_json"
"""

NODE_METRICS_AGENT_SCRIPT = r"""#!/usr/bin/env python3
import datetime
import json
import os
import subprocess
import time
import urllib.error
import urllib.request


def utcnow():
    return datetime.datetime.now(datetime.timezone.utc).isoformat().replace("+00:00", "Z")


def run(argv, timeout=8):
    try:
        completed = subprocess.run(argv, capture_output=True, text=True, timeout=timeout, check=False)
        return {
            "ok": completed.returncode == 0,
            "exit_code": completed.returncode,
            "stdout": completed.stdout.strip(),
            "stderr": completed.stderr.strip(),
        }
    except Exception as exc:
        return {"ok": False, "exit_code": None, "stdout": "", "stderr": str(exc)}


def read_cpu_totals():
    with open("/proc/stat", "r", encoding="utf-8") as handle:
        parts = handle.readline().split()
    values = [int(value) for value in parts[1:8]]
    idle = values[3] + values[4]
    return sum(values), idle


def cpu_percent():
    state_file = os.environ.get("DOCKER_INFRA_METRICS_STATE_FILE", "/var/lib/docker-infra/node-metrics.prev")
    total, idle = read_cpu_totals()
    previous = None
    try:
        with open(state_file, "r", encoding="utf-8") as handle:
            raw_total, raw_idle = handle.read().split()[:2]
            previous = (int(raw_total), int(raw_idle))
    except Exception:
        previous = None
    try:
        os.makedirs(os.path.dirname(state_file), mode=0o700, exist_ok=True)
        with open(state_file, "w", encoding="utf-8") as handle:
            handle.write(f"{total} {idle}\n")
    except Exception:
        pass
    if not previous or total <= previous[0]:
        return 0.0
    total_delta = total - previous[0]
    idle_delta = max(0, idle - previous[1])
    used = max(0, total_delta - idle_delta)
    return round(min(100.0, used * 100.0 / max(1, total_delta)), 2)


def memory():
    values = {}
    with open("/proc/meminfo", "r", encoding="utf-8") as handle:
        for line in handle:
            parts = line.split()
            if len(parts) >= 2:
                values[parts[0].rstrip(":")] = int(parts[1]) * 1024
    total = values.get("MemTotal", 0)
    available = values.get("MemAvailable", 0)
    free = values.get("MemFree", 0)
    cache = max(0, values.get("Buffers", 0) + values.get("Cached", 0) + values.get("SReclaimable", 0) - values.get("Shmem", 0))
    used = max(0, total - free - cache)
    return {
        "total": total,
        "used": used,
        "cache": cache,
        "free": free,
        "available": available,
        "used_percent": round(used * 100.0 / total, 2) if total else 0.0,
        "cache_percent": round(cache * 100.0 / total, 2) if total else 0.0,
        "free_percent": round(free * 100.0 / total, 2) if total else 0.0,
        "available_percent": round(available * 100.0 / total, 2) if total else 0.0,
    }


def storage():
    result = run(["df", "-Pk", "/"], timeout=4)
    if not result["ok"]:
        return {"total": 0, "used": 0, "available": 0, "used_percent": 0.0}
    lines = [line for line in result["stdout"].splitlines() if line.strip()]
    if len(lines) < 2:
        return {"total": 0, "used": 0, "available": 0, "used_percent": 0.0}
    parts = lines[1].split()
    total = int(parts[1]) * 1024
    used = int(parts[2]) * 1024
    available = int(parts[3]) * 1024
    percent = float(parts[4].rstrip("%"))
    return {"total": total, "used": used, "available": available, "used_percent": percent}


def container_items():
    result = run(["docker", "ps", "-a", "--no-trunc", "--format", "{{json .}}"], timeout=10)
    if not result["ok"]:
        return []
    items = []
    for line in result["stdout"].splitlines():
        try:
            item = json.loads(line)
        except Exception:
            continue
        items.append({
            "id": item.get("ID") or item.get("Id") or "",
            "name": item.get("Names") or item.get("Name") or "",
            "image": item.get("Image") or "",
            "state": item.get("State") or "",
            "status": item.get("Status") or "",
            "ports": item.get("Ports") or "",
            "labels": item.get("Labels") or item.get("labels") or "",
        })
    return items


def container_payload():
    items = container_items()
    running = len([item for item in items if str(item.get("state") or "").lower() == "running"])
    return {
        "summary": {"total": len(items), "running": running, "stopped": max(0, len(items) - running)},
        "items": items,
    }


def post_metric(payload):
    base_url = os.environ.get("DOCKER_INFRA_REPORTER_BASE_URL", "").rstrip("/")
    token = os.environ.get("DOCKER_INFRA_REPORTER_TOKEN", "")
    if not base_url:
        raise RuntimeError("DOCKER_INFRA_REPORTER_BASE_URL is required")
    if not token:
        raise RuntimeError("DOCKER_INFRA_REPORTER_TOKEN is required")
    request = urllib.request.Request(
        f"{base_url}/api/reporter/metrics",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json", "Authorization": f"Bearer {token}"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=20) as response:
        body = response.read().decode("utf-8", errors="replace")
        if response.status < 200 or response.status >= 300:
            raise RuntimeError(f"reporter response status {response.status}: {body[:200]}")
        return response.status


def env_int(name, default, minimum, maximum):
    try:
        value = int(os.environ.get(name) or default)
    except Exception:
        value = default
    return max(minimum, min(value, maximum))


def stat(values):
    numbers = [float(value or 0.0) for value in values]
    if not numbers:
        numbers = [0.0]
    return {
        "min": round(min(numbers), 2),
        "max": round(max(numbers), 2),
        "last": round(numbers[-1], 2),
        "avg": round(sum(numbers) / len(numbers), 2),
    }


def metric_sample():
    return {
        "reported_at": utcnow(),
        "cpu_percent": cpu_percent(),
        "memory": memory(),
    }


def collect_window(window_seconds, sample_seconds):
    samples = []
    deadline = time.monotonic() + window_seconds
    while True:
        samples.append(metric_sample())
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            break
        time.sleep(min(sample_seconds, remaining))
    return samples


def main():
    node_id = os.environ.get("DOCKER_INFRA_NODE_ID", "")
    if not node_id:
        raise RuntimeError("DOCKER_INFRA_NODE_ID is required")
    interval_seconds = env_int("DOCKER_INFRA_METRICS_INTERVAL_SECONDS", 600, 600, 3600)
    window_seconds = env_int("DOCKER_INFRA_METRICS_WINDOW_SECONDS", interval_seconds, 600, 3600)
    sample_seconds = env_int("DOCKER_INFRA_METRICS_SAMPLE_SECONDS", 1, 1, 60)
    samples = collect_window(window_seconds, sample_seconds)
    last = samples[-1]
    mem = last["memory"]
    disk = storage()
    payload = {
        "node_id": node_id,
        "reported_at": last["reported_at"],
        "cpu_percent": last["cpu_percent"],
        "memory": mem,
        "storage": disk,
        "containers": container_payload(),
        "metadata": {
            "source": "systemd_collector",
            "agent_version": os.environ.get("DOCKER_INFRA_METRICS_AGENT_VERSION", ""),
            "interval_seconds": interval_seconds,
            "window_seconds": window_seconds,
            "sample_interval_seconds": sample_seconds,
            "sample_count": len(samples),
            "resource_window": {
                "sample_count": len(samples),
                "started_at": samples[0]["reported_at"],
                "ended_at": last["reported_at"],
                "window_seconds": window_seconds,
                "sample_interval_seconds": sample_seconds,
                "cpu_percent": stat([sample["cpu_percent"] for sample in samples]),
                "memory_used_percent": stat([sample["memory"].get("used_percent") for sample in samples]),
                "memory_cache_percent": stat([sample["memory"].get("cache_percent") for sample in samples]),
                "memory_free_percent": stat([sample["memory"].get("free_percent") for sample in samples]),
                "storage_used_percent": stat([disk.get("used_percent")]),
            },
        },
    }
    status = post_metric(payload)
    print(f"reported node metrics: status={status}")


if __name__ == "__main__":
    try:
        main()
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")[:200]
        raise SystemExit(f"reporter http error {exc.code}: {detail}")
"""

DOCKER_IMAGE_USAGE_SCRIPT = r"""
ids=$(docker container ls -aq --no-trunc)
if [ -z "$ids" ]; then
  exit 0
fi
docker inspect --format '{{json .}}' $ids
"""

DOCKER_IMAGE_STORAGE_SCRIPT = r"""
import json
import os
import shutil
import subprocess


def run(argv, timeout=8):
    try:
        completed = subprocess.run(argv, capture_output=True, text=True, timeout=timeout, check=False)
        return {
            "ok": completed.returncode == 0,
            "stdout": completed.stdout.strip(),
            "stderr": completed.stderr.strip(),
        }
    except Exception as exc:
        return {"ok": False, "stdout": "", "stderr": str(exc)}


def docker_root():
    result = run(["docker", "info", "--format", "{{json .}}"], timeout=8)
    if result["ok"] and result["stdout"]:
        try:
            payload = json.loads(result["stdout"])
            value = str(payload.get("DockerRootDir") or "").strip()
            if value:
                return value
        except Exception:
            pass
    return "/var/lib/docker"


def probe_path(path):
    current = os.path.abspath(os.path.expanduser(path or "/var/lib/docker"))
    while current and not os.path.exists(current):
        parent = os.path.dirname(current)
        if parent == current:
            break
        current = parent
    return current or "/"


root = docker_root()
try:
    usage = shutil.disk_usage(probe_path(root))
    total = int(usage.total)
    used = int(usage.used)
    available = int(usage.free)
    used_percent = round(used * 100.0 / total, 2) if total else 0.0
    print(json.dumps({
        "available": True,
        "path": root,
        "total_bytes": total,
        "used_bytes": used,
        "available_bytes": available,
        "used_percent": used_percent,
    }, ensure_ascii=False))
except Exception as exc:
    print(json.dumps({
        "available": False,
        "path": root,
        "total_bytes": 0,
        "used_bytes": 0,
        "available_bytes": 0,
        "used_percent": 0.0,
        "message": str(exc),
    }, ensure_ascii=False))
"""

DOCKER_IMAGE_DELETE_ESTIMATE_SCRIPT = r"""
import json
import subprocess
import sys


SIZE_UNITS = {
    "b": 1,
    "kb": 1024,
    "mb": 1024 ** 2,
    "gb": 1024 ** 3,
    "tb": 1024 ** 4,
    "pb": 1024 ** 5,
}


def run(argv, timeout=30):
    try:
        completed = subprocess.run(argv, capture_output=True, text=True, timeout=timeout, check=False)
        return {
            "ok": completed.returncode == 0,
            "stdout": completed.stdout.strip(),
            "stderr": completed.stderr.strip(),
            "exit_code": completed.returncode,
        }
    except Exception as exc:
        return {"ok": False, "stdout": "", "stderr": str(exc), "exit_code": None}


def parse_json_lines(stdout):
    items = []
    for line in (stdout or "").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            payload = json.loads(line)
        except Exception:
            continue
        if isinstance(payload, dict):
            items.append(payload)
    return items


def docker_df_image_rows(stdout):
    rows = []
    for row in parse_json_lines(stdout):
        images = row.get("Images")
        if isinstance(images, list):
            rows.extend([item for item in images if isinstance(item, dict)])
        else:
            rows.append(row)
    return rows


def parse_size_bytes(value):
    text = str(value or "").strip().replace(" ", "").lower()
    if "(" in text:
        text = text.split("(", 1)[0].strip()
    if not text or text in {"n/a", "-"}:
        return 0
    number = ""
    unit = ""
    for char in text:
        if char.isdigit() or char == ".":
            number += char
        else:
            unit += char
    if not number:
        return 0
    try:
        amount = float(number)
    except Exception:
        return 0
    return int(amount * SIZE_UNITS.get(unit or "b", 1))


def normalize_id(value):
    text = str(value or "").strip()
    if not text:
        return ""
    return text if text.startswith("sha256:") else f"sha256:{text}"


def compact_id(value):
    return normalize_id(value).replace("sha256:", "", 1)


def row_refs(row):
    repository = str(row.get("Repository") or row.get("repository") or "").strip()
    tag = str(row.get("Tag") or row.get("tag") or "").strip()
    digest = str(row.get("Digest") or row.get("digest") or "").strip()
    image_id = normalize_id(row.get("ID") or row.get("Id") or row.get("id"))
    digest_value = "" if digest == "<none>" else digest
    refs = {image_id, compact_id(image_id)}
    if repository not in {"", "<none>"} and tag not in {"", "<none>"}:
        refs.add(f"{repository}:{tag}")
        if digest_value:
            refs.add(f"{repository}:{tag}@{digest_value}")
    if repository not in {"", "<none>"} and digest_value:
        refs.add(f"{repository}@{digest_value}")
    if repository not in {"", "<none>"}:
        refs.add(repository)
    return {item for item in refs if item}


def container_image_ids():
    ids = run(["docker", "container", "ls", "-aq", "--no-trunc"], timeout=15)
    if not ids["ok"] or not ids["stdout"].strip():
        return set()
    result = run(["docker", "inspect", "--format", "{{json .}}", *ids["stdout"].split()], timeout=30)
    in_use = set()
    for item in parse_json_lines(result["stdout"] if result["ok"] else ""):
        image_id = normalize_id(item.get("Image"))
        if image_id:
            in_use.add(image_id)
    return in_use


def match_image_id(value, image_ids):
    raw = str(value or "").strip()
    if not raw:
        return ""
    normalized = normalize_id(raw)
    if normalized in image_ids:
        return normalized
    compact = raw.replace("sha256:", "", 1)
    matches = [image_id for image_id in image_ids if compact_id(image_id).startswith(compact)]
    return matches[0] if len(matches) == 1 else ""


def docker_df_unique_sizes(image_ids, ref_to_id):
    result = run(["docker", "system", "df", "-v", "--format", "{{json .}}"], timeout=30)
    if not result["ok"]:
        return {}, result["stderr"] or result["stdout"] or "docker system df failed"
    sizes = {}
    rows = docker_df_image_rows(result["stdout"])
    for row in rows:
        image_id = match_image_id(row.get("ImageID") or row.get("Image ID") or row.get("ID"), image_ids)
        if not image_id:
            repository = str(row.get("Repository") or row.get("REPOSITORY") or "").strip()
            tag = str(row.get("Tag") or row.get("TAG") or "").strip()
            if repository and repository != "<none>" and tag and tag != "<none>":
                image_id = ref_to_id.get(f"{repository}:{tag}", "")
        if not image_id:
            continue
        value = row.get("UniqueSize") or row.get("Unique Size") or row.get("UNIQUE SIZE") or row.get("Unique")
        size = parse_size_bytes(value)
        if size > sizes.get(image_id, 0):
            sizes[image_id] = size
    return sizes, ""


def estimate(requested_refs):
    list_result = run(["docker", "image", "ls", "--digests", "--no-trunc", "--format", "{{json .}}"], timeout=20)
    if not list_result["ok"]:
        return {
            "available": False,
            "message": list_result["stderr"] or list_result["stdout"] or "docker image list failed",
            "reclaimable_bytes": 0,
        }
    rows = parse_json_lines(list_result["stdout"])
    image_ids = {normalize_id(row.get("ID") or row.get("Id") or row.get("id")) for row in rows}
    image_ids = {image_id for image_id in image_ids if image_id}
    selected_refs = {str(item or "").strip() for item in requested_refs if str(item or "").strip()}
    selected_rows_by_id = {}
    selected_display_size_by_id = {}
    rows_by_id = {}
    force_image_ids = set()
    ref_to_id = {}
    for row in rows:
        image_id = normalize_id(row.get("ID") or row.get("Id") or row.get("id"))
        if not image_id:
            continue
        rows_by_id[image_id] = rows_by_id.get(image_id, 0) + 1
        row_size = parse_size_bytes(row.get("Size") or row.get("VirtualSize") or row.get("SIZE"))
        for ref in row_refs(row):
            ref_to_id[ref] = image_id
        refs = row_refs(row)
        if image_id in selected_refs or compact_id(image_id) in selected_refs:
            force_image_ids.add(image_id)
        if refs.intersection(selected_refs):
            selected_rows_by_id[image_id] = selected_rows_by_id.get(image_id, 0) + 1
            if row_size > selected_display_size_by_id.get(image_id, 0):
                selected_display_size_by_id[image_id] = row_size
    removable_ids = set()
    for image_id, selected_count in selected_rows_by_id.items():
        if image_id in force_image_ids or selected_count >= rows_by_id.get(image_id, 0):
            removable_ids.add(image_id)
    used_ids = container_image_ids()
    blocked_ids = removable_ids.intersection(used_ids)
    removable_ids = removable_ids.difference(blocked_ids)
    unique_sizes, df_error = docker_df_unique_sizes(image_ids, ref_to_id)
    if removable_ids and df_error:
        return {
            "available": False,
            "message": df_error,
            "requested_count": len(selected_refs),
            "matched_image_count": len(selected_rows_by_id),
            "removable_image_count": len(removable_ids),
            "blocked_image_count": len(blocked_ids),
            "reclaimable_bytes": 0,
        }
    missing_ids = [image_id for image_id in removable_ids if image_id not in unique_sizes]
    reclaimable_bytes = sum(unique_sizes.get(image_id, 0) for image_id in removable_ids)
    selected_size_bytes = sum(selected_display_size_by_id.get(image_id, 0) for image_id in selected_rows_by_id)
    removable_size_bytes = sum(selected_display_size_by_id.get(image_id, 0) for image_id in removable_ids)
    return {
        "available": True,
        "requested_count": len(selected_refs),
        "matched_image_count": len(selected_rows_by_id),
        "removable_image_count": len(removable_ids),
        "blocked_image_count": len(blocked_ids),
        "tag_only_count": max(0, len(selected_refs) - len(removable_ids)),
        "missing_unique_count": len(missing_ids),
        "reclaimable_bytes": int(max(0, reclaimable_bytes)),
        "selected_size_bytes": int(max(0, selected_size_bytes)),
        "removable_size_bytes": int(max(0, removable_size_bytes)),
        "shared_or_retained_bytes": int(max(0, removable_size_bytes - reclaimable_bytes)),
        "method": "docker_system_df_verbose",
        "command": "docker system df -v --format '{{json .}}'",
    }


try:
    refs = json.loads(sys.argv[1]) if len(sys.argv) > 1 else []
except Exception:
    refs = []

print(json.dumps(estimate(refs), ensure_ascii=False))
"""

DOCKER_PRUNE_ESTIMATE_SCRIPT = r"""
import json
import subprocess
import sys


SIZE_UNITS = {
    "b": 1,
    "kb": 1024,
    "mb": 1024 ** 2,
    "gb": 1024 ** 3,
    "tb": 1024 ** 4,
    "pb": 1024 ** 5,
}


def run(argv, timeout=20):
    try:
        completed = subprocess.run(argv, capture_output=True, text=True, timeout=timeout, check=False)
        return {
            "ok": completed.returncode == 0,
            "stdout": completed.stdout.strip(),
            "stderr": completed.stderr.strip(),
        }
    except Exception as exc:
        return {"ok": False, "stdout": "", "stderr": str(exc)}


def parse_json_lines(stdout):
    items = []
    for line in (stdout or "").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            payload = json.loads(line)
        except Exception:
            continue
        if isinstance(payload, dict):
            items.append(payload)
    return items


def parse_size_bytes(value):
    text = str(value or "").strip().replace(" ", "").lower()
    if "(" in text:
        text = text.split("(", 1)[0].strip()
    if not text or text in {"n/a", "-"}:
        return 0
    number = ""
    unit = ""
    for char in text:
        if char.isdigit() or char == ".":
            number += char
        else:
            unit += char
    if not number:
        return 0
    try:
        amount = float(number)
    except Exception:
        return 0
    return int(amount * SIZE_UNITS.get(unit or "b", 1))


def type_key(row):
    return str(row.get("Type") or row.get("TYPE") or row.get("type") or "").strip().lower()


def estimate(action):
    result = run(["docker", "system", "df", "--format", "{{json .}}"], timeout=20)
    if not result["ok"]:
        return {
            "available": False,
            "message": result["stderr"] or result["stdout"] or "docker system df failed",
            "reclaimable_bytes": 0,
        }
    rows = parse_json_lines(result["stdout"])
    image_row = {}
    for row in rows:
        key = type_key(row)
        if key == "images":
            image_row = row
            break
    images = parse_size_bytes(image_row.get("Reclaimable") or image_row.get("RECLAIMABLE") or image_row.get("reclaimable"))
    image_total = parse_size_bytes(image_row.get("Size") or image_row.get("SIZE") or image_row.get("size"))
    command = "docker image prune -a -f"
    return {
        "available": True,
        "action": "image",
        "command": command,
        "method": "docker_system_df",
        "reclaimable_bytes": int(max(0, images)),
        "image_total_bytes": int(max(0, image_total)),
        "images_reclaimable_bytes": int(max(0, images)),
        "total_count": image_row.get("TotalCount") or image_row.get("TOTAL COUNT") or image_row.get("total_count") or "",
        "active_count": image_row.get("Active") or image_row.get("ACTIVE") or image_row.get("active") or "",
    }


action = str(sys.argv[1] if len(sys.argv) > 1 else "image").strip()
if action != "image":
    action = "image"
print(json.dumps(estimate(action), ensure_ascii=False))
"""

AI_RESOURCE_SCRIPT = r"""
python3 - <<'PY'
import json
import os
import shutil
import subprocess


def run(argv, timeout=4):
    try:
        completed = subprocess.run(argv, capture_output=True, text=True, timeout=timeout, check=False)
        return {
            "ok": completed.returncode == 0,
            "exit_code": completed.returncode,
            "stdout": completed.stdout.strip(),
            "stderr": completed.stderr.strip(),
        }
    except Exception as exc:
        return {"ok": False, "exit_code": None, "stdout": "", "stderr": str(exc)}


def mem_total_bytes():
    try:
        with open("/proc/meminfo", "r", encoding="utf-8") as handle:
            for line in handle:
                if line.startswith("MemTotal:"):
                    return int(line.split()[1]) * 1024
    except Exception:
        return None
    return None


def module_names():
    try:
        with open("/proc/modules", "r", encoding="utf-8") as handle:
            return {line.split()[0] for line in handle if line.strip()}
    except Exception:
        return set()


def pci_devices():
    if not shutil.which("lspci"):
        return []
    result = run(["lspci"], timeout=3)
    if not result["ok"]:
        return []
    devices = []
    for line in result["stdout"].splitlines():
        lowered = line.lower()
        if "vga compatible controller" not in lowered and "3d controller" not in lowered and "display controller" not in lowered:
            continue
        vendor = "unknown"
        if "nvidia" in lowered:
            vendor = "nvidia"
        elif "intel" in lowered:
            vendor = "intel"
        elif "advanced micro devices" in lowered or " amd " in f" {lowered} " or "ati technologies" in lowered or "radeon" in lowered:
            vendor = "amd"
        devices.append({"vendor": vendor, "description": line})
    return devices


def nvidia_info(modules):
    info = {
        "driver_installed": bool(shutil.which("nvidia-smi") or "nvidia" in modules),
        "kernel_module_loaded": "nvidia" in modules,
        "nvidia_smi": bool(shutil.which("nvidia-smi")),
        "gpus": [],
    }
    if shutil.which("nvidia-smi"):
        result = run(
            [
                "nvidia-smi",
                "--query-gpu=name,memory.total,driver_version",
                "--format=csv,noheader,nounits",
            ],
            timeout=6,
        )
        info["check"] = result
        if result["ok"]:
            for line in result["stdout"].splitlines():
                parts = [part.strip() for part in line.split(",")]
                if len(parts) >= 3:
                    try:
                        memory_total = int(float(parts[1])) * 1024 * 1024
                    except Exception:
                        memory_total = None
                    info["gpus"].append(
                        {"vendor": "nvidia", "name": parts[0], "memory_total": memory_total, "driver_version": parts[2]}
                    )
    return info


def radeon_info(modules):
    rocm = bool(shutil.which("rocm-smi") or shutil.which("rocminfo"))
    loaded = [name for name in ["amdgpu", "radeon"] if name in modules]
    info = {
        "driver_installed": bool(loaded or rocm),
        "kernel_modules": loaded,
        "rocm_available": rocm,
        "gpus": [],
    }
    if shutil.which("rocm-smi"):
        result = run(["rocm-smi", "--showproductname", "--json"], timeout=6)
        info["check"] = result
        if result["ok"]:
            try:
                raw = json.loads(result["stdout"])
                for key, value in raw.items():
                    if isinstance(value, dict):
                        name = value.get("Card series") or value.get("Card model") or value.get("GPU ID") or key
                        info["gpus"].append({"vendor": "amd", "name": str(name), "source": "rocm-smi"})
            except Exception:
                pass
    return info


modules = module_names()
nvidia = nvidia_info(modules)
radeon = radeon_info(modules)
payload = {
    "cpu": {"logical_cores": os.cpu_count()},
    "memory": {"total": mem_total_bytes()},
    "gpu": {
        "devices": pci_devices(),
        "nvidia": nvidia,
        "radeon": radeon,
        "driver_summary": [
            {"driver": "nvidia", "installed": nvidia["driver_installed"], "module_loaded": nvidia["kernel_module_loaded"]},
            {"driver": "radeon", "installed": radeon["driver_installed"], "modules": radeon["kernel_modules"]},
        ],
    },
    "runtime": {
        "docker": bool(shutil.which("docker")),
        "ollama": bool(shutil.which("ollama")),
    },
}
print(json.dumps(payload, ensure_ascii=False))
PY
"""

AI_OLLAMA_SCAN_SCRIPT = r"""
python3 - <<'PY'
import json
import os
import shutil
import subprocess
import urllib.error
import urllib.request


def run(argv, timeout=4):
    try:
        completed = subprocess.run(argv, capture_output=True, text=True, timeout=timeout, check=False)
        return {
            "ok": completed.returncode == 0,
            "exit_code": completed.returncode,
            "stdout": completed.stdout.strip(),
            "stderr": completed.stderr.strip(),
        }
    except Exception as exc:
        return {"ok": False, "exit_code": None, "stdout": "", "stderr": str(exc)}


def safe_port(value):
    try:
        port = int(value)
    except Exception:
        port = 11434
    return max(1, min(port, 65535))


port = safe_port(os.environ.get("OLLAMA_PORT") or 11434)
path = shutil.which("ollama") or ""
version = ""
if path:
    version_result = run(["ollama", "--version"], timeout=3)
    version = version_result["stdout"] or version_result["stderr"]

process_result = run(["pgrep", "-x", "ollama"], timeout=2) if shutil.which("pgrep") else {"ok": False, "stdout": "", "stderr": ""}
systemd_active = ""
if shutil.which("systemctl"):
    systemd_result = run(["systemctl", "is-active", "ollama"], timeout=3)
    systemd_active = systemd_result["stdout"] or systemd_result["stderr"]

api_reachable = False
api_error = ""
models = []
try:
    with urllib.request.urlopen(f"http://127.0.0.1:{port}/api/tags", timeout=5) as response:
        data = json.loads(response.read().decode("utf-8"))
        models = data.get("models") if isinstance(data, dict) else []
        if not isinstance(models, list):
            models = []
        api_reachable = True
except urllib.error.HTTPError as exc:
    api_error = f"HTTP {exc.code}"
except Exception as exc:
    api_error = str(exc)

payload = {
    "port": port,
    "installed": bool(path),
    "path": path,
    "version": version,
    "process_running": bool(process_result.get("ok")),
    "systemd_active": systemd_active,
    "api_reachable": api_reachable,
    "running": bool(api_reachable or process_result.get("ok") or systemd_active == "active"),
    "models": models,
    "model_count": len(models),
    "api_error": api_error,
}
print(json.dumps(payload, ensure_ascii=False))
PY
"""


class LocalCommandScripts:
    SYSTEM_METRICS_SCRIPT = SYSTEM_METRICS_SCRIPT
    NODE_METRICS_AGENT_SCRIPT = NODE_METRICS_AGENT_SCRIPT
    DOCKER_IMAGE_USAGE_SCRIPT = DOCKER_IMAGE_USAGE_SCRIPT
    DOCKER_IMAGE_STORAGE_SCRIPT = DOCKER_IMAGE_STORAGE_SCRIPT
    DOCKER_IMAGE_DELETE_ESTIMATE_SCRIPT = DOCKER_IMAGE_DELETE_ESTIMATE_SCRIPT
    DOCKER_PRUNE_ESTIMATE_SCRIPT = DOCKER_PRUNE_ESTIMATE_SCRIPT
    AI_RESOURCE_SCRIPT = AI_RESOURCE_SCRIPT
    AI_OLLAMA_SCAN_SCRIPT = AI_OLLAMA_SCAN_SCRIPT


Model = LocalCommandScripts()
