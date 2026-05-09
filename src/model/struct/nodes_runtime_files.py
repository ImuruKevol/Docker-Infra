import base64
import json
import os
import posixpath
import shutil
import shlex
import time
from pathlib import Path, PurePosixPath


shared = wiz.model("struct/nodes_shared")
_load_json = shared.load_json
NodeError = shared.NodeError

PROTECTED_SYSTEM_PATHS = {
    "/",
    "/bin",
    "/boot",
    "/cdrom",
    "/dev",
    "/etc",
    "/home",
    "/lib",
    "/lib32",
    "/lib64",
    "/libx32",
    "/lost+found",
    "/media",
    "/mnt",
    "/opt",
    "/proc",
    "/root",
    "/run",
    "/sbin",
    "/snap",
    "/srv",
    "/sys",
    "/tmp",
    "/usr",
    "/var",
}
PROTECTED_SYSTEM_PREFIXES = {"/dev", "/proc", "/run", "/sys"}
FILE_LIST_LIMIT = 5000


def _show_hidden_value(value):
    return str(value or "").strip().lower() in {"1", "true", "yes", "on"}


def _list_limit(value):
    try:
        limit = int(value)
    except Exception:
        limit = FILE_LIST_LIMIT
    return max(100, min(limit, 20000))


class NodeRuntimeFilesMixin:
    def _is_local_master_node(self, node):
        return bool(node.get("is_local_master") or node.get("role") == "local_master" or node.get("name") == "local-master")

    def _normalize_browse_path(self, value):
        path = str(PurePosixPath(value or "/"))
        path = path if path.startswith("/") else f"/{path}"
        return posixpath.normpath(path)

    def _is_protected_system_path(self, value):
        path = self._normalize_browse_path(value).rstrip("/") or "/"
        if path in PROTECTED_SYSTEM_PATHS:
            return True
        return any(path == prefix or path.startswith(f"{prefix}/") for prefix in PROTECTED_SYSTEM_PREFIXES)

    def _assert_mutable_path(self, value, action):
        if not self._is_protected_system_path(value):
            return
        raise NodeError(
            403,
            "시스템 보호 경로는 이름 변경, 이동, 삭제할 수 없습니다.",
            "NODE_SYSTEM_PATH_PROTECTED",
            path=self._normalize_browse_path(value),
            action=action,
        )

    def _decorate_file_items(self, items):
        rows = []
        for item in items or []:
            item_path = item.get("path") or item.get("name") or ""
            rows.append({**item, "protected": self._is_protected_system_path(item_path)})
        return rows

    def _default_browse_path(self, node, env=None):
        if self._is_local_master_node(node):
            return self._normalize_browse_path(str(Path.home()))
        credential = node.get("credential") or {}
        username = str(credential.get("username") or "").strip()
        result = self._run_ssh_command(node, ["sh", "-lc", 'printf "%s\\n" "$HOME"'], timeout_seconds=5, env=env)
        if result.get("status") == "ok":
            home = str(result.get("stdout") or "").strip()
            if home:
                return self._normalize_browse_path(home.splitlines()[-1])
        if username == "root":
            return "/root"
        if username:
            return self._normalize_browse_path(f"/home/{username}")
        return "/"

    def _resolve_browse_path(self, node, value, env=None):
        raw = str(value or "").strip()
        if not raw or raw == "~":
            if not self._is_local_master_node(node):
                return "~"
            return self._default_browse_path(node, env=env)
        if raw.startswith("~/"):
            if not self._is_local_master_node(node):
                return raw
            home = self._default_browse_path(node, env=env).rstrip("/")
            suffix = raw[2:].strip("/")
            return self._normalize_browse_path(f"{home}/{suffix}") if suffix else home or "/"
        return self._normalize_browse_path(raw)

    def _list_local_dir(self, path, show_hidden=False, limit=FILE_LIST_LIMIT):
        started = time.monotonic()
        base = os.path.abspath(os.path.expanduser(path or "/"))
        if not os.path.isdir(base):
            raise NodeError(404, "선택한 경로를 열 수 없습니다.", "NODE_PATH_NOT_FOUND", path=base)
        items = []
        total_count = 0
        try:
            iterator = os.scandir(base)
        except OSError as exc:
            raise NodeError(404, "선택한 경로를 열 수 없습니다.", "NODE_PATH_NOT_FOUND", path=base, reason=str(exc))
        with iterator:
            for entry in iterator:
                name = entry.name
                if not show_hidden and name.startswith("."):
                    continue
                total_count += 1
                try:
                    is_dir = entry.is_dir(follow_symlinks=False)
                    size = 0 if is_dir else entry.stat(follow_symlinks=False).st_size
                except OSError:
                    is_dir = False
                    size = 0
                entry_path = os.path.join(base, name) if base != "/" else "/" + name
                items.append({
                    "name": name,
                    "path": entry_path,
                    "type": "folder" if is_dir else "file",
                    "size": size,
                })
        items.sort(key=lambda item: (item["type"] != "folder", item["name"].lower()))
        truncated = len(items) > limit
        if truncated:
            items = items[:limit]
        return {
            "path": base,
            "items": items,
            "total_count": total_count,
            "truncated": truncated,
            "limit": limit,
            "duration_ms": int((time.monotonic() - started) * 1000),
        }

    def _remote_list_dir(self, node, path, show_hidden=False, limit=FILE_LIST_LIMIT, env=None):
        script = """
import json
import os
import sys
import time

base = os.path.abspath(os.path.expanduser(sys.argv[1] or "/"))
show_hidden = sys.argv[2] == "1"
limit = int(sys.argv[3] or "5000")
started = time.monotonic()
if not os.path.isdir(base):
    sys.exit(44)

items = []
total_count = 0
try:
    iterator = os.scandir(base)
except OSError:
    sys.exit(44)

with iterator:
    for entry in iterator:
        if not show_hidden and entry.name.startswith("."):
            continue
        total_count += 1
        try:
            is_dir = entry.is_dir(follow_symlinks=False)
            size = 0 if is_dir else entry.stat(follow_symlinks=False).st_size
        except OSError:
            is_dir = False
            size = 0
        entry_path = os.path.join(base, entry.name) if base != "/" else "/" + entry.name
        items.append({
            "name": entry.name,
            "path": entry_path,
            "type": "folder" if is_dir else "file",
            "size": size,
        })

items.sort(key=lambda item: (item["type"] != "folder", item["name"].lower()))
truncated = len(items) > limit
if truncated:
    items = items[:limit]
print(json.dumps({"path": base, "items": items, "total_count": total_count, "truncated": truncated, "limit": limit, "duration_ms": int((time.monotonic() - started) * 1000)}, ensure_ascii=False))
""".strip()
        result = self._run_ssh_command(node, ["python3", "-c", script, path, "1" if show_hidden else "0", str(limit)], timeout_seconds=8, env=env)
        if result["status"] != "ok":
            raise NodeError(404, "선택한 경로를 열 수 없습니다.", "NODE_PATH_NOT_FOUND", check=result)
        try:
            data = json.loads(result.get("stdout") or "{}")
            data["ssh_duration_ms"] = result.get("duration_ms")
            return data
        except Exception:
            raise NodeError(404, "선택한 경로를 열 수 없습니다.", "NODE_PATH_NOT_FOUND", check=result)

    def browse_files(self, node_id, payload=None, env=None):
        payload = payload or {}
        node, _ = self._target_node(node_id, env=env)
        path = self._resolve_browse_path(node, payload.get("path"), env=env)
        show_hidden = _show_hidden_value(payload.get("show_hidden"))
        limit = _list_limit(payload.get("limit"))
        if self._is_local_master_node(node):
            data = self._list_local_dir(path, show_hidden=show_hidden, limit=limit)
        else:
            data = self._remote_list_dir(node, path, show_hidden=show_hidden, limit=limit, env=env)
        current = data.get("path") or path
        parent = str(PurePosixPath(current).parent) if current != "/" else None
        items = data.get("items") or []
        items = self._decorate_file_items(items)
        return {
            "path": current,
            "parent": None if parent == current else parent,
            "items": items,
            "total_count": data.get("total_count", len(items)),
            "truncated": bool(data.get("truncated")),
            "limit": data.get("limit", limit),
            "duration_ms": data.get("duration_ms"),
            "ssh_duration_ms": data.get("ssh_duration_ms"),
        }

    def read_file_text(self, node_id, path, env=None):
        path = self._normalize_browse_path(path)
        node, _ = self._target_node(node_id, env=env)
        if self._is_local_master_node(node):
            result = self.local_executor.run("filesystem.read", params={"path": path}, timeout_seconds=8, env=env)
        else:
            quoted = shlex.quote(path)
            result = self._run_ssh_command(node, ["sh", "-lc", f'[ -f {quoted} ] || exit 44; cat -- {quoted}'], timeout_seconds=8, env=env)
        if result["status"] != "ok":
            raise NodeError(404, "선택한 파일을 읽을 수 없습니다.", "NODE_FILE_READ_FAILED", check=result)
        return result["stdout"]

    def _remote_mutation_result(self, result, message, error_code):
        if result["status"] != "ok":
            raise NodeError(409, message, error_code, check=result)
        return {"status": result.get("status"), "exit_code": result.get("exit_code")}

    def write_file_bytes(self, node_id, path, content, env=None):
        path = self._normalize_browse_path(path)
        node, _ = self._target_node(node_id, env=env)
        payload = base64.b64encode(content or b"").decode("ascii")
        if self._is_local_master_node(node):
            target = Path(path).expanduser().resolve()
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(content or b"")
            return {"path": str(target), "size": target.stat().st_size}
        quoted_path = shlex.quote(path)
        quoted_parent = shlex.quote(str(PurePosixPath(path).parent))
        script = (
            f"mkdir -p {quoted_parent}; "
            f"cat <<'__DOCKER_INFRA_FILE__' | base64 -d > {quoted_path}\n"
            f"{payload}\n"
            "__DOCKER_INFRA_FILE__"
        )
        result = self._run_ssh_command(node, ["sh", "-lc", script], timeout_seconds=60, env=env)
        self._remote_mutation_result(result, "파일을 업로드할 수 없습니다.", "NODE_FILE_UPLOAD_FAILED")
        return {"path": path, "size": len(content or b"")}

    def make_directory(self, node_id, path, env=None):
        path = self._normalize_browse_path(path)
        node, _ = self._target_node(node_id, env=env)
        if self._is_local_master_node(node):
            target = Path(path).expanduser().resolve()
            target.mkdir(parents=True, exist_ok=True)
            return {"path": str(target)}
        result = self._run_ssh_command(node, ["mkdir", "-p", path], timeout_seconds=10, env=env)
        self._remote_mutation_result(result, "폴더를 만들 수 없습니다.", "NODE_FOLDER_CREATE_FAILED")
        return {"path": path}

    def rename_path(self, node_id, path, new_name, env=None):
        path = self._normalize_browse_path(path)
        name = str(new_name or "").strip().strip("/")
        if not name or "/" in name or name in {".", ".."}:
            raise NodeError(400, "새 이름이 올바르지 않습니다.", "NODE_FILE_NAME_INVALID")
        target_path = str(PurePosixPath(path).with_name(name))
        self._assert_mutable_path(path, "rename")
        self._assert_mutable_path(target_path, "rename")
        node, _ = self._target_node(node_id, env=env)
        if self._is_local_master_node(node):
            source = Path(path).expanduser().resolve()
            target = source.with_name(name)
            source.rename(target)
            return {"path": str(target)}
        result = self._run_ssh_command(node, ["mv", "--", path, target_path], timeout_seconds=20, env=env)
        self._remote_mutation_result(result, "이름을 변경할 수 없습니다.", "NODE_FILE_RENAME_FAILED")
        return {"path": target_path}

    def delete_path(self, node_id, path, env=None):
        path = self._normalize_browse_path(path)
        self._assert_mutable_path(path, "delete")
        node, _ = self._target_node(node_id, env=env)
        if self._is_local_master_node(node):
            target = Path(path).expanduser().resolve()
            if target.is_dir():
                shutil.rmtree(target)
            elif target.exists():
                target.unlink()
            return {"deleted": True, "path": str(target)}
        result = self._run_ssh_command(node, ["rm", "-rf", "--", path], timeout_seconds=30, env=env)
        self._remote_mutation_result(result, "삭제할 수 없습니다.", "NODE_FILE_DELETE_FAILED")
        return {"deleted": True, "path": path}

    def move_path(self, node_id, path, destination, env=None):
        path = self._normalize_browse_path(path)
        destination = self._normalize_browse_path(destination)
        target_path = str(PurePosixPath(destination) / PurePosixPath(path).name)
        self._assert_mutable_path(path, "move")
        self._assert_mutable_path(destination, "move")
        self._assert_mutable_path(target_path, "move")
        node, _ = self._target_node(node_id, env=env)
        if self._is_local_master_node(node):
            source = Path(path).expanduser().resolve()
            target_dir = Path(destination).expanduser().resolve()
            target_dir.mkdir(parents=True, exist_ok=True)
            target = target_dir / source.name
            source.rename(target)
            return {"path": str(target)}
        result = self._run_ssh_command(node, ["sh", "-lc", f"mkdir -p {shlex.quote(destination)} && mv -- {shlex.quote(path)} {shlex.quote(target_path)}"], timeout_seconds=30, env=env)
        self._remote_mutation_result(result, "파일을 이동할 수 없습니다.", "NODE_FILE_MOVE_FAILED")
        return {"path": target_path}


Model = NodeRuntimeFilesMixin
