import base64
import json
from urllib import error as urlerror
from urllib import parse as urlparse
from urllib import request as urlrequest


integrations = wiz.model("struct/integrations")
shared = wiz.model("struct/images_shared")
ImageError = shared.ImageError
encode_repository_name = shared.encode_repository_name

PAGE_SIZE = 100


def _config(env=None):
    item = integrations.get("harbor", env=env)
    enabled = bool(item.get("enabled"))
    fields = item.get("fields") or {}
    return {
        "enabled": enabled,
        "url": str(fields.get("url") or "").strip().rstrip("/"),
        "username": str(fields.get("username") or "").strip(),
        "password": str(item.get("secret_value") or "").strip(),
    }


def _headers(config):
    token = base64.b64encode(f"{config['username']}:{config['password']}".encode("utf-8")).decode("ascii")
    return {"Authorization": f"Basic {token}", "Accept": "application/json"}


def _request_json(config, path, query=None, method="GET"):
    if not config["enabled"]:
        raise ImageError(409, "Harbor 연동이 꺼져 있습니다.", "HARBOR_DISABLED")
    if not config["url"] or not config["username"] or not config["password"]:
        raise ImageError(400, "Harbor URL, 계정, 비밀번호를 먼저 저장해주세요.", "HARBOR_CONFIGURATION_REQUIRED")
    query_string = f"?{urlparse.urlencode(query or {})}" if query else ""
    req = urlrequest.Request(f"{config['url']}{path}{query_string}", headers=_headers(config), method=method)
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
            "url": config["url"],
            "username": config["username"],
            "configured": bool(config["url"] and config["username"] and config["password"]),
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
            name = str(repository.get("name") or "")
            display_name = name.split("/", 1)[-1] if "/" in name else name
            items.append(
                {
                    "name": name,
                    "display_name": display_name,
                    "artifact_count": int(repository.get("artifact_count") or 0),
                    "pull_count": int(repository.get("pull_count") or 0),
                    "update_time": repository.get("update_time"),
                }
            )
        return items

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
