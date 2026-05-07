# 서버 목록 load API 경량화와 background 상세 분리

- 날짜: 2026-05-07
- ID: 030

## 사용자 요청

서버 관리 화면의 `load` API가 서버 두 대만 있어도 2.76초나 걸리므로, 서버 수가 늘어나도 감당할 수 있게 반드시 1초 미만으로 줄여달라는 요청이었다.

## 변경 파일

- `devlog.md`
- `devlog/2026-05-07/030-servers-load-api-fast-path.md`
- `src/app/page.servers/api.py`
- `src/app/page.servers/view.ts`
- `src/model/struct/nodes.py`
- `src/route/api-nodes/controller.py`

## 작업 내용

- `nodes.overview_summary()`를 추가해, node 목록과 선택된 node의 기본 정보만 빠르게 반환하는 경량 경로를 분리했다.
- `page.servers/load`와 `page.servers/overview`, `GET /api/nodes`는 더 이상 local master sync나 selected detail/panel을 같이 계산하지 않고 이 fast path를 사용하도록 바꿨다.
- `/servers` 화면은 `load` 응답으로 목록만 즉시 그리고, 이후 `cached_detail`과 background refresh로 상세를 채우도록 조정했다.
- 이 변경으로 첫 목록 API는 local Docker 상태 확인, metric script, live `docker ps` 호출을 전혀 기다리지 않게 됐다.

## 검증

- `/opt/conda/envs/docker-infra/bin/python -m py_compile src/model/struct/nodes.py src/app/page.servers/api.py src/route/api-nodes/controller.py`: 통과
- `/opt/conda/envs/docker-infra/bin/python -m unittest tests/api/test_wiz_structure_contract.py tests/api/test_node_reporter.py tests/api/test_playwright_setup.py tests/api/test_ssh_managed.py`: 통과
- `wiz_project_build(projectName="main", clean=false)`: 통과
- `DOCKER_INFRA_BASE_URL=http://127.0.0.1:3001 DOCKER_INFRA_TEST_PASSWORD='____' npm run e2e -- tests/e2e/specs/servers.spec.ts`: 통과
- 로그인 세션으로 `POST /wiz/api/page.servers/load` 3회 실측: `0.078s`, `0.096s`, `0.078s`
- `git -C /root/docker-infra/project/main diff --check`: 통과
