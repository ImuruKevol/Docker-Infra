# 019. Compose 검증기와 validation API 구현

- 날짜: 2026-05-07
- 원 요청: 사용자가 "이어서 진행해줘"라고 요청했다.
- 범위: TODO P6-01 Compose 검증기

## 변경 파일

- `src/model/docker_infra/compose_validator.py`
- `src/route/api-compose-validate/app.json`
- `src/route/api-compose-validate/controller.py`
- `src/app/page.dashboard/api.py`
- `docs/api/openapi.json`
- `docs/docker-infra-runtime.md`
- `README.md`
- `tests/api/test_compose_validator.py`
- `tests/api/test_openapi_contract.py`
- `devlog.md`
- `devlog/2026-05-07/019-compose-validator-api.md`

## 작업 내용

- YAML parser 기반 Compose loader와 duplicate key scan을 추가했다.
- `namespace` regex와 compose filename 정책을 검증하도록 했다.
- service별 `container_name`, `hostname`을 금지하고 정확한 `details[].path`와 error code를 반환하도록 했다.
- service network는 `docker_infra_overlay`만 허용하고 누락된 service/root overlay network를 normalized Compose에 보강하도록 했다.
- `deploy.replicas`, `deploy.update_config`, `deploy.rollback_config`, `deploy.restart_policy` 기본 정책을 보강하되 기존 값을 유지하도록 했다.
- Compose `healthcheck` 또는 요청 payload의 Job health check를 요구하도록 했다.
- `/api/compose/validate` route와 OpenAPI schema/example을 추가했다.
- 대시보드 진행표, README, 런타임 문서에 P6-01 완료 내용을 반영했다.

## 검증

- `/opt/conda/envs/docker-infra/bin/python -m json.tool docs/api/openapi.json`
  - 결과: JSON 파싱 성공
- `/opt/conda/envs/docker-infra/bin/python -m py_compile src/model/docker_infra/compose_validator.py src/route/api-compose-validate/controller.py tests/api/test_compose_validator.py`
  - 결과: 성공
- `/opt/conda/envs/docker-infra/bin/python -m unittest discover tests/api -p 'test_compose_validator.py'`
  - 결과: 9개 통과
- `/opt/conda/envs/docker-infra/bin/python -m unittest discover tests/api`
  - 결과: 68개 통과, 11개 skip(DB/live API 미설정)
- WIZ build
  - 결과: 성공
- `npx playwright test --list`
  - 결과: 6개 테스트 목록 확인
- `git diff --check`
  - 결과: 성공

## Cleanup

- P6-01 검증기는 DB row나 파일을 생성하지 않는다.
- Python `__pycache__` 디렉토리를 제거했다.
