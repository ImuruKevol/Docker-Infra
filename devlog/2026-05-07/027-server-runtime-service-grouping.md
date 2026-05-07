# 서버 상세 metric 경량 갱신과 서비스/컨테이너 제어 흐름 보강

- 날짜: 2026-05-07
- ID: 027

## 사용자 요청

서버 상세의 CPU, memory, storage 자동 갱신이 지금은 모든 정보를 다시 읽어 비효율적이니 metric만 따로 갱신하게 바꿔야 한다. 컨테이너 상태 문구와 색상은 실제 가동 상태가 바로 보이도록 수정해야 하고, 각 컨테이너와 등록된 서비스 묶음은 실행/재시작/중지 액션을 확인 modal 뒤에 수행할 수 있어야 한다. 또한 등록 서비스와 미등록 컨테이너를 구분하고, 미등록 컨테이너는 서버 파일 트리에서 Compose 파일을 골라 서비스 초안으로 자동 등록할 수 있어야 하며, 포트 포워딩 정보는 IPv6를 숨기고 host port -> container port 형태 badge로 더 읽기 쉽게 보여줘야 한다.

## 변경 파일

- `../../config.env`
- `devlog.md`
- `docs/docker-infra-development-todo.md`
- `docs/docker-infra-runtime.md`
- `src/app/page.servers/api.py`
- `src/app/page.servers/view.pug`
- `src/app/page.servers/view.ts`
- `src/model/struct/local_command_catalog.py`
- `src/model/struct/nodes.py`
- `src/model/struct/nodes_runtime.py`
- `src/model/struct/nodes_shared.py`
- `src/model/struct/services.py`
- `tests/e2e/specs/servers.spec.ts`

## 작업 내용

- 서버 상세 자동 갱신 경로를 `refresh_metrics`로 분리해 CPU/memory/storage만 다시 읽고, 컨테이너/서비스 목록은 별도 `refresh_containers` 요청에서만 갱신하도록 정리했다.
- `nodes_runtime` mixin을 추가해 live container 수집, 등록 서비스 매칭, 미등록 컨테이너 분리, 단일 컨테이너 액션, 서비스 단위 일괄 액션, 서버 파일 트리 조회를 분리 구현했다.
- `docker ps` label과 port 문자열을 파싱해 `service_namespace`, `runtime_service_name`, `runtime_kind`, `port_bindings` 구조를 만들고 IPv6 published binding은 화면에서 제외했다.
- 서버 화면을 등록 서비스 컨테이너 섹션과 미등록 컨테이너 섹션으로 재구성하고, 등록 서비스는 서비스 단위 실행/재시작/중지 버튼을 제공하도록 바꿨다.
- 각 컨테이너의 상태 badge를 `실행 중`, `재시작 중`, `중지됨`, `이상`, `일시 중지`, `준비됨` 같은 운영 의미 중심 문구와 색상으로 바꿨다.
- 컨테이너 실행/재시작/중지와 서비스 일괄 액션은 모두 확인 modal을 거친 뒤 수행하게 했다.
- 미등록 컨테이너에는 서버 파일 트리 modal을 연결해 `docker-compose.yaml` 또는 `docker-compose.yml`을 선택하면 Compose 내용을 읽어 서비스 초안을 자동 등록하도록 추가했다.
- local master에서도 컨테이너 start/stop/restart가 가능하도록 `config.env`의 `DOCKER_INFRA_LOCAL_EXECUTOR_ALLOWLIST`에 해당 local command를 추가했다.
- TODO와 runtime 문서를 metric 경량 갱신, 서비스/미등록 컨테이너 분리, Compose import 흐름 기준으로 갱신했다.

## 검증

- `wiz_project_build(projectName="main", clean=false)`: 통과
- `/opt/conda/envs/docker-infra/bin/python -m py_compile src/model/struct/nodes_runtime.py src/model/struct/nodes_shared.py src/model/struct/services.py src/model/struct/local_command_catalog.py src/app/page.servers/api.py`: 통과
- `/opt/conda/envs/docker-infra/bin/python -m unittest tests/api/test_wiz_structure_contract.py tests/api/test_node_reporter.py`: 통과
- `git -C /root/docker-infra/project/main diff --check`: 통과
- `DOCKER_INFRA_BASE_URL=http://127.0.0.1:3001 DOCKER_INFRA_TEST_PASSWORD='____' npm run e2e -- tests/e2e/specs/servers.spec.ts`: 통과
