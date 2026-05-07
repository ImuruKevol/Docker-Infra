# 015. Secret masking과 로그 검색/다운로드 구현

- 날짜: 2026-05-06
- 원 요청: 사용자가 "이어서 진행해줘"라고 요청했다.
- 범위: TODO P4-02 Secret masking과 로그 보존

## 변경 파일

- `src/model/docker_infra/secret_masking.py`
- `src/model/docker_infra/jobs.py`
- `src/route/api-jobs-path/controller.py`
- `src/app/page.dashboard/api.py`
- `docs/api/openapi.json`
- `docs/docker-infra-runtime.md`
- `README.md`
- `tests/api/test_secret_masking_logs.py`
- `tests/api/test_jobs_api.py`
- `tests/api/test_openapi_contract.py`
- `devlog.md`
- `devlog/2026-05-06/015-secret-masking-log-retention.md`

## 작업 내용

- `system_settings`의 암호화된 secret 값을 masking registry로 읽는 `secret_masking` 모델을 추가했다.
- Job log append 시 stdout/stderr/system message를 DB 저장 전에 masking하도록 변경했다.
- log append body와 metadata의 `secret_values`를 runtime secret으로 받아 저장 전 masking에 포함했다.
- 민감 key assignment와 PEM private key block을 heuristic masking 대상으로 추가했다.
- `/api/jobs/{job_id}/logs/search`와 `/api/jobs/{job_id}/logs/download` 계약과 route를 추가했다.
- 검색 query에 secret 원문이 들어와도 query를 먼저 masking한 뒤 저장된 masking log를 검색하도록 했다.
- 대시보드 진행표와 런타임 문서, README에 P4-02 완료 내용을 반영했다.

## 검증

- `/opt/conda/envs/docker-infra/bin/python -m json.tool docs/api/openapi.json`
- `/opt/conda/envs/docker-infra/bin/python -m py_compile src/model/docker_infra/secret_masking.py src/model/docker_infra/jobs.py src/route/api-jobs-path/controller.py tests/api/test_secret_masking_logs.py tests/api/test_jobs_api.py tests/api/test_openapi_contract.py`
- `/opt/conda/envs/docker-infra/bin/python -m unittest discover tests/api`  
  - 결과: 47개 통과, 9개 skip(DB 미설정)
- 테스트 DB migration 적용 후 `tests.api.test_secret_masking_logs.SecretMaskingLogsIntegrationTest`
  - 결과: 1개 통과
- 테스트 DB migration 적용 후 `/opt/conda/envs/docker-infra/bin/python -m unittest discover tests/api`
  - 결과: 56개 통과, 4개 skip
- `npx playwright test --list`
  - 결과: 5개 테스트 목록 확인
- WIZ build
  - 결과: 성공
- `git diff --check`
  - 결과: 통과

## Cleanup

- 통합 테스트 row는 `test_run_id` 기준 cleanup finalizer로 삭제되도록 검증했다.
- 테스트 PostgreSQL 컨테이너와 volume을 검증 후 제거했다.
- `__pycache__`와 `.runtime` 생성 산출물이 남지 않았는지 확인했다.
