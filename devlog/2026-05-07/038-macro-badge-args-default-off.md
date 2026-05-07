# 서버 상세 매크로 선택 뱃지 정렬과 실행 인자 기본 비활성 UX 적용

- 날짜: 2026-05-07
- ID: 038

## 사용자 요청

- 서버 상세의 실행할 매크로 search select에서 `이 서버 전용`, `전역` 뱃지를 매크로 이름 바로 오른쪽에 붙여야 했다.
- search select 바로 아래에 있던 설명 카드는 제거해야 했다.
- 실행 인자는 기본적으로 사용하지 않는 흐름으로 바꾸고, 체크박스를 켰을 때만 입력창이 보이게 해야 했다.

## 변경 파일

- `devlog.md`
- `devlog/2026-05-07/038-macro-badge-args-default-off.md`
- `src/app/component.search.select/view.html`
- `src/app/page.servers/view.ts`
- `src/app/page.servers/view.pug`
- `tests/e2e/specs/servers.spec.ts`

## 작업 내용

- 공통 search select 컴포넌트에서 선택값과 드롭다운 목록 모두 매크로 이름 옆에 badge가 바로 붙도록 레이아웃을 조정했다.
- 서버 상세 매크로 탭에서 search select 아래에 있던 선택 매크로 설명 카드를 제거했다.
- `macroArgsEnabled` 상태를 추가하고, 실행 인자는 기본 비활성으로 두었다.
- `실행 인자 사용` 체크박스를 켰을 때만 입력창이 보이도록 바꿨다.
- 매크로 실행 API에는 체크가 켜져 있을 때만 인자를 넘기고, 꺼져 있으면 빈 문자열로 실행되도록 정리했다.
- 웹 터미널 E2E는 연결 성공 판정을 badge 문자열 대신 `다시 연결` 버튼과 `연결 종료` 버튼 활성화로 확인하도록 안정화했다.

## 검증

- `wiz_project_build(projectName="main", clean=false)`: 통과
- `cd /root/docker-infra/project/main && /opt/conda/envs/docker-infra/bin/python -m unittest tests.api.test_server_macros tests.api.test_wiz_structure_contract`: 통과 (`skipped=1`)
- `systemctl restart wiz.docker-infra`: 완료
- `cd /root/docker-infra/project/main && DOCKER_INFRA_TEST_PASSWORD='____' DOCKER_INFRA_BASE_URL='http://127.0.0.1:3001' npx playwright test tests/e2e/specs/servers.spec.ts`: 5 passed
- `cd /root/docker-infra/project/main && git diff --check`: 통과
