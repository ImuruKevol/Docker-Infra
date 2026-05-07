# Job/Step/Log 모델과 API 구현

- **ID**: 014
- **날짜**: 2026-05-06
- **유형**: Job Queue/API/테스트

## 사용자 원 요청

사용자가 작업을 이어서 진행해 달라고 요청했다.

## 작업 요약

TODO P4-01의 Job/Step/Log 모델과 API를 구현했다. P2에서 이미 만든 `jobs`, `job_steps`, `job_logs` table을 사용하므로 새 migration은 추가하지 않았다. Job 생성, 목록, 상세 조회, job 상태 전이, step 상태 전이, stream별 log append, cancel, retry 기능을 `docker_infra/jobs.py` repository로 묶었다.

상태 전이는 명시적으로 제한했다. Job은 `pending -> running/canceled`, `running -> succeeded/failed/canceled`만 허용하며 terminal 상태에서는 직접 재전이하지 않는다. Step은 `pending -> running/skipped/canceled`, `running -> succeeded/failed/canceled`만 허용한다. Step 실패/취소/전체 완료 상태는 parent job 상태에 반영된다.

Failed job retry는 기존 row를 재사용하지 않고 새 job을 만든다. 새 job metadata에는 `retry_of`, `retry_attempt`를 기록하고, step metadata에는 `retry_of_step`을 기록해 이전 로그와 retry 로그가 `job_id` 기준으로 분리되도록 했다.

## 변경 파일 목록

### Model/API routes

- `src/model/docker_infra/jobs.py`: Job/Step/Log repository, 상태 전이, log append, cancel, retry, cleanup 구현
- `src/route/api-jobs/app.json`: `/api/jobs` route 추가
- `src/route/api-jobs/controller.py`: job 목록 조회와 생성 API 추가
- `src/route/api-jobs-path/app.json`: `/api/jobs/<path:path>` route 추가
- `src/route/api-jobs-path/controller.py`: detail, status, step status, logs, cancel, retry action API 추가

### OpenAPI/docs/tests

- `docs/api/openapi.json`: `/api/jobs`, `/api/jobs/{job_id}`, status/step/log/cancel/retry path와 Job schema 추가
- `tests/api/test_jobs_api.py`: Job API 정적 검증과 PostgreSQL integration 검증 추가
- `tests/api/test_openapi_contract.py`: Job API path/schema 계약 검증 추가
- `docs/docker-infra-runtime.md`: Job Queue API, 상태 전이, retry/log 분리 정책 문서화
- `README.md`: P4-01 구현 상태 반영
- `src/app/page.dashboard/api.py`: P4-01 완료 상태 반영

### 작업 기록

- `devlog.md`: 014 항목 추가
- `devlog/2026-05-06/014-job-step-log-api.md`: 상세 작업 기록 추가

## 검증

- `/opt/conda/envs/docker-infra/bin/python -m json.tool docs/api/openapi.json` 실행: 성공
- `/opt/conda/envs/docker-infra/bin/python -m py_compile src/model/docker_infra/jobs.py src/route/api-jobs/controller.py src/route/api-jobs-path/controller.py tests/api/test_jobs_api.py tests/api/test_openapi_contract.py` 실행: 성공
- `/opt/conda/envs/docker-infra/bin/python -m unittest discover tests/api` 실행: no-DB 환경에서 44개 중 36개 통과, live API/Swagger와 DB integration 8개는 환경변수 미설정으로 skip
- `docker compose -f docker/compose/test.yaml --profile api up -d postgres`로 테스트 PostgreSQL 실행 후 `scripts/docker_infra_migrate.py up` 실행: `001`, `002` 적용 성공
- 동일 DB 환경으로 `/opt/conda/envs/docker-infra/bin/python -m unittest tests.api.test_jobs_api.JobsRepositoryIntegrationTest` 실행: 3개 통과
- 동일 DB 환경으로 `/opt/conda/envs/docker-infra/bin/python -m unittest discover tests/api` 실행: 52개 중 48개 통과, live API/Swagger 4개는 `DOCKER_INFRA_BASE_URL` 미설정으로 skip
- `npx playwright test --list` 실행: Chromium 기준 2개 spec 파일, 5개 테스트 discovery 성공
- `/opt/conda/envs/docker-infra/bin/wiz project build --project main` 실행: 성공
- `git diff --check` 실행: 통과

## Cleanup

검증에 사용한 PostgreSQL 테스트 container, network, volume은 `docker compose -f docker/compose/test.yaml --profile api down -v`로 제거했다. 통합 테스트가 만든 job, step, log row는 `test_run_id` 기준 cleanup helper가 삭제했다. 검증 중 생성된 `.runtime`, `__pycache__`, 임시 OpenAPI 출력 파일도 삭제했다. 실제 운영 DB row, Swarm resource, proxy 실제 설정, DNS/Harbor/GitLab 리소스는 생성하지 않았다.
