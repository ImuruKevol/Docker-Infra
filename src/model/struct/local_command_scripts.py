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


class LocalCommandScripts:
    SYSTEM_METRICS_SCRIPT = SYSTEM_METRICS_SCRIPT
    DOCKER_IMAGE_USAGE_SCRIPT = DOCKER_IMAGE_USAGE_SCRIPT


Model = LocalCommandScripts()
