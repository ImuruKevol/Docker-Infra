import os
import shlex
import signal
import subprocess
import tempfile
import threading
import time
from pathlib import Path

connect = wiz.model("db/postgres").connect
operations_model = wiz.model("struct/operations")
nodes_model = wiz.model("struct/nodes")
ssh_executor = wiz.model("struct/ssh_executor")
shared = wiz.model("struct/macros_shared")
MacroError = shared.MacroError
macro_row = shared.macro_row
macro_file_row = shared.macro_file_row
normalize_script_text = shared.normalize_script_text
normalize_timeout = shared.normalize_timeout
trim_output = shared.trim_output
SCOPE_NODE = shared.SCOPE_NODE


class MacroRunner:
    MacroError = MacroError

    def _select_sql(self):
        return """
            SELECT m.*, n.name AS node_name, n.host AS node_host, COALESCE(f.files, '[]'::jsonb) AS files
            FROM shell_macros m
            LEFT JOIN nodes n ON n.id = m.node_id
            LEFT JOIN LATERAL (
                SELECT jsonb_agg(
                    jsonb_build_object(
                        'id', mf.id::text,
                        'filename', mf.filename,
                        'content_type', mf.content_type,
                        'size_bytes', mf.size_bytes,
                        'created_at', mf.created_at
                    )
                    ORDER BY lower(mf.filename), mf.created_at
                ) AS files
                FROM shell_macro_files mf
                WHERE mf.macro_id = m.id
            ) f ON true
        """

    def _fetch(self, cursor, macro_id):
        cursor.execute(
            self._select_sql() + " WHERE m.id = %s",
            (macro_id,),
        )
        row = cursor.fetchone()
        if row is None:
            raise MacroError(404, "매크로를 찾을 수 없습니다.", "MACRO_NOT_FOUND")
        return macro_row(row)

    def _fetch_files(self, cursor, macro_id):
        cursor.execute(
            """
            SELECT id, filename, content_type, size_bytes, content, created_at
            FROM shell_macro_files
            WHERE macro_id = %s
            ORDER BY lower(filename), created_at
            """,
            (macro_id,),
        )
        return [
            {
                **macro_file_row(row),
                "content": bytes(row["content"] or b""),
            }
            for row in cursor.fetchall()
        ]

    def _parse_args(self, args_text):
        if args_text in (None, ""):
            return []
        try:
            return [str(item) for item in shlex.split(str(args_text))]
        except ValueError:
            raise MacroError(400, "인자 형식이 올바르지 않습니다. 따옴표를 확인해주세요.", "INVALID_MACRO_ARGS")

    def _remote_command(self, script, args, workdir=None):
        encoded_script = shlex.quote(normalize_script_text(script))
        arg_tokens = " ".join(shlex.quote(arg) for arg in args)
        encoded_workdir = shlex.quote(workdir or "")
        return [
            "sh",
            "-lc",
            (
                "tmp=$(mktemp /tmp/docker-infra-macro.XXXXXX.sh) && "
                f"workdir={encoded_workdir} && "
                'cleanup(){ rm -f "$tmp"; if [ -n "$workdir" ]; then rm -rf -- "$workdir"; fi; }; '
                "trap cleanup EXIT; "
                f"printf '%s\\n' {encoded_script} > \"$tmp\" && "
                "chmod 700 \"$tmp\" && "
                'if [ -n "$workdir" ]; then cd "$workdir"; export DOCKER_INFRA_MACRO_DIR="$workdir" MACRO_FILES_DIR="$workdir"; fi && '
                f"/bin/bash \"$tmp\" {arg_tokens}"
            ),
        ]

    def _spawn_background(self, target, *args, **kwargs):
        socketio = getattr(getattr(wiz.server, "app", None), "socketio", None)
        if socketio is not None and hasattr(socketio, "start_background_task"):
            socketio.start_background_task(target, *args, **kwargs)
            return
        worker = threading.Thread(target=target, args=args, kwargs=kwargs, daemon=True)
        worker.start()

    def _append_output(self, operation_id, message, stream="system", env=None):
        if not message:
            return
        operations_model.append_output(operation_id, trim_output(message), stream=stream, env=env)

    def _append_stream(self, operation_id, pipe, stream_name, env=None):
        try:
            for line in iter(pipe.readline, ""):
                self._append_output(operation_id, line.rstrip("\r\n"), stream=stream_name, env=env)
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

    def _run_process(self, operation_id, argv, timeout_seconds, env=None, cwd=None, extra_env=None):
        started = time.monotonic()
        process_env = None
        if extra_env:
            process_env = os.environ.copy()
            process_env.update({key: str(value) for key, value in extra_env.items()})
        try:
            process = subprocess.Popen(
                argv,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                bufsize=1,
                preexec_fn=os.setsid,
                close_fds=True,
                cwd=cwd,
                env=process_env,
            )
        except FileNotFoundError as exc:
            self._append_output(operation_id, str(exc), stream="stderr", env=env)
            return {
                "status": "error",
                "exit_code": None,
                "duration_ms": int((time.monotonic() - started) * 1000),
                "timed_out": False,
            }

        readers = [
            threading.Thread(target=self._append_stream, args=(operation_id, process.stdout, "stdout", env), daemon=True),
            threading.Thread(target=self._append_stream, args=(operation_id, process.stderr, "stderr", env), daemon=True),
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
            self._append_output(operation_id, f"macro timed out after {timeout_seconds}s", stream="stderr", env=env)
        finally:
            for reader in readers:
                reader.join(timeout=2)

        duration_ms = int((time.monotonic() - started) * 1000)
        if timed_out:
            return {"status": "timeout", "exit_code": exit_code, "duration_ms": duration_ms, "timed_out": True}
        return {
            "status": "ok" if exit_code == 0 else "error",
            "exit_code": exit_code,
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

    def _operation_workdir_name(self, operation_id):
        raw = str(operation_id or "run")
        safe = "".join(ch if ch.isalnum() or ch in {"-", "_"} else "-" for ch in raw)
        return f"docker-infra-macro-{safe}"

    def _append_file_transfer_summary(self, operation_id, macro_files, location, env=None):
        if not macro_files:
            return
        names = ", ".join(item["filename"] for item in macro_files[:5])
        if len(macro_files) > 5:
            names += f" 외 {len(macro_files) - 5}개"
        self._append_output(operation_id, f"Attached files copied to {location}: {names}", stream="system", env=env)

    def _write_local_macro_files(self, workdir, macro_files):
        base = Path(workdir)
        for item in macro_files or []:
            target = (base / item["filename"]).resolve()
            if target.parent != base:
                raise MacroError(400, "첨부 파일 이름이 올바르지 않습니다.", "MACRO_FILE_NAME_INVALID")
            target.write_bytes(item.get("content") or b"")

    def _write_remote_macro_files(self, operation_id, node, macro_files, env=None):
        if not macro_files:
            return None
        workdir = f"/tmp/{self._operation_workdir_name(operation_id)}"
        for item in macro_files:
            target = f"{workdir}/{item['filename']}"
            nodes_model.write_file_bytes(node["id"], target, item.get("content") or b"", env=env)
        return workdir

    def _execute_local(self, operation_id, script, args, timeout_seconds, macro_files=None, env=None):
        path = None
        try:
            with tempfile.NamedTemporaryFile("w", encoding="utf-8", suffix=".sh", prefix="docker-infra-macro-", delete=False) as handle:
                handle.write(normalize_script_text(script))
                path = handle.name
            Path(path).chmod(0o700)
            if macro_files:
                with tempfile.TemporaryDirectory(prefix=f"{self._operation_workdir_name(operation_id)}-") as workdir:
                    self._write_local_macro_files(workdir, macro_files)
                    self._append_file_transfer_summary(operation_id, macro_files, workdir, env=env)
                    return self._run_process(
                        operation_id,
                        ["/bin/bash", path, *args],
                        timeout_seconds,
                        env=env,
                        cwd=workdir,
                        extra_env={"DOCKER_INFRA_MACRO_DIR": workdir, "MACRO_FILES_DIR": workdir},
                    )
            return self._run_process(operation_id, ["/bin/bash", path, *args], timeout_seconds, env=env)
        finally:
            if path and Path(path).exists():
                Path(path).unlink(missing_ok=True)

    def _execute_remote(self, operation_id, node, script, args, timeout_seconds, macro_files=None, env=None):
        workdir = self._write_remote_macro_files(operation_id, node, macro_files or [], env=env)
        if workdir:
            self._append_file_transfer_summary(operation_id, macro_files or [], workdir, env=env)
        command = self._remote_command(script, args, workdir=workdir)
        argv = self._remote_argv(node, command, timeout_seconds, env=env)
        return self._run_process(operation_id, argv, timeout_seconds, env=env)

    def _finish_operation(self, operation_id, macro, node, result, env=None):
        result_payload = {
            "macro_id": macro["id"],
            "macro_name": macro["name"],
            "scope_type": macro["scope_type"],
            "file_count": macro.get("file_count", 0),
            "node_id": node["id"],
            "node_name": node.get("name"),
            "status": result.get("status"),
            "exit_code": result.get("exit_code"),
            "duration_ms": result.get("duration_ms"),
            "timed_out": result.get("timed_out"),
        }
        if result.get("status") == "ok":
            operations_model.transition(
                operation_id,
                "succeeded",
                message="매크로 실행이 완료되었습니다.",
                result_payload=result_payload,
                env=env,
            )
            return
        operations_model.transition(
            operation_id,
            "failed",
            message="매크로 실행에 실패했습니다.",
            result_payload=result_payload,
            env=env,
        )

    def _execute_operation(self, operation_id, macro, node, args, timeout_seconds, macro_files=None, env=None):
        try:
            if node["is_local_master"]:
                result = self._execute_local(operation_id, macro["script"], args, timeout_seconds, macro_files=macro_files, env=env)
            else:
                result = self._execute_remote(operation_id, node, macro["script"], args, timeout_seconds, macro_files=macro_files, env=env)
        except Exception as exc:
            self._append_output(operation_id, str(exc), stream="stderr", env=env)
            result = {"status": "error", "exit_code": None, "duration_ms": 0, "timed_out": False}
        self._finish_operation(operation_id, macro, node, result, env=env)

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
                macro_files = self._fetch_files(cursor, macro_id)
        if not macro["enabled"]:
            raise MacroError(409, "비활성화된 매크로는 실행할 수 없습니다.", "MACRO_DISABLED")
        if macro["scope_type"] == SCOPE_NODE and macro["node_id"] != str(node_id):
            raise MacroError(409, "서버 전용 매크로는 연결된 서버에서만 실행할 수 있습니다.", "MACRO_SCOPE_MISMATCH")

        node = nodes_model.detail(node_id, env=env)
        operation = operations_model.create(
            "macro.run",
            target_type="node",
            target_id=node_id,
            message="매크로 실행을 시작했습니다.",
            requested_payload={
                "macro_id": macro_id,
                "node_id": node_id,
                "args": args,
                "files": [{key: item[key] for key in ("id", "filename", "content_type", "size_bytes", "created_at")} for item in macro_files],
            },
            test_run_id=payload.get("test_run_id"),
            metadata={
                "macro_name": macro["name"],
                "macro_scope_type": macro["scope_type"],
                "macro_node_id": macro["node_id"],
                "macro_file_count": len(macro_files),
                "node_name": node.get("name"),
                "node_host": node.get("host"),
            },
            env=env,
        )
        operation_id = operation["id"]
        self._append_output(
            operation_id,
            f"Run macro '{macro['name']}' on {node.get('name') or node.get('host')} with args={args}",
            stream="system",
            env=env,
        )
        self._spawn_background(self._execute_operation, operation_id, macro, node, args, timeout_seconds, macro_files, env)
        return operations_model.detail(operation_id, env=env)


Model = MacroRunner()
