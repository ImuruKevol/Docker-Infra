# 016. Local Executor와 local command check API 구현

- 날짜: 2026-05-06
- 원 요청: 사용자가 "이어서 진행해줘"라고 요청했다.
- 범위: TODO P5-01 Local Executor

## 변경 파일

- `src/model/docker_infra/local_executor.py`
- `src/model/docker_infra/setup.py`
- `src/route/api-system-local-command-check/app.json`
- `src/route/api-system-local-command-check/controller.py`
- `src/app/page.dashboard/api.py`
- `docs/api/openapi.json`
- `docs/docker-infra-runtime.md`
- `README.md`
- `tests/api/test_local_executor.py`
- `tests/api/test_openapi_contract.py`
- `devlog.md`
- `devlog/2026-05-06/016-local-executor-command-check.md`

## 작업 내용

- Docker Infra 실행 host에서 명령을 실행하는 `LocalExecutor` 모델을 추가했다.
- Docker CLI, Swarm 조회, nginx/apachectl version/configtest adapter를 등록했다.
- `swarm.init`, overlay network 생성, proxy reload 같은 destructive command는 `DOCKER_INFRA_LOCAL_EXECUTOR_ALLOWLIST`에 등록된 경우에만 실행하도록 막았다.
- stdout/stderr, exit code, timeout, duration을 capture하는 공통 result 구조를 정의했다.
- 실패 명령도 예외로 숨기지 않고 `status=error`, `exit_code`, `stderr`를 반환하도록 했다.
- optional `job_id`/`step_ref`가 전달되면 실행 결과를 Job log에 append할 수 있게 연결했다.
- 설치 환경 감지의 Docker/proxy probe가 새 Local Executor adapter를 사용하도록 정리했다.
- `/api/system/local-command/check` route와 OpenAPI 계약을 추가했다.
- 대시보드 진행표와 README, 런타임 문서에 P5-01 완료 내용을 반영했다.

## 검증

- `/opt/conda/envs/docker-infra/bin/python -m json.tool docs/api/openapi.json`
- `/opt/conda/envs/docker-infra/bin/python -m py_compile src/model/docker_infra/local_executor.py src/model/docker_infra/setup.py src/route/api-system-local-command-check/controller.py tests/api/test_local_executor.py tests/api/test_openapi_contract.py`
- `/opt/conda/envs/docker-infra/bin/python -m unittest discover tests/api`
  - 결과: 54개 통과, 9개 skip(DB 미설정)
- 테스트 DB migration 적용 후 `/opt/conda/envs/docker-infra/bin/python -m unittest discover tests/api`
  - 결과: 63개 통과, 4개 skip
- `LocalExecutor().check("docker.version")`
  - 결과: `status=ok`, `exit_code=0`
- `npx playwright test --list`
  - 결과: 5개 테스트 목록 확인
- WIZ build
  - 결과: 성공

## Cleanup

- P5-01 check API 자체는 DB row와 파일을 생성하지 않는다.
- 생성된 임시 OpenAPI 검증 파일과 Python cache를 제거했다.
- 테스트 PostgreSQL 컨테이너와 volume을 제거했다.
