# AI Agent 히스토리 목록 텍스트 드래그 선택 보강

- 날짜: 2026-06-08
- ID: 007
- 리뷰 ID: klffpnhvpdesiwbdgxbcrjlcfoeilcnh

## 사용자 원 요청

히스토리쪽에서는 여전히 똑같은 버그가 있어.

## 변경 파일

- `src/angular/app/app.component.pug`
- `src/angular/app/app.component.ts`
- `src/angular/app/app.component.scss`
- `tests/api/test_ai_agent_history.py`
- `tests/e2e/specs/ai-agent-selection.spec.ts`
- `devlog.md`
- `devlog/2026-06-08/007-ai-agent-history-list-selection.md`

## 작업 내용

- 히스토리 목록 카드 본문을 `button`에서 선택 가능한 `role="button"` 요소로 변경해 텍스트 드래그 선택이 가능하도록 했다.
- 드래그 선택 후 발생하는 클릭 이벤트가 히스토리 상세 열기로 오인되지 않도록 선택 활성 상태에서는 `selectAgentHistory` 실행을 무시하도록 보강했다.
- 히스토리 목록, 상세, 다음 동작 텍스트 영역에 명시적인 `user-select: text` 스타일과 선택 보호 대상을 추가했다.
- 히스토리 목록 드래그 선택 E2E를 추가해 목록 텍스트 선택이 유지되고 드래그만으로 상세가 열리지 않는지 검증했다.

## 확인 결과

- `/opt/conda/envs/docker-infra/bin/python -m unittest tests.api.test_ai_agent_history`: 통과
- `wiz_project_build(clean=false)`: 통과
- `DOCKER_INFRA_BASE_URL=https://infra-dev.nanoha.kr DOCKER_INFRA_TEST_PASSWORD=... npx playwright test tests/e2e/specs/ai-agent-selection.spec.ts --project=chromium`: 통과
- 수정 전 히스토리 목록 제목 드래그 선택이 `0`글자로 비는 것을 브라우저 스크립트로 확인했고, 수정 후 Playwright E2E에서 선택 유지가 통과함을 확인했다.
