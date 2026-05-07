# OpenAPI/Swagger 공통 계약과 schema 검증 테스트 보강

- **ID**: 008
- **날짜**: 2026-05-06
- **유형**: API 계약/테스트 하네스

## 사용자 원 요청

사용자가 다음 작업들을 이어서 진행해 달라고 요청했고, 작업 규모가 크지 않으면 여러 작업을 이어서 진행해도 좋다고 했다.

## 작업 요약

TODO P1-01의 OpenAPI/Swagger 기반을 보강했다. 기존 `/openapi.json`, `/swagger`, `/api/system/health`, 대시보드, password-only login placeholder 계약을 유지하면서 공통 error schema, pagination metadata, job status/summary, secret masking response schema, session cookie security scheme을 추가했다.

`jsonschema`가 현재 conda 환경에 설치되어 있지 않아 새 의존성을 추가하지 않고, 테스트 전용 최소 OpenAPI response validator를 구현했다. 이 validator는 `$ref`, `required`, 기본 타입, enum, nullable, `additionalProperties: false`를 검증한다. 정적 OpenAPI 예시가 선언된 schema와 맞지 않거나 required/enum이 깨지면 API 테스트가 실패하도록 고정했다.

Swagger UI route가 `/openapi.json`을 바라보는지도 정적 테스트와 선택적 live HTTP 테스트로 확인하도록 추가했다.

## 변경 파일 목록

### API 계약

- `docs/api/openapi.json`: tags, `sessionCookie` security scheme, page/page_size parameter, `ErrorData`, `ErrorDetail`, `PaginationMeta`, `SecretMaskedValue`, `JobStatus`, `JobStepStatus`, `JobSummary`, `JobStepSummary` schema 추가

### 테스트

- `tests/api/openapi_validator.py`: 테스트 전용 최소 OpenAPI response schema validator 추가
- `tests/api/test_openapi_contract.py`: 공통 component 존재, response example schema 검증, required/enum 실패 검증, live response schema 검증 추가
- `tests/api/test_swagger_contract.py`: Swagger UI가 `/openapi.json`을 연결하는지 정적/선택적 live 테스트 추가

### Source app

- `src/app/page.dashboard/api.py`: P1-01 완료와 P1-02 진행 상태를 반영하도록 checklist 갱신

### 작업 기록

- `devlog.md`: 008 항목 추가
- `devlog/2026-05-06/008-openapi-swagger-common-contracts.md`: 상세 작업 기록 추가

## 검증

- `/opt/conda/envs/docker-infra/bin/python -m json.tool docs/api/openapi.json` 실행: JSON 파싱 성공
- `/opt/conda/envs/docker-infra/bin/python -m unittest discover tests/api` 실행: 18개 중 14개 통과, live API/Swagger 4개는 `DOCKER_INFRA_BASE_URL` 미설정으로 skip
- `/opt/conda/envs/docker-infra/bin/python -m py_compile src/app/page.dashboard/api.py tests/api/openapi_validator.py tests/api/test_openapi_contract.py tests/api/test_swagger_contract.py` 실행: 성공
- `/opt/conda/envs/docker-infra/bin/wiz project build --project main` 실행: 성공
- `git diff --check` 실행: 통과
- 검증 중 생성된 `.runtime`, `/tmp/docker-infra-openapi.json`, `__pycache__` 삭제 완료

## Cleanup

이번 작업은 실제 DB row, Docker container, Docker volume, Swarm resource, proxy 실제 설정, DNS/Harbor/GitLab 리소스를 생성하지 않았다. 테스트 중 생성된 project-local runtime/cache 산출물만 삭제했다.
