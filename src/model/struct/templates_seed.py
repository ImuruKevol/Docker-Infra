import textwrap


SEED_VERSION = "2026-05-20-compose-template-v1"


def block(text):
    return textwrap.dedent(text).strip() + "\n"


def schema(title, description, fields, required=None):
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "title": title,
        "description": description,
        "type": "object",
        "properties": {
            item["name"]: {
                "title": item.get("title") or item["name"],
                "type": item.get("type", "string"),
                "description": item.get("description", ""),
                "default": item.get("default"),
                **({"enum": item["enum"]} if item.get("enum") else {}),
                **({"secret": True} if item.get("secret") else {}),
            }
            for item in fields
        },
        "required": required or [item["name"] for item in fields if item.get("required", True)],
    }


def readme(title, summary, public_port, services):
    return "\n".join(
        [
            f"# {title}",
            "",
            summary,
            "",
            f"- 공개 대상 포트: `{public_port}`",
            f"- 포함 구성: {', '.join(services)}",
            "- 템플릿 변수는 `values.schema.json`을 기준으로 입력받습니다.",
            "- `container_name`, `hostname`, 외부 네트워크는 Docker Infra 배포 규칙에 맞게 사용하지 않습니다.",
            "",
        ]
    )


def metadata(tags, components, public_endpoint, component_labels=None, generated_secrets=None):
    return {
        "tags": tags,
        "seed_version": SEED_VERSION,
        "domain_ready": True,
        "components": components,
        "public_endpoint": public_endpoint,
        "component_labels": component_labels or {},
        "generated_secrets": generated_secrets or [],
    }


def default_templates():
    return [
        {
            "name": "WIZ Framework 개발환경",
            "namespace": "wiz_framework_dev",
            "enabled": True,
            "metadata": metadata(
                ["framework", "wiz", "dev"],
                ["app", "db"],
                {"service": "app", "port": 3000, "label": "WIZ 개발 서버"},
                {"app": "WIZ 개발 서버", "db": "개발 DB"},
                ["database_password"],
            ),
            "files": {
                "docker-compose.yaml": block(
                    """
                    services:
                      app:
                        image: {{ wiz_image }}
                        working_dir: /workspace
                        command: >
                          bash -lc "python -m pip install --no-cache-dir season=={{ season_version }} psycopg[binary] peewee PyYAML &&
                          if [ ! -f config/service.py ]; then wiz create starter && cp -a starter/. . && rm -rf starter; fi &&
                          wiz run --host 0.0.0.0 --port 3000"
                        ports:
                          - "{{ service_port }}:3000"
                        environment:
                          WIZ_PROJECT: {{ wiz_project }}
                          DATABASE_URL: "postgresql://{{ database_user }}:{{ database_password }}@{{ namespace }}_db:5432/{{ database_name }}"
                          PYTHONUNBUFFERED: "1"
                        volumes:
                          - wiz_workspace:/workspace
                          - wiz_cache:/root/.cache
                        depends_on:
                          - db
                        healthcheck:
                          test: ["CMD-SHELL", "python -c \\"import urllib.request; urllib.request.urlopen('http://127.0.0.1:3000', timeout=5).close()\\""]
                          interval: 30s
                          timeout: 8s
                          retries: 5
                      db:
                        image: {{ db_image }}
                        environment:
                          POSTGRES_DB: {{ database_name }}
                          POSTGRES_USER: {{ database_user }}
                          POSTGRES_PASSWORD: {{ database_password }}
                        volumes:
                          - postgres_data:/var/lib/postgresql/data
                        healthcheck:
                          test: ["CMD-SHELL", "pg_isready -U {{ database_user }} -d {{ database_name }}"]
                          interval: 30s
                          timeout: 5s
                          retries: 5
                    volumes:
                      wiz_workspace:
                      wiz_cache:
                      postgres_data:
                    """
                ),
                "values.default.yaml": block(
                    """
                    namespace: wiz_framework_dev
                    wiz_image: python:3.11-bookworm
                    season_version: 2.5.2
                    wiz_project: main
                    db_image: postgres:16
                    service_port: 3000
                    database_name: wiz
                    database_user: wiz
                    database_password: change_me
                    """
                ),
                "values.schema.json": schema(
                    "WIZ Framework 개발환경",
                    "서비스 이름만 입력해도 WIZ 개발 런타임 초안을 만들 수 있습니다.",
                    [
                        {"name": "namespace", "title": "서비스 내부 이름", "default": "wiz_framework_dev"},
                        {"name": "wiz_image", "title": "WIZ 런타임 이미지", "default": "python:3.11-bookworm"},
                        {"name": "season_version", "title": "Season/WIZ 버전", "default": "2.5.2"},
                        {"name": "wiz_project", "title": "WIZ 프로젝트명", "default": "main"},
                        {"name": "db_image", "title": "DB 이미지", "default": "postgres:16"},
                        {"name": "service_port", "title": "공개 포트", "type": "integer", "default": 3000},
                        {"name": "database_name", "title": "DB 이름", "default": "wiz"},
                        {"name": "database_user", "title": "DB 계정", "default": "wiz"},
                        {"name": "database_password", "title": "DB 비밀번호", "default": "change_me", "secret": True},
                    ],
                ),
                "README.md": readme("WIZ Framework 개발환경", "WIZ 기반 앱 개발을 시작하기 위한 기본 런타임입니다.", 3000, ["WIZ", "PostgreSQL"]),
            },
        },
        {
            "name": "Wiki.js 문서 사이트",
            "namespace": "wikijs_site",
            "enabled": True,
            "metadata": metadata(
                ["web", "wiki"],
                ["web", "db"],
                {"service": "web", "port": 3000, "label": "문서 사이트 화면"},
                {"web": "문서 사이트 화면", "db": "데이터베이스"},
                ["database_password"],
            ),
            "files": {
                "docker-compose.yaml": block(
                    """
                    services:
                      web:
                        image: {{ web_image }}
                        ports:
                          - "{{ service_port }}:3000"
                        environment:
                          DB_TYPE: postgres
                          DB_HOST: "{{ namespace }}_db"
                          DB_PORT: "5432"
                          DB_NAME: {{ database_name }}
                          DB_USER: {{ database_user }}
                          DB_PASS: {{ database_password }}
                        volumes:
                          - wiki_data:/wiki/data
                        healthcheck:
                          test: ["CMD-SHELL", "wget -qO- http://127.0.0.1:3000/ || exit 1"]
                          interval: 30s
                          timeout: 5s
                          retries: 5
                      db:
                        image: {{ db_image }}
                        environment:
                          POSTGRES_DB: {{ database_name }}
                          POSTGRES_USER: {{ database_user }}
                          POSTGRES_PASSWORD: {{ database_password }}
                        volumes:
                          - postgres_data:/var/lib/postgresql/data
                        healthcheck:
                          test: ["CMD-SHELL", "pg_isready -U {{ database_user }} -d {{ database_name }}"]
                          interval: 30s
                          timeout: 5s
                          retries: 5
                    volumes:
                      wiki_data:
                      postgres_data:
                    """
                ),
                "values.default.yaml": block(
                    """
                    namespace: wikijs_site
                    web_image: requarks/wiki:2
                    db_image: postgres:16
                    service_port: 3000
                    database_name: wiki
                    database_user: wiki
                    database_password: change_me
                    """
                ),
                "values.schema.json": schema(
                    "Wiki.js 문서 사이트",
                    "사내 문서 사이트를 DB와 함께 실행합니다.",
                    [
                        {"name": "namespace", "title": "서비스 내부 이름", "default": "wikijs_site"},
                        {"name": "web_image", "title": "웹 이미지", "default": "requarks/wiki:2"},
                        {"name": "db_image", "title": "DB 이미지", "default": "postgres:16"},
                        {"name": "service_port", "title": "공개 포트", "type": "integer", "default": 3000},
                        {"name": "database_name", "title": "DB 이름", "default": "wiki"},
                        {"name": "database_user", "title": "DB 계정", "default": "wiki"},
                        {"name": "database_password", "title": "DB 비밀번호", "default": "change_me", "secret": True},
                    ],
                ),
                "README.md": readme("Wiki.js 문서 사이트", "사내 문서와 운영 매뉴얼을 관리하는 위키 서비스입니다.", 3000, ["Wiki.js", "PostgreSQL"]),
            },
        },
    ]


class TemplatesSeed:
    default_templates = staticmethod(default_templates)


Model = TemplatesSeed()
