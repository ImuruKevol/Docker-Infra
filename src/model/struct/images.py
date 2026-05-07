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
DOCKER_IMAGE_USAGE_COMMAND = ["sh", "-lc", "ids=$(docker container ls -aq --no-trunc); if [ -z \"$ids\" ]; then exit 0; fi; docker inspect --format '{{json .}}' $ids"]


class Images:
    ImageError = ImageError

    def load(self, env=None):
        node_items = []
        for node in nodes.list(env=env):
            node_items.append({"id": node["id"], "name": node["name"], "host": node["host"], "status": node["status"], "is_local_master": node["is_local_master"]})
        harbor_status = harbor.status(env=env)
        cached = self._cached_summary(env=env)
        selected_node_id = next((item["id"] for item in node_items if item["is_local_master"]), node_items[0]["id"] if node_items else "")
        return {
            "harbor": harbor_status,
            "harbor_error": "",
            "harbor_projects": [],
            "harbor_summary": cached["harbor"],
            "nodes": node_items,
            "local_summary_by_node": cached["local"],
            "selected_node_id": selected_node_id,
            "selected_project": "",
        }

    def harbor_overview(self, env=None):
        projects = harbor.list_projects(env=env)
        return {
            "projects": projects,
            "selected_project": projects[0]["name"] if projects else "",
            "summary": {
                "project_count": len(projects),
                "tag_count": 0,
            },
        }

    def harbor_project_detail(self, project_name, env=None):
        repositories = harbor.list_repositories(project_name, env=env)
        tag_rows = []
        for repository in repositories:
            tag_rows.extend(harbor.list_artifacts(project_name, repository["name"], env=env))
        self._replace_cached_images("harbor", f"harbor://{project_name}", [self._harbor_cache_row(project_name, item, env=env) for item in tag_rows], env=env)
        return {
            "project_name": project_name,
            "repositories": repositories,
            "tags": tag_rows,
            "summary": {"repository_count": len(repositories), "tag_count": len(tag_rows)},
        }

    def delete_harbor_artifact(self, payload, env=None):
        project_name = str((payload or {}).get("project_name") or "").strip()
        items = (payload or {}).get("items") or []
        delete_items = []
        if isinstance(items, list) and len(items) > 0:
            seen = set()
            for item in items:
                repository_name = str((item or {}).get("repository_name") or "").strip()
                digest = str((item or {}).get("digest") or "").strip()
                key = (repository_name, digest)
                if not repository_name or not digest or key in seen:
                    continue
                seen.add(key)
                delete_items.append(key)
        else:
            repository_name = str((payload or {}).get("repository_name") or "").strip()
            digest = str((payload or {}).get("digest") or "").strip()
            if repository_name and digest:
                delete_items.append((repository_name, digest))
        if not project_name or len(delete_items) == 0:
            raise ImageError(400, "프로젝트, 저장소, digest가 필요합니다.", "HARBOR_DELETE_REQUIRED")
        for repository_name, digest in delete_items:
            harbor.delete_artifact(project_name, repository_name, digest, env=env)
        return self.harbor_project_detail(project_name, env=env)

    def delete_harbor_project(self, payload, env=None):
        project_name = str((payload or {}).get("project_name") or "").strip()
        if not project_name:
            raise ImageError(400, "project_name이 필요합니다.", "HARBOR_PROJECT_REQUIRED")
        harbor.delete_project(project_name, env=env)
        with connect(env=env) as connection:
            with connection.cursor() as cursor:
                cursor.execute("DELETE FROM images WHERE source = 'harbor' AND registry = %s", (f"harbor://{project_name}",))
        return self.harbor_overview(env=env)

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
            in_use = usage_count > 0
            if in_use:
                used_count += 1
            item["usage_count"] = usage_count
            item["running_count"] = int(usage.get("running_count") or 0)
            item["in_use"] = in_use
            item["last_used_at"] = usage.get("last_used_at") or ""
            item["containers"] = usage.get("containers") or []
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
        image_ref = str((payload or {}).get("image_ref") or "").strip()
        if not node_id or not image_ref:
            raise ImageError(400, "node_id와 image_ref가 필요합니다.", "LOCAL_IMAGE_DELETE_REQUIRED")
        node = nodes.detail(node_id, env=env)
        result = self._run_node_command(node, remove_ref=image_ref, env=env)
        if result["status"] != "ok":
            raise ImageError(409, self._command_failure(result), "LOCAL_IMAGE_DELETE_FAILED", check=serialize(result))
        return self.local_node_detail(node_id, env=env)

    def _run_node_command(self, node, remove_ref="", env=None):
        if node["is_local_master"]:
            command_id = "docker.image.remove" if remove_ref else "docker.images"
            params = {"image_ref": remove_ref} if remove_ref else {}
            return local_executor.run(command_id, params=params, timeout_seconds=20, env=env)
        command = ["docker", "image", "rm", remove_ref] if remove_ref else DEFAULT_DOCKER_IMAGE_COMMAND
        return nodes._run_ssh_command(node, command, timeout_seconds=20, env=env)

    def _run_usage_command(self, node, env=None):
        if node["is_local_master"]:
            return local_executor.run("docker.images.usage", timeout_seconds=20, env=env)
        return nodes._run_ssh_command(node, DOCKER_IMAGE_USAGE_COMMAND, timeout_seconds=20, env=env)

    def _command_failure(self, result):
        output = str(result.get("stderr") or result.get("stdout") or "").strip()
        if result.get("status") == "missing":
            return "Docker 또는 SSH 실행 파일을 찾을 수 없습니다."
        if result.get("status") == "timeout" or result.get("timed_out"):
            return "응답 시간이 초과되었습니다."
        if output:
            return output.splitlines()[-1][:200]
        return "이미지 작업에 실패했습니다."

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

    def _cached_summary(self, env=None):
        harbor_summary = {"project_count": 0, "tag_count": 0}
        local_summary = {}
        with connect(env=env) as connection:
            with connection.cursor() as cursor:
                cursor.execute("SELECT project FROM images WHERE source = 'harbor'")
                projects = [str(item["project"] or "").strip() for item in cursor.fetchall()]
                harbor_summary = {
                    "project_count": len({item for item in projects if item}),
                    "tag_count": len(projects),
                }
                cursor.execute("SELECT metadata FROM images WHERE source = 'local'")
                for row in cursor.fetchall():
                    metadata = row.get("metadata") or {}
                    node_id = str(metadata.get("node_id") or "").strip()
                    if not node_id:
                        continue
                    summary = local_summary.setdefault(node_id, {"image_count": 0, "used_count": 0, "unused_count": 0})
                    summary["image_count"] += 1
                    if metadata.get("in_use"):
                        summary["used_count"] += 1
                    else:
                        summary["unused_count"] += 1
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
            if item.get("running"):
                entry["running_count"] += 1
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


Model = Images()
