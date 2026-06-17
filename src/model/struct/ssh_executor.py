import shlex
import subprocess
import time
from pathlib import Path
config = wiz.config("docker_infra")
managed_ssh = wiz.model("struct/ssh_managed")
DEFAULT_TIMEOUT_SECONDS = 15
MAX_TIMEOUT_SECONDS = 1800
MAX_CAPTURE_CHARS = 20000
def _normalize_timeout(timeout_seconds):
    if timeout_seconds in (None, ""):
        return DEFAULT_TIMEOUT_SECONDS
    return max(1, min(int(timeout_seconds), MAX_TIMEOUT_SECONDS))
def _capture_limit(value):
    if value in (None, ""):
        return MAX_CAPTURE_CHARS
    try:
        return int(value)
    except (TypeError, ValueError):
        return MAX_CAPTURE_CHARS


def _trim(value, limit=None):
    if value is None:
        return ""
    text = str(value)
    capture_limit = _capture_limit(limit)
    if capture_limit <= 0 or len(text) <= capture_limit:
        return text
    return text[:capture_limit] + "\n[truncated]"


def _is_truncated(value, limit=None):
    if value is None:
        return False
    capture_limit = _capture_limit(limit)
    return capture_limit > 0 and len(str(value)) > capture_limit


def _result(host, command, status, exit_code=None, stdout="", stderr="", duration_ms=0, timed_out=False, capture_limit=None):
    stdout_truncated = _is_truncated(stdout, capture_limit)
    stderr_truncated = _is_truncated(stderr)
    result = {
        "host": host,
        "command": command,
        "command_display": shlex.join(command),
        "status": status,
        "exit_code": exit_code,
        "stdout": _trim(stdout, capture_limit),
        "stderr": _trim(stderr),
        "duration_ms": duration_ms,
        "timed_out": timed_out,
    }
    if stdout_truncated:
        result["stdout_truncated"] = True
        result["stdout_capture_limit"] = _capture_limit(capture_limit)
    if stderr_truncated:
        result["stderr_truncated"] = True
        result["stderr_capture_limit"] = MAX_CAPTURE_CHARS
    return result
class SSHExecutor:
    def _target(self, host, username=None):
        if username:
            return f"{username}@{host}"
        return host

    def _port_args(self, port):
        if port in (None, ""):
            return []
        return ["-p", str(port)]

    def ssh_config(self, host):
        try:
            completed = subprocess.run(
                ["ssh", "-G", host],
                capture_output=True,
                text=True,
                timeout=5,
                check=False,
            )
        except Exception:
            return {}
        if completed.returncode != 0:
            return {}
        config = {}
        for line in completed.stdout.splitlines():
            if " " not in line:
                continue
            key, value = line.split(" ", 1)
            config[key.strip()] = value.strip()
        return config
    def known_fingerprint(self, host, port=None, env=None):
        lookup = host if not port or int(port) == 22 else f"[{host}]:{port}"
        try:
            completed = subprocess.run(
                ["ssh-keygen", "-F", lookup, "-f", str(self.known_hosts_file(env=env))],
                capture_output=True,
                text=True,
                timeout=5,
                check=False,
            )
        except Exception:
            return None
        for line in completed.stdout.splitlines():
            if " SHA256:" in line:
                return line.strip()
        return None
    def scan_fingerprint(self, host, port=None):
        port = int(port or 22)
        try:
            scan = subprocess.run(
                ["ssh-keyscan", "-p", str(port), "-T", "5", host],
                capture_output=True,
                text=True,
                timeout=8,
                check=False,
            )
            if scan.returncode != 0 and not scan.stdout:
                return None
            keygen = subprocess.run(
                ["ssh-keygen", "-lf", "-"],
                input=scan.stdout,
                capture_output=True,
                text=True,
                timeout=5,
                check=False,
            )
        except Exception:
            return None
        fingerprints = [line.strip() for line in keygen.stdout.splitlines() if " SHA256:" in line]
        return fingerprints[0] if fingerprints else None
    def key_file(self, name="docker-infra-node", env=None):
        key_dir = Path(config.ssh_key_dir(env)).expanduser()
        key_dir.mkdir(parents=True, exist_ok=True)
        return key_dir / name

    def known_hosts_file(self, name="docker-infra-known_hosts", env=None):
        key_dir = Path(config.ssh_key_dir(env)).expanduser()
        key_dir.mkdir(parents=True, exist_ok=True)
        path = key_dir / name
        path.touch(exist_ok=True)
        path.chmod(0o600)
        return path
    def prepare_known_host(self, host, port=None, env=None):
        port = int(port or 22)
        known_hosts = self.known_hosts_file(env=env)
        targets = [host] if port == 22 else [f"[{host}]:{port}", host]
        for target in targets:
            subprocess.run(
                ["ssh-keygen", "-R", target, "-f", str(known_hosts)],
                capture_output=True,
                text=True,
                timeout=5,
                check=False,
            )
        scan = subprocess.run(
            ["ssh-keyscan", "-p", str(port), "-T", "5", host],
            capture_output=True,
            text=True,
            timeout=8,
            check=False,
        )
        if scan.stdout:
            with known_hosts.open("a", encoding="utf-8") as handle:
                handle.write(scan.stdout)
        return str(known_hosts)
    def remove_known_host(self, host, port=None, env=None):
        port = int(port or 22)
        known_hosts = self.known_hosts_file(env=env)
        targets = [host] if port == 22 else [f"[{host}]:{port}", host]
        results = []
        for target in targets:
            try:
                completed = subprocess.run(
                    ["ssh-keygen", "-R", target, "-f", str(known_hosts)],
                    capture_output=True,
                    text=True,
                    timeout=5,
                    check=False,
                )
                results.append({
                    "target": target,
                    "status": "ok" if completed.returncode == 0 else "error",
                    "exit_code": completed.returncode,
                    "stdout": _trim(completed.stdout),
                    "stderr": _trim(completed.stderr),
                })
            except Exception as exc:
                results.append({"target": target, "status": "error", "exit_code": None, "stderr": str(exc)})
        return {"known_hosts": str(known_hosts), "targets": targets, "results": results}
    def known_hosts_for_run(self, host, port=None, env=None):
        known_hosts = self.known_hosts_file(env=env)
        if self.known_fingerprint(host, port=port, env=env):
            return str(known_hosts)
        return self.prepare_known_host(host, port=port, env=env)
    def ensure_key_file(self, name="docker-infra-node", env=None):
        key_file = self.key_file(name=name, env=env)
        public_key_file = Path(f"{key_file}.pub")
        if not key_file.exists() or not public_key_file.exists():
            subprocess.run(
                [
                    "ssh-keygen",
                    "-t",
                    "ed25519",
                    "-N",
                    "",
                    "-C",
                    "docker-infra-managed-key",
                    "-f",
                    str(key_file),
                ],
                capture_output=True,
                text=True,
                timeout=15,
                check=True,
            )
        key_file.chmod(0o600)
        return {"key_file": str(key_file), "public_key": public_key_file.read_text(encoding="utf-8").strip()}
    def run_with_password(self, host, username, password, command, port=None, timeout_seconds=None, env=None):
        timeout = _normalize_timeout(timeout_seconds)
        remote_command = shlex.join(command)
        known_hosts_file = self.known_hosts_for_run(host, port=port, env=env)
        argv = [
            "ssh",
            *self._port_args(port),
            "-o",
            "BatchMode=no",
            "-o",
            "PreferredAuthentications=password,keyboard-interactive",
            "-o",
            "PubkeyAuthentication=no",
            "-o",
            f"UserKnownHostsFile={known_hosts_file}",
            "-o",
            "StrictHostKeyChecking=accept-new",
            "-o",
            "LogLevel=ERROR",
            "-o",
            f"ConnectTimeout={min(timeout, 30)}",
            self._target(host, username),
            remote_command,
        ]
        raw = managed_ssh.interactive_password_run(argv, password, timeout)
        return _result(
            host,
            command,
            raw["status"],
            exit_code=raw["exit_code"],
            stdout=raw["stdout"],
            stderr=raw["stderr"],
            duration_ms=raw["duration_ms"],
            timed_out=raw["timed_out"],
        )
    def install_public_key(self, host, username, password, public_key, port=None, timeout_seconds=None, env=None):
        quoted_key = shlex.quote(public_key)
        script = (
            "umask 077; mkdir -p ~/.ssh; touch ~/.ssh/authorized_keys; "
            f"grep -qxF {quoted_key} ~/.ssh/authorized_keys || printf '%s\\n' {quoted_key} >> ~/.ssh/authorized_keys; "
            "chmod 700 ~/.ssh; chmod 600 ~/.ssh/authorized_keys"
        )
        return self.run_with_password(
            host,
            username,
            password,
            ["sh", "-lc", script],
            port=port,
            timeout_seconds=timeout_seconds,
            env=env,
        )
    def failure_reason(self, result):
        if result is None:
            return "원인을 확인할 수 없습니다."
        if result.get("timed_out") or result.get("status") == "timeout":
            return "서버 응답이 없어 연결 시간이 초과되었습니다."
        if result.get("status") == "missing":
            return "SSH 실행 파일을 찾을 수 없습니다."
        output = f"{result.get('stderr', '')}\n{result.get('stdout', '')}".lower()
        hints = [
            (["permission denied"], "SSH 계정 또는 비밀번호를 확인해주세요."),
            (["connection refused"], "SSH 포트가 열려 있지 않거나 SSH 서비스가 실행 중이 아닙니다."),
            (["host key verification failed"], "서버 SSH host key 검증에 실패했습니다."),
            (["could not resolve hostname", "name or service not known"], "서버 주소를 확인해주세요."),
            (["connection timed out", "operation timed out"], "서버에 연결하는 동안 시간이 초과되었습니다."),
            (["no route to host", "network is unreachable"], "서버 네트워크 경로에 접근할 수 없습니다."),
            (["connection closed by remote host", "kex_exchange_identification"], "서버가 SSH 연결을 바로 종료했습니다."),
            (["permission denied (publickey)"], "저장된 SSH key로 인증할 수 없습니다."),
        ]
        for patterns, message in hints:
            if any(pattern in output for pattern in patterns):
                return message
        if result.get("exit_code") == 255:
            return "SSH 연결 설정 또는 인증 정보를 확인해주세요."
        lines = [line.strip() for line in output.splitlines() if line.strip()]
        if lines:
            return lines[-1][:160]
        return "원인을 확인할 수 없습니다."
    def run(self, host, command, timeout_seconds=None, username=None, port=None, key_file=None, env=None, capture_limit=None):
        timeout = _normalize_timeout(timeout_seconds)
        remote_command = shlex.join(command)
        known_hosts_file = self.known_hosts_for_run(host, port=port, env=env)
        argv = [
            "ssh",
            *self._port_args(port),
            "-o",
            "BatchMode=yes",
            "-o",
            f"UserKnownHostsFile={known_hosts_file}",
            "-o",
            "StrictHostKeyChecking=accept-new",
            "-o",
            "LogLevel=ERROR",
            "-o",
            f"ConnectTimeout={min(timeout, 30)}",
        ]
        if key_file:
            argv.extend(["-i", str(key_file), "-o", "IdentitiesOnly=yes"])
        argv.extend([
            self._target(host, username),
            remote_command,
        ])
        started = time.monotonic()
        try:
            completed = subprocess.run(argv, capture_output=True, text=True, timeout=timeout, check=False)
            duration_ms = int((time.monotonic() - started) * 1000)
            return _result(
                host,
                command,
                "ok" if completed.returncode == 0 else "error",
                exit_code=completed.returncode,
                stdout=completed.stdout,
                stderr=completed.stderr,
                duration_ms=duration_ms,
                capture_limit=capture_limit,
            )
        except FileNotFoundError as exc:
            duration_ms = int((time.monotonic() - started) * 1000)
            return _result(host, command, "missing", stderr=str(exc), duration_ms=duration_ms, capture_limit=capture_limit)
        except subprocess.TimeoutExpired as exc:
            duration_ms = int((time.monotonic() - started) * 1000)
            return _result(
                host,
                command,
                "timeout",
                stdout=exc.stdout,
                stderr=exc.stderr or f"ssh command timed out after {timeout}s",
                duration_ms=duration_ms,
                timed_out=True,
                capture_limit=capture_limit,
            )
Model = SSHExecutor()
