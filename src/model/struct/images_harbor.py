import base64
import json
from urllib import error as urlerror
from urllib import parse as urlparse
from urllib import request as urlrequest


backup_system = wiz.model("struct/backup_system")
shared = wiz.model("struct/images_shared")
ImageError = shared.ImageError
encode_repository_name = shared.encode_repository_name

PAGE_SIZE = 100


def _config(env=None):
    item = backup_system.connection_config(env=env)
    return {
        "enabled": bool(item.get("enabled")),
        "status": item.get("status") or "disabled",
        "url": str(item.get("harbor_url") or "").strip().rstrip("/"),
        "username": str(item.get("username") or "admin").strip(),
        "password": str(item.get("password") or "").strip(),
        "configured": bool(item.get("configured")),
    }


def _headers(config):
    token = base64.b64encode(f"{config['username']}:{config['password']}".encode("utf-8")).decode("ascii")
    return {"Authorization": f"Basic {token}", "Accept": "application/json"}


def _request_json(config, path, query=None, method="GET", payload=None):
    if not config["enabled"]:
        raise ImageError(409, "서비스 백업 시스템이 꺼져 있습니다.", "BACKUP_SYSTEM_DISABLED")
    if not config["configured"]:
        raise ImageError(400, "서비스 백업 시스템 관리자 정보가 준비되지 않았습니다.", "BACKUP_SYSTEM_CONFIGURATION_REQUIRED")
    if config["status"] not in {"running"}:
        raise ImageError(409, "서비스 백업 시스템이 실행 중이 아닙니다.", "BACKUP_SYSTEM_NOT_RUNNING")
    query_string = f"?{urlparse.urlencode(query or {})}" if query else ""
    headers = _headers(config)
    data = None
    if payload is not None:
        headers["Content-Type"] = "application/json"
        data = json.dumps(payload).encode("utf-8")
    req = urlrequest.Request(f"{config['url']}{path}{query_string}", headers=headers, data=data, method=method)
    try:
        with urlrequest.urlopen(req, timeout=15) as response:
            body = response.read().decode("utf-8")
            return response.status, json.loads(body or "{}") if body else {}
    except urlerror.HTTPError as exc:
        message = exc.read().decode("utf-8", errors="ignore") or "Harbor API 호출에 실패했습니다."
        raise ImageError(exc.code, message, "HARBOR_REQUEST_FAILED")
    except urlerror.URLError as exc:
        raise ImageError(502, str(exc.reason), "HARBOR_REQUEST_FAILED")


class HarborImages:
    ImageError = ImageError

    def status(self, env=None):
        config = _config(env=env)
        return {
            "enabled": config["enabled"],
            "status": config["status"],
            "url": config["url"],
            "username": config["username"],
            "configured": bool(config["configured"]),
        }

    def list_projects(self, env=None):
        config = _config(env=env)
        status, payload = _request_json(config, "/api/v2.0/projects", {"page": 1, "page_size": PAGE_SIZE})
        if status != 200:
            raise ImageError(status, "Harbor 프로젝트 목록을 불러올 수 없습니다.", "HARBOR_PROJECTS_FAILED")
        items = []
        for project in payload if isinstance(payload, list) else []:
            metadata = project.get("metadata") or {}
            items.append(
                {
                    "project_id": project.get("project_id"),
                    "name": project.get("name"),
                    "repo_count": int(project.get("repo_count") or 0),
                    "public": metadata.get("public") == "true",
                    "pull_count": int(project.get("pull_count") or 0),
                    "update_time": project.get("update_time"),
                }
            )
        return items

    def list_repositories(self, project_name, env=None):
        config = _config(env=env)
        status, payload = _request_json(
            config,
            f"/api/v2.0/projects/{urlparse.quote(str(project_name or '').strip(), safe='')}/repositories",
            {"page": 1, "page_size": PAGE_SIZE},
        )
        if status != 200:
            raise ImageError(status, "Harbor 저장소 목록을 불러올 수 없습니다.", "HARBOR_REPOSITORIES_FAILED")
        items = []
        for repository in payload if isinstance(payload, list) else []:
            full_name = str(repository.get("name") or "")
            name = full_name.split("/", 1)[-1] if "/" in full_name else full_name
            items.append(
                {
                    "name": name,
                    "full_name": full_name,
                    "display_name": name,
                    "artifact_count": int(repository.get("artifact_count") or 0),
                    "pull_count": int(repository.get("pull_count") or 0),
                    "update_time": repository.get("update_time"),
                }
            )
        return items

    def create_project(self, project_name, public=False, env=None):
        name = str(project_name or "").strip()
        if not name:
            raise ImageError(400, "project_name이 필요합니다.", "HARBOR_PROJECT_REQUIRED")
        config = _config(env=env)
        status, _ = _request_json(
            config,
            "/api/v2.0/projects",
            method="POST",
            payload={
                "project_name": name,
                "metadata": {
                    "public": "true" if bool(public) else "false",
                },
            },
        )
        if status not in {200, 201}:
            raise ImageError(status, "Harbor 프로젝트를 생성할 수 없습니다.", "HARBOR_PROJECT_CREATE_FAILED")
        return True

    def list_artifacts(self, project_name, repository_name, env=None):
        config = _config(env=env)
        status, payload = _request_json(
            config,
            f"/api/v2.0/projects/{urlparse.quote(str(project_name or '').strip(), safe='')}/repositories/{encode_repository_name(repository_name)}/artifacts",
            {"page": 1, "page_size": PAGE_SIZE, "with_tag": "true", "with_label": "false", "with_scan_overview": "false"},
        )
        if status != 200:
            raise ImageError(status, "Harbor 태그 목록을 불러올 수 없습니다.", "HARBOR_ARTIFACTS_FAILED")
        items = []
        for artifact in payload if isinstance(payload, list) else []:
            tags = artifact.get("tags") or []
            if not tags:
                tags = [{"name": "<untagged>", "push_time": artifact.get("push_time")}]
            for tag in tags:
                items.append(
                    {
                        "repository_name": repository_name,
                        "tag": tag.get("name"),
                        "digest": artifact.get("digest"),
                        "size": artifact.get("size"),
                        "push_time": tag.get("push_time") or artifact.get("push_time"),
                        "artifact_type": artifact.get("type") or artifact.get("artifact_type") or "image",
                        "labels": artifact.get("labels") or [],
                    }
                )
        return items

    def delete_artifact(self, project_name, repository_name, reference, env=None):
        config = _config(env=env)
        status, _ = _request_json(
            config,
            f"/api/v2.0/projects/{urlparse.quote(str(project_name or '').strip(), safe='')}/repositories/{encode_repository_name(repository_name)}/artifacts/{urlparse.quote(str(reference or '').strip(), safe=':')}",
            method="DELETE",
        )
        if status not in {200, 202, 204}:
            raise ImageError(status, "Harbor 이미지를 삭제할 수 없습니다.", "HARBOR_DELETE_FAILED")
        return True

    def delete_tag(self, project_name, repository_name, reference, tag=None, env=None):
        config = _config(env=env)
        tag = str(tag if tag is not None else reference or "").strip()
        try:
            status, _ = _request_json(
                config,
                f"/api/v2.0/projects/{urlparse.quote(str(project_name or '').strip(), safe='')}/repositories/{encode_repository_name(repository_name)}/artifacts/{urlparse.quote(str(reference or '').strip(), safe=':')}/tags/{urlparse.quote(tag, safe='')}",
                method="DELETE",
            )
        except ImageError as exc:
            if exc.status_code == 404:
                return False
            raise
        if status not in {200, 202, 204}:
            raise ImageError(status, "Harbor 이미지 태그를 삭제할 수 없습니다.", "HARBOR_TAG_DELETE_FAILED")
        return True

    def delete_repository(self, project_name, repository_name, env=None):
        config = _config(env=env)
        status, _ = _request_json(
            config,
            f"/api/v2.0/projects/{urlparse.quote(str(project_name or '').strip(), safe='')}/repositories/{encode_repository_name(repository_name)}",
            method="DELETE",
        )
        if status not in {200, 202, 204}:
            raise ImageError(status, "Harbor 이미지 저장소를 삭제할 수 없습니다.", "HARBOR_REPOSITORY_DELETE_FAILED")
        return True

    def delete_project(self, project_name, env=None):
        config = _config(env=env)
        status, _ = _request_json(
            config,
            f"/api/v2.0/projects/{urlparse.quote(str(project_name or '').strip(), safe='')}",
            method="DELETE",
        )
        if status not in {200, 202, 204}:
            raise ImageError(status, "Harbor 프로젝트를 삭제할 수 없습니다.", "HARBOR_PROJECT_DELETE_FAILED")
        return True


Model = HarborImages()
