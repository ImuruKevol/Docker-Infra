# 서버 상세 race 방지, Docker 미설치 안내, SSH key 표시 정리와 서버 매크로 실행 기능 추가

- 날짜: 2026-05-07
- ID: 035

## 사용자 요청

- 서버 상세에서 상태 갱신 API 응답이 늦게 도착한 상태에서 다른 서버를 클릭하면 화면 정보가 꼬이는 문제를 고쳐야 했다.
- 일반 서버 상세에서 raw SSH fingerprint 문자열은 숨기고, key file 위치/존재 여부와 fingerprint 등록 상태만 보이게 해야 했다.
- Docker가 설치되지 않았거나 daemon에 연결할 수 없는 서버는 등록 서비스 컨테이너/미등록 컨테이너 카드를 숨기고, Docker를 사용할 수 없는 서버라는 사실을 명확히 보여줘야 했다.
- Electron 설계 문서에만 있던 매크로(스크립트 실행) 관리/실행 기능을 웹 서비스에도 추가해야 했다. 매크로는 저장/수정/삭제/실행이 가능해야 하고, 서버별 실행 시 인자를 따로 넣을 수 있어야 하며, 편집기는 Monaco Editor를 사용해야 했다.

## 변경 파일

- `devlog.md`
- `devlog/2026-05-07/035-servers-race-docker-macro-ui.md`
- `docs/docker-infra-design.md`
- `docs/docker-infra-development-todo.md`
- `src/app/page.servers/api.py`
- `src/app/page.servers/view.ts`
- `src/app/page.servers/view.pug`
- `src/model/db/migrations/004_shell_macros.sql`
- `src/model/db/migrations/004_shell_macros.down.sql`
- `src/model/struct.py`
- `src/model/struct/macros.py`
- `src/model/struct/nodes_runtime.py`
- `src/model/struct/nodes_runtime_state.py`
- `src/model/struct/nodes_view.py`
- `tests/api/test_migration_schema.py`
- `tests/api/test_server_macros.py`
- `tests/e2e/specs/servers.spec.ts`

## 작업 내용

- 서버 상세 화면에 selection epoch 기반 stale-response 차단 로직을 넣어, 이전 서버의 `cached_detail`, `refresh_metrics`, `refresh_containers` 응답이 늦게 도착해도 현재 선택된 서버 상세를 덮어쓰지 않도록 정리했다.
- `cached_detail`과 `refresh_containers`가 내려주는 node payload를 `nodes_view.py` 기준으로 최소화하고, 일반 서버 상세에서는 raw fingerprint를 제거한 `username`, `has_key_file`, `key_file_path`, `fingerprint_registered`만 내려주도록 정리했다.
- 서버 상세 UI는 raw fingerprint 문자열 대신 `관리용 SSH key` 카드에서 key file 경로와 준비 상태, fingerprint 등록 상태만 보여주게 바꿨다. 로컬 중심 서버는 key file/fingerprint가 불필요하다는 상태로 별도 표기했다.
- `docker ps` 실패가 `docker: command not found`, daemon 연결 실패 등 Docker 미가용 상태로 판정되면 예외를 던지지 않고 `docker.available=false`를 상세 payload에 포함하도록 runtime 경로를 조정했다.
- Docker 미가용 서버는 상세 화면에 경고 카드를 먼저 보여주고, 등록 서비스 컨테이너/미등록 컨테이너 패널은 렌더하지 않도록 분기했다. 상단 컨테이너 요약도 `Docker 사용 불가` 기준으로 바꿨다.
- `shell_macros` 테이블 migration과 `struct/macros.py`를 추가해 웹 UI에서 매크로를 저장/수정/삭제/실행할 수 있게 했다.
- 매크로 실행은 local master에서는 로컬 bash temp script로, 일반 서버에서는 저장된 관리용 SSH key를 사용한 원격 bash temp script로 실행되게 구성했다.
- 매크로 실행 시 인자를 별도로 입력할 수 있게 했고, `shlex.split`으로 인자를 파싱해 `$1`, `$2`, `$@` 형태로 사용할 수 있게 했다.
- 매크로 실행 결과는 기존 job/log 모델에 연결해 실행 이력과 stdout/stderr를 action modal에서 바로 볼 수 있게 했다.
- 서버 화면에 Monaco Editor 기반 매크로 추가/수정 모달을 추가했고, 서버별 매크로 실행 인자 입력과 실행 버튼을 노출했다.
- Playwright 서버 화면 테스트에 stale response 방지 시나리오를 추가했다.

## 검증

- `python -m unittest tests.api.test_wiz_structure_contract tests.api.test_migration_schema tests.api.test_server_macros`: 통과 (`OK`, `skipped=1`)
- `DOCKER_INFRA_TEST_PASSWORD='____' python -m unittest tests.api.test_server_macros.ServerMacrosLiveFlowTest`: 통과
- live API 확인:
  - `/wiz/api/page.servers/load`에서 `mini2` 조회 가능 확인
  - `/wiz/api/page.servers/cached_detail`의 `credential` 키가 `username`, `has_key_file`, `key_file_path`, `fingerprint_registered`만 포함하는 것 확인
  - `mini2`의 `docker` 상태가 `available=false`, `reason='bash: line 1: docker: command not found'`로 내려오는 것 확인
- `wiz_project_build(projectName="main", clean=false)`: 통과
- `DOCKER_INFRA_TEST_PASSWORD='____' DOCKER_INFRA_BASE_URL='http://127.0.0.1:3001' npx playwright test tests/e2e/specs/servers.spec.ts`: 3 passed
- `git -C /root/docker-infra/project/main diff --check`: 통과
