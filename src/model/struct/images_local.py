from psycopg.types.json import Jsonb


connect = wiz.model("db/postgres").connect
nodes = wiz.model("struct/nodes")
local_executor = wiz.model("struct/local_executor")
harbor = wiz.model("struct/images_harbor")
shared = wiz.model("struct/images_shared")
ImageError = shared.ImageError
parse_docker_image_lines = shared.parse_docker_image_lines
parse_docker_container_inspect_lines = shared.parse_docker_container_inspect_lines
serialize = shared.serialize

DEFAULT_DOCKER_IMAGE_COMMAND = ["docker", "image", "ls", "--digests", "--no-trunc", "--format", "{{json .}}"]
DOCKER_IMAGE_USAGE_COMMAND = [
    "sh",
    "-lc",
    "ids=$(docker container ls -aq --no-trunc); if [ -z \"$ids\" ]; then exit 0; fi; docker inspect --format '{{json .}}' $ids",
]


class ImagesLocalMixin:
    def _is_local_master_node(self, node):
        return bool(node.get("is_local_master") or node.get("role") == "local_master" or node.get("name") == "local-master")

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
            repository = str(item.get("repository") or "").strip()
            tag = str(item.get("tag") or "").strip()
            digest = str(item.get("digest") or "").strip()
            image_id = str(item.get("image_id") or "").strip()
            tag_ref = f"{repository}:{tag}" if repository not in {"", "<none>"} and tag not in {"", "<none>"} else ""
            digest_ref = f"{repository}@{digest}" if repository not in {"", "<none>"} and digest else ""
            tag_digest_ref = f"{repository}:{tag}@{digest}" if tag_ref and digest else ""
            known = {value for value in [tag_ref, digest_ref, tag_digest_ref, image_id, item.get("remove_ref")] if value}
            if requested not in known:
                continue
            for value in [tag_digest_ref, digest_ref, image_id, tag_ref, item.get("remove_ref")]:
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

    def local_node_detail(self, node_id, env=None):
        node = nodes.detail(node_id, env=env)
        result = self._run_node_command(node, env=env)
        if result["status"] != "ok":
            return {
                "node": {"id": node["id"], "name": node["name"], "host": node["host"], "is_local_master": node["is_local_master"]},
                "docker_available": False,
                "message": self._command_failure(result),
                "images": [],
                "summary": {"image_count": 0, "used_count": 0, "unused_count": 0},
            }
        items = parse_docker_image_lines(result.get("stdout"))
        usage_map = self._image_usage_map(node, env=env)
        used_count = 0
        for item in items:
            usage = usage_map.get(item["image_id"], {})
            usage_count = int(usage.get("usage_count") or item.get("containers_count") or 0)
            item["usage_count"] = usage_count
            item["running_count"] = int(usage.get("running_count") or 0)
            item["in_use"] = usage_count > 0
            item["last_used_at"] = usage.get("last_used_at") or ""
            item["containers"] = usage.get("containers") or []
            used_count += 1 if item["in_use"] else 0
        self._replace_cached_images("local", f"node://{node_id}", [self._local_cache_row(node, item) for item in items], env=env)
        return {
            "node": {"id": node["id"], "name": node["name"], "host": node["host"], "is_local_master": node["is_local_master"]},
            "docker_available": True,
            "message": "",
            "images": items,
            "summary": {"image_count": len(items), "used_count": used_count, "unused_count": max(0, len(items) - used_count)},
        }

    def delete_local_image(self, payload, env=None):
        node_id = str((payload or {}).get("node_id") or "").strip()
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
        if not node_id or len(image_refs) == 0:
            raise ImageError(400, "node_id와 image_ref가 필요합니다.", "LOCAL_IMAGE_DELETE_REQUIRED")
        node = nodes.detail(node_id, env=env)
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
