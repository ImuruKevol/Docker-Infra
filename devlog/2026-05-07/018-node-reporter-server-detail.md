# 018. Node Reporter와 서버 상세 API/UI 구현

- 날짜: 2026-05-07
- 원 요청: 사용자가 "이어서 진행해줘"라고 요청했다.
- 범위: TODO P5-04 Node Reporter와 서버 상세

## 변경 파일

- `src/model/docker_infra/nodes.py`
- `src/controller/base.py`
- `src/route/api-reporter-metrics/app.json`
- `src/route/api-reporter-metrics/controller.py`
- `src/route/api-nodes-path/controller.py`
- `src/app/page.servers/api.py`
- `src/app/page.servers/view.pug`
- `src/app/page.servers/view.ts`
- `src/app/page.dashboard/api.py`
- `docs/api/openapi.json`
- `docs/docker-infra-runtime.md`
- `README.md`
- `tests/api/test_node_reporter.py`
- `tests/api/test_openapi_contract.py`
- `tests/e2e/specs/servers.spec.ts`
- `devlog.md`
- `devlog/2026-05-07/018-node-reporter-server-detail.md`

## 작업 내용

- node reporter token 발급 API를 추가하고 token 원문은 발급 응답에서만 표시하도록 했다.
- reporter token hash를 `node_credentials.metadata.token_hash`에 저장하고 API 응답에서는 제거했다.
- `/api/reporter/metrics` metric ingestion route를 추가하고 bearer token 또는 `X-Reporter-Token`으로 인증하게 했다.
- CPU, memory, storage, container summary를 `node_metrics`에 저장하고 `reported_at` 기준 최신 metric을 조회하도록 했다.
- node 상세 응답에 `reporter` 상태와 `latest_metric`을 포함했다.
- `/api/nodes/{node_id}/metrics`, `/api/nodes/{node_id}/containers` API를 추가했다.
- `/servers` 화면을 node 목록, 서버 상세 metric, container table을 표시하는 화면으로 교체했다.
- 서버 상세 Playwright spec과 API/DB 통합 테스트를 추가했다.
- 대시보드 진행표와 README, 런타임 문서에 P5-04 완료 내용을 반영했다.

## 검증

- `/opt/conda/envs/docker-infra/bin/python -m json.tool docs/api/openapi.json`
- `/opt/conda/envs/docker-infra/bin/python -m py_compile src/model/docker_infra/nodes.py src/route/api-nodes-path/controller.py src/route/api-reporter-metrics/controller.py src/app/page.servers/api.py tests/api/test_node_reporter.py tests/api/test_openapi_contract.py`
- `/opt/conda/envs/docker-infra/bin/python -m unittest discover tests/api`
  - 결과: 59개 통과, 11개 skip(DB 미설정)
- 테스트 DB migration 적용 후 `tests.api.test_node_reporter`
  - 결과: 5개 통과
- 테스트 DB migration 적용 후 `/opt/conda/envs/docker-infra/bin/python -m unittest discover tests/api`
  - 결과: 74개 통과, 4개 skip
- `npx playwright test --list`
  - 결과: 6개 테스트 목록 확인
- WIZ build
  - 결과: 성공

## Cleanup

- 테스트 DB row는 `test_run_id` 기준으로 삭제되도록 검증했다.
- 테스트 PostgreSQL 컨테이너와 volume, Python cache, 임시 OpenAPI 검증 파일을 제거했다.
