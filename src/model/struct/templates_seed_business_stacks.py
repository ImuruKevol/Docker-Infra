shared = wiz.model("struct/templates_seed_shared")


def templates():
    return [
        {
            "name": "Odoo 업무 관리",
            "namespace": "odoo_suite",
            "description": "Odoo 업무 관리 웹 서비스와 PostgreSQL DB를 함께 실행하는 템플릿",
            "metadata": shared.metadata(
                "web",
                "odoo:18",
                ["web", "db"],
                public_endpoint={"service": "web", "port": 8069, "label": "업무 관리 화면"},
                component_labels={"web": "업무 관리 화면", "db": "데이터베이스"},
                generated_secrets=["database_password"],
            ),
            "files": {
                "docker-compose.yaml": shared.block("""
                    services:
                      web:
                        image: {{ web_image }}
                        ports:
                          - "{{ service_port }}:8069"
                        environment:
                          HOST: "{{ namespace }}_db"
                          USER: {{ database_user }}
                          PASSWORD: {{ database_password }}
                        volumes:
                          - odoo_data:/var/lib/odoo
                        healthcheck:
                          test: ["CMD-SHELL", "curl -fsS http://127.0.0.1:8069/web/login || exit 1"]
                          interval: 30s
                          timeout: 5s
                          retries: 5
                      db:
                        image: {{ db_image }}
                        environment:
                          POSTGRES_DB: postgres
                          POSTGRES_USER: {{ database_user }}
                          POSTGRES_PASSWORD: {{ database_password }}
                        volumes:
                          - postgres_data:/var/lib/postgresql/data
                        healthcheck:
                          test: ["CMD-SHELL", "pg_isready -U {{ database_user }} -d postgres"]
                          interval: 30s
                          timeout: 5s
                          retries: 5
                    volumes:
                      odoo_data:
                      postgres_data:
                """),
                "values.default.yaml": shared.block("""
                    namespace: odoo_suite
                    web_image: odoo:18
                    db_image: postgres:16
                    service_port: 8069
                    database_user: odoo
                    database_password: odoo_change_me
                """),
                "values.schema.json": shared.schema("Odoo 업무 관리", "업무 관리/ERP 서비스를 DB와 함께 실행합니다.", shared.base_fields("odoo_suite", "odoo:18", 8069) + [
                    {"name": "db_image", "title": "DB 이미지", "default": "postgres:16"},
                    {"name": "database_user", "title": "DB 계정", "default": "odoo"},
                    {"name": "database_password", "title": "DB 비밀번호", "default": "odoo_change_me"},
                ], ["namespace", "web_image", "db_image", "service_port", "database_user", "database_password"]),
                "README.md": shared.readme("Odoo 업무 관리", "업무 관리, 재고, CRM 등 Odoo 기반 서비스를 구성합니다.", 8069, ["Odoo", "PostgreSQL"]),
            },
        },
        {
            "name": "Wiki.js 문서 사이트",
            "namespace": "wikijs_site",
            "description": "Wiki.js 웹 서비스와 PostgreSQL DB를 함께 실행하는 문서 관리 템플릿",
            "metadata": shared.metadata(
                "web",
                "requarks/wiki:2",
                ["web", "db"],
                public_endpoint={"service": "web", "port": 3000, "label": "문서 사이트 화면"},
                component_labels={"web": "문서 사이트 화면", "db": "데이터베이스"},
                generated_secrets=["database_password"],
            ),
            "files": {
                "docker-compose.yaml": shared.block("""
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
                """),
                "values.default.yaml": shared.block("""
                    namespace: wikijs_site
                    web_image: requarks/wiki:2
                    db_image: postgres:16
                    service_port: 3000
                    database_name: wiki
                    database_user: wiki
                    database_password: wiki_change_me
                """),
                "values.schema.json": shared.schema("Wiki.js 문서 사이트", "사내 문서 사이트를 DB와 함께 실행합니다.", shared.base_fields("wikijs_site", "requarks/wiki:2", 3000) + [
                    {"name": "db_image", "title": "DB 이미지", "default": "postgres:16"},
                    {"name": "database_name", "title": "DB 이름", "default": "wiki"},
                    {"name": "database_user", "title": "DB 계정", "default": "wiki"},
                    {"name": "database_password", "title": "DB 비밀번호", "default": "wiki_change_me"},
                ], ["namespace", "web_image", "db_image", "service_port", "database_name", "database_user", "database_password"]),
                "README.md": shared.readme("Wiki.js 문서 사이트", "사내 매뉴얼, 운영 문서, 정책 문서를 관리하는 위키 서비스입니다.", 3000, ["Wiki.js", "PostgreSQL"]),
            },
        },
    ]


Model = type("TemplatesSeedBusinessStacks", (), {"templates": staticmethod(templates)})()
