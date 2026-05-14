import json
import re
import shlex
import subprocess
import time
import uuid
from pathlib import Path

from psycopg.types.json import Jsonb


connect = wiz.model("db/postgres").connect
config = wiz.config("docker_infra")
nodes = wiz.model("struct/nodes")
local_executor = wiz.model("struct/local_executor")
local_catalog = wiz.model("struct/local_command_catalog")
harbor = wiz.model("struct/images_harbor")
shared = wiz.model("struct/images_shared")
ImageError = shared.ImageError
parse_docker_image_lines = shared.parse_docker_image_lines
parse_docker_container_inspect_lines = shared.parse_docker_container_inspect_lines
parse_size_bytes = shared.parse_size_bytes
serialize = shared.serialize

DEFAULT_DOCKER_IMAGE_COMMAND = ["docker", "image", "ls", "--digests", "--no-trunc", "--format", "{{json .}}"]
DOCKER_IMAGE_USAGE_COMMAND = [
    "sh",
    "-lc",
    "ids=$(docker container ls -aq --no-trunc); if [ -z \"$ids\" ]; then exit 0; fi; docker inspect --format '{{json .}}' $ids",
]
DOCKER_IMAGE_STORAGE_COMMAND = ["python3", "-c", local_catalog.DOCKER_IMAGE_STORAGE_SCRIPT]
DOCKER_IMAGE_DELETE_ESTIMATE_COMMAND = ["python3", "-c", local_catalog.DOCKER_IMAGE_DELETE_ESTIMATE_SCRIPT]
DOCKER_PRUNE_ESTIMATE_COMMAND = ["python3", "-c", local_catalog.DOCKER_PRUNE_ESTIMATE_SCRIPT]
DOCKER_IMAGE_PRUNE_COMMAND = ["docker", "image", "prune", "-a", "-f"]
IMAGE_ARCHIVE_EXTENSIONS = (".tar", ".tar.gz", ".tgz")
IMAGE_IMPORT_TIMEOUT_SECONDS = 1800
REMOTE_IMAGE_IMPORT_DIR = "/tmp/docker-infra-image-imports"


class ImagesLocalMixin:
    def _is_local_master_node(self, node):
        return bool(node.get("is_local_master") or node.get("role") == "local_master" or node.get("name") == "local-master")

    def _image_known_refs(self, item):
        repository = str(item.get("repository") or "").strip()
        tag = str(item.get("tag") or "").strip()
        digest = str(item.get("digest") or "").strip()
        image_id = str(item.get("image_id") or "").strip()
        tag_ref = f"{repository}:{tag}" if repository not in {"", "<none>"} and tag not in {"", "<none>"} else ""
        digest_ref = f"{repository}@{digest}" if repository not in {"", "<none>"} and digest else ""
        tag_digest_ref = f"{repository}:{tag}@{digest}" if tag_ref and digest else ""
        return [value for value in [tag_digest_ref, digest_ref, image_id, tag_ref, item.get("remove_ref")] if value]

    def _image_ref_candidates(self, node, image_ref, env=None):
        requested = str(image_ref or "").strip()
        if not requested:
            return []
        candidates = [requested]
        try:
            result = self._run_node_command(node, env=env)
            items = parse_docker_image_lines(result.get("stdout")) if result.get("status") == "ok" else []
        except Exception:
            items = []
        for item in items:
            known = set(self._image_known_refs(item))
            if requested not in known:
                continue
            for value in self._image_known_refs(item):
                if value:
                    candidates.append(value)
        deduped = []
        seen = set()
        for value in candidates:
            if value in seen:
                continue
            seen.add(value)
            deduped.append(value)
        return deduped

    def _image_not_found(self, result):
        output = str(result.get("stderr") or result.get("stdout") or "").lower()
        return "no such image" in output or "image not known" in output

    def _remove_image_with_fallbacks(self, node, image_ref, env=None):
        last_result = None
        for candidate in self._image_ref_candidates(node, image_ref, env=env):
            result = self._run_node_command(node, remove_ref=candidate, env=env)
            if result.get("status") == "ok":
                return result, candidate
            last_result = result
            if not self._image_not_found(result):
                break
        return last_result or {"status": "error", "stderr": "이미지 참조를 확인할 수 없습니다."}, image_ref

    def _decorate_local_images(self, node, items, env=None):
        usage_map = self._image_usage_map(node, env=env)
        used_count = 0
        total_size_bytes = 0
        for item in items:
            usage = usage_map.get(item["image_id"], {})
            usage_count = int(usage.get("usage_count") or item.get("containers_count") or 0)
            item["usage_count"] = usage_count
            item["running_count"] = int(usage.get("running_count") or 0)
            item["in_use"] = usage_count > 0
            item["last_used_at"] = usage.get("last_used_at") or ""
            item["containers"] = usage.get("containers") or []
            total_size_bytes += int(item.get("size_bytes") or 0)
            used_count += 1 if item["in_use"] else 0
        return {
            "image_count": len(items),
            "used_count": used_count,
            "unused_count": max(0, len(items) - used_count),
            "total_size_bytes": total_size_bytes,
        }

    def _empty_storage(self, message=""):
        return {
            "available": False,
            "path": "",
            "total_bytes": 0,
            "used_bytes": 0,
            "available_bytes": 0,
            "used_percent": 0,
            "message": message,
        }

    def _json_payload(self, result, default=None):
        try:
            payload = json.loads(result.get("stdout") or "{}")
        except Exception:
            return default if default is not None else {}
        return payload if isinstance(payload, dict) else (default if default is not None else {})

    def _storage_payload(self, node, env=None):
        result = self._run_storage_command(node, env=env)
        if result.get("status") != "ok":
            return self._empty_storage(self._command_failure(result))
        payload = self._json_payload(result, default={})
        if not payload:
            return self._empty_storage("저장소 용량 응답을 해석할 수 없습니다.")
        payload.setdefault("available", bool(payload.get("total_bytes")))
        payload.setdefault("path", "")
        payload.setdefault("total_bytes", 0)
        payload.setdefault("used_bytes", 0)
        payload.setdefault("available_bytes", 0)
        payload.setdefault("used_percent", 0)
        payload.setdefault("message", "")
        return payload

    def local_node_detail(self, node_id, env=None):
        node = nodes.detail(node_id, env=env)
        storage = self._storage_payload(node, env=env)
        result = self._run_node_command(node, env=env)
        if result["status"] != "ok":
            return {
                "node": {"id": node["id"], "name": node["name"], "host": node["host"], "is_local_master": node["is_local_master"]},
                "docker_available": False,
                "message": self._command_failure(result),
                "images": [],
                "storage": storage,
                "summary": {"image_count": 0, "used_count": 0, "unused_count": 0, "total_size_bytes": 0},
            }
        items = parse_docker_image_lines(result.get("stdout"))
        summary = self._decorate_local_images(node, items, env=env)
        self._replace_cached_images("local", f"node://{node_id}", [self._local_cache_row(node, item) for item in items], env=env)
        return {
            "node": {"id": node["id"], "name": node["name"], "host": node["host"], "is_local_master": node["is_local_master"]},
            "docker_available": True,
            "message": "",
            "images": items,
            "storage": storage,
            "summary": summary,
        }

    def _payload_image_refs(self, payload):
        image_refs = []
        items = (payload or {}).get("items") or []
        if isinstance(items, list) and len(items) > 0:
            seen = set()
            for item in items:
                image_ref = str((item or {}).get("image_ref") or "").strip()
                if image_ref and image_ref not in seen:
                    seen.add(image_ref)
                    image_refs.append(image_ref)
        else:
            image_ref = str((payload or {}).get("image_ref") or "").strip()
            if image_ref:
                image_refs.append(image_ref)
        return image_refs

    def _assert_local_images_removable(self, node, image_refs, env=None):
        requested = {str(item or "").strip() for item in image_refs if str(item or "").strip()}
        if not requested:
            return
        result = self._run_node_command(node, env=env)
        if result.get("status") != "ok":
            return
        items = parse_docker_image_lines(result.get("stdout"))
        self._decorate_local_images(node, items, env=env)
        blocked = []
        for item in items:
            if not set(self._image_known_refs(item)).intersection(requested):
                continue
            if item.get("in_use"):
                label = item.get("remove_ref") or item.get("image_id")
                blocked.append({"image_ref": label, "usage_count": item.get("usage_count") or 0, "containers": item.get("containers") or []})
        if blocked:
            raise ImageError(409, "사용 중인 이미지는 삭제할 수 없습니다.", "LOCAL_IMAGE_IN_USE", images=blocked)

    def local_delete_estimate(self, payload, env=None):
        node_id = str((payload or {}).get("node_id") or "").strip()
        image_refs = self._payload_image_refs(payload)
        if not node_id or len(image_refs) == 0:
            raise ImageError(400, "node_id와 image_ref가 필요합니다.", "LOCAL_IMAGE_DELETE_REQUIRED")
        node = nodes.detail(node_id, env=env)
        result = self._run_delete_estimate_command(node, image_refs, env=env)
        if result.get("status") != "ok":
            raise ImageError(409, self._command_failure(result), "LOCAL_IMAGE_ESTIMATE_FAILED", check=serialize(result))
        estimate = self._json_payload(result, default={})
        if not estimate or estimate.get("available") is False:
            raise ImageError(409, estimate.get("message") or "삭제 예상 확보 용량을 계산할 수 없습니다.", "LOCAL_IMAGE_ESTIMATE_FAILED", check=serialize(result))
        return {"node_id": node_id, "estimate": estimate}

    def _prune_action(self, payload):
        action = str((payload or {}).get("action") or "image").strip()
        if action != "image":
            raise ImageError(400, "지원하지 않는 이미지 정리 작업입니다.", "INVALID_PRUNE_ACTION")
        return action

    def local_prune_estimate(self, payload, env=None):
        node_id = str((payload or {}).get("node_id") or "").strip()
        action = self._prune_action(payload)
        if not node_id:
            raise ImageError(400, "node_id가 필요합니다.", "NODE_ID_REQUIRED")
        node = nodes.detail(node_id, env=env)
        result = self._run_prune_estimate_command(node, action, env=env)
        if result.get("status") != "ok":
            raise ImageError(409, self._command_failure(result), "LOCAL_PRUNE_ESTIMATE_FAILED", check=serialize(result))
        estimate = self._json_payload(result, default={})
        if not estimate or estimate.get("available") is False:
            raise ImageError(409, estimate.get("message") or "prune 예상 확보 용량을 계산할 수 없습니다.", "LOCAL_PRUNE_ESTIMATE_FAILED", check=serialize(result))
        return {"node_id": node_id, "action": action, "estimate": estimate}

    def _parse_prune_result(self, action, result):
        stdout = str(result.get("stdout") or "").strip()
        reclaimed_text = ""
        for line in stdout.splitlines():
            if "Total reclaimed space:" in line:
                reclaimed_text = line.split("Total reclaimed space:", 1)[-1].strip()
        return {
            "action": action,
            "command": result.get("command_display") or " ".join(result.get("command") or []),
            "stdout": stdout,
            "stderr": str(result.get("stderr") or "").strip(),
            "reclaimed": reclaimed_text,
            "reclaimed_bytes": parse_size_bytes(reclaimed_text),
        }

    def prune_local(self, payload, env=None):
        node_id = str((payload or {}).get("node_id") or "").strip()
        action = self._prune_action(payload)
        if not node_id:
            raise ImageError(400, "node_id가 필요합니다.", "NODE_ID_REQUIRED")
        if not bool((payload or {}).get("confirmed")):
            raise ImageError(400, "미사용 이미지 정리 실행 확인이 필요합니다.", "LOCAL_PRUNE_CONFIRM_REQUIRED")
        node = nodes.detail(node_id, env=env)
        result = self._run_prune_command(node, action, env=env)
        if result.get("status") != "ok":
            self._record_operation(
                "image.local.prune",
                target_type="node",
                target_id=node_id,
                payload={"node_id": node_id, "action": action},
                result={"check": serialize(result)},
                status="failed",
                env=env,
            )
            raise ImageError(409, self._command_failure(result), "LOCAL_PRUNE_FAILED", check=serialize(result))
        prune_result = self._parse_prune_result(action, result)
        self._record_operation(
            "image.local.prune",
            target_type="node",
            target_id=node_id,
            payload={"node_id": node_id, "action": action},
            result=prune_result,
            env=env,
        )
        detail = self.local_node_detail(node_id, env=env)
        detail["prune_result"] = prune_result
        return detail

    def delete_local_image(self, payload, env=None):
        node_id = str((payload or {}).get("node_id") or "").strip()
        image_refs = self._payload_image_refs(payload)
        if not node_id or len(image_refs) == 0:
            raise ImageError(400, "node_id와 image_ref가 필요합니다.", "LOCAL_IMAGE_DELETE_REQUIRED")
        node = nodes.detail(node_id, env=env)
        self._assert_local_images_removable(node, image_refs, env=env)
        deleted = []
        for image_ref in image_refs:
            result, deleted_ref = self._remove_image_with_fallbacks(node, image_ref, env=env)
            if result["status"] != "ok":
                self._record_operation(
                    "image.local.delete",
                    target_type="node",
                    target_id=node_id,
                    payload={"node_id": node_id, "image_refs": image_refs},
                    result={"failed_image_ref": image_ref, "check": serialize(result)},
                    status="failed",
                    env=env,
                )
                raise ImageError(409, self._command_failure(result), "LOCAL_IMAGE_DELETE_FAILED", image_ref=image_ref, check=serialize(result))
            deleted.append(deleted_ref)
        self._record_operation(
            "image.local.delete",
            target_type="node",
            target_id=node_id,
            payload={"node_id": node_id, "image_refs": image_refs},
            result={"deleted": deleted, "deleted_count": len(deleted)},
            env=env,
        )
        return self.local_node_detail(node_id, env=env)

    def _safe_import_filename(self, filename):
        raw = Path(str(filename or "")).name.strip()
        if not raw:
            raise ImageError(400, "업로드할 이미지 tar 파일이 필요합니다.", "LOCAL_IMAGE_IMPORT_FILE_REQUIRED")
        if not raw.lower().endswith(IMAGE_ARCHIVE_EXTENSIONS):
            raise ImageError(400, "tar 형식의 Docker image archive만 업로드할 수 있습니다.", "LOCAL_IMAGE_IMPORT_FILE_INVALID")
        safe = re.sub(r"[^A-Za-z0-9_.-]+", "-", raw).strip(".-")
        return safe or "image.tar"

    def _save_import_archive(self, file_storage, env=None):
        filename = self._safe_import_filename(getattr(file_storage, "filename", ""))
        root = Path(config.data_dir(env)) / "image-imports"
        root.mkdir(parents=True, exist_ok=True)
        target = root / f"{uuid.uuid4().hex}-{filename}"
        file_storage.save(str(target))
        size = target.stat().st_size if target.exists() else 0
        if size <= 0:
            try:
                target.unlink(missing_ok=True)
            except Exception:
                pass
            raise ImageError(400, "빈 파일은 import할 수 없습니다.", "LOCAL_IMAGE_IMPORT_FILE_EMPTY")
        return {"path": target, "filename": filename, "size": size}

    def _subprocess_result(self, argv, timeout_seconds=IMAGE_IMPORT_TIMEOUT_SECONDS):
        started = time.monotonic()
        try:
            completed = subprocess.run(argv, capture_output=True, text=True, timeout=timeout_seconds, check=False)
            duration_ms = int((time.monotonic() - started) * 1000)
            status = "ok" if completed.returncode == 0 else "error"
            return {
                "command": argv,
                "command_display": shlex.join(argv),
                "status": status,
                "exit_code": completed.returncode,
                "stdout": completed.stdout,
                "stderr": completed.stderr,
                "duration_ms": duration_ms,
            }
        except FileNotFoundError as exc:
            duration_ms = int((time.monotonic() - started) * 1000)
            return {
                "command": argv,
                "command_display": shlex.join(argv),
                "status": "missing",
                "exit_code": None,
                "stdout": "",
                "stderr": str(exc),
                "duration_ms": duration_ms,
            }
        except subprocess.TimeoutExpired as exc:
            duration_ms = int((time.monotonic() - started) * 1000)
            return {
                "command": argv,
                "command_display": shlex.join(argv),
                "status": "timeout",
                "exit_code": None,
                "stdout": exc.stdout or "",
                "stderr": exc.stderr or f"command timed out after {timeout_seconds}s",
                "duration_ms": duration_ms,
                "timed_out": True,
            }

    def _scp_upload_to_node(self, node, local_path, remote_path, env=None):
        credential = node.get("credential") or {}
        key_file = credential.get("key_file") or (credential.get("metadata") or {}).get("key_file")
        username = credential.get("username")
        if not username:
            raise ImageError(409, "서버 SSH 계정 정보가 없습니다. 서버를 다시 등록해주세요.", "NODE_SSH_USERNAME_MISSING")
        if not key_file:
            raise ImageError(409, "서버 SSH key file 정보가 없습니다. 서버를 다시 등록해주세요.", "NODE_SSH_KEY_MISSING")
        known_hosts = nodes.ssh_executor.known_hosts_for_run(node["host"], port=node.get("ssh_port"), env=env)
        argv = [
            "scp",
            "-q",
            "-o",
            "BatchMode=yes",
            "-o",
            f"UserKnownHostsFile={known_hosts}",
            "-o",
            "StrictHostKeyChecking=accept-new",
            "-o",
            "LogLevel=ERROR",
            "-o",
            "ConnectTimeout=30",
        ]
        if node.get("ssh_port"):
            argv.extend(["-P", str(node.get("ssh_port"))])
        argv.extend(["-i", str(key_file), "-o", "IdentitiesOnly=yes", str(local_path), f"{username}@{node['host']}:{remote_path}"])
        return self._subprocess_result(argv, timeout_seconds=IMAGE_IMPORT_TIMEOUT_SECONDS)

    def _copy_import_archive_to_remote(self, node, staged, env=None):
        remote_dir = f"{REMOTE_IMAGE_IMPORT_DIR}/{uuid.uuid4().hex}"
        result = nodes._run_ssh_command(node, ["mkdir", "-p", remote_dir], timeout_seconds=20, env=env)
        if result.get("status") != "ok":
            raise ImageError(409, self._command_failure(result), "LOCAL_IMAGE_IMPORT_TRANSFER_FAILED", check=serialize(result))
        remote_path = f"{remote_dir}/{staged['filename']}"
        transfer = self._scp_upload_to_node(node, staged["path"], remote_path, env=env)
        if transfer.get("status") != "ok":
            nodes._run_ssh_command(node, ["rm", "-rf", remote_dir], timeout_seconds=20, env=env)
            raise ImageError(409, self._command_failure(transfer), "LOCAL_IMAGE_IMPORT_TRANSFER_FAILED", check=serialize(transfer))
        return remote_path, remote_dir, transfer

    def _cleanup_remote_import(self, node, remote_dir, env=None):
        if not remote_dir:
            return
        try:
            nodes._run_ssh_command(node, ["rm", "-rf", remote_dir], timeout_seconds=20, env=env)
        except Exception:
            pass

    def _parse_image_load_result(self, result):
        stdout = str(result.get("stdout") or "").strip()
        stderr = str(result.get("stderr") or "").strip()
        loaded_images = []
        loaded_image_ids = []
        for line in f"{stdout}\n{stderr}".splitlines():
            text = line.strip()
            lower = text.lower()
            if lower.startswith("loaded image:"):
                loaded_images.append(text.split(":", 1)[1].strip())
            elif lower.startswith("loaded image id:"):
                loaded_image_ids.append(text.split(":", 1)[1].strip())
        return {
            "command": result.get("command_display") or " ".join(result.get("command") or []),
            "stdout": stdout,
            "stderr": stderr,
            "loaded_images": loaded_images,
            "loaded_image_ids": loaded_image_ids,
            "duration_ms": result.get("duration_ms") or 0,
        }

    def _import_staged_local_image(self, node_id, staged, env=None):
        node = nodes.detail(node_id, env=env)
        operation_payload = {"node_id": node_id, "filename": staged["filename"], "size": staged["size"]}
        remote_dir = ""
        operation_recorded = False
        try:
            import_path = str(staged["path"])
            transfer_result = None
            if not self._is_local_master_node(node):
                import_path, remote_dir, transfer_result = self._copy_import_archive_to_remote(node, staged, env=env)
            result = self._run_image_load_command(node, import_path, env=env)
            import_result = {
                "filename": staged["filename"],
                "size": staged["size"],
                "load": self._parse_image_load_result(result),
            }
            if transfer_result:
                import_result["transfer"] = serialize(transfer_result)
            if result.get("status") != "ok":
                raise ImageError(409, self._command_failure(result), "LOCAL_IMAGE_IMPORT_FAILED", check=serialize(result))
            self._record_operation(
                "image.local.import",
                target_type="node",
                target_id=node_id,
                payload=operation_payload,
                result=import_result,
                env=env,
            )
            operation_recorded = True
            detail = self.local_node_detail(node_id, env=env)
            detail["import_result"] = import_result
            return detail
        except ImageError as exc:
            if not operation_recorded:
                self._record_operation(
                    "image.local.import",
                    target_type="node",
                    target_id=node_id,
                    payload=operation_payload,
                    result={"message": exc.message, "error_code": exc.error_code, **serialize(exc.extra)},
                    status="failed",
                    env=env,
                )
            raise
        finally:
            self._cleanup_remote_import(node, remote_dir, env=env)
            try:
                staged["path"].unlink(missing_ok=True)
            except Exception:
                pass

    def import_local_image(self, payload, file_storage, env=None):
        node_id = str((payload or {}).get("node_id") or "").strip()
        if not node_id:
            raise ImageError(400, "node_id가 필요합니다.", "NODE_ID_REQUIRED")
        if file_storage is None:
            raise ImageError(400, "업로드할 이미지 tar 파일이 필요합니다.", "LOCAL_IMAGE_IMPORT_FILE_REQUIRED")

        staged = self._save_import_archive(file_storage, env=env)
        return self._import_staged_local_image(node_id, staged, env=env)

    def _run_node_command(self, node, remove_ref="", env=None):
        if self._is_local_master_node(node):
            command_id = "docker.image.remove" if remove_ref else "docker.images"
            return local_executor.run(command_id, params={"image_ref": remove_ref} if remove_ref else {}, timeout_seconds=20, env=env)
        command = ["docker", "image", "rm", "-f", remove_ref] if remove_ref else DEFAULT_DOCKER_IMAGE_COMMAND
        return nodes._run_ssh_command(node, command, timeout_seconds=20, env=env)

    def _run_usage_command(self, node, env=None):
        if self._is_local_master_node(node):
            return local_executor.run("docker.images.usage", timeout_seconds=20, env=env)
        return nodes._run_ssh_command(node, DOCKER_IMAGE_USAGE_COMMAND, timeout_seconds=20, env=env)

    def _run_storage_command(self, node, env=None):
        if self._is_local_master_node(node):
            return local_executor.run("docker.images.storage", timeout_seconds=20, env=env)
        return nodes._run_ssh_command(node, DOCKER_IMAGE_STORAGE_COMMAND, timeout_seconds=20, env=env)

    def _run_delete_estimate_command(self, node, image_refs, env=None):
        if self._is_local_master_node(node):
            return local_executor.run(
                "docker.images.delete_estimate",
                params={"image_refs": image_refs},
                timeout_seconds=45,
                env=env,
            )
        command = [*DOCKER_IMAGE_DELETE_ESTIMATE_COMMAND, json.dumps(image_refs)]
        return nodes._run_ssh_command(node, command, timeout_seconds=45, env=env)

    def _run_prune_estimate_command(self, node, action, env=None):
        if self._is_local_master_node(node):
            return local_executor.run("docker.prune.estimate", params={"action": action}, timeout_seconds=20, env=env)
        command = [*DOCKER_PRUNE_ESTIMATE_COMMAND, action]
        return nodes._run_ssh_command(node, command, timeout_seconds=20, env=env)

    def _run_prune_command(self, node, action, env=None):
        if self._is_local_master_node(node):
            return local_executor.run("docker.image.prune", timeout_seconds=300, env=env)
        return nodes._run_ssh_command(node, DOCKER_IMAGE_PRUNE_COMMAND, timeout_seconds=300, env=env)

    def _run_image_load_command(self, node, image_path, env=None):
        if self._is_local_master_node(node):
            return local_executor.run(
                "docker.image.load",
                params={"path": image_path},
                timeout_seconds=IMAGE_IMPORT_TIMEOUT_SECONDS,
                env=env,
            )
        return nodes._run_ssh_command(node, ["docker", "load", "-i", image_path], timeout_seconds=IMAGE_IMPORT_TIMEOUT_SECONDS, env=env)

    def _command_failure(self, result):
        output = str(result.get("stderr") or result.get("stdout") or "").strip()
        if result.get("status") == "missing":
            return "Docker 또는 SSH 실행 파일을 찾을 수 없습니다."
        if result.get("status") == "timeout" or result.get("timed_out"):
            return "응답 시간이 초과되었습니다."
        return output.splitlines()[-1][:200] if output else "이미지 작업에 실패했습니다."

    def _replace_cached_images(self, source, registry, rows, env=None):
        with connect(env=env) as connection:
            with connection.cursor() as cursor:
                cursor.execute("DELETE FROM images WHERE source = %s AND registry = %s", (source, registry))
                for item in rows:
                    cursor.execute(
                        """
                        INSERT INTO images(registry, project, name, tag, digest, source, metadata)
                        VALUES (%s, %s, %s, %s, %s, %s, %s)
                        ON CONFLICT (registry, name, tag) DO UPDATE SET
                            project = EXCLUDED.project,
                            digest = EXCLUDED.digest,
                            source = EXCLUDED.source,
                            metadata = EXCLUDED.metadata
                        """,
                        (item["registry"], item["project"], item["name"], item["tag"], item["digest"], item["source"], Jsonb(item["metadata"])),
                    )

    def _replace_harbor_repository_cache(self, project_name, repository_name, rows, env=None):
        registry = f"harbor://{project_name}"
        with connect(env=env) as connection:
            with connection.cursor() as cursor:
                cursor.execute("DELETE FROM images WHERE source = 'harbor' AND registry = %s AND name = %s", (registry, repository_name))
                for item in rows:
                    cache_row = self._harbor_cache_row(project_name, item, env=env)
                    cursor.execute(
                        """
                        INSERT INTO images(registry, project, name, tag, digest, source, metadata)
                        VALUES (%s, %s, %s, %s, %s, %s, %s)
                        ON CONFLICT (registry, name, tag) DO UPDATE SET
                            project = EXCLUDED.project,
                            digest = EXCLUDED.digest,
                            source = EXCLUDED.source,
                            metadata = EXCLUDED.metadata
                        """,
                        (cache_row["registry"], cache_row["project"], cache_row["name"], cache_row["tag"], cache_row["digest"], cache_row["source"], Jsonb(cache_row["metadata"])),
                    )

    def _cached_summary(self, env=None):
        harbor_summary = {"project_count": 0, "tag_count": 0}
        local_summary = {}
        with connect(env=env) as connection:
            with connection.cursor() as cursor:
                cursor.execute("SELECT project FROM images WHERE source = 'harbor'")
                projects = [str(item["project"] or "").strip() for item in cursor.fetchall()]
                harbor_summary = {"project_count": len({item for item in projects if item}), "tag_count": len(projects)}
                cursor.execute("SELECT metadata FROM images WHERE source = 'local'")
                for row in cursor.fetchall():
                    node_id = str((row.get("metadata") or {}).get("node_id") or "").strip()
                    if not node_id:
                        continue
                    summary = local_summary.setdefault(node_id, {"image_count": 0, "used_count": 0, "unused_count": 0})
                    summary["image_count"] += 1
                    summary["used_count" if (row.get("metadata") or {}).get("in_use") else "unused_count"] += 1
        return {"harbor": harbor_summary, "local": local_summary}

    def _image_usage_map(self, node, env=None):
        result = self._run_usage_command(node, env=env)
        if result["status"] != "ok":
            return {}
        usage = {}
        for item in parse_docker_container_inspect_lines(result.get("stdout")):
            image_id = str(item.get("image_id") or "").strip()
            if not image_id:
                continue
            entry = usage.setdefault(image_id, {"usage_count": 0, "running_count": 0, "last_used_at": "", "containers": []})
            entry["usage_count"] += 1
            entry["running_count"] += 1 if item.get("running") else 0
            timestamp = str(item.get("last_used_at") or "").strip()
            if timestamp and (not entry["last_used_at"] or timestamp > entry["last_used_at"]):
                entry["last_used_at"] = timestamp
            entry["containers"].append(
                {
                    "container_id": item.get("container_id"),
                    "name": item.get("name"),
                    "status": item.get("status"),
                    "running": item.get("running"),
                    "last_used_at": item.get("last_used_at"),
                }
            )
        return usage

    def _harbor_cache_row(self, project_name, item, env=None):
        status = harbor.status(env=env)
        return {
            "registry": f"harbor://{project_name}",
            "project": project_name,
            "name": item["repository_name"],
            "tag": item["tag"],
            "digest": item["digest"],
            "source": "harbor",
            "metadata": {"harbor_url": status["url"], "artifact_type": item["artifact_type"], "push_time": item["push_time"], "size": item["size"]},
        }

    def _local_cache_row(self, node, item):
        return {
            "registry": f"node://{node['id']}",
            "project": node["name"],
            "name": item["repository"] or item["image_id"],
            "tag": item["tag"] or "<none>",
            "digest": item["digest"],
            "source": "local",
            "metadata": {
                "node_id": node["id"],
                "host": node["host"],
                "image_id": item["image_id"],
                "size": item["size"],
                "size_bytes": item.get("size_bytes") or 0,
                "created_at": item.get("created_at") or "",
                "created_since": item["created_since"],
                "containers_count": item.get("containers_count") or 0,
                "usage_count": item.get("usage_count") or 0,
                "running_count": item.get("running_count") or 0,
                "in_use": bool(item.get("in_use")),
                "last_used_at": item.get("last_used_at") or "",
                "remove_ref": item["remove_ref"],
            },
        }


Model = ImagesLocalMixin
