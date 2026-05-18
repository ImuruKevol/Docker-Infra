# 223. DDNS 스키마 미적용 시 도메인 관리 화면 복구

- 날짜: 2026-05-18
- 요청자: 권태욱
- 리뷰 ID: lrmzidmbdswuudpmvcjfayyucjmiofzx

## 원 요청

> 도메인 관리 화면에 "도메인 정보를 불러올 수 없습니다."만 뜨고 있어.

## 변경 요약

- DDNS 테이블이 아직 없는 DB에서도 기존 도메인 관리 화면이 200 응답으로 로드되도록 DDNS 로드 실패를 기존 도메인 로드와 분리했다.
- `ddns_endpoints`, `ddns_registrations` 존재 여부를 먼저 확인하고, 미적용 상태면 DDNS 섹션에 별도 경고를 내려주도록 했다.
- 도메인 관리 UI에 DDNS 경고 표시 상태를 추가했다.
- 기존 migration checksum mismatch 때문에 전체 migration runner가 중단되는 상태를 확인하고, 015 DDNS migration만 현재 DB에 수동 적용해 `schema_migrations` 기록을 맞췄다.

## 변경 파일

- `src/app/page.domains/api.py`
- `src/app/page.domains/view.pug`
- `src/app/page.domains/view.ts`
- `src/model/struct/domains_ddns.py`
- `tests/api/test_domain_management_ui.py`
- `devlog.md`
- `devlog/2026-05-18/223-domain-ddns-schema-pending-fallback.md`

## DB 적용

- `src/model/db/migrations/015_ddns_gateway.sql` 실행
- `schema_migrations`에 `015 / ddns_gateway` checksum 기록 upsert

## 검증

- `/opt/conda/envs/docker-infra/bin/python -m py_compile src/model/struct/domains_ddns.py src/app/page.domains/api.py`: 통과
- `/opt/conda/envs/docker-infra/bin/python -m unittest tests.api.test_domain_management_ui tests.api.test_services_preflight tests.api.test_migration_schema.MigrationSchemaStaticContractTest`: 19개 테스트 통과
- `scripts/docker_infra_migrate.py status`: 015 적용 및 checksum 일치 확인
- `to_regclass('ddns_endpoints')`, `to_regclass('ddns_registrations')`: 테이블 존재 확인
- `/opt/conda/envs/docker-infra/bin/wiz project build --project main`: 통과

## 남은 리스크

- 기존 001, 011 migration checksum mismatch와 012, 014 pending 상태는 남아 있어 전체 migration runner는 계속 중단될 수 있다.
- DDNS Edge 서버 실제 연동은 외부 서버 API가 준비된 뒤 통합 검증이 필요하다.
