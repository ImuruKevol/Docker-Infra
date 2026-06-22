import datetime
import hashlib
import hmac
import ipaddress
import secrets
import shlex
import shutil
import subprocess


config = wiz.config("docker_infra")
connect = wiz.model("db/postgres").connect

CRON_MARKER = "# docker-infra-service-backup"
CRON_ROUTE = "/api/system/backup/tick"
CRON_TOKEN_HEADER = "X-Docker-Infra-Cron-Token"


class CronError(Exception):
    def __init__(self, status_code, message, error_code, **extra):
        super().__init__(message)
        self.status_code = status_code
        self.message = message
        self.error_code = error_code
        self.extra = extra


def _utcnow():
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def _hash_token(token):
    return hashlib.sha256(str(token or "").encode("utf-8")).hexdigest()


def _clamp_int(value, default, minimum, maximum):
    try:
        number = int(value)
    except (TypeError, ValueError):
        number = default
    return max(minimum, min(maximum, number))


def _schedule(policy):
    hour, minute = 2, 0
    try:
        raw_hour, raw_minute = str(policy.get("schedule_time") or "02:00").split(":", 1)
        hour = _clamp_int(raw_hour, 2, 0, 23)
        minute = _clamp_int(raw_minute, 0, 0, 59)
    except (TypeError, ValueError):
        pass

    if str(policy.get("schedule_type") or "weekly") == "monthly":
        day = _clamp_int(policy.get("schedule_month_day"), 1, 1, 31)
        return f"{minute} {hour} {day} * *"

    # UI weekday: 0=Mon ... 6=Sun. Cron weekday: 1=Mon ... 6=Sat, 0=Sun.
    weekday = _clamp_int(policy.get("schedule_weekday"), 0, 0, 6)
    cron_weekday = 0 if weekday == 6 else weekday + 1
    return f"{minute} {hour} * * {cron_weekday}"


def _base_url(env=None):
    values = config.runtime_env(env)
    base = (
        values.get("DOCKER_INFRA_BACKUP_CRON_BASE_URL")
        or values.get("DOCKER_INFRA_INTERNAL_BASE_URL")
        or "http://127.0.0.1:3001"
    )
    return str(base).rstrip("/")


def _crontab_binary():
    binary = shutil.which("crontab")
    if not binary:
        raise CronError(500, "crontab 명령을 찾을 수 없습니다.", "CRONTAB_COMMAND_NOT_FOUND")
    return binary


def _crontab_user(env=None):
    return str(config.runtime_env(env).get("DOCKER_INFRA_BACKUP_CRON_USER", "root")).strip()


def _run_crontab(args, input_text=None):
    command = [_crontab_binary()]
    user = _crontab_user()
    if user:
        command.extend(["-u", user])
    command.extend(args)
    try:
        return subprocess.run(
            command,
            input=input_text,
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        raise CronError(504, "crontab 명령 실행 시간이 초과되었습니다.", "CRONTAB_COMMAND_TIMEOUT") from exc
    except OSError as exc:
        raise CronError(500, f"crontab 명령을 실행할 수 없습니다: {exc}", "CRONTAB_COMMAND_FAILED") from exc


def _read_crontab():
    result = _run_crontab(["-l"])
    if result.returncode == 0:
        return result.stdout or ""
    stderr = (result.stderr or "").lower()
    if "no crontab" in stderr or "no crontab for" in stderr:
        return ""
    raise CronError(500, result.stderr.strip() or "crontab을 읽을 수 없습니다.", "CRONTAB_READ_FAILED")


def _write_crontab(content):
    content = content.rstrip()
    if not content:
        result = _run_crontab(["-r"])
        stderr = (result.stderr or "").lower()
        if result.returncode == 0 or "no crontab" in stderr or "no crontab for" in stderr:
            return
        raise CronError(500, result.stderr.strip() or "crontab을 비울 수 없습니다.", "CRONTAB_WRITE_FAILED")

    result = _run_crontab(["-"], input_text=f"{content}\n")
    if result.returncode != 0:
        raise CronError(500, result.stderr.strip() or "crontab을 저장할 수 없습니다.", "CRONTAB_WRITE_FAILED")


def _without_managed_entry(content):
    return "\n".join(line for line in (content or "").splitlines() if CRON_MARKER not in line).strip()


def _curl_command(token, env=None):
    curl = shutil.which("curl") or "/usr/bin/curl"
    url = f"{_base_url(env)}{CRON_ROUTE}"
    header = f"{CRON_TOKEN_HEADER}: {token}"
    return f"{shlex.quote(curl)} -fsS -X POST -H {shlex.quote(header)} {shlex.quote(url)} >/dev/null 2>&1"


def _is_loopback(value):
    try:
        return ipaddress.ip_address(str(value or "").strip()).is_loopback
    except ValueError:
        return str(value or "").strip().lower() in {"localhost"}


class BackupSystemCron:
    CronError = CronError

    def prepare(self, policy, current=None, env=None):
        enabled = bool((policy or {}).get("enabled"))
        metadata = {
            "enabled": enabled,
            "installed": False,
            "route": CRON_ROUTE,
            "updated_at": _utcnow(),
        }
        if not enabled:
            return {"metadata": metadata, "token": None}

        token = secrets.token_urlsafe(32)
        schedule = _schedule(policy or {})
        metadata.update(
            {
                "installed": True,
                "schedule": schedule,
                "token_hash": _hash_token(token),
            }
        )
        return {"metadata": metadata, "token": token}

    def sync(self, policy, plan, env=None):
        plan = plan or {}
        metadata = plan.get("metadata") or {}
        if not metadata.get("enabled"):
            current = _read_crontab()
            next_content = _without_managed_entry(current)
            if next_content != (current or "").strip():
                _write_crontab(next_content)
            return {"installed": False, "schedule": None}

        token = plan.get("token")
        if not token:
            raise CronError(500, "자동 백업 cron 토큰을 만들 수 없습니다.", "CRON_TOKEN_REQUIRED")
        schedule = metadata.get("schedule") or _schedule(policy or {})
        current = _read_crontab()
        next_content = _without_managed_entry(current)
        line = f"{schedule} {_curl_command(token, env=env)} {CRON_MARKER}"
        next_content = f"{next_content}\n{line}".strip() if next_content else line
        _write_crontab(next_content)
        return {"installed": True, "schedule": schedule}

    def verify_token(self, token, env=None):
        if not token:
            return False
        with connect(env=env) as connection:
            with connection.cursor() as cursor:
                cursor.execute("SELECT metadata FROM backup_system_settings WHERE singleton_key = 'default'")
                row = cursor.fetchone()
        metadata = dict(row["metadata"] or {}) if row else {}
        cron = dict(metadata.get("backup_cron") or {})
        expected = cron.get("token_hash")
        return bool(expected) and hmac.compare_digest(str(expected), _hash_token(token))

    def request_allowed(self, request):
        forwarded = (request.headers.get("X-Forwarded-For") or "").split(",", 1)[0].strip()
        remote = forwarded or request.remote_addr
        return _is_loopback(remote)


Model = BackupSystemCron()
