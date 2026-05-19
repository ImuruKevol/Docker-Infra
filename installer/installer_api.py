#!/usr/bin/env python3
import argparse
import json
import os
import subprocess
import threading
from collections import deque
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse


ALLOWED_STEPS = {
    "all",
    "apt",
    "env",
    "postgres",
    "python",
    "node",
    "bundle",
    "migrate",
    "service",
    "setup",
    "nginx",
    "verify",
    "cleanup",
}


class Runner:
    def __init__(self):
        self.script = Path(os.environ.get("DOCKER_INFRA_INSTALLER_SCRIPT", "/opt/docker-infra/installer/install.sh"))
        self.log_path = Path(os.environ.get("DOCKER_INFRA_INSTALLER_LOG", "/var/log/docker-infra/installer.log"))
        self.state_path = Path(os.environ.get("DOCKER_INFRA_INSTALLER_STATE", "/opt/docker-infra/installer/state.json"))
        self.initial_setup_file = Path(os.environ.get("DOCKER_INFRA_INITIAL_SETUP_FILE", "/etc/docker-infra/initial-setup.json"))
        self.lock = threading.Lock()
        self.process = None
        self.current_step = None
        self.started_at = None
        self.finished_at = None
        self.exit_code = None

    def _now(self):
        return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

    def _append_log(self, line):
        self.log_path.parent.mkdir(parents=True, exist_ok=True)
        with self.log_path.open("a", encoding="utf-8") as handle:
            handle.write(f"{line}\n")

    def _tail_log(self, limit=180):
        if not self.log_path.is_file():
            return []
        lines = deque(maxlen=limit)
        with self.log_path.open("r", encoding="utf-8", errors="replace") as handle:
            for line in handle:
                lines.append(line.rstrip("\n"))
        return list(lines)

    def _write_state(self):
        self.state_path.parent.mkdir(parents=True, exist_ok=True)
        state = {
            "running": self.running,
            "step": self.current_step,
            "started_at": self.started_at,
            "finished_at": self.finished_at,
            "exit_code": self.exit_code,
        }
        self.state_path.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")

    @property
    def running(self):
        return self.process is not None and self.process.poll() is None

    def refresh(self):
        with self.lock:
            if self.process is not None:
                code = self.process.poll()
                if code is not None and self.exit_code is None:
                    self.exit_code = code
                    self.finished_at = self._now()
                    result = "success" if code == 0 else "failed"
                    self._append_log(
                        f"[{self.finished_at}] 단계 종료: {self.current_step or '-'} result={result} exit_code={code}"
                    )
                    self.process = None
                    self._write_state()

    def status(self):
        self.refresh()
        return {
            "running": self.running,
            "step": self.current_step,
            "started_at": self.started_at,
            "finished_at": self.finished_at,
            "exit_code": self.exit_code,
            "log_tail": self._tail_log(),
        }

    def _write_initial_setup(self, payload):
        if not isinstance(payload, dict):
            return
        cleaned = {
            "password": str(payload.get("password") or ""),
            "confirm_password": str(payload.get("confirm_password") or ""),
            "advertise_address": str(payload.get("advertise_address") or ""),
            "proxy_type": "nginx",
            "service_root": str(payload.get("service_root") or ".runtime/dev/services"),
            "backup_system": payload.get("backup_system") if isinstance(payload.get("backup_system"), dict) else {},
        }
        self.initial_setup_file.parent.mkdir(parents=True, exist_ok=True)
        fd = os.open(self.initial_setup_file, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(cleaned, handle, ensure_ascii=False)

    def run(self, step, setup_payload=None):
        if step not in ALLOWED_STEPS:
            raise ValueError(f"unknown step: {step}")
        if not self.script.is_file():
            raise FileNotFoundError(f"installer script not found: {self.script}")

        with self.lock:
            if self.running:
                return {"started": False, "running": True, "step": self.current_step}

            self.log_path.parent.mkdir(parents=True, exist_ok=True)
            if step in {"all", "setup"}:
                self._write_initial_setup(setup_payload)

            log_handle = self.log_path.open("w", encoding="utf-8")
            log_handle.write(f"\n[{self._now()}] starting step: {step}\n")
            log_handle.flush()

            env = os.environ.copy()
            env["PYTHONUNBUFFERED"] = "1"
            self.current_step = step
            self.started_at = self._now()
            self.finished_at = None
            self.exit_code = None
            self.process = subprocess.Popen(
                [str(self.script), "--step", step],
                stdout=log_handle,
                stderr=subprocess.STDOUT,
                stdin=subprocess.DEVNULL,
                env=env,
                text=True,
            )
            log_handle.close()
            self._write_state()
            return {"started": True, "running": True, "step": step, "pid": self.process.pid}


runner = Runner()


class Handler(BaseHTTPRequestHandler):
    server_version = "DockerInfraInstaller/1.0"

    def _send_json(self, status, payload):
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(data)

    def _read_body(self):
        length = int(self.headers.get("Content-Length") or "0")
        if length <= 0:
            return {}
        raw = self.rfile.read(length).decode("utf-8")
        return json.loads(raw or "{}")

    def _path(self):
        return urlparse(self.path).path.rstrip("/") or "/"

    def do_GET(self):
        path = self._path()
        if path == "/health":
            self._send_json(200, {"ok": True})
            return
        if path == "/status":
            self._send_json(200, {"ok": True, "status": runner.status(), "steps": sorted(ALLOWED_STEPS)})
            return
        self._send_json(404, {"ok": False, "message": "not found"})

    def do_POST(self):
        if self._path() != "/run":
            self._send_json(404, {"ok": False, "message": "not found"})
            return
        try:
            body = self._read_body()
            step = str(body.get("step") or "").strip()
            result = runner.run(step, setup_payload=body.get("setup"))
            self._send_json(200, {"ok": True, "result": result, "status": runner.status()})
        except ValueError as exc:
            self._send_json(400, {"ok": False, "message": str(exc)})
        except Exception as exc:
            self._send_json(500, {"ok": False, "message": str(exc)})

    def log_message(self, fmt, *args):
        return


def main():
    parser = argparse.ArgumentParser(description="Docker Infra installer API")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8791)
    args = parser.parse_args()

    server = ThreadingHTTPServer((args.host, args.port), Handler)
    server.serve_forever()


if __name__ == "__main__":
    main()
