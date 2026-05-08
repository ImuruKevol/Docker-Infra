import textwrap


def _schema(title, description, fields, required=None):
    properties = {}
    for item in fields:
        properties[item["name"]] = {
            "title": item["title"],
            "type": item.get("type", "string"),
            "description": item.get("description", ""),
            "default": item.get("default"),
        }
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "title": title,
        "description": description,
        "type": "object",
        "properties": properties,
        "required": required or [],
    }


def _readme(title, summary, image, ports):
    lines = [f"# {title}", "", summary, "", f"- 기본 이미지: `{image}`"]
    if ports:
        lines.append(f"- 기본 포트: {', '.join(str(port) for port in ports)}")
    lines.extend(["", "이 템플릿은 Docker Infra 서비스 생성 규칙에 맞게 healthcheck와 overlay network를 포함합니다.", ""])
    return "\n".join(lines)


def _defaults(namespace, service_name, image, port, extra=None):
    values = {"namespace": namespace, "service_name": service_name, "image": image, "service_port": port}
    values.update(extra or {})
    return values


def default_templates():
    return [
        {
            "name": "Nginx 정적 웹",
            "namespace": "nginx_static",
            "description": "정적 웹 자산을 바로 서비스할 때 사용하는 Nginx 템플릿",
            "metadata": {"category": "service", "primary_image": "nginx:alpine"},
            "files": {
                "docker-compose.yaml": textwrap.dedent(
                    """
                    services:
                      {{ service_name }}:
                        image: {{ image }}
                        ports:
                          - "{{ service_port }}:80"
                        healthcheck:
                          test: ["CMD-SHELL", "wget -qO- http://127.0.0.1/ || exit 1"]
                          interval: 30s
                          timeout: 5s
                          retries: 3
                    """
                ).strip() + "\n",
                "values.default.yaml": textwrap.dedent(
                    """
                    namespace: nginx_static
                    service_name: web
                    image: nginx:alpine
                    service_port: 8080
                    """
                ).strip() + "\n",
                "values.schema.json": _schema("Nginx 정적 웹", "정적 사이트 배포용 기본 템플릿", [
                    {"name": "namespace", "title": "서비스 ID", "default": "nginx_static"},
                    {"name": "service_name", "title": "Compose 서비스 이름", "default": "web"},
                    {"name": "image", "title": "이미지", "default": "nginx:alpine"},
                    {"name": "service_port", "title": "외부 포트", "type": "integer", "default": 8080},
                ], ["namespace", "service_name", "image", "service_port"]),
                "README.md": _readme("Nginx 정적 웹", "간단한 정적 사이트 또는 프런트엔드 번들을 배포합니다.", "nginx:alpine", [8080]),
            },
        },
        {
            "name": "Node.js API",
            "namespace": "node_api",
            "description": "Node.js 런타임 기반 API 서비스를 위한 기본 템플릿",
            "metadata": {"category": "was", "primary_image": "node:24-bookworm-slim"},
            "files": {
                "docker-compose.yaml": "services:\n  {{ service_name }}:\n    image: {{ image }}\n    working_dir: /app\n    command: [\"node\", \"server.js\"]\n    ports:\n      - \"{{ service_port }}:{{ container_port }}\"\n    environment:\n      NODE_ENV: production\n      PORT: \"{{ container_port }}\"\n    healthcheck:\n      test: [\"CMD-SHELL\", \"node -e \\\"fetch('http://127.0.0.1:' + process.env.PORT).then(() => process.exit(0)).catch(() => process.exit(1))\\\"\"]\n      interval: 30s\n      timeout: 5s\n      retries: 3\n",
                "values.default.yaml": "namespace: node_api\nservice_name: api\nimage: node:24-bookworm-slim\nservice_port: 3000\ncontainer_port: 3000\n",
                "values.schema.json": _schema("Node.js API", "Node.js 기반 웹 API", [
                    {"name": "namespace", "title": "서비스 ID", "default": "node_api"},
                    {"name": "service_name", "title": "Compose 서비스 이름", "default": "api"},
                    {"name": "image", "title": "이미지", "default": "node:24-bookworm-slim"},
                    {"name": "service_port", "title": "외부 포트", "type": "integer", "default": 3000},
                    {"name": "container_port", "title": "컨테이너 포트", "type": "integer", "default": 3000},
                ], ["namespace", "service_name", "image", "service_port", "container_port"]),
                "README.md": _readme("Node.js API", "Node.js 기반 API 서버 템플릿입니다.", "node:24-bookworm-slim", [3000]),
            },
        },
        {
            "name": "Spring Boot API",
            "namespace": "springboot_api",
            "description": "JAR 기반 Java 서비스를 위한 Spring Boot 템플릿",
            "metadata": {"category": "was", "primary_image": "eclipse-temurin:21-jre-alpine-3.22"},
            "files": {
                "docker-compose.yaml": "services:\n  {{ service_name }}:\n    image: {{ image }}\n    command: [\"java\", \"-jar\", \"/app/app.jar\"]\n    ports:\n      - \"{{ service_port }}:{{ container_port }}\"\n    environment:\n      SERVER_PORT: \"{{ container_port }}\"\n    healthcheck:\n      test: [\"CMD-SHELL\", \"wget -qO- http://127.0.0.1:{{ container_port }}/actuator/health || exit 1\"]\n      interval: 30s\n      timeout: 5s\n      retries: 3\n",
                "values.default.yaml": "namespace: springboot_api\nservice_name: app\nimage: eclipse-temurin:21-jre-alpine-3.22\nservice_port: 8080\ncontainer_port: 8080\n",
                "values.schema.json": _schema("Spring Boot API", "Spring Boot 애플리케이션용 기본 템플릿", [
                    {"name": "namespace", "title": "서비스 ID", "default": "springboot_api"},
                    {"name": "service_name", "title": "Compose 서비스 이름", "default": "app"},
                    {"name": "image", "title": "이미지", "default": "eclipse-temurin:21-jre-alpine-3.22"},
                    {"name": "service_port", "title": "외부 포트", "type": "integer", "default": 8080},
                    {"name": "container_port", "title": "컨테이너 포트", "type": "integer", "default": 8080},
                ], ["namespace", "service_name", "image", "service_port", "container_port"]),
                "README.md": _readme("Spring Boot API", "Actuator health endpoint를 기준으로 상태를 확인하는 Java API 템플릿입니다.", "eclipse-temurin:21-jre-alpine-3.22", [8080]),
            },
        },
        {
            "name": "PostgreSQL DB",
            "namespace": "postgres_db",
            "description": "단일 PostgreSQL 인스턴스를 배포하는 데이터베이스 템플릿",
            "metadata": {"category": "db", "primary_image": "postgres:18-alpine"},
            "files": {
                "docker-compose.yaml": "services:\n  {{ service_name }}:\n    image: {{ image }}\n    ports:\n      - \"{{ service_port }}:5432\"\n    environment:\n      POSTGRES_DB: {{ database_name }}\n      POSTGRES_USER: {{ database_user }}\n      POSTGRES_PASSWORD: {{ database_password }}\n    volumes:\n      - {{ volume_name }}:/var/lib/postgresql\n    healthcheck:\n      test: [\"CMD-SHELL\", \"pg_isready -U {{ database_user }} -d {{ database_name }}\"]\n      interval: 30s\n      timeout: 5s\n      retries: 5\nvolumes:\n  {{ volume_name }}:\n",
                "values.default.yaml": "namespace: postgres_db\nservice_name: db\nimage: postgres:18-alpine\nservice_port: 5432\ndatabase_name: app\ndatabase_user: app\ndatabase_password: change_me\nvolume_name: postgres_data\n",
                "values.schema.json": _schema("PostgreSQL DB", "PostgreSQL 데이터베이스 템플릿", [
                    {"name": "namespace", "title": "서비스 ID", "default": "postgres_db"},
                    {"name": "service_name", "title": "Compose 서비스 이름", "default": "db"},
                    {"name": "image", "title": "이미지", "default": "postgres:18-alpine"},
                    {"name": "service_port", "title": "외부 포트", "type": "integer", "default": 5432},
                    {"name": "database_name", "title": "DB 이름", "default": "app"},
                    {"name": "database_user", "title": "DB 계정", "default": "app"},
                    {"name": "database_password", "title": "DB 비밀번호", "default": "change_me"},
                    {"name": "volume_name", "title": "Volume 이름", "default": "postgres_data"},
                ], ["namespace", "service_name", "image", "service_port", "database_name", "database_user", "database_password", "volume_name"]),
                "README.md": _readme("PostgreSQL DB", "운영용 단일 PostgreSQL 인스턴스를 시작할 수 있는 기본 템플릿입니다.", "postgres:18-alpine", [5432]),
            },
        },
        {
            "name": "MariaDB DB",
            "namespace": "mariadb_db",
            "description": "MariaDB 기반 애플리케이션용 데이터베이스 템플릿",
            "metadata": {"category": "db", "primary_image": "mariadb:11.8-ubi"},
            "files": {
                "docker-compose.yaml": "services:\n  {{ service_name }}:\n    image: {{ image }}\n    ports:\n      - \"{{ service_port }}:3306\"\n    environment:\n      MARIADB_DATABASE: {{ database_name }}\n      MARIADB_USER: {{ database_user }}\n      MARIADB_PASSWORD: {{ database_password }}\n      MARIADB_ROOT_PASSWORD: {{ root_password }}\n    volumes:\n      - {{ volume_name }}:/var/lib/mysql\n    healthcheck:\n      test: [\"CMD-SHELL\", \"mariadb-admin ping -h 127.0.0.1 -u root -p{{ root_password }}\"]\n      interval: 30s\n      timeout: 5s\n      retries: 5\nvolumes:\n  {{ volume_name }}:\n",
                "values.default.yaml": "namespace: mariadb_db\nservice_name: db\nimage: mariadb:11.8-ubi\nservice_port: 3306\ndatabase_name: app\ndatabase_user: app\ndatabase_password: change_me\nroot_password: root_change_me\nvolume_name: mariadb_data\n",
                "values.schema.json": _schema("MariaDB DB", "MariaDB 데이터베이스 템플릿", [
                    {"name": "namespace", "title": "서비스 ID", "default": "mariadb_db"},
                    {"name": "service_name", "title": "Compose 서비스 이름", "default": "db"},
                    {"name": "image", "title": "이미지", "default": "mariadb:11.8-ubi"},
                    {"name": "service_port", "title": "외부 포트", "type": "integer", "default": 3306},
                    {"name": "database_name", "title": "DB 이름", "default": "app"},
                    {"name": "database_user", "title": "DB 계정", "default": "app"},
                    {"name": "database_password", "title": "DB 비밀번호", "default": "change_me"},
                    {"name": "root_password", "title": "root 비밀번호", "default": "root_change_me"},
                    {"name": "volume_name", "title": "Volume 이름", "default": "mariadb_data"},
                ], ["namespace", "service_name", "image", "service_port", "database_name", "database_user", "database_password", "root_password", "volume_name"]),
                "README.md": _readme("MariaDB DB", "MariaDB 운영 인스턴스용 템플릿입니다.", "mariadb:11.8-ubi", [3306]),
            },
        },
        {
            "name": "Redis Cache",
            "namespace": "redis_cache",
            "description": "Redis 캐시 또는 세션 저장소 템플릿",
            "metadata": {"category": "cache", "primary_image": "redis:8-alpine"},
            "files": {
                "docker-compose.yaml": "services:\n  {{ service_name }}:\n    image: {{ image }}\n    command: [\"redis-server\", \"--appendonly\", \"yes\"]\n    ports:\n      - \"{{ service_port }}:6379\"\n    volumes:\n      - {{ volume_name }}:/data\n    healthcheck:\n      test: [\"CMD\", \"redis-cli\", \"ping\"]\n      interval: 30s\n      timeout: 5s\n      retries: 5\nvolumes:\n  {{ volume_name }}:\n",
                "values.default.yaml": "namespace: redis_cache\nservice_name: redis\nimage: redis:8-alpine\nservice_port: 6379\nvolume_name: redis_data\n",
                "values.schema.json": _schema("Redis Cache", "Redis 캐시 템플릿", [
                    {"name": "namespace", "title": "서비스 ID", "default": "redis_cache"},
                    {"name": "service_name", "title": "Compose 서비스 이름", "default": "redis"},
                    {"name": "image", "title": "이미지", "default": "redis:8-alpine"},
                    {"name": "service_port", "title": "외부 포트", "type": "integer", "default": 6379},
                    {"name": "volume_name", "title": "Volume 이름", "default": "redis_data"},
                ], ["namespace", "service_name", "image", "service_port", "volume_name"]),
                "README.md": _readme("Redis Cache", "세션 저장소와 캐시 용도의 Redis 템플릿입니다.", "redis:8-alpine", [6379]),
            },
        },
        {
            "name": "RabbitMQ Queue",
            "namespace": "rabbitmq_queue",
            "description": "메시지 큐와 관리 UI를 함께 제공하는 RabbitMQ 템플릿",
            "metadata": {"category": "queue", "primary_image": "rabbitmq:4-management"},
            "files": {
                "docker-compose.yaml": "services:\n  {{ service_name }}:\n    image: {{ image }}\n    ports:\n      - \"{{ service_port }}:5672\"\n      - \"{{ management_port }}:15672\"\n    environment:\n      RABBITMQ_DEFAULT_USER: {{ username }}\n      RABBITMQ_DEFAULT_PASS: {{ password }}\n    volumes:\n      - {{ volume_name }}:/var/lib/rabbitmq\n    healthcheck:\n      test: [\"CMD-SHELL\", \"rabbitmq-diagnostics -q ping\"]\n      interval: 30s\n      timeout: 5s\n      retries: 5\nvolumes:\n  {{ volume_name }}:\n",
                "values.default.yaml": "namespace: rabbitmq_queue\nservice_name: rabbitmq\nimage: rabbitmq:4-management\nservice_port: 5672\nmanagement_port: 15672\nusername: app\npassword: change_me\nvolume_name: rabbitmq_data\n",
                "values.schema.json": _schema("RabbitMQ Queue", "RabbitMQ 메시지 브로커 템플릿", [
                    {"name": "namespace", "title": "서비스 ID", "default": "rabbitmq_queue"},
                    {"name": "service_name", "title": "Compose 서비스 이름", "default": "rabbitmq"},
                    {"name": "image", "title": "이미지", "default": "rabbitmq:4-management"},
                    {"name": "service_port", "title": "AMQP 포트", "type": "integer", "default": 5672},
                    {"name": "management_port", "title": "관리 UI 포트", "type": "integer", "default": 15672},
                    {"name": "username", "title": "기본 계정", "default": "app"},
                    {"name": "password", "title": "기본 비밀번호", "default": "change_me"},
                    {"name": "volume_name", "title": "Volume 이름", "default": "rabbitmq_data"},
                ], ["namespace", "service_name", "image", "service_port", "management_port", "username", "password", "volume_name"]),
                "README.md": _readme("RabbitMQ Queue", "관리 UI를 포함한 RabbitMQ 템플릿입니다.", "rabbitmq:4-management", [5672, 15672]),
            },
        },
    ]


class TemplatesSeed:
    default_templates = staticmethod(default_templates)


Model = TemplatesSeed()
