import shlex
from pathlib import Path, PurePosixPath


shared = wiz.model("struct/nodes_shared")
_load_json = shared.load_json
NodeError = shared.NodeError


class NodeRuntimeFilesMixin:
    def _normalize_browse_path(self, value):
        path = str(PurePosixPath(value or "/"))
        return path if path.startswith("/") else f"/{path}"

    def _default_browse_path(self, node, env=None):
        if node["is_local_master"]:
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
            return self._default_browse_path(node, env=env)
        if raw.startswith("~/"):
            home = self._default_browse_path(node, env=env).rstrip("/")
            suffix = raw[2:].strip("/")
            return self._normalize_browse_path(f"{home}/{suffix}") if suffix else home or "/"
        return self._normalize_browse_path(raw)

    def _remote_list_dir(self, node, path, env=None):
        quoted = shlex.quote(path)
        script = f'base={quoted}; [ -d "$base" ] || exit 44; printf "%s\\n" "$base"; find "$base" -mindepth 1 -maxdepth 1 -printf "%f\\t%y\\t%s\\n" 2>/dev/null | sort'
        result = self._run_ssh_command(node, ["sh", "-lc", script], timeout_seconds=8, env=env)
        if result["status"] != "ok":
            raise NodeError(404, "선택한 경로를 열 수 없습니다.", "NODE_PATH_NOT_FOUND", check=result)
        lines = (result["stdout"] or "").splitlines()
        current = lines[0] if lines else path
        items = []
        for line in lines[1:]:
            name, entry_type, size = (line.split("\t", 2) + ["", "", ""])[:3]
            item_path = f"{current.rstrip('/')}/{name}" if current != "/" else f"/{name}"
            items.append({"name": name, "path": item_path, "type": "folder" if entry_type == "d" else "file", "size": int(size or 0)})
        return {"path": current, "items": items}

    def browse_files(self, node_id, payload=None, env=None):
        payload = payload or {}
        node, _ = self._target_node(node_id, env=env)
        path = self._resolve_browse_path(node, payload.get("path"), env=env)
        if node["is_local_master"]:
            result = self.local_executor.run("filesystem.list", params={"path": path}, timeout_seconds=8, env=env)
            if result["status"] != "ok":
                raise NodeError(404, "선택한 경로를 열 수 없습니다.", "NODE_PATH_NOT_FOUND", check=result)
            data = _load_json(result["stdout"])
        else:
            data = self._remote_list_dir(node, path, env=env)
        current = data.get("path") or path
        parent = str(PurePosixPath(current).parent) if current != "/" else None
        show_hidden = str(payload.get("show_hidden") or "").strip().lower() in {"1", "true", "yes", "on"}
        items = data.get("items") or []
        if not show_hidden:
            items = [item for item in items if not str(item.get("name") or "").startswith(".")]
        return {"path": current, "parent": None if parent == current else parent, "items": items}

    def read_file_text(self, node_id, path, env=None):
        path = self._normalize_browse_path(path)
        node, _ = self._target_node(node_id, env=env)
        if node["is_local_master"]:
            result = self.local_executor.run("filesystem.read", params={"path": path}, timeout_seconds=8, env=env)
        else:
            quoted = shlex.quote(path)
            result = self._run_ssh_command(node, ["sh", "-lc", f'[ -f {quoted} ] || exit 44; cat -- {quoted}'], timeout_seconds=8, env=env)
        if result["status"] != "ok":
            raise NodeError(404, "선택한 파일을 읽을 수 없습니다.", "NODE_FILE_READ_FAILED", check=result)
        return result["stdout"]


Model = NodeRuntimeFilesMixin
