# 224. DDNS API 등록을 와일드카드 프록시 suffix 방식으로 전환

- 날짜: 2026-05-18
- 요청자: 권태욱
- 리뷰 ID: lrmzidmbdswuudpmvcjfayyucjmiofzx

## 원 요청

> DDNS 서버 추가에서 API Base URL은 왜 있는거야?
> 해당 DDNS 서버쪽에는 예를 들어 "*.season.co.kr"이 프록시 서버로 등록이 되어있고, 그 프록시 서버에서는 nginx/apache2 설정으로 "*.customer.season.co.kr" 설정이 이 Docker Infra로 연결이 되는거야. 그래서 이 Docker Infra에서는 "*.customer.season.co.kr"를 와일드카드 도메인으로 해서 사용을 하는거지.
> 그렇게 되면 그냥 wildcard suffix만 설정하면 되고, 다른 설정은 필요가 없어. 이 방식이 DDNS가 맞는지 확인하고 수정해줘.

## 변경 요약

- 요청 구조를 API 기반 DDNS가 아니라 외부 wildcard DNS/프록시가 Docker Infra로 전달하는 suffix 방식으로 정리했다.
- 도메인 관리 화면에서 API Base URL, 등록 경로, health path, token, TLS 검증 입력을 제거하고 wildcard suffix만 저장하게 했다.
- wildcard suffix 도메인은 Cloudflare DNS 작업을 건너뛰되, Docker Infra 로컬 nginx 설정은 정상 생성되도록 배포 흐름을 수정했다.
- 서비스 생성/수정/상태/흐름/프리플라이트 문구와 metadata를 wildcard proxy + nginx 라우팅 기준으로 조정했다.
- 기존 `ddns_endpoints` 테이블은 호환성을 위해 유지하되 API 관련 컬럼을 optional/empty 값으로 완화하는 016 migration을 추가했다.

## 변경 파일

- `src/model/db/migrations/016_wildcard_proxy_endpoints.sql`
- `src/model/db/migrations/016_wildcard_proxy_endpoints.down.sql`
- `src/model/struct/domains_ddns.py`
- `src/model/struct/domains.py`
- `src/model/struct/service_nginx.py`
- `src/model/struct/services.py`
- `src/model/struct/services_delete.py`
- `src/model/struct/services_flow.py`
- `src/model/struct/services_preflight.py`
- `src/model/struct/services_status.py`
- `src/model/struct/services_update.py`
- `src/model/struct/services_wizard.py`
- `src/app/page.domains/api.py`
- `src/app/page.domains/view.pug`
- `src/app/page.domains/view.ts`
- `src/app/page.services/view.pug`
- `src/app/page.services/view.ts`
- `src/app/page.services.create/view.pug`
- `src/app/page.services.create/view.ts`
- `tests/api/test_domain_management_ui.py`
- `devlog.md`
- `devlog/2026-05-18/224-wildcard-proxy-domain-suffix.md`

## DB 적용

- `src/model/db/migrations/016_wildcard_proxy_endpoints.sql` 실행
- `schema_migrations`에 `016 / wildcard_proxy_endpoints` checksum 기록 upsert
- `ddns_endpoints.api_base_url`, `ddns_endpoints.registration_path` nullable 및 empty default 확인

## 검증

- `/opt/conda/envs/docker-infra/bin/python -m py_compile ...`: 통과
- `/opt/conda/envs/docker-infra/bin/python -m unittest tests.api.test_domain_management_ui tests.api.test_services_preflight tests.api.test_migration_schema.MigrationSchemaStaticContractTest`: 19개 테스트 통과
- `scripts/docker_infra_migrate.py status`: 016 적용 및 checksum 일치 확인
- `information_schema.columns`: API 관련 컬럼 nullable/default 완화 확인
- `/opt/conda/envs/docker-infra/bin/wiz project build --project main`: 통과

## 남은 리스크

- 기존 001, 011 migration checksum mismatch와 012, 014 pending 상태는 남아 있어 전체 migration runner는 계속 중단될 수 있다.
- 실제 외부 프록시 서버의 wildcard host 전달, Host header 유지, TLS 종료 방식은 운영 프록시 설정에서 통합 검증이 필요하다.
