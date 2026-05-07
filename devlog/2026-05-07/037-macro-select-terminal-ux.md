# 공통 검색형 매크로 선택 컴포넌트와 서버 상세 매크로/웹 터미널 UX 보강

- 날짜: 2026-05-07
- ID: 037

## 사용자 요청

- 매크로 검색 및 선택 UI를 공통 컴포넌트로 만들고, select 안에서 실시간 필터링이 되게 해야 했다.
- 서버 상세의 매크로 탭 UI/UX가 어색하므로 전역 매크로 실행 영역과 서버 전용 매크로 관리 영역을 더 자연스럽게 재배치해야 했다.
- 웹 터미널은 사이트 다크모드와 별개로 실제 터미널처럼 검은 배경과 ANSI 색상을 사용해야 하고, bash 고정이 아니라 서버의 실제 로그인 셸 환경을 따라야 했다.
- 웹 터미널의 `터미널 연결` 버튼은 상단 액션 묶음이 아니라 안내 문구 영역으로 옮겨야 했다.

## 변경 파일

- `devlog.md`
- `devlog/2026-05-07/037-macro-select-terminal-ux.md`
- `src/app/component.search.select/app.json`
- `src/app/component.search.select/view.ts`
- `src/app/component.search.select/view.html`
- `src/app/page.servers/view.ts`
- `src/app/page.servers/view.pug`
- `src/model/struct/nodes_terminal.py`
- `tests/api/test_server_macros.py`

## 작업 내용

- `component.search.select` 공통 컴포넌트를 추가하고, 검색 입력과 선택 드롭다운을 한 컴포넌트 안에 묶어 실시간 필터링 가능한 select UI를 만들었다.
- 서버 상세 매크로 탭에서 기존 `검색 input + HTML select` 조합을 제거하고, 새 공통 컴포넌트로 교체했다.
- 매크로 탭은 `매크로 실행` 카드와 `이 서버 전용 매크로` 카드로 분리해, 전역/서버 전용 매크로 실행 흐름과 서버 전용 매크로 관리 흐름이 서로 섞이지 않도록 정리했다.
- 서버 전용 매크로 `추가` 버튼은 해당 카드 헤더로 옮겨, 목록과 동작 위치가 떨어져 보이던 문제를 정리했다.
- 웹 터미널 색상 테마는 다크모드 연동을 제거하고, 검은 배경과 표준 ANSI 계열 색상 팔레트로 고정했다.
- 로컬 터미널은 `pwd` 기반으로 실제 로그인 셸을 찾아 실행하고, 원격 터미널은 SSH 뒤에 별도 `sh -lc ... bash`를 덧붙이지 않고 원격 계정의 기본 로그인 셸로 바로 진입하도록 바꿨다.
- 웹 터미널 안내 박스 안으로 `터미널 연결` 버튼을 이동하고, 연결 전/후 모두 실제 로그인 셸과 ANSI 색상을 사용한다는 설명을 붙였다.
- 정적 계약 테스트에 공통 검색형 select 컴포넌트와 서버 화면의 컴포넌트 사용 여부를 추가했다.

## 검증

- `cd /root/docker-infra/project/main && /opt/conda/envs/docker-infra/bin/python -m py_compile src/model/struct/nodes_terminal.py tests/api/test_server_macros.py`: 통과
- `wiz_project_build(projectName="main", clean=false)`: 통과
- `systemctl restart wiz.docker-infra`: 완료
- `cd /root/docker-infra/project/main && /opt/conda/envs/docker-infra/bin/python -m unittest tests.api.test_server_macros tests.api.test_wiz_structure_contract tests.api.test_migration_schema`: 통과 (`skipped=1`)
- `cd /root/docker-infra/project/main && DOCKER_INFRA_TEST_PASSWORD='____' DOCKER_INFRA_BASE_URL='http://127.0.0.1:3001' npx playwright test tests/e2e/specs/servers.spec.ts`: 5 passed
- `cd /root/docker-infra/project/main && git diff --check`: 통과
