import textwrap


def default_template(schema):
    return {
        "name": "Harbor Registry",
        "namespace": "harbor_registry",
        "description": "Harbor 공식 구성 요소를 기준으로 한 Harbor 레지스트리 스택 초안 템플릿",
        "metadata": {"category": "service", "primary_image": "goharbor/harbor-core:v2.15.0"},
        "files": {
            "docker-compose.yaml": textwrap.dedent(
                """
                services:
                  proxy:
                    image: goharbor/nginx-photon:{{ harbor_version }}
                    ports:
                      - "{{ http_port }}:8080"
                      - "{{ https_port }}:8443"
                    depends_on:
                      - core
                      - registry
                      - portal
                    healthcheck:
                      test: ["CMD-SHELL", "wget -qO- http://127.0.0.1:8080/ || exit 1"]
                      interval: 30s
                      timeout: 5s
                      retries: 10
                  portal:
                    image: goharbor/harbor-portal:{{ harbor_version }}
                    healthcheck:
                      test: ["CMD-SHELL", "wget -qO- http://127.0.0.1:8080/ || exit 1"]
                      interval: 30s
                      timeout: 5s
                      retries: 10
                  core:
                    image: goharbor/harbor-core:{{ harbor_version }}
                    environment:
                      CORE_SECRET: {{ core_secret }}
                      JOBSERVICE_SECRET: {{ jobservice_secret }}
                      HARBOR_ADMIN_PASSWORD: {{ admin_password }}
                      POSTGRESQL_HOST: db
                      POSTGRESQL_PORT: 5432
                      POSTGRESQL_USERNAME: {{ db_user }}
                      POSTGRESQL_PASSWORD: {{ db_password }}
                      POSTGRESQL_DATABASE: registry
                      _REDIS_URL_CORE: redis://redis:6379/0
                    depends_on:
                      - db
                      - redis
                      - registry
                    healthcheck:
                      test: ["CMD-SHELL", "wget -qO- http://127.0.0.1:8080/api/v2.0/ping || exit 1"]
                      interval: 30s
                      timeout: 5s
                      retries: 10
                  registry:
                    image: goharbor/registry-photon:{{ harbor_version }}
                    healthcheck:
                      test: ["CMD-SHELL", "wget -qO- http://127.0.0.1:5000/v2/_catalog || exit 1"]
                      interval: 30s
                      timeout: 5s
                      retries: 10
                  redis:
                    image: goharbor/redis-photon:{{ harbor_version }}
                    healthcheck:
                      test: ["CMD", "redis-cli", "ping"]
                      interval: 30s
                      timeout: 5s
                      retries: 10
                  db:
                    image: goharbor/harbor-db:{{ harbor_version }}
                    environment:
                      POSTGRES_USER: {{ db_user }}
                      POSTGRES_PASSWORD: {{ db_password }}
                    healthcheck:
                      test: ["CMD-SHELL", "pg_isready -U {{ db_user }} -d registry || exit 1"]
                      interval: 30s
                      timeout: 5s
                      retries: 10
                """
            ).strip() + "\n",
            "values.default.yaml": textwrap.dedent(
                """
                namespace: harbor_registry
                service_name: harbor
                harbor_version: v2.15.0
                http_port: 8081
                https_port: 8444
                admin_password: Harbor12345
                core_secret: harbor_core_secret
                jobservice_secret: harbor_jobservice_secret
                db_user: postgres
                db_password: change_me
                image: goharbor/harbor-core:v2.15.0
                """
            ).strip() + "\n",
            "values.schema.json": schema("Harbor Registry", "Harbor 레지스트리 스택 초안 템플릿", [
                {"name": "namespace", "title": "서비스 ID", "default": "harbor_registry"},
                {"name": "service_name", "title": "Compose 서비스 이름", "default": "harbor"},
                {"name": "harbor_version", "title": "Harbor 버전", "default": "v2.15.0"},
                {"name": "http_port", "title": "HTTP 포트", "type": "integer", "default": 8081},
                {"name": "https_port", "title": "HTTPS 포트", "type": "integer", "default": 8444},
                {"name": "admin_password", "title": "관리자 비밀번호", "default": "Harbor12345"},
                {"name": "core_secret", "title": "Core Secret", "default": "harbor_core_secret"},
                {"name": "jobservice_secret", "title": "Jobservice Secret", "default": "harbor_jobservice_secret"},
                {"name": "db_user", "title": "DB 계정", "default": "postgres"},
                {"name": "db_password", "title": "DB 비밀번호", "default": "change_me"},
                {"name": "image", "title": "대표 이미지", "default": "goharbor/harbor-core:v2.15.0"},
            ], ["namespace", "service_name", "harbor_version", "http_port", "https_port", "admin_password", "core_secret", "jobservice_secret", "db_user", "db_password"]),
            "README.md": "\n".join([
                "# Harbor Registry",
                "",
                "Harbor 공식 문서의 Docker Compose 기반 배포 구조를 참고해 만든 운영 초안 템플릿입니다.",
                "",
                "- 대표 이미지: `goharbor/harbor-core:v2.15.0`",
                "- 기본 포트: 8081, 8444",
                "",
                "실제 운영 전에는 인증서, 외부 URL, 영속 볼륨, 추가 Harbor 구성 요소(jobservice, registryctl 등)를 환경에 맞게 보완해야 합니다.",
                "",
            ]),
        },
    }


class TemplatesSeedHarbor:
    default_template = staticmethod(default_template)


Model = TemplatesSeedHarbor()
