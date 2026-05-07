import fcntl
import os
import pty
import select
import subprocess
import termios
import time


class SSHManaged:
    def _preexec_tty(self, slave_fd):
        def runner():
            os.setsid()
            fcntl.ioctl(slave_fd, termios.TIOCSCTTY, 0)
        return runner

    def _prompt_detected(self, buffer):
        text = (buffer or "").lower()
        prompts = [
            "password:",
            "password for ",
            "'s password:",
            "passphrase",
            "verification code",
            "one-time password",
            "otp:",
            "passcode:",
        ]
        return any(prompt in text for prompt in prompts)

    def interactive_password_run(self, argv, password, timeout):
        started = time.monotonic()
        master_fd, slave_fd = pty.openpty()
        output = []
        prompt_buffer = ""
        password_prompts = 0
        process = None
        try:
            process = subprocess.Popen(
                argv,
                stdin=slave_fd,
                stdout=slave_fd,
                stderr=slave_fd,
                close_fds=True,
                preexec_fn=self._preexec_tty(slave_fd),
            )
            os.close(slave_fd)
            slave_fd = None
            deadline = started + timeout

            while process.poll() is None:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    process.kill()
                    return {
                        "status": "timeout",
                        "exit_code": None,
                        "stdout": "".join(output),
                        "stderr": f"ssh command timed out after {timeout}s",
                        "duration_ms": int((time.monotonic() - started) * 1000),
                        "timed_out": True,
                    }

                readable, _, _ = select.select([master_fd], [], [], min(0.2, remaining))
                if not readable:
                    continue
                try:
                    chunk = os.read(master_fd, 4096)
                except OSError:
                    break
                if not chunk:
                    break
                text = chunk.decode("utf-8", errors="replace")
                output.append(text)
                prompt_buffer = (prompt_buffer + text)[-512:]
                if self._prompt_detected(prompt_buffer) and password_prompts < 3:
                    os.write(master_fd, f"{password}\n".encode("utf-8"))
                    password_prompts += 1
                    prompt_buffer = ""

            exit_code = process.wait(timeout=1)
            while True:
                readable, _, _ = select.select([master_fd], [], [], 0)
                if not readable:
                    break
                try:
                    chunk = os.read(master_fd, 4096)
                except OSError:
                    break
                if not chunk:
                    break
                output.append(chunk.decode("utf-8", errors="replace"))
            return {
                "status": "ok" if exit_code == 0 else "error",
                "exit_code": exit_code,
                "stdout": "".join(output),
                "stderr": "",
                "duration_ms": int((time.monotonic() - started) * 1000),
                "timed_out": False,
            }
        except FileNotFoundError as exc:
            return {
                "status": "missing",
                "exit_code": None,
                "stdout": "".join(output),
                "stderr": str(exc),
                "duration_ms": int((time.monotonic() - started) * 1000),
                "timed_out": False,
            }
        finally:
            if process is not None and process.poll() is None:
                process.kill()
            if slave_fd is not None:
                try:
                    os.close(slave_fd)
                except OSError:
                    pass
            try:
                os.close(master_fd)
            except OSError:
                pass


Model = SSHManaged()
