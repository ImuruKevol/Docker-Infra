# 222. DDNS Edge 서버 분리 등록 흐름 추가

- 날짜: 2026-05-17
- 요청자: 권태욱
- 리뷰 ID: lrmzidmbdswuudpmvcjfayyucjmiofzx

## 원 요청

> "*.nanoha.kr"를 받는 서버는 아예 별개의 서버에 있다고 생각을 하고, 거기에서 이 Docker Infra 서비스를 등록만 하면 바로 도메인을 물려서 사용할 수 있도록 하게 하고 싶어. 기존 도메인 설정 부분과 꼬이지 않도록 잘 설계해줘.

## 변경 요약

- Cloudflare zone과 별개로 외부 DDNS Edge 서버를 등록하는 데이터 모델과 마이그레이션을 추가했다.
- 서비스 도메인 선택에서 DDNS endpoint를 zone처럼 선택할 수 있게 하되, Cloudflare `zone_id`와 DDNS metadata가 섞이지 않도록 분리했다.
- DDNS 도메인은 로컬 nginx/certbot/Cloudflare DNS 적용 대상에서 제외하고, 배포 시 외부 DDNS 서버에 서비스 target만 등록하도록 했다.
- 서비스 삭제 시 DDNS 등록도 해제하도록 처리했다.
- 도메인 관리 화면에 DDNS Edge 서버 추가, 상태 확인, 삭제 UI와 API를 추가했다.

## 변경 파일

- `src/model/db/migrations/015_ddns_gateway.sql`
- `src/model/db/migrations/015_ddns_gateway.down.sql`
- `src/model/struct.py`
- `src/model/struct/domains.py`
- `src/model/struct/domains_ddns.py`
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
- `src/app/page.services/api.py`
- `src/app/page.services/view.pug`
- `src/app/page.services/view.ts`
- `src/app/page.services.create/api.py`
- `src/app/page.services.create/view.pug`
- `src/app/page.services.create/view.ts`
- `tests/api/test_domain_management_ui.py`
- `tests/api/test_migration_schema.py`

## 검증

- `/opt/conda/envs/docker-infra/bin/python -m py_compile ...`: 통과
- `cd project/main && /opt/conda/envs/docker-infra/bin/python -m unittest tests.api.test_domain_management_ui tests.api.test_services_preflight tests.api.test_migration_schema.MigrationSchemaStaticContractTest`: 19개 테스트 통과
- `/opt/conda/envs/docker-infra/bin/wiz project build --project main`: 통과

## 남은 리스크

- 외부 DDNS Edge 서버의 실제 API 구현과 응답 schema가 이 클라이언트 계약과 다르면 endpoint 설정 또는 어댑터 조정이 필요하다.
- 실제 `*.nanoha.kr` 위임, TLS 종료, upstream reachability는 별도 DDNS Edge 서버 환경에서 통합 검증이 필요하다.
