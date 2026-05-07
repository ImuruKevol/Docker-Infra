import os
import shlex
import signal
import subprocess
import tempfile
import threading
import time
from pathlib import Path

connect = wiz.model("db/postgres").connect
jobs_model = wiz.model("struct/jobs")
nodes_model = wiz.model("struct/nodes")
ssh_executor = wiz.model("struct/ssh_executor")
shared = wiz.model("struct/macros_shared")
MacroError = shared.MacroError
macro_row = shared.macro_row
normalize_timeout = shared.normalize_timeout
trim_output = shared.trim_output
SCOPE_NODE = shared.SCOPE_NODE


class MacroRunner:
    MacroError = MacroError
    def _fetch(self, cursor, macro_id):
        cursor.execute(
            """
            SELECT m.*, n.name AS node_name, n.host AS node_host
            FROM shell_macros m
            LEFT JOIN nodes n ON n.id = m.node_id
            WHERE m.id = %s
            """,
            (macro_id,),
        )
        row = cursor.fetchone()
        if row is None:
            raise MacroError(404, "매크로를 찾을 수 없습니다.", "MACRO_NOT_FOUND")
        return macro_row(row)

    def _parse_args(self, args_text):
        if args_text in (None, ""):
            return []
        try:
            return [str(item) for item in shlex.split(str(args_text))]
        except ValueError:
            raise MacroError(400, "인자 형식이 올바르지 않습니다. 따옴표를 확인해주세요.", "INVALID_MACRO_ARGS")

    def _remote_command(self, script, args):
        encoded_script = shlex.quote(script)
        arg_tokens = " ".join(shlex.quote(arg) for arg in args)
        return [
            "sh",
            "-lc",
            (
                "tmp=$(mktemp /tmp/docker-infra-macro.XXXXXX.sh) && "
                f"printf '%s\\n' {encoded_script} > \"$tmp\" && "
                "chmod 700 \"$tmp\" && "
                f"/bin/bash \"$tmp\" {arg_tokens}; "
                "rc=$?; rm -f \"$tmp\"; exit $rc"
            ),
        ]

    def _append_logs(self, job_id, result, env=None):
        if result.get("stdout"):
            jobs_model.append_log(job_id, result["stdout"], stream="stdout", step_ref=1, env=env)
        if result.get("stderr"):
            jobs_model.append_log(job_id, result["stderr"], stream="stderr", step_ref=1, env=env)

    def _spawn_background(self, target, *args, **kwargs):
        socketio = getattr(getattr(wiz.server, "app", None), "socketio", None)
        if socketio is not None and hasattr(socketio, "start_background_task"):
            socketio.start_background_task(target, *args, **kwargs)
            return
        worker = threading.Thread(target=target, args=args, kwargs=kwargs, daemon=True)
        worker.start()

    def _append_stream(self, job_id, pipe, stream_name, env=None):
        try:
            for line in iter(pipe.readline, ""):
                jobs_model.append_log(job_id, trim_output(line.rstrip("\r\n")), stream=stream_name, step_ref=1, env=env)
        finally:
            try:
                pipe.close()
            except Exception:
                pass

    def _terminate_process(self, process):
        if process.poll() is not None:
            return
        try:
            os.killpg(process.pid, signal.SIGTERM)
        except Exception:
            try:
                process.terminate()
            except Exception:
                pass

    def _run_process(self, job_id, argv, timeout_seconds, env=None):
        started = time.monotonic()
        try:
            process = subprocess.Popen(
                argv,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                bufsize=1,
                preexec_fn=os.setsid,
                close_fds=True,
            )
        except FileNotFoundError as exc:
            return {
                "status": "error",
                "exit_code": None,
                "stdout": "",
                "stderr": trim_output(str(exc)),
                "duration_ms": int((time.monotonic() - started) * 1000),
                "timed_out": False,
            }

        readers = [
            threading.Thread(target=self._append_stream, args=(job_id, process.stdout, "stdout", env), daemon=True),
            threading.Thread(target=self._append_stream, args=(job_id, process.stderr, "stderr", env), daemon=True),
        ]
        for reader in readers:
            reader.start()

        timed_out = False
        exit_code = None
        try:
            exit_code = process.wait(timeout=timeout_seconds)
        except subprocess.TimeoutExpired:
            timed_out = True
            self._terminate_process(process)
            try:
                exit_code = process.wait(timeout=5)
            except Exception:
                exit_code = None
            jobs_model.append_log(
                job_id,
                f"macro timed out after {timeout_seconds}s",
                stream="stderr",
                step_ref=1,
                env=env,
            )
        finally:
            for reader in readers:
                reader.join(timeout=2)

        duration_ms = int((time.monotonic() - started) * 1000)
        if timed_out:
            return {
                "status": "timeout",
                "exit_code": None,
                "stdout": "",
                "stderr": "",
                "duration_ms": duration_ms,
                "timed_out": True,
            }
        return {
            "status": "ok" if exit_code == 0 else "error",
            "exit_code": exit_code,
            "stdout": "",
            "stderr": "",
            "duration_ms": duration_ms,
            "timed_out": False,
        }

    def _remote_argv(self, node, command, timeout_seconds, env=None):
        credential = node.get("credential") or {}
        key_file = credential.get("key_file") or (credential.get("metadata") or {}).get("key_file")
        username = credential.get("username")
        if not username:
            raise MacroError(409, "서버 SSH 계정 정보가 없습니다. 서버를 다시 등록해주세요.", "NODE_SSH_USERNAME_MISSING")
        if not key_file:
            raise MacroError(409, "서버 SSH key file 정보가 없습니다. 서버를 다시 등록해주세요.", "NODE_SSH_KEY_MISSING")
        known_hosts = ssh_executor.prepare_known_host(node["host"], port=node.get("ssh_port"), env=env)
        argv = [
            "ssh",
            "-o",
            "BatchMode=yes",
            "-o",
            f"UserKnownHostsFile={known_hosts}",
            "-o",
            "StrictHostKeyChecking=accept-new",
            "-o",
            "LogLevel=ERROR",
            "-o",
            f"ConnectTimeout={min(timeout_seconds, 30)}",
            "-i",
            str(key_file),
            "-o",
            "IdentitiesOnly=yes",
        ]
        if node.get("ssh_port"):
            argv.extend(["-p", str(node["ssh_port"])])
        argv.extend([f"{username}@{node['host']}", shlex.join(command)])
        return argv

    def _execute_local(self, job_id, script, args, timeout_seconds, env=None):
        path = None
        try:
            with tempfile.NamedTemporaryFile("w", encoding="utf-8", suffix=".sh", prefix="docker-infra-macro-", delete=False) as handle:
                handle.write(script)
                path = handle.name
            Path(path).chmod(0o700)
            return self._run_process(job_id, ["/bin/bash", path, *args], timeout_seconds, env=env)
        finally:
            if path and Path(path).exists():
                Path(path).unlink(missing_ok=True)

    def _execute_remote(self, job_id, node, script, args, timeout_seconds, env=None):
        command = self._remote_command(script, args)
        argv = self._remote_argv(node, command, timeout_seconds, env=env)
        return self._run_process(job_id, argv, timeout_seconds, env=env)

    def _finish_job(self, job_id, macro, node, result, env=None):
        self._append_logs(job_id, result, env=env)
        result_payload = {
            "macro_id": macro["id"],
            "macro_name": macro["name"],
            "scope_type": macro["scope_type"],
            "node_id": node["id"],
            "node_name": node.get("name"),
            "status": result.get("status"),
            "exit_code": result.get("exit_code"),
            "timed_out": result.get("timed_out"),
        }
        if result.get("status") == "ok":
            jobs_model.update_step_status(job_id, 1, "succeeded", metadata=result_payload, env=env)
            jobs_model.transition_job(job_id, "succeeded", result_payload=result_payload, env=env)
            return
        jobs_model.update_step_status(job_id, 1, "failed", metadata=result_payload, env=env)
        jobs_model.transition_job(job_id, "failed", result_payload=result_payload, env=env)

    def _execute_job(self, job_id, macro, node, args, timeout_seconds, env=None):
        try:
            if node["is_local_master"]:
                result = self._execute_local(job_id, macro["script"], args, timeout_seconds, env=env)
            else:
                result = self._execute_remote(job_id, node, macro["script"], args, timeout_seconds, env=env)
        except Exception as exc:
            result = {
                "status": "error",
                "exit_code": None,
                "stdout": "",
                "stderr": trim_output(str(exc)),
                "duration_ms": 0,
                "timed_out": False,
            }
        self._finish_job(job_id, macro, node, result, env=env)

    def run(self, payload, env=None):
        payload = payload or {}
        macro_id = payload.get("macro_id")
        node_id = payload.get("node_id")
        timeout_seconds = normalize_timeout(payload.get("timeout_seconds"))

        if not macro_id:
            raise MacroError(400, "macro_id는 필수입니다.", "MACRO_ID_REQUIRED")
        if not node_id:
            raise MacroError(400, "node_id는 필수입니다.", "NODE_ID_REQUIRED")

        args = self._parse_args(payload.get("args"))
        with connect(env=env) as connection:
            with connection.cursor() as cursor:
                macro = self._fetch(cursor, macro_id)
        if not macro["enabled"]:
            raise MacroError(409, "비활성화된 매크로는 실행할 수 없습니다.", "MACRO_DISABLED")
        if macro["scope_type"] == SCOPE_NODE and macro["node_id"] != str(node_id):
            raise MacroError(409, "서버 전용 매크로는 연결된 서버에서만 실행할 수 있습니다.", "MACRO_SCOPE_MISMATCH")

        node = nodes_model.detail(node_id, env=env)
        job = jobs_model.create(
            "macro.run",
            steps=[{"name": "script.execute"}],
            requested_payload={"macro_id": macro_id, "node_id": node_id, "args": args},
            test_run_id=payload.get("test_run_id"),
            metadata={
                "macro_name": macro["name"],
                "macro_scope_type": macro["scope_type"],
                "macro_node_id": macro["node_id"],
                "node_name": node.get("name"),
                "node_host": node.get("host"),
            },
            env=env,
        )
        job_id = job["id"]
        jobs_model.transition_job(job_id, "running", env=env)
        jobs_model.update_step_status(job_id, 1, "running", metadata={"macro_id": macro_id, "node_id": node_id}, env=env)
        jobs_model.append_log(
            job_id,
            f"Run macro '{macro['name']}' on {node.get('name') or node.get('host')} with args={args}",
            stream="system",
            step_ref=1,
            env=env,
        )
        self._spawn_background(self._execute_job, job_id, macro, node, args, timeout_seconds, env)
        return jobs_model.detail(job_id, env=env)


Model = MacroRunner()
