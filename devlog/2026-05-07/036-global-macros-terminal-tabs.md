# 전역 매크로 관리 화면, 서버 상세 탭형 매크로/웹 터미널, Monaco 다크모드·저장 단축키 적용

- 날짜: 2026-05-07
- ID: 036

## 사용자 요청

- 매크로 수정 모달의 Monaco Editor가 웹 사이트의 현재 다크모드 상태를 따라가야 했다.
- macOS에서는 `Cmd+S`, Windows/Linux에서는 `Ctrl+S`로 저장되게 해야 했다.
- 매크로는 서버 상세 안에서만 관리하는 구조가 아니라, 좌측 사이드 메뉴에 별도 `/macros` 메뉴를 두고 전역으로 관리할 수 있어야 했다.
- 다만 서버 상세에 있던 매크로 기능은 제거하지 않고, 해당 서버에서만 보이는 서버 전용 매크로 타입으로 유지해야 했다.
- 서버 상세는 탭 구조로 정리하고, 매크로는 검색 가능한 선택 UI로 고른 뒤 확인 모달 없이 바로 실행하며, 결과는 탭 내부에 표시해야 했다.
- 서버 상세에 xterm 기반 웹 터미널 탭을 추가하고, 탭 진입만으로는 연결하지 말고 `터미널 연결` 버튼을 눌렀을 때만 PTY 세션을 붙여야 했다.

## 변경 파일

- `devlog.md`
- `devlog/2026-05-07/036-global-macros-terminal-tabs.md`
- `docs/docker-infra-design.md`
- `docs/docker-infra-development-todo.md`
- `src/app/component.nav.sidebar/view.ts`
- `src/assets/lang/en.json`
- `src/assets/lang/ko.json`
- `src/app/page.servers/api.py`
- `src/app/page.servers/socket.py`
- `src/app/page.servers/view.pug`
- `src/app/page.servers/view.ts`
- `src/app/page.macros/api.py`
- `src/app/page.macros/app.json`
- `src/app/page.macros/view.pug`
- `src/app/page.macros/view.ts`
- `src/app/page.macros/view.html` 삭제
- `src/model/db/migrations/005_shell_macros_scope.sql`
- `src/model/db/migrations/005_shell_macros_scope.down.sql`
- `src/model/struct/macros.py`
- `src/model/struct/macros_shared.py`
- `src/model/struct/macros_store.py`
- `src/model/struct/macros_runner.py`
- `src/model/struct/nodes_terminal.py`
- `tests/api/test_server_macros.py`
- `tests/e2e/specs/servers.spec.ts`

## 작업 내용

- `shell_macros`를 전역 매크로와 서버 전용 매크로로 분리하기 위해 `scope_type`, `node_id`를 추가하는 migration `005`를 만들고 실제 DB에도 적용했다.
- 기존 단일 `struct/macros.py`를 `macros_shared.py`, `macros_store.py`, `macros_runner.py`로 분리해 WIZ model 파일 길이 제약을 유지하면서 scope별 저장/조회/실행을 분리했다.
- `/macros` 전용 페이지를 새로 만들고, 좌측 사이드 메뉴에 전역 매크로 메뉴를 추가했다.
- 전역 매크로 페이지는 목록/검색/상세/추가/수정/삭제를 지원하고, Monaco Editor modal을 사용하도록 구성했다.
- 전역 매크로와 서버 전용 매크로 modal 모두에서 `document:keydown` 기준 `Cmd+S` / `Ctrl+S` 저장 단축키를 처리했다.
- Monaco Editor theme는 `<html class="dark">` 변화를 `MutationObserver`로 감지해 `vs` / `vs-dark`로 동기화되게 했다.
- 서버 상세는 `개요`, `매크로`, `웹 터미널` 탭 구조로 재구성했다.
- 서버 상세 매크로 탭은 전역 매크로와 서버 전용 매크로를 함께 조회하고, 검색 가능한 입력 + select 방식으로 선택 후 즉시 실행하도록 바꿨다.
- 서버 상세에서 매크로 실행 결과는 더 이상 modal로 띄우지 않고, 탭 내부 결과 패널에 job 상태와 로그를 표시하도록 변경했다.
- 서버 상세에서 매크로 추가/수정은 서버 전용 매크로로 강제 저장되게 API와 UI payload를 정리했다.
- `page.servers/socket.py`와 `nodes_terminal.py`를 추가해 xterm 웹 터미널용 PTY 세션을 로컬 master와 SSH 관리 서버 모두에서 열 수 있게 했다.
- 웹 터미널은 탭 진입 시 자동 연결하지 않고, `터미널 연결` 버튼을 눌렀을 때만 socket namespace와 PTY 세션을 만들도록 했다.
- 서비스 재기동 후 실제 브라우저에서 터미널 연결/종료까지 확인할 수 있게 Playwright 시나리오를 보강했다.

## 검증

- `cd /root/docker-infra/project/main && /opt/conda/envs/docker-infra/bin/python scripts/docker_infra_migrate.py up`: 통과 (`005` 적용)
- `cd /root/docker-infra/project/main && /opt/conda/envs/docker-infra/bin/python -m py_compile src/app/page.servers/api.py src/app/page.servers/socket.py src/app/page.macros/api.py src/model/struct/macros.py src/model/struct/macros_shared.py src/model/struct/macros_store.py src/model/struct/macros_runner.py src/model/struct/nodes_terminal.py`: 통과
- `wiz_project_build(projectName="main", clean=false)`: 통과
- `systemctl restart wiz.docker-infra`: 완료
- `cd /root/docker-infra/project/main && /opt/conda/envs/docker-infra/bin/python -m unittest tests.api.test_server_macros tests.api.test_wiz_structure_contract tests.api.test_migration_schema`: 통과 (`skipped=1`)
- `cd /root/docker-infra/project/main && DOCKER_INFRA_TEST_PASSWORD='____' /opt/conda/envs/docker-infra/bin/python -m unittest tests.api.test_server_macros.ServerMacrosLiveFlowTest`: 통과
- `cd /root/docker-infra/project/main && DOCKER_INFRA_TEST_PASSWORD='____' DOCKER_INFRA_BASE_URL='http://127.0.0.1:3001' npx playwright test tests/e2e/specs/servers.spec.ts`: 5 passed
- `cd /root/docker-infra/project/main && git diff --check`: 통과
