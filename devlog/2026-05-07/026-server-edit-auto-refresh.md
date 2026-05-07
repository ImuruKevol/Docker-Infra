# 서버 수정 모달, master 고정 목록, 자동 갱신과 SSH 오류 안내 보강

- 날짜: 2026-05-07
- ID: 026

## 사용자 요청

이미 등록된 서버 정보를 수정할 수 있게 해야 하고, 왼쪽의 별도 서버 구성 카드는 서버 목록 카드에 통합해야 한다. 서버 목록은 무조건 중심 서버를 맨 위에 고정하고 그 아래에 일반 서버를 보여줘야 한다. 서버 상세의 CPU, memory, storage 정보는 1초, 3초, 5초, 10초 주기로 갱신할 수 있어야 하고, 컨테이너 포트 포워딩 정보는 더 읽기 쉽게 보여줘야 한다. 의미가 모호한 `상태 수집 준비` UI는 정리해야 하며, 실제로 서버 추가 시 발생한 `SSH 비밀번호로 서버에 접속할 수 없습니다.` 오류 원인도 더 잘 드러나야 한다.

## 변경 파일

- `devlog.md`
- `docs/api/openapi.json`
- `docs/docker-infra-design.md`
- `docs/docker-infra-development-todo.md`
- `docs/docker-infra-runtime.md`
- `src/app/page.servers/api.py`
- `src/app/page.servers/view.pug`
- `src/app/page.servers/view.ts`
- `src/model/struct/nodes.py`
- `src/model/struct/nodes_manage.py`
- `src/model/struct/nodes_registry.py`
- `src/model/struct/nodes_shared.py`
- `src/model/struct/ssh_executor.py`
- `src/route/api-nodes/controller.py`
- `tests/e2e/specs/servers.spec.ts`

## 작업 내용

- 서버 목록 카드 하나로 중심 서버/일반 서버 구성을 통합하고, node 정렬을 `is_local_master DESC` 기준으로 바꿔 중심 서버를 항상 최상단에 고정했다.
- 서버 추가 모달을 서버 수정에도 재사용하도록 바꾸고, `node_id`가 있으면 기존 정보를 수정하는 `save_slave` 경로를 추가했다.
- 수정 시 비밀번호를 비워두면 저장된 SSH key로 다시 연결 확인한 뒤 저장하도록 했고, host/username/port 변경 시에도 같은 검증 흐름을 사용하게 했다.
- 서버 상세는 `detail(refresh=1)` 경로로 local master 또는 SSH check를 다시 실행한 뒤 최신 metric/container 정보를 반환하도록 바꿨다.
- 서버 상세 헤더에 1초, 3초, 5초, 10초 자동 갱신 선택과 즉시 갱신 버튼을 추가했다.
- `상태 수집 준비` 버튼과 token modal을 운영자 화면에서 제거하고, 현재 화면이 로컬 명령/저장된 SSH key로 상태를 갱신한다는 설명만 남겼다.
- 컨테이너 포트 문자열을 backend에서 `port_bindings` 구조로 파싱하고, 화면에서는 `외부 -> 내부/protocol` 형태로 읽기 쉽게 렌더링하도록 바꿨다.
- SSH 실행기는 관리용 `known_hosts` 파일을 별도로 사용하도록 바꾸고, password/key 연결 실패 시 `permission denied`, `connection refused`, `host key verification failed` 같은 원인을 사람이 읽을 수 있는 문장으로 변환해 응답에 포함하도록 보강했다.
- TODO, 설계 문서, runtime 문서, OpenAPI 문서를 서버 수정/자동 갱신/기본 UI 기준에 맞게 갱신했다.

## 검증

- WIZ build: 통과
- Python compile check: 통과
- `python -m unittest tests/api/test_wiz_structure_contract.py tests/api/test_node_reporter.py`: 통과
- `python -m json.tool docs/api/openapi.json`: 통과
- `git -C /root/docker-infra/project/main diff --check`: 통과
- `DOCKER_INFRA_BASE_URL=http://127.0.0.1:3001 DOCKER_INFRA_TEST_PASSWORD='____' npm run e2e -- tests/e2e/specs/servers.spec.ts`: 통과
