# API 테스트 공통 클라이언트와 cleanup 하네스 추가

- **ID**: 009
- **날짜**: 2026-05-06
- **유형**: API 테스트 하네스/cleanup

## 사용자 원 요청

사용자가 작업을 이어서 진행해 달라고 요청했다.

## 작업 요약

TODO P1-02의 API 테스트 공통 클라이언트 기반을 추가했다. `DOCKER_INFRA_BASE_URL`을 사용하는 HTTP client fixture, password-only login fixture, OpenAPI response 검증 helper, TODO 규칙에 맞춘 `test_run_id`/namespace/resource naming helper를 구현했다.

변경성 테스트에서 사용할 cleanup finalizer도 보강했다. cleanup registry는 LIFO 순서로 실행되고 실패 시 retry 후 실패 리소스 report를 남긴다. stale cleanup CLI는 `.runtime/test` 하위 marker 파일을 기준으로 오래된 테스트 리소스만 삭제하도록 만들었다.

실제 password-only 인증 구현은 P3 단계 작업이므로 login fixture는 현재 인증 API가 501을 반환하면 live 테스트에서 skip할 수 있게 했다.

## 변경 파일 목록

### API test fixtures

- `tests/fixtures/api_client.py`: `DockerInfraApiClient`, `password_only_login` fixture 추가
- `tests/fixtures/openapi_response.py`: OpenAPI response schema 조회/검증 helper 추가
- `tests/fixtures/test_ids.py`: `di_test_{yyyymmdd}_{short_uuid}` namespace와 stack/domain/image tag naming helper 보강

### Cleanup

- `tests/cleanup/cleanup_registry.py`: retry/report 지원 cleanup registry와 unittest finalizer 등록 helper 추가
- `tests/cleanup/stale_cleanup.py`: `.runtime/test` marker 기반 stale resource cleanup CLI 추가

### Tests

- `tests/api/test_api_test_harness.py`: API client, OpenAPI response helper, login fixture, cleanup retry/report/finalizer, stale cleanup 검증 추가

### Docs/source

- `docs/docker-infra-runtime.md`: API 테스트 하네스 환경변수, fixture, stale cleanup 명령 문서화
- `src/app/page.dashboard/api.py`: P1-02 완료와 P1-03 대기 상태를 반영하도록 checklist 갱신

### 작업 기록

- `devlog.md`: 009 항목 추가
- `devlog/2026-05-06/009-api-test-client-cleanup-harness.md`: 상세 작업 기록 추가

## 검증

- `/opt/conda/envs/docker-infra/bin/python -m unittest discover tests/api` 실행: 25개 중 21개 통과, live API/Swagger 4개는 `DOCKER_INFRA_BASE_URL` 미설정으로 skip
- `/opt/conda/envs/docker-infra/bin/python -m py_compile tests/fixtures/test_ids.py tests/fixtures/openapi_response.py tests/fixtures/api_client.py tests/cleanup/cleanup_registry.py tests/cleanup/stale_cleanup.py tests/api/test_api_test_harness.py` 실행: 성공
- `/opt/conda/envs/docker-infra/bin/python tests/cleanup/stale_cleanup.py --dry-run` 실행: 성공, stale resource 0개
- `/opt/conda/envs/docker-infra/bin/wiz project build --project main` 실행: 성공
- `git diff --check` 실행: 통과
- 검증 중 생성된 `.runtime`과 `__pycache__` 삭제 완료

## Cleanup

이번 작업은 실제 DB row, Docker container, Docker volume, Swarm resource, proxy 실제 설정, DNS/Harbor/GitLab 리소스를 생성하지 않았다. 테스트가 만든 project-local `.runtime/test` 리소스와 Python bytecode cache는 삭제했다.
