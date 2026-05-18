# 225. 중간 DDNS 관리 시스템 API 등록 방식 복원

- 날짜: 2026-05-18
- 요청자: 권태욱
- 리뷰 ID: lrmzidmbdswuudpmvcjfayyucjmiofzx

## 원 요청

> 생각해보니 처음 작업한게 맞는 것 같아. 아래는 만들려고 하는 DDNS 서비스에 대한 내용이야. 아래 내용을 참고해서 DDNS 등록에 대한 부분들을 다시 수정해줘.
> ---
> # DNS 관리 시스템
>
> > DDNS를 구현하기 위한 중간 관리 시스템
>
> 이 시스템에 CloudFlare DNS를 등록해놓아야 함(domain, zone id, api key 등)
> 각 도메인마다 서브도메인 + 와일드카드로 권한 관리를 한다.
> ex: 도메인이 season.co.kr이면 *.sub.season.co.kr에 대해 관리 시스템 자체의 API Key를 발급
>
> 각 서브 도메인을 사용하는 시스템(주로 k8s 등 서버 인프라 관리 시스템)에서는 이 중간 관리 시스템을 이용하여 DDNS를 사용하는 식으로 연동된다.
> 각 서버에서는 NetworkManager 등 패키지를 사용해서 IP 변경 시 사용 중인 서브 도메인과 해당 서브 도메인의 API Key, IP를 이 중간 관리 시스템으로 API 형태로 요청하면 이 중간 관리 시스템에 등록된 CloudFlare API 정보를 이용해서 CloudFlare DNS 정보를 수정한다.

## 변경 요약

- DDNS를 외부 reverse proxy가 아니라 Cloudflare 권한을 가진 중간 DDNS 관리 시스템 API로 다시 정리했다.
- 도메인 관리 화면에 API Base URL, 등록/갱신 경로, health path, API Token, TLS 검증 설정을 복원했다.
- DDNS 도메인은 로컬 nginx 설정을 생성하면서 Cloudflare 직접 작업은 건너뛰고, DDNS 관리 API에 `domain`, `subdomain`, `wildcard_suffix`, `ip`, `record_type` payload로 등록하도록 수정했다.
- 서비스 생성/수정 기본 SSL 흐름은 `edge`가 아니라 기존 인증서 확인 후 `certbot` 대상으로 돌아가게 했다.
- 서비스 삭제 시 DDNS 관리 API의 DELETE 경로로 DNS 레코드 삭제를 시도하도록 복원했다.
- 기존 wildcard mode 흔적을 DDNS 관리 모드로 보정하는 017 migration을 추가했다.

## 변경 파일

- `src/model/db/migrations/017_ddns_management_mode.sql`
- `src/model/db/migrations/017_ddns_management_mode.down.sql`
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
- `src/app/page.services/view.ts`
- `src/app/page.services.create/view.ts`
- `tests/api/test_domain_management_ui.py`
- `devlog.md`
- `devlog/2026-05-18/225-ddns-management-api-registration.md`

## DB 적용

- `src/model/db/migrations/017_ddns_management_mode.sql` 실행
- `schema_migrations`에 `017 / ddns_management_mode` checksum 기록 upsert

## 검증

- `/opt/conda/envs/docker-infra/bin/python -m py_compile ...`: 통과
- `/opt/conda/envs/docker-infra/bin/python -m unittest tests.api.test_domain_management_ui tests.api.test_services_preflight tests.api.test_migration_schema.MigrationSchemaStaticContractTest`: 19개 테스트 통과
- `scripts/docker_infra_migrate.py status`: 017 적용 및 checksum 일치 확인
- wildcard-proxy 전환 문구/식별자 제거 확인
- `/opt/conda/envs/docker-infra/bin/wiz project build --project main`: 통과

## 남은 리스크

- 기존 001, 011 migration checksum mismatch와 012, 014 pending 상태는 남아 있어 전체 migration runner는 계속 중단될 수 있다.
- 실제 DDNS 관리 시스템의 API path, 인증 방식, 응답 필드명이 현재 계약과 다르면 endpoint 설정 또는 payload 어댑터 조정이 필요하다.
