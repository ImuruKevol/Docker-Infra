# 실제 사용 DB schema 기준 unused table 정리

- **날짜**: 2026-05-20
- **ID**: 273
- **유형**: DB schema 정리
- **요청 원문**: `실제 사용하는 스키마로 싹 정리할 것. 작업 진행해줘.`

## 변경 사항

- 실제 앱 코드에서 사용하는 `service_image_backups` 테이블을 정식 migration schema로 승격했다.
- `service_image_backups`에 `service_id/created_at`, `digest` 인덱스와 `updated_at` trigger를 명시했다.
- 더 이상 앱 코드에서 조회/갱신하지 않는 legacy 테이블을 `020_actual_schema_cleanup.sql`에서 제거하도록 했다.
  - `proxy_configs`
  - `certificates`
  - `electron_setting_backups`
- 기록/조회 코드가 없는 캐시성 테이블의 unused `test_run_id` 컬럼을 제거하도록 했다.
  - `cloudflare_dns_records.test_run_id`
  - `images.test_run_id`
- 인증서 목록은 DB `certificates` 테이블 대신 현재 실제 저장소인 `system_settings` 기반 `webserver` 모델에서 읽도록 catalog 코드를 정리했다.
- legacy 설정 백업 테이블 조회는 제거하고 빈 목록으로 반환하도록 정리했다.
- migration static contract 테스트를 `019` baseline + `020` cleanup 구조에 맞게 갱신했다.

## 변경 파일

- `src/model/db/migrations/020_actual_schema_cleanup.sql`
- `src/model/db/migrations/020_actual_schema_cleanup.down.sql`
- `src/model/struct/service_image_backups.py`
- `src/model/struct/infra_catalog_registry.py`
- `src/model/struct/infra_catalog.py`
- `tests/api/test_migration_schema.py`
- `devlog.md`
- `devlog/2026-05-20/273-db-actual-schema-cleanup.md`

## 검증

- `/opt/conda/envs/docker-infra/bin/python -m py_compile src/model/struct/service_image_backups.py src/model/struct/infra_catalog_registry.py src/model/struct/infra_catalog.py tests/api/test_migration_schema.py`: 통과
- `/opt/conda/envs/docker-infra/bin/python -m unittest tests.api.test_migration_schema.MigrationSchemaStaticContractTest`: 통과
- `wiz_project_build(projectName=main, clean=false)`: 통과
- migration 목록 확인: `019_current_schema`, `020_actual_schema_cleanup` 순서 확인
- 앱 코드 내 `proxy_configs`, `electron_setting_backups`, DB `certificates` table 직접 조회 참조 제거 확인

## 남은 리스크

- 실제 운영/개발 DB에는 migration을 직접 적용하지 않았다. 배포 시 migration runner가 `020_actual_schema_cleanup`을 적용해야 한다.
- `019`는 이미 적용됐을 가능성을 고려해 checksum을 변경하지 않았다. 신규 설치 기준으로는 `019` 생성 후 `020`에서 legacy table을 제거한다.
