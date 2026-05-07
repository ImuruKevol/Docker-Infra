# PostgreSQL migration 체계와 핵심 테이블 구현

- **ID**: 011
- **날짜**: 2026-05-06
- **유형**: 데이터 모델/migration/API

## 사용자 원 요청

사용자가 "P2-01, P2-02 작업을 진행해줘"라고 요청했다.

## 작업 요약

TODO P2-01의 PostgreSQL 연결과 migration 체계를 추가했다. Docker Infra 전용 DB 연결 helper, migration up/down/status 실행기, `schema_migrations` version table, CLI 명령을 구현했고, 빈 DB에서 `001` migration을 적용하고 재실행 시 중복 적용되지 않는지 검증했다. down migration은 최신 적용 migration을 롤백할 수 있게 구성했으며 runtime 문서에 실행/rollback 정책을 추가했다.

TODO P2-02의 핵심 테이블 20개를 `001_core_schema` migration에 반영했다. 모든 핵심 테이블에 `created_at`, `updated_at`, `metadata`, `test_run_id`를 포함했고, secret 성격의 필드는 평문 column 대신 `_enc` column으로 정의했다. 대표 CRUD 검증을 위해 `/api/system/settings` route와 `SettingsRepository`를 추가했으며, secret 설정 조회 응답은 plaintext를 반환하지 않고 masked response만 노출하도록 했다.

## 변경 파일 목록

### Database/migration

- `requirements.txt`: PostgreSQL driver `psycopg[binary]==3.3.4` 추가
- `src/model/docker_infra/database.py`: PostgreSQL 연결 설정, schema/env helper 추가
- `src/model/docker_infra/migration.py`: migration discovery, checksum, up/down/status, schema version 조회 추가
- `src/model/docker_infra/migrations/001_core_schema.sql`: `schema_migrations`와 Docker Infra 핵심 테이블 20개 추가
- `src/model/docker_infra/migrations/001_core_schema.down.sql`: core schema rollback SQL 추가
- `scripts/docker_infra_migrate.py`: migration `up`, `down`, `status` CLI 추가

### System settings/API

- `src/model/docker_infra/settings.py`: system setting CRUD repository와 secret masking 처리 추가
- `src/model/docker_infra/system.py`: health check에 DB 연결 상태와 schema version 보고 추가
- `src/route/api-system-settings/app.json`: `/api/system/settings` route 설정 추가
- `src/route/api-system-settings/controller.py`: settings list/get/upsert/delete API 추가

### OpenAPI/tests/docs/source

- `docs/api/openapi.json`: system settings API와 request/response schema 추가
- `tests/api/openapi_validator.py`: nullable `$ref` schema 검증 처리 보강
- `tests/api/test_openapi_contract.py`: system settings path/schema 계약 검증 추가
- `tests/api/test_migration_schema.py`: migration SQL 정적 검증, optional PostgreSQL integration 검증 추가
- `docs/docker-infra-runtime.md`: migration 환경변수, 실행, rollback, 테스트 DB cleanup 문서화
- `README.md`: PostgreSQL migration과 settings API 진행 상태 반영
- `src/app/page.dashboard/api.py`: P2-01/P2-02 완료 상태를 반영하도록 checklist 갱신

### 작업 기록

- `devlog.md`: 011 항목 추가
- `devlog/2026-05-06/011-postgresql-migrations-core-tables.md`: 상세 작업 기록 추가

## 검증

- `/opt/conda/envs/docker-infra/bin/python -m json.tool docs/api/openapi.json` 실행: 성공
- `/opt/conda/envs/docker-infra/bin/python -m py_compile src/model/docker_infra/database.py src/model/docker_infra/migration.py src/model/docker_infra/settings.py src/model/docker_infra/system.py scripts/docker_infra_migrate.py tests/api/test_migration_schema.py tests/api/openapi_validator.py` 실행: 성공
- `/opt/conda/envs/docker-infra/bin/python -m unittest discover tests/api` 실행: no-DB 환경에서 33개 중 28개 통과, live API/Swagger와 DB integration 5개는 환경변수 미설정으로 skip
- `docker compose -f docker/compose/test.yaml --profile api up -d postgres`로 테스트 PostgreSQL 실행 후 `scripts/docker_infra_migrate.py up` 실행: `001` 적용 성공
- 동일 DB에서 `scripts/docker_infra_migrate.py up` 재실행: pending migration 없음 확인
- 동일 DB에서 `scripts/docker_infra_migrate.py status` 실행: `001` 적용 상태와 checksum 일치 확인
- 동일 DB 환경으로 `/opt/conda/envs/docker-infra/bin/python -m unittest tests.api.test_migration_schema.PostgreSQLMigrationIntegrationTest` 실행: 2개 통과
- 동일 DB 환경으로 `/opt/conda/envs/docker-infra/bin/python -m unittest discover tests/api` 실행: 35개 중 31개 통과, live API/Swagger 4개는 `DOCKER_INFRA_BASE_URL` 미설정으로 skip
- 동일 DB에서 `scripts/docker_infra_migrate.py down` 실행: `001` rollback 성공
- `/opt/conda/envs/docker-infra/bin/wiz project build --project main` 실행: 성공
- `git diff --check` 실행: 통과

## Cleanup

검증에 사용한 PostgreSQL 테스트 container, network, volume은 `docker compose -f docker/compose/test.yaml --profile api down -v`로 제거했다. 검증 중 생성된 `.runtime`, `__pycache__`, 임시 OpenAPI 출력 파일도 삭제했다. 실제 운영 DB row, Swarm resource, proxy 실제 설정, DNS/Harbor/GitLab 리소스는 생성하지 않았다.
