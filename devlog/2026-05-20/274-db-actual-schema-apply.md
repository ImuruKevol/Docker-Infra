# 실제 DB에 schema cleanup migration 적용

- **날짜**: 2026-05-20
- **ID**: 274
- **유형**: DB migration 적용
- **요청 원문**: `실제 DB에도 적용해줘.`

## 변경 사항

- 실제 DB의 migration 상태를 확인했다.
  - 적용 전 `019_current_schema`, `020_actual_schema_cleanup` 모두 미적용 상태였다.
- migration runner로 실제 DB에 미적용 migration을 적용했다.
  - 적용된 migration: `019`, `020`
- 적용 후 schema 상태를 확인했다.
  - `service_image_backups` 테이블 존재 확인
  - `proxy_configs`, `certificates`, `electron_setting_backups` 제거 확인
  - `cloudflare_dns_records.test_run_id`, `images.test_run_id` 제거 확인
  - `schema_migrations`에 `019`, `020` 적용 기록 확인

## 변경 파일

- `devlog.md`
- `devlog/2026-05-20/274-db-actual-schema-apply.md`

## 검증

- `/opt/conda/envs/docker-infra/bin/python`으로 `migration.status()` 확인: `019`, `020` 적용 전 미적용
- `/opt/conda/envs/docker-infra/bin/python`으로 `migration.migrate_up()` 실행: `applied=019,020`
- `/opt/conda/envs/docker-infra/bin/python`으로 실제 DB information schema 확인:
  - `service_image_backups`: present
  - `proxy_configs`: missing
  - `certificates`: missing
  - `electron_setting_backups`: missing
  - `cloudflare_dns_records` 컬럼 목록에 `test_run_id` 없음
  - `images` 컬럼 목록에 `test_run_id` 없음

## 남은 리스크

- 이번 작업은 실제 DB schema에 destructive cleanup을 적용했다. 제거된 legacy 테이블/컬럼 데이터는 down migration 또는 별도 백업 없이는 복구되지 않는다.
