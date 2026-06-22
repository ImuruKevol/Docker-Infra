connect = wiz.model("db/postgres").connect
nodes = wiz.model("struct/nodes")
operations = wiz.model("struct/operations")
harbor = wiz.model("struct/images_harbor")
shared = wiz.model("struct/images_shared")
local_mixin = wiz.model("struct/images_local")
ImageError = shared.ImageError


class Images(local_mixin):
    ImageError = ImageError

    def _record_operation(self, operation_type, target_type=None, target_id=None, payload=None, result=None, status="succeeded", env=None):
        return operations.create(
            operation_type,
            target_type=target_type,
            target_id=target_id,
            status=status,
            message=f"{operation_type} {status}",
            requested_payload=payload or {},
            result_payload=result or {},
            env=env,
        )

    def load(self, env=None):
        node_items = []
        for node in nodes.list(env=env):
            node_items.append({
                "id": node["id"],
                "name": node["name"],
                "host": node["host"],
                "status": node["status"],
                "role": node.get("role"),
                "swarm_node_id": node.get("swarm_node_id"),
                "is_local_master": node["is_local_master"],
            })
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
        return {
            "project_name": project_name,
            "repositories": repositories,
            "selected_repository": repositories[0]["name"] if repositories else "",
            "summary": {
                "repository_count": len(repositories),
                "artifact_count": sum(int(item.get("artifact_count") or 0) for item in repositories),
                "pull_count": sum(int(item.get("pull_count") or 0) for item in repositories),
            },
        }

    def harbor_repository_tags(self, project_name, repository_name, env=None):
        project_name = str(project_name or "").strip()
        repository_name = str(repository_name or "").strip()
        if not project_name or not repository_name:
            raise ImageError(400, "project_name과 repository_name이 필요합니다.", "HARBOR_REPOSITORY_REQUIRED")
        tag_rows = harbor.list_artifacts(project_name, repository_name, env=env)
        self._replace_harbor_repository_cache(project_name, repository_name, tag_rows, env=env)
        return {
            "project_name": project_name,
            "repository_name": repository_name,
            "tags": tag_rows,
            "summary": {
                "tag_count": len(tag_rows),
            },
        }

    def delete_harbor_artifact(self, payload, env=None):
        project_name = str((payload or {}).get("project_name") or "").strip()
        current_repository = str((payload or {}).get("repository_name") or "").strip()
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
                if not current_repository:
                    current_repository = repository_name
        else:
            repository_name = str((payload or {}).get("repository_name") or "").strip()
            digest = str((payload or {}).get("digest") or "").strip()
            if repository_name and digest:
                delete_items.append((repository_name, digest))
                current_repository = repository_name
        if not project_name or len(delete_items) == 0:
            raise ImageError(400, "프로젝트, 저장소, digest가 필요합니다.", "HARBOR_DELETE_REQUIRED")
        for repository_name, digest in delete_items:
            harbor.delete_artifact(project_name, repository_name, digest, env=env)
        self._record_operation(
            "image.harbor_artifact.delete",
            target_type="harbor_project",
            target_id=project_name,
            payload={"project_name": project_name, "items": [{"repository_name": name, "digest": digest} for name, digest in delete_items]},
            result={"deleted_count": len(delete_items)},
            env=env,
        )
        return self.harbor_repository_tags(project_name, current_repository, env=env)

    def delete_harbor_project(self, payload, env=None):
        project_name = str((payload or {}).get("project_name") or "").strip()
        if not project_name:
            raise ImageError(400, "project_name이 필요합니다.", "HARBOR_PROJECT_REQUIRED")
        deleted_repositories = []
        deleted_artifacts = 0
        for repository in harbor.list_repositories(project_name, env=env):
            repository_name = str(repository.get("name") or "").strip()
            if not repository_name:
                continue
            seen_digests = set()
            try:
                artifacts = harbor.list_artifacts(project_name, repository_name, env=env)
            except ImageError as exc:
                if exc.status_code != 404:
                    raise
                artifacts = []
            for artifact in artifacts:
                digest = str((artifact or {}).get("digest") or "").strip()
                if not digest or digest in seen_digests:
                    continue
                seen_digests.add(digest)
                try:
                    harbor.delete_artifact(project_name, repository_name, digest, env=env)
                    deleted_artifacts += 1
                except ImageError as exc:
                    if exc.status_code != 404:
                        raise
            try:
                harbor.delete_repository(project_name, repository_name, env=env)
                deleted_repositories.append(repository_name)
            except ImageError as exc:
                if exc.status_code != 404:
                    raise
        harbor.delete_project(project_name, env=env)
        with connect(env=env) as connection:
            with connection.cursor() as cursor:
                cursor.execute("DELETE FROM images WHERE source = 'harbor' AND registry = %s", (f"harbor://{project_name}",))
        self._record_operation(
            "image.harbor_project.delete",
            target_type="harbor_project",
            target_id=project_name,
            payload={"project_name": project_name},
            result={
                "deleted": True,
                "deleted_repositories": deleted_repositories,
                "deleted_repository_count": len(deleted_repositories),
                "deleted_artifact_count": deleted_artifacts,
            },
            env=env,
        )
        return self.harbor_overview(env=env)

    def delete_harbor_repository(self, payload, env=None):
        project_name = str((payload or {}).get("project_name") or "").strip()
        repositories = []
        items = (payload or {}).get("items") or []
        if isinstance(items, list) and len(items) > 0:
            seen = set()
            for item in items:
                repository_name = str((item or {}).get("repository_name") or "").strip()
                if not repository_name or repository_name in seen:
                    continue
                seen.add(repository_name)
                repositories.append(repository_name)
        else:
            repository_name = str((payload or {}).get("repository_name") or "").strip()
            if repository_name:
                repositories.append(repository_name)
        if not project_name or len(repositories) == 0:
            raise ImageError(400, "project_name과 repository_name이 필요합니다.", "HARBOR_REPOSITORY_REQUIRED")
        for repository_name in repositories:
            harbor.delete_repository(project_name, repository_name, env=env)
            with connect(env=env) as connection:
                with connection.cursor() as cursor:
                    cursor.execute(
                        "DELETE FROM images WHERE source = 'harbor' AND registry = %s AND name = %s",
                        (f"harbor://{project_name}", repository_name),
                    )
        self._record_operation(
            "image.harbor_repository.delete",
            target_type="harbor_project",
            target_id=project_name,
            payload={"project_name": project_name, "repositories": repositories},
            result={"deleted_count": len(repositories)},
            env=env,
        )
        return self.harbor_project_detail(project_name, env=env)

    def create_harbor_project(self, payload, env=None):
        project_name = str((payload or {}).get("project_name") or "").strip()
        is_public = bool((payload or {}).get("public"))
        harbor.create_project(project_name, public=is_public, env=env)
        return self.harbor_overview(env=env)

Model = Images()
