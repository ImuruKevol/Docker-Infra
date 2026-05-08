# 061. Job route/model 제거와 operation log 기반 실행 기록 전환

## 사용자 요청

이전 작업에 이어 남은 작업을 순서대로 진행한다. P1 순서에 따라 기존 Job 시스템을 제거하고, 실행 결과와 위험 작업 기록을 lightweight operation log 기준으로 전환한다.

## 변경 파일

- `src/model/struct/operations.py`: `operation_logs` 저장, 상태 전이, output append, 조회 모델을 추가했다.
- `src/model/db/migrations/008_remove_job_system.sql`: `operation_logs` 테이블을 추가하고 기존 `jobs`, `job_steps`, `job_logs` 테이블을 제거하는 migration을 추가했다.
- `src/model/db/migrations/008_remove_job_system.down.sql`: rollback 시 기존 Job 테이블을 복구하는 down migration을 추가했다.
- `src/route/api-jobs/`, `src/route/api-jobs-path/`: 기존 Job route를 삭제했다.
- `src/model/struct/jobs.py`, `src/model/struct/jobs_shared.py`, `src/model/struct/jobs_logs.py`, `src/model/struct/jobs_lifecycle.py`: 기존 Job model을 삭제했다.
- `src/model/struct/local_executor.py`, `src/route/api-system-local-command-check/controller.py`: local command의 `job_id`, `step_ref` 연동을 제거했다.
- `src/model/struct/nodes.py`, `src/model/struct/nodes_join.py`, `src/route/api-nodes-path/controller.py`: Swarm join 흐름을 Job 대신 operation 반환으로 전환했다.
- `src/model/struct/macros_runner.py`, `src/app/page.servers/api.py`, `src/app/page.servers/view.ts`, `src/app/page.servers/view.pug`: 매크로 실행과 polling을 `/api/jobs` 대신 `operation_status`와 operation output 기준으로 전환했다.
- `src/model/struct/nodes_runtime.py`: 컨테이너/서비스 컨테이너 start, stop, restart 결과를 operation log에 기록하도록 했다.
- `src/model/struct/images.py`: Harbor artifact/project/repository 삭제와 로컬 이미지 삭제 결과를 operation log에 기록하도록 했다.
- `src/model/struct/domains.py`, `src/model/struct/domains_cloudflare.py`: 도메인 zone, DNS record, 인증서 생성/수정/삭제/동기화 결과를 operation log에 기록하도록 했다.
- `src/model/struct/compose_rules.py`, `src/model/struct/compose_validator.py`, `src/model/struct/services.py`: `job_health_check` 용어를 `health_check`/`has_health_check` 기준으로 정리했다.
- `src/model/struct/infra_catalog.py`, `src/model/struct/infra_catalog_registry.py`, `src/model/struct/services_runtime.py`: dashboard/service detail의 최근 작업 조회를 `operation_logs` 기준으로 변경했다.
- `src/app/page.dashboard/view.ts`, `src/app/page.dashboard/view.pug`, `src/app/page.services/view.pug`: 최근 Job UI를 최근 작업/operation UI로 변경했다.
- `tests/api/test_jobs_api.py`: Job API 테스트를 제거했다.
- `tests/api/test_migration_schema.py`, `tests/api/test_sample_cleanup.py`, `tests/api/test_secret_masking_logs.py`, `tests/api/test_server_macros.py`: operation log 구조와 macro operation polling 기준으로 테스트를 갱신했다.
- `docs/docker-infra-development-todo.md`, `docs/docker-infra-remaining-todo.md`: P1 Job 시스템 제거 체크리스트를 완료 상태로 반영했다.
- `devlog.md`: 061 작업 요약 row를 추가했다.
- `devlog/2026-05-08/061-remove-job-system-operation-log.md`: 상세 devlog를 추가했다.

## 검증

- `/opt/conda/envs/docker-infra/bin/python`으로 `migration.migrate_up()` 실행: `008` migration 적용 완료.
- `python -m py_compile src/model/struct/operations.py src/model/struct/local_executor.py src/model/struct/nodes.py src/model/struct/nodes_join.py src/model/struct/macros_runner.py src/model/struct/compose_rules.py src/model/struct/compose_validator.py src/model/struct/services_runtime.py`: 통과.
- `python -m py_compile src/model/struct/images.py src/model/struct/domains.py src/model/struct/domains_cloudflare.py`: 통과.
- `rg -n "wiz\\.model\\(\"struct/jobs|struct\"\\)\\.jobs|/api/jobs|api-jobs|JobError|job_id|step_ref|job_health_check" src tests docs/api/openapi.json`: 실제 소스/테스트/OpenAPI에서 제거 확인. 기존 core/down migration의 과거 테이블 정의는 제외했다.
- `python -m unittest tests.api.test_sample_cleanup tests.api.test_secret_masking_logs tests.api.test_migration_schema tests.api.test_server_macros.ServerMacrosStaticContractTest`: 통과.
- `PYTHONPATH=tests/api python -m unittest tests.api.test_openapi_contract.OpenApiContractTest.test_static_openapi_contains_initial_contract tests.api.test_openapi_contract.OpenApiContractTest.test_static_openapi_contains_p1_common_components tests.api.test_openapi_contract.OpenApiContractTest.test_static_response_examples_match_declared_schemas`: 통과.
- `git diff --check`: 통과.
- `wiz_project_build(clean=false)`: 통과.
