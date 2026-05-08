# 062. 최초 구성 마법사 백업 시스템 토글과 설정 스키마 추가

## 사용자 요청

> 이어서 진행해줘.

직전 작업에서 정리한 남은 TODO 순서에 따라 P2 `최초 구성 마법사` 작업을 이어서 진행했다.

## 변경 파일

- `config/docker_infra.py`
  - 내장 Harbor 백업 저장소 기본 data directory와 기본 HTTP/HTTPS 포트 설정 함수를 추가했다.
- `src/model/db/migrations/009_backup_system_settings.sql`
- `src/model/db/migrations/009_backup_system_settings.down.sql`
  - 내장 백업 시스템 상태와 용량 정보를 저장할 `backup_system_settings` 스키마를 추가했다.
- `src/model/struct/backup_system.py`
  - 백업 시스템 기본 설정, 상태 조회, 최초 구성 저장, 저장 경로 용량 계산 로직을 추가했다.
- `src/model/struct.py`
  - `backup_system` struct 접근자를 추가했다.
- `src/model/struct/setup.py`
  - 최초 구성 상태 응답에 `backup_system`을 포함하고, 설치 완료 시 백업 시스템 선택값을 저장하도록 연결했다.
- `src/app/page.access/api.py`
  - 최초 구성 완료 응답에 백업 시스템 상태를 포함했다.
- `src/app/page.access/view.ts`
- `src/app/page.access/view.pug`
  - 최초 구성 화면에 `서비스 백업 시스템 구성` 토글을 추가했다.
  - 기본 비활성화, 저장 경로, 예상 남은 용량, 필요 포트 안내를 표시했다.
- `docs/docker-infra-remaining-todo.md`
- `docs/docker-infra-development-todo.md`
  - 완료된 P2 항목과 backup system config schema 항목을 반영했다.
- `docs/api/openapi.json`
- `tests/api/test_migration_schema.py`
- `tests/api/test_openapi_contract.py`
  - setup API와 DB schema 계약에 `BackupSystemStatus`와 `backup_system_settings`를 반영했다.

## DB 적용

- `009_backup_system_settings` migration을 실제 DB에 적용했다.

## 검증

- `python -m py_compile src/model/struct/backup_system.py src/model/struct/setup.py src/model/struct.py config/docker_infra.py`
- `PYTHONPATH=tests/api /opt/conda/envs/docker-infra/bin/python -m unittest tests.api.test_migration_schema.MigrationSchemaStaticContractTest tests.api.test_openapi_contract.OpenApiContractTest.test_static_openapi_contains_initial_contract tests.api.test_openapi_contract.OpenApiContractTest.test_static_openapi_contains_p1_common_components tests.api.test_openapi_contract.OpenApiContractTest.test_static_response_examples_match_declared_schemas`
- `wiz_project_build(clean=false)`
- `git diff --check`

## 남은 작업

- 백업 시스템 활성화 시 실제 Harbor Compose 설치/실행은 P3에서 이어서 구현한다.
- 설치 실패 시 재시도/건너뛰기/비활성화 선택지는 실제 설치 실행 API와 함께 연결해야 한다.
