# DB migration SQL을 현재 schema baseline으로 통합

- **날짜**: 2026-05-19
- **ID**: 240
- **유형**: DB migration 정리
- **요청 원문**: `model/db/migrations 에 DB 형상이 바뀐 과정들이 쭉 순서대로 전부 있음. 근데 같은 테이블에 대해 여러 번 바뀐 것도 있고, 롤백된 것도 있는 등 중복이 좀 많음. 그래서 현재 sql들을 하나의 sql로 싹 정리가 필요함.`

## 변경 사항

- `src/model/db/migrations/001_core_schema.sql`부터 `018_ddns_update_api_contract.sql`까지의 up/down migration 파일을 제거했다.
- `src/model/db/migrations/019_current_schema.sql`과 `019_current_schema.down.sql`을 추가해 현재 DB 형상을 단일 baseline migration으로 정리했다.
- 새 baseline은 기존 DB에 001~018 적용 기록이 있어도 checksum mismatch를 피하도록 별도 버전 `019`로 구성했고, 실행 시 기존 `schema_migrations` 기록을 019 기준으로 정리한다.
- 기존 단계별 migration에 있던 compatibility 동작을 유지했다.
  - `node_credentials.key_file` metadata 이관
  - `shell_macros` scope/index 구조
  - Cloudflare DNS cache 컬럼/테이블
  - Job/GitLab/Harbor/template 제거
  - operation log, backup system, service management index
  - DDNS endpoint/registration 최종 schema와 registration path 기본값
- `tests/api/test_migration_schema.py`를 단일 baseline migration 기준 검증으로 갱신했다.
- `docs/template-removal-todo.md`의 삭제된 migration 파일명 참조를 현재 baseline 파일명으로 갱신했다.

## 변경 파일

- `src/model/db/migrations/019_current_schema.sql`
- `src/model/db/migrations/019_current_schema.down.sql`
- `src/model/db/migrations/001_core_schema*.sql` ~ `018_ddns_update_api_contract*.sql` 삭제
- `tests/api/test_migration_schema.py`
- `docs/template-removal-todo.md`
- `devlog.md`
- `devlog/2026-05-19/240-db-sql-current-schema-consolidation.md`

## 검증

- `/opt/conda/envs/docker-infra/bin/python -m unittest tests.api.test_migration_schema`: 통과
- `/opt/conda/envs/docker-infra/bin/python -m py_compile src/model/db/migration.py tests/api/test_migration_schema.py`: 통과
- `wiz_project_build(projectName=main, clean=false)`: 통과
- 임시 PostgreSQL schema에서 `019_current_schema.sql` 적용: 성공
- 기존 001~018 migration 적용 결과와 새 019 baseline 적용 결과를 임시 PostgreSQL schema 두 개에서 비교했다.
  - 테이블 차이 없음
  - 컬럼 차이 없음
  - 인덱스 차이 없음
  - 제약 차이 없음
  - 트리거 차이 없음

## 남은 리스크

- 실제 운영/개발 DB에는 새 migration을 적용하지 않았다. 배포 시 migration runner가 `019_current_schema`를 적용하면서 `schema_migrations`를 019 기준으로 정리한다.
