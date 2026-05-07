# 서버 상세 cached 초기 렌더와 미등록 Compose 등록 UX 최적화

- 날짜: 2026-05-07
- ID: 029

## 사용자 요청

서버 상세 화면의 첫 로딩이 너무 느리니 API 분리나 최적화로 개선하고, 필요하면 UI에서도 빨라 보이도록 처리해달라는 요청이었다. 또한 미등록 컨테이너는 컨테이너별로 Compose 등록을 하는 것이 아니라, 하나의 Compose가 여러 컨테이너를 포함할 수 있으므로 표 상단에 공용 `Compose 등록` 버튼이 있어야 한다는 요구가 있었다.

## 변경 파일

- `devlog.md`
- `devlog/2026-05-07/029-server-cached-detail-compose-import.md`
- `docs/docker-infra-development-todo.md`
- `docs/docker-infra-runtime.md`
- `src/app/page.servers/api.py`
- `src/app/page.servers/view.pug`
- `src/app/page.servers/view.ts`
- `src/model/struct/nodes.py`
- `src/model/struct/nodes_runtime.py`

## 작업 내용

- 서버 상세 최초 진입과 node 전환 시 live `docker ps` 결과를 기다리지 않도록 cached 상세 경로를 추가했다.
- `nodes_runtime`에 `cached_containers_panel`, `cached_detail`을 추가해 DB에 저장된 최신 metric snapshot과 container snapshot으로 즉시 상세를 만들 수 있게 했다.
- `nodes.overview()`도 선택된 node에 대해 cached container/service grouping 결과를 함께 반환하도록 바꿔, `/servers` 첫 진입은 별도 상세 API를 한 번 더 기다리지 않고 바로 렌더링하게 했다.
- page API에 `cached_detail()` endpoint를 추가했다.
- 화면은 overview/cached detail로 먼저 그린 뒤, `refresh_metrics`와 `refresh_containers`를 background로 다시 호출해 실제 최신 상태를 맞추도록 바꿨다.
- 상세 헤더에 `저장된 상태를 불러오는 중`, `최근 상태를 다시 확인하는 중` 안내를 넣어 체감 로딩을 개선했다.
- 미등록 컨테이너의 `Compose 등록` 버튼을 개별 row에서 제거하고, 섹션 상단 공용 버튼으로 이동했다.
- 공용 Compose 등록 modal은 특정 컨테이너가 없어도 동작하도록 문구를 일반화했다.

## 검증

- `wiz_project_build(projectName="main", clean=false)`: 통과
- `/opt/conda/envs/docker-infra/bin/python -m py_compile src/model/struct/nodes.py src/model/struct/nodes_runtime.py src/app/page.servers/api.py`: 통과
- `/opt/conda/envs/docker-infra/bin/python -m unittest tests/api/test_wiz_structure_contract.py tests/api/test_node_reporter.py tests/api/test_playwright_setup.py tests/api/test_ssh_managed.py`: 통과
- `DOCKER_INFRA_BASE_URL=http://127.0.0.1:3001 DOCKER_INFRA_TEST_PASSWORD='____' npm run e2e -- tests/e2e/specs/servers.spec.ts tests/e2e/specs/services.spec.ts`: 통과
- `git -C /root/docker-infra/project/main diff --check`: 통과
