# 서버 관리 모달 UX와 관리용 SSH key 등록 흐름 보강

- 날짜: 2026-05-07
- ID: 025

## 사용자 요청

서버 관리 화면의 추가/수정 입력 영역을 모달로 분리하고, 서버 추가 시 관리자/일반 서버 역할 선택을 없애야 한다. Docker Infra 실행 서버는 자동으로 local master로 등록되어야 하며, 서버 추가는 password 접속 확인 후 SSH key file과 fingerprint를 확인/생성하고 DB에는 key file과 fingerprint만 저장해야 한다. 서버 상세에는 CPU, memory, storage, containers 정보가 표시되어야 하고, Reporter/token/check 같은 기술 용어와 설계 문서 대비 부족한 서버 관리 기능을 보완해야 한다.

## 변경 파일

- `README.md`
- `config/docker_infra.py`
- `docs/api/openapi.json`
- `docs/docker-infra-design.md`
- `docs/docker-infra-development-todo.md`
- `src/app/page.servers/api.py`
- `src/app/page.servers/view.pug`
- `src/app/page.servers/view.ts`
- `src/model/db/migrations/003_node_ssh_key_file.sql`
- `src/model/db/migrations/003_node_ssh_key_file.down.sql`
- `src/model/struct/local_command_catalog.py`
- `src/model/struct/nodes.py`
- `src/model/struct/nodes_join.py`
- `src/model/struct/nodes_local_master.py`
- `src/model/struct/nodes_registry.py`
- `src/model/struct/nodes_shared.py`
- `src/model/struct/ssh_executor.py`
- `src/model/struct/ssh_managed.py`
- `src/route/api-nodes/controller.py`
- `tests/api/test_nodes_swarm.py`
- `tests/e2e/helpers/auth.ts`
- `tests/e2e/specs/servers.spec.ts`

## 작업 내용

- 서버 추가 UI를 사이드 패널에서 모달로 분리하고 역할 선택을 제거했다.
- 서버 등록 backend를 password 최초 접속 확인, SSH fingerprint 확인, 관리용 SSH key file 자동 생성, remote `authorized_keys` 등록, key 기반 재접속 확인 순서로 바꿨다.
- `node_credentials.key_file` migration을 추가하고, password/private key 원문 저장 대신 key file과 fingerprint 공개 상태만 응답하도록 정리했다.
- `check`와 `join`이 저장된 key file, SSH 계정, port를 사용하도록 SSH 실행 경로를 보강했다.
- local master 자동 동기화와 local/remote CPU, memory, storage, container snapshot 저장 흐름을 추가했다.
- 서버 상세 화면에 CPU, memory, storage, container summary/table, SSH key 상태, 최신 수집 시간을 표시했다.
- "Reporter" 용어는 화면에서 "상태 수집"으로 낮춰 표현하고, 결과 확인은 모달로 표시하도록 바꿨다.
- 설계 문서, TODO, OpenAPI, E2E/API 테스트 계약을 변경된 서버 등록 흐름에 맞게 갱신했다.

## 검증

- `scripts/docker_infra_migrate.py up`: migration `003` 적용 완료
- Python compile check: 통과
- `python -m json.tool docs/api/openapi.json`: 통과
- `git diff --check`: 통과
- WIZ clean build: 통과
- `python -m unittest tests.api.test_node_reporter.NodeReporterStaticContractTest tests.api.test_nodes_swarm.NodesSwarmStaticContractTest tests.api.test_wiz_structure_contract`: 통과
- `DOCKER_INFRA_TEST_PASSWORD=... DOCKER_INFRA_BASE_URL=http://127.0.0.1:3001 npm run e2e -- tests/e2e/specs/servers.spec.ts`: 통과
