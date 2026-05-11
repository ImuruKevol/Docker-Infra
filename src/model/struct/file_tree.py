import os
import shutil
import time
from pathlib import Path, PurePosixPath


connect = wiz.model("db/postgres").connect
config = wiz.config("docker_infra")
nodes = wiz.model("struct/nodes")
FILE_TREE_LIST_LIMIT = 5000


class FileTreeError(Exception):
    def __init__(self, status_code, message, error_code, **extra):
        super().__init__(message)
        self.status_code = status_code
        self.message = message
        self.error_code = error_code
        self.extra = extra


def _text(value):
    return str(value or "").strip()


def _safe_relative(value):
    raw = _text(value)
    if raw in {"", "."}:
        return PurePosixPath(".")
    path = PurePosixPath(raw)
    if path.is_absolute() or any(part in {"..", ""} for part in path.parts):
        raise FileTreeError(400, "경로가 올바르지 않습니다.", "FILE_TREE_PATH_INVALID")
    return path


def _safe_name(value):
    name = _text(value).strip("/")
    if not name or "/" in name or name in {".", ".."}:
        raise FileTreeError(400, "이름이 올바르지 않습니다.", "FILE_TREE_NAME_INVALID")
    return name


def _show_hidden(context):
    return str((context or {}).get("show_hidden") or "").strip().lower() in {"1", "true", "yes", "on"}


def _list_limit(context):
    try:
        value = int((context or {}).get("limit") or FILE_TREE_LIST_LIMIT)
    except Exception:
        value = FILE_TREE_LIST_LIMIT
    return max(100, min(value, 20000))


class FileTree:
    FileTreeError = FileTreeError

    def _node_id(self, context):
        node_id = _text((context or {}).get("node_id"))
        if not node_id:
            raise FileTreeError(400, "node_id가 필요합니다.", "NODE_ID_REQUIRED")
        return node_id

    def _local_root(self, scope, context, env=None):
        context = context or {}
        if scope == "service":
            service_id = _text(context.get("service_id"))
            if not service_id:
                raise FileTreeError(400, "service_id가 필요합니다.", "SERVICE_ID_REQUIRED")
            with connect(env=env) as connection:
                with connection.cursor() as cursor:
                    cursor.execute("SELECT compose_path FROM services WHERE id = %s", (service_id,))
                    row = cursor.fetchone()
            if row is None:
                raise FileTreeError(404, "서비스를 찾을 수 없습니다.", "SERVICE_NOT_FOUND")
            return Path(row["compose_path"]).expanduser().resolve().parent
        if scope == "image":
            root = Path(config.data_dir(env)) / "image-files"
            root.mkdir(parents=True, exist_ok=True)
            return root.resolve()
        raise FileTreeError(400, "지원하지 않는 파일 트리 범위입니다.", "FILE_TREE_SCOPE_INVALID")

    def _resolve_local(self, scope, context, relative_path="", env=None):
        root = self._local_root(scope, context, env=env)
        relative = _safe_relative(relative_path)
        target = root if str(relative) == "." else (root / relative).resolve()
        if target != root and not target.is_relative_to(root):
            raise FileTreeError(400, "허용된 루트 밖의 경로에는 접근할 수 없습니다.", "FILE_TREE_PATH_OUTSIDE_ROOT")
        return root, target

    def _node_path(self, path, default=""):
        value = _text(path)
        if not value or value == ".":
            return default
        if value == "~" or value.startswith("~/"):
            return value
        return value if value.startswith("/") else f"/{value}"

    def list(self, payload, env=None):
        body = payload or {}
        scope = _text(body.get("scope"))
        context = body.get("context") or {}
        list_context = {**context, "limit": context.get("limit") or body.get("limit")}
        path = body.get("path")
        if scope == "node":
            return nodes.browse_files(
                self._node_id(context),
                {"path": self._node_path(path), "show_hidden": context.get("show_hidden"), "limit": list_context.get("limit")},
                env=env,
            )
        root, target = self._resolve_local(scope, context, path, env=env)
        if not target.exists():
            raise FileTreeError(404, "선택한 경로를 찾을 수 없습니다.", "FILE_TREE_PATH_NOT_FOUND")
        if not target.is_dir():
            raise FileTreeError(400, "폴더만 열 수 있습니다.", "FILE_TREE_PATH_NOT_DIRECTORY")
        items = []
        show_hidden = _show_hidden(list_context)
        limit = _list_limit(list_context)
        started = time.monotonic()
        total_count = 0
        with os.scandir(target) as entries:
            for entry in entries:
                if not show_hidden and entry.name.startswith("."):
                    continue
                total_count += 1
                try:
                    is_dir = entry.is_dir(follow_symlinks=False)
                    size = 0 if is_dir else entry.stat(follow_symlinks=False).st_size
                except OSError:
                    is_dir = False
                    size = 0
                child = Path(entry.path)
                items.append({
                    "name": entry.name,
                    "path": "." if child == root else child.relative_to(root).as_posix(),
                    "type": "folder" if is_dir else "file",
                    "size": size,
                    "protected": False,
                })
        items.sort(key=lambda item: (item["type"] != "folder", item["name"].lower()))
        truncated = len(items) > limit
        if truncated:
            items = items[:limit]
        current = "." if target == root else target.relative_to(root).as_posix()
        parent = None if target == root else ("." if target.parent == root else target.parent.relative_to(root).as_posix())
        return {
            "path": current,
            "parent": parent,
            "items": items,
            "root": str(root),
            "total_count": total_count,
            "truncated": truncated,
            "limit": limit,
            "duration_ms": int((time.monotonic() - started) * 1000),
        }

    def read(self, payload, env=None):
        body = payload or {}
        scope = _text(body.get("scope"))
        context = body.get("context") or {}
        path = body.get("path")
        if scope == "node":
            content = nodes.read_file_text(self._node_id(context), self._node_path(path), env=env)
            return {"path": self._node_path(path), "content": content}
        _, target = self._resolve_local(scope, context, path, env=env)
        if not target.is_file():
            raise FileTreeError(404, "선택한 파일을 찾을 수 없습니다.", "FILE_TREE_FILE_NOT_FOUND")
        return {"path": _text(path), "content": target.read_text(encoding="utf-8")}

    def mutate(self, payload, env=None):
        body = payload or {}
        scope = _text(body.get("scope"))
        action = _text(body.get("action"))
        context = body.get("context") or {}
        path = body.get("path")
        if scope == "node":
            node_id = self._node_id(context)
            if action == "mkdir":
                return nodes.make_directory(node_id, self._node_path(path), env=env)
            if action == "rename":
                return nodes.rename_path(node_id, self._node_path(path), body.get("new_name"), env=env)
            if action == "delete":
                return nodes.delete_path(node_id, self._node_path(path), env=env)
            if action == "move":
                return nodes.move_path(node_id, self._node_path(path), self._node_path(body.get("destination")), env=env)
            raise FileTreeError(400, "지원하지 않는 파일 작업입니다.", "FILE_TREE_ACTION_INVALID")

        root, target = self._resolve_local(scope, context, path, env=env)
        if action == "mkdir":
            target.mkdir(parents=True, exist_ok=True)
            return {"path": "." if target == root else target.relative_to(root).as_posix()}
        if action == "rename":
            name = _safe_name(body.get("new_name"))
            renamed = target.with_name(name)
            if not target.exists():
                raise FileTreeError(404, "변경할 파일을 찾을 수 없습니다.", "FILE_TREE_PATH_NOT_FOUND")
            target.rename(renamed)
            return {"path": renamed.relative_to(root).as_posix()}
        if action == "delete":
            if target == root:
                raise FileTreeError(400, "루트 폴더는 삭제할 수 없습니다.", "FILE_TREE_ROOT_DELETE_FORBIDDEN")
            if target.is_dir():
                shutil.rmtree(target)
            elif target.exists():
                target.unlink()
            return {"deleted": True, "path": _text(path)}
        if action == "move":
            destination_rel = _safe_relative(body.get("destination"))
            destination = root if str(destination_rel) == "." else (root / destination_rel).resolve()
            if destination != root and not destination.is_relative_to(root):
                raise FileTreeError(400, "이동할 폴더가 허용 범위를 벗어났습니다.", "FILE_TREE_PATH_OUTSIDE_ROOT")
            if not destination.is_dir():
                raise FileTreeError(400, "파일을 이동할 대상 폴더를 찾을 수 없습니다.", "FILE_TREE_DESTINATION_INVALID")
            moved = destination / target.name
            target.rename(moved)
            return {"path": moved.relative_to(root).as_posix()}
        raise FileTreeError(400, "지원하지 않는 파일 작업입니다.", "FILE_TREE_ACTION_INVALID")

    def upload(self, scope, context, destination, file_storages, env=None):
        context = context or {}
        destination = destination or "."
        saved = []
        if scope == "node":
            node_id = self._node_id(context)
            base = PurePosixPath(self._node_path(destination))
            for storage in file_storages:
                rel = _safe_relative(storage.filename)
                target = str(base / rel)
                content = storage.read()
                nodes.write_file_bytes(node_id, target, content, env=env)
                saved.append({"path": target, "size": len(content)})
            return {"uploaded": saved, "count": len(saved)}

        root, target_dir = self._resolve_local(scope, context, destination, env=env)
        target_dir.mkdir(parents=True, exist_ok=True)
        for storage in file_storages:
            rel = _safe_relative(storage.filename)
            target = (target_dir / rel).resolve()
            if target != root and not target.is_relative_to(root):
                raise FileTreeError(400, "업로드 경로가 허용 범위를 벗어났습니다.", "FILE_TREE_PATH_OUTSIDE_ROOT")
            target.parent.mkdir(parents=True, exist_ok=True)
            storage.save(str(target))
            saved.append({"path": target.relative_to(root).as_posix(), "size": target.stat().st_size})
        return {"uploaded": saved, "count": len(saved)}


Model = FileTree()
