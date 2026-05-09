shared = wiz.model("struct/templates_seed_shared")


def templates():
    return [
        {
            "name": "WordPress 사이트",
            "namespace": "wordpress_site",
            "description": "WordPress 웹 서비스와 MariaDB가 함께 동작하는 홈페이지/블로그 템플릿",
            "metadata": shared.metadata(
                "web",
                "wordpress:latest",
                ["web", "db"],
                public_endpoint={"service": "web", "port": 80, "label": "웹 화면"},
                component_labels={"web": "웹 화면", "db": "데이터베이스"},
                generated_secrets=["database_password", "db_root_password"],
            ),
            "files": {
                "docker-compose.yaml": shared.block("""
                    services:
                      web:
                        image: {{ web_image }}
                        ports:
                          - "{{ service_port }}:80"
                        environment:
                          WORDPRESS_DB_HOST: "{{ namespace }}_db:3306"
                          WORDPRESS_DB_NAME: {{ database_name }}
                          WORDPRESS_DB_USER: {{ database_user }}
                          WORDPRESS_DB_PASSWORD: {{ database_password }}
                        volumes:
                          - wordpress_data:/var/www/html
                        healthcheck:
                          test: ["CMD-SHELL", "curl -fsS http://127.0.0.1/ || exit 1"]
                          interval: 30s
                          timeout: 5s
                          retries: 5
                      db:
                        image: {{ db_image }}
                        environment:
                          MARIADB_DATABASE: {{ database_name }}
                          MARIADB_USER: {{ database_user }}
                          MARIADB_PASSWORD: {{ database_password }}
                          MARIADB_ROOT_PASSWORD: {{ db_root_password }}
                        volumes:
                          - mariadb_data:/var/lib/mysql
                        healthcheck:
                          test: ["CMD-SHELL", "mariadb-admin ping -h 127.0.0.1 -u root -p{{ db_root_password }} || exit 1"]
                          interval: 30s
                          timeout: 5s
                          retries: 5
                    volumes:
                      wordpress_data:
                      mariadb_data:
                """),
                "values.default.yaml": shared.block("""
                    namespace: wordpress_site
                    web_image: wordpress:latest
                    db_image: mariadb:latest
                    service_port: 8080
                    database_name: wordpress
                    database_user: wordpress
                    database_password: wordpress_change_me
                    db_root_password: root_change_me
                """),
                "values.schema.json": shared.schema("WordPress 사이트", "WordPress와 MariaDB를 함께 실행합니다.", shared.base_fields("wordpress_site", "wordpress:latest", 8080) + [
                    {"name": "db_image", "title": "DB 이미지", "default": "mariadb:latest"},
                    {"name": "database_name", "title": "DB 이름", "default": "wordpress"},
                    {"name": "database_user", "title": "DB 계정", "default": "wordpress"},
                    {"name": "database_password", "title": "DB 비밀번호", "default": "wordpress_change_me"},
                    {"name": "db_root_password", "title": "DB 관리자 비밀번호", "default": "root_change_me"},
                ], ["namespace", "web_image", "db_image", "service_port", "database_name", "database_user", "database_password", "db_root_password"]),
                "README.md": shared.readme("WordPress 사이트", "홈페이지, 블로그, 소규모 쇼핑몰의 기본 구성입니다.", 8080, ["WordPress", "MariaDB"]),
            },
        },
        {
            "name": "Nextcloud 파일 공유",
            "namespace": "nextcloud_stack",
            "description": "Nextcloud, PostgreSQL, Redis를 함께 실행하는 파일 공유 템플릿",
            "metadata": shared.metadata(
                "web",
                "nextcloud:latest",
                ["web", "db", "redis"],
                public_endpoint={"service": "web", "port": 80, "label": "파일 공유 화면"},
                component_labels={"web": "파일 공유 화면", "db": "데이터베이스", "redis": "캐시"},
                generated_secrets=["database_password"],
            ),
            "files": {
                "docker-compose.yaml": shared.block("""
                    services:
                      web:
                        image: {{ web_image }}
                        ports:
                          - "{{ service_port }}:80"
                        environment:
                          POSTGRES_HOST: "{{ namespace }}_db"
                          POSTGRES_DB: {{ database_name }}
                          POSTGRES_USER: {{ database_user }}
                          POSTGRES_PASSWORD: {{ database_password }}
                          REDIS_HOST: "{{ namespace }}_redis"
                        volumes:
                          - nextcloud_data:/var/www/html
                        healthcheck:
                          test: ["CMD-SHELL", "php -v >/dev/null 2>&1 || exit 1"]
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
                      redis:
                        image: {{ redis_image }}
                        volumes:
                          - redis_data:/data
                        healthcheck:
                          test: ["CMD", "redis-cli", "ping"]
                          interval: 30s
                          timeout: 5s
                          retries: 5
                    volumes:
                      nextcloud_data:
                      postgres_data:
                      redis_data:
                """),
                "values.default.yaml": shared.block("""
                    namespace: nextcloud_stack
                    web_image: nextcloud:latest
                    db_image: postgres:16
                    redis_image: redis:alpine
                    service_port: 8081
                    database_name: nextcloud
                    database_user: nextcloud
                    database_password: nextcloud_change_me
                """),
                "values.schema.json": shared.schema("Nextcloud 파일 공유", "파일 공유 서비스와 DB/캐시를 함께 실행합니다.", shared.base_fields("nextcloud_stack", "nextcloud:latest", 8081) + [
                    {"name": "db_image", "title": "DB 이미지", "default": "postgres:16"},
                    {"name": "redis_image", "title": "Redis 이미지", "default": "redis:alpine"},
                    {"name": "database_name", "title": "DB 이름", "default": "nextcloud"},
                    {"name": "database_user", "title": "DB 계정", "default": "nextcloud"},
                    {"name": "database_password", "title": "DB 비밀번호", "default": "nextcloud_change_me"},
                ], ["namespace", "web_image", "db_image", "redis_image", "service_port", "database_name", "database_user", "database_password"]),
                "README.md": shared.readme("Nextcloud 파일 공유", "사내 파일 공유와 협업 저장소를 빠르게 구성합니다.", 8081, ["Nextcloud", "PostgreSQL", "Redis"]),
            },
        },
    ]


Model = type("TemplatesSeedWebStacks", (), {"templates": staticmethod(templates)})()
