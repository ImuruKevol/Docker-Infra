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
mem_total=$(awk '/MemTotal:/ {printf "%.0f", $2 * 1024}' /proc/meminfo)
mem_available=$(awk '/MemAvailable:/ {printf "%.0f", $2 * 1024}' /proc/meminfo)
mem_used=$((mem_total - mem_available))
mem_percent=$(awk -v used="$mem_used" -v total="$mem_total" 'BEGIN { if (total <= 0) print "0.0"; else printf "%.2f", (used * 100 / total) }')
storage_json=$(df -Pk / | awk 'NR==2 { gsub("%", "", $5); printf "\"total\":%d,\"used\":%d,\"available\":%d,\"used_percent\":%.2f", $2 * 1024, $3 * 1024, $4 * 1024, $5 }')
printf '{"cpu_percent":%s,"memory":{"total":%s,"used":%s,"available":%s,"used_percent":%s},"storage":{%s}}\n' "$cpu_percent" "$mem_total" "$mem_used" "$mem_available" "$mem_percent" "$storage_json"
"""

DOCKER_IMAGE_USAGE_SCRIPT = r"""
ids=$(docker container ls -aq --no-trunc)
if [ -z "$ids" ]; then
  exit 0
fi
docker inspect --format '{{json .}}' $ids
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


class LocalCommandScripts:
    SYSTEM_METRICS_SCRIPT = SYSTEM_METRICS_SCRIPT
    DOCKER_IMAGE_USAGE_SCRIPT = DOCKER_IMAGE_USAGE_SCRIPT
    AI_RESOURCE_SCRIPT = AI_RESOURCE_SCRIPT


Model = LocalCommandScripts()
