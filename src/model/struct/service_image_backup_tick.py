import datetime
import threading


backup_system = wiz.model("struct/backup_system")
scheduler = wiz.model("struct/service_image_backup_scheduler")


class ServiceImageBackupTick:
    def __init__(self):
        self._lock = threading.Lock()
        self._running = False
        self._last_tick_at = None
        self._last_result = None

    def _recent(self, seconds=60):
        if self._last_tick_at is None:
            return False
        return (datetime.datetime.now(datetime.timezone.utc) - self._last_tick_at).total_seconds() < seconds

    def _execute(self, env=None):
        try:
            self._last_result = scheduler.run({}, env=env)
        except Exception as exc:
            self._last_result = {"processed": 0, "succeeded": 0, "failed": 1, "message": str(exc)}
        finally:
            with self._lock:
                self._running = False

    def tick(self, env=None):
        status = backup_system.status(env=env)
        policy = status.get("backup_policy") or {}
        if not policy.get("enabled"):
            return {"scheduled": False, "reason": "disabled", "backup_system": status}
        with self._lock:
            if self._running:
                return {"scheduled": False, "reason": "running", "backup_system": status}
            if self._recent():
                return {"scheduled": False, "reason": "throttled", "last_result": self._last_result, "backup_system": status}
            self._running = True
            self._last_tick_at = datetime.datetime.now(datetime.timezone.utc)
        worker = threading.Thread(target=self._execute, kwargs={"env": env}, daemon=True)
        worker.start()
        return {"scheduled": True, "reason": "started", "backup_system": status}


Model = ServiceImageBackupTick()
