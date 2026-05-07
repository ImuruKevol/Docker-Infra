# 서버 상세 웹 터미널 집중 보기 토글과 전체 폭 확장 레이아웃 적용

- 날짜: 2026-05-07
- ID: 041

## 사용자 요청

- 서버 상세에 웹 터미널은 서버 목록 부분을 포함한 컨텐츠 영역을 꽉채워서 볼 수 있도록 토글 버튼을 추가해줘.

## 변경 파일

- `devlog.md`
- `devlog/2026-05-07/041-web-terminal-expand-toggle.md`
- `src/angular/index.pug`
- `src/app/page.servers/view.pug`
- `src/app/page.servers/view.ts`
- `tests/e2e/specs/servers.spec.ts`

## 작업 내용

- 서버 상세 웹 터미널 탭에 `터미널 넓게 보기 / 기본 레이아웃` 토글 버튼을 추가했다.
- 집중 보기 상태에서는 좌측 서버 목록을 숨기고, 서버 상세 상단 요약 카드도 접어서 터미널이 컨텐츠 영역 전체 폭을 사용하도록 바꿨다.
- 집중 보기 상태에서 터미널 카드와 xterm 호스트 높이를 키우고, 토글 직후 `fitTerminal()`을 다시 호출해 실제 셀 크기도 즉시 맞추도록 정리했다.
- 서버 변경이나 다른 상세 탭으로 이동하면 터미널 집중 보기 상태가 자동으로 해제되도록 했다.
- Playwright에 레이아웃 토글 검증을 추가해 서버 목록이 숨겨졌다가 다시 보이는지 확인하도록 했다.
- 검증 중 현재 프로젝트의 `src/angular/index.pug`에 있던 탭/공백 혼용이 Pug build를 막고 있어, 관련 없는 동작 변경 없이 들여쓰기만 정리했다.

## 검증

- `cd /root/docker-infra/project/main && /opt/conda/envs/docker-infra/bin/python -m unittest tests.api.test_wiz_structure_contract`: 통과
- `cd /root/docker-infra/project/main && git diff --check -- src/app/page.servers/view.ts src/app/page.servers/view.pug src/angular/index.pug tests/e2e/specs/servers.spec.ts devlog.md devlog/2026-05-07/041-web-terminal-expand-toggle.md`: 통과
- `wiz_project_build(projectName="main", clean=false)`: 통과
- `systemctl restart wiz.docker-infra`: 완료
- `curl http://127.0.0.1:3001/api/system/health`: 서버 기동 확인
- `cd /root/docker-infra/project/main && DOCKER_INFRA_TEST_PASSWORD='____' DOCKER_INFRA_BASE_URL='http://127.0.0.1:3001' npx playwright test tests/e2e/specs/servers.spec.ts`: 6 passed
