import fcntl
import os
import pty
import pwd
import shlex
import signal
import struct
import subprocess
import termios
import time

ssh_executor = wiz.model("struct/ssh_executor")
nodes_model = wiz.model("struct/nodes")
shared = wiz.model("struct/nodes_shared")
NodeError = shared.NodeError


class NodeTerminal:
    NodeError = NodeError

    def _node(self, node_id, env=None):
        return nodes_model.detail(node_id, env=env)

    def _is_local_master_node(self, node):
        return bool(node.get("is_local_master") or node.get("role") == "local_master" or node.get("name") == "local-master")

    def _shell_env(self, shell_path=None, home=None, username=None):
        env = os.environ.copy()
        env["TERM"] = env.get("TERM") or "xterm-256color"
        env["COLORTERM"] = env.get("COLORTERM") or "truecolor"
        env["LANG"] = env.get("LANG") or "C.UTF-8"
        env["LC_ALL"] = env.get("LC_ALL") or env["LANG"]
        if shell_path:
            env["SHELL"] = shell_path
        if home:
            env["HOME"] = home
        if username:
            env["USER"] = username
            env["LOGNAME"] = username
        return env

    def _set_winsize(self, fd, cols, rows):
        cols = max(40, int(cols or 120))
        rows = max(12, int(rows or 32))
        winsize = struct.pack("HHHH", rows, cols, 0, 0)
        fcntl.ioctl(fd, termios.TIOCSWINSZ, winsize)

    def _result(self, command, status, exit_code=None, stdout="", stderr="", duration_ms=0, timed_out=False):
        return {
            "command": command,
            "command_display": shlex.join(command),
            "status": status,
            "exit_code": exit_code,
            "stdout": stdout or "",
            "stderr": stderr or "",
            "duration_ms": duration_ms,
            "timed_out": timed_out,
        }

    def _run_local_command(self, command, timeout_seconds=8):
        started = time.monotonic()
        try:
            completed = subprocess.run(
                command,
                capture_output=True,
                text=True,
                timeout=max(1, int(timeout_seconds or 8)),
                check=False,
            )
            return self._result(
                command,
                "ok" if completed.returncode == 0 else "error",
                exit_code=completed.returncode,
                stdout=completed.stdout,
                stderr=completed.stderr,
                duration_ms=int((time.monotonic() - started) * 1000),
            )
        except FileNotFoundError as exc:
            return self._result(
                command,
                "missing",
                stderr=str(exc),
                duration_ms=int((time.monotonic() - started) * 1000),
            )
        except subprocess.TimeoutExpired as exc:
            return self._result(
                command,
                "timeout",
                stdout=exc.stdout,
                stderr=exc.stderr or f"command timed out after {timeout_seconds}s",
                duration_ms=int((time.monotonic() - started) * 1000),
                timed_out=True,
            )

    def _run_node_command(self, node, command, timeout_seconds=8, env=None):
        if self._is_local_master_node(node):
            return self._run_local_command(command, timeout_seconds=timeout_seconds)
        return nodes_model._run_ssh_command(node, command, timeout_seconds=timeout_seconds, env=env)

    def _command_failure(self, result, default_message):
        if result.get("timed_out") or result.get("status") == "timeout":
            return "응답 시간이 초과되었습니다."
        if result.get("status") == "missing":
            return "실행 파일을 찾을 수 없습니다."
        output = result.get("stderr") or result.get("stdout") or ""
        rows = [line.strip() for line in str(output or "").splitlines() if line.strip()]
        return rows[-1][:160] if rows else default_message

    def _local_shell(self):
        shell = os.environ.get("SHELL") or "/bin/bash"
        home = os.environ.get("HOME") or "/root"
        username = os.environ.get("USER") or "root"
        try:
            info = pwd.getpwuid(os.getuid())
            shell = info.pw_shell or shell
            home = info.pw_dir or home
            username = info.pw_name or username
        except Exception:
            pass
        if not os.path.exists(shell):
            shell = "/bin/bash" if os.path.exists("/bin/bash") else "/bin/sh"
        return {"shell": shell, "home": home, "username": username}

    def _local_command(self):
        identity = self._local_shell()
        return [identity["shell"], "-l"], identity

    def _remote_command(self, node, env=None):
        credential = node.get("credential") or {}
        username = credential.get("username")
        key_file = credential.get("key_file") or (credential.get("metadata") or {}).get("key_file")
        if not username:
            raise NodeError(409, "서버 SSH 계정 정보가 없습니다. 서버를 다시 등록해주세요.", "NODE_SSH_USERNAME_MISSING")
        if not key_file:
            raise NodeError(409, "서버 SSH key file 정보가 없습니다. 서버를 다시 등록해주세요.", "NODE_SSH_KEY_MISSING")
        known_hosts = ssh_executor.prepare_known_host(node["host"], port=node.get("ssh_port"), env=env)
        command = [
            "ssh",
            "-tt",
            "-o",
            f"UserKnownHostsFile={known_hosts}",
            "-o",
            "StrictHostKeyChecking=accept-new",
            "-o",
            "LogLevel=ERROR",
            "-o",
            "ServerAliveInterval=30",
            "-o",
            "ServerAliveCountMax=3",
            "-i",
            str(key_file),
            "-o",
            "IdentitiesOnly=yes",
        ]
        if node.get("ssh_port"):
            command.extend(["-p", str(node["ssh_port"])])
        command.append(f"{username}@{node['host']}")
        return command, {"shell": None, "home": None, "username": username}

    def _remote_exec_command(self, node, remote_command, env=None):
        command, identity = self._remote_command(node, env=env)
        command.append(shlex.join(remote_command))
        return command, identity

    def _ensure_container_running(self, node, container_id, env=None):
        result = self._run_node_command(
            node,
            ["docker", "inspect", "--format", "{{.State.Running}}", container_id],
            timeout_seconds=8,
            env=env,
        )
        if result.get("status") != "ok" or result.get("exit_code") not in (None, 0):
            reason = self._command_failure(result, "container inspect failed")
            raise NodeError(404, f"선택한 컨테이너를 확인할 수 없습니다. {reason}", "CONTAINER_INSPECT_FAILED", check=result)
        running = str(result.get("stdout") or "").strip().splitlines()
        if not running or running[-1].strip().lower() != "true":
            raise NodeError(409, "실행 중인 컨테이너만 터미널에 연결할 수 있습니다.", "CONTAINER_NOT_RUNNING", check=result)

    def _shell_probe_command(self, container_id, shell):
        if shell == "bash":
            return ["docker", "exec", container_id, "bash", "-lc", "printf __docker_infra_shell_ok__"]
        return ["docker", "exec", container_id, "sh", "-c", "printf __docker_infra_shell_ok__"]

    def _select_container_shell(self, node, container_id, env=None):
        checks = []
        for shell in ["bash", "sh"]:
            result = self._run_node_command(
                node,
                self._shell_probe_command(container_id, shell),
                timeout_seconds=8,
                env=env,
            )
            checks.append({key: result.get(key) for key in ["command_display", "status", "exit_code", "stderr"]})
            if result.get("status") == "ok" and result.get("exit_code") in (None, 0):
                return shell
        raise NodeError(
            409,
            "컨테이너에 bash 또는 sh가 없어 터미널을 열 수 없습니다.",
            "CONTAINER_SHELL_NOT_FOUND",
            checks=checks,
        )

    def _container_exec_command(self, container_id, shell):
        return [
            "docker",
            "exec",
            "-it",
            "-e",
            "TERM=xterm-256color",
            "-e",
            "COLORTERM=truecolor",
            container_id,
            shell,
        ]

    def create_session(self, node_id, cols=120, rows=32, env=None):
        node = self._node(node_id, env=env)
        command, identity = self._local_command() if self._is_local_master_node(node) else self._remote_command(node, env=env)
        master_fd, slave_fd = pty.openpty()
        self._set_winsize(slave_fd, cols, rows)
        process = subprocess.Popen(
            command,
            stdin=slave_fd,
            stdout=slave_fd,
            stderr=slave_fd,
            env=self._shell_env(shell_path=identity.get("shell"), home=identity.get("home"), username=identity.get("username")),
            preexec_fn=os.setsid,
            close_fds=True,
        )
        os.close(slave_fd)
        flags = fcntl.fcntl(master_fd, fcntl.F_GETFL)
        fcntl.fcntl(master_fd, fcntl.F_SETFL, flags | os.O_NONBLOCK)
        return {
            "node_id": str(node["id"]),
            "node_name": node.get("name"),
            "command": shlex.join(command),
            "master_fd": master_fd,
            "process": process,
            "shell_path": identity.get("shell"),
        }

    def create_container_session(self, node_id, container_id, cols=120, rows=32, env=None):
        node_id = str(node_id or "").strip()
        container_id = str(container_id or "").strip()
        if not node_id:
            raise NodeError(400, "node_id는 필수입니다.", "NODE_ID_REQUIRED")
        if not container_id:
            raise NodeError(400, "container_id는 필수입니다.", "CONTAINER_ID_REQUIRED")

        node = self._node(node_id, env=env)
        self._ensure_container_running(node, container_id, env=env)
        shell = self._select_container_shell(node, container_id, env=env)
        docker_command = self._container_exec_command(container_id, shell)
        command, identity = (
            (docker_command, {"shell": None, "home": None, "username": None})
            if self._is_local_master_node(node)
            else self._remote_exec_command(node, docker_command, env=env)
        )

        master_fd, slave_fd = pty.openpty()
        self._set_winsize(slave_fd, cols, rows)
        process = subprocess.Popen(
            command,
            stdin=slave_fd,
            stdout=slave_fd,
            stderr=slave_fd,
            env=self._shell_env(shell_path=identity.get("shell"), home=identity.get("home"), username=identity.get("username")),
            preexec_fn=os.setsid,
            close_fds=True,
        )
        os.close(slave_fd)
        flags = fcntl.fcntl(master_fd, fcntl.F_GETFL)
        fcntl.fcntl(master_fd, fcntl.F_SETFL, flags | os.O_NONBLOCK)
        return {
            "node_id": str(node["id"]),
            "node_name": node.get("name"),
            "container_id": container_id,
            "shell": shell,
            "command": shlex.join(command),
            "master_fd": master_fd,
            "process": process,
            "shell_path": identity.get("shell"),
        }

    def read(self, session, size=65536):
        try:
            data = os.read(session["master_fd"], size)
            return data.decode("utf-8", errors="ignore") if data else ""
        except BlockingIOError:
            return ""
        except OSError:
            return ""

    def write(self, session, data):
        if not session or session["process"].poll() is not None:
            return False
        payload = data if isinstance(data, bytes) else str(data or "").encode("utf-8", errors="ignore")
        if not payload:
            return True
        os.write(session["master_fd"], payload)
        return True

    def resize(self, session, cols, rows):
        if not session:
            return
        self._set_winsize(session["master_fd"], cols, rows)

    def is_alive(self, session):
        return bool(session) and session["process"].poll() is None

    def exit_code(self, session):
        if not session:
            return None
        return session["process"].poll()

    def close(self, session):
        if not session:
            return
        process = session.get("process")
        if process and process.poll() is None:
            try:
                os.killpg(process.pid, signal.SIGHUP)
            except Exception:
                try:
                    process.terminate()
                except Exception:
                    pass
        try:
            os.close(session["master_fd"])
        except Exception:
            pass


Model = NodeTerminal()
