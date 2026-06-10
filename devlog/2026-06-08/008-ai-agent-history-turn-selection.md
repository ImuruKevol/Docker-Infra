# AI Agent 히스토리 turn 카드 드래그 선택 보강

- 날짜: 2026-06-08
- ID: 008
- 리뷰 ID: klffpnhvpdesiwbdgxbcrjlcfoeilcnh

## 사용자 원 요청

정확하게는 `ai-agent-markdown` 클래스가 먹여진 히스토리의 각 세션별 턴 응답 본문 영역만 블록 선택이 안되고 있어. 다른 부분들은 전부 블록이 잘 유지되고 있어.

## 변경 파일

- `src/angular/app/app.component.pug`
- `src/angular/app/app.component.ts`
- `src/angular/app/app.component.scss`
- `tests/api/test_ai_agent_history.py`
- `tests/e2e/specs/ai-agent-selection.spec.ts`
- `devlog.md`
- `devlog/2026-06-08/008-ai-agent-history-turn-selection.md`

## 작업 내용

- 직전 작업에서 추가했던 `ai-agent-history-turn` 복사 버튼 UI와 관련 로직/스타일/테스트를 제거했다.
- `ai-agent-history-turn` 카드 자체에 선택 가능 표시를 유지하고, 카드 내부 텍스트가 브라우저 기본 드래그 선택으로 복사 가능하도록 했다.
- `agentHistoryResponseHtml(turn)`가 매 change detection마다 새 `SafeHtml` 객체를 반환해 `[innerHTML]` DOM을 다시 쓰지 않도록 Markdown HTML을 내용 기준으로 캐싱했다.
- E2E를 복사 버튼 기준이 아니라 `.ai-agent-history-turn .ai-agent-markdown p` 실제 마우스 드래그 선택 기준으로 변경했다.

## 확인 결과

- `/opt/conda/envs/docker-infra/bin/python -m unittest tests.api.test_ai_agent_history`: 통과
- `wiz_project_build(clean=false)`: 통과
- `DOCKER_INFRA_BASE_URL=https://infra-dev.nanoha.kr DOCKER_INFRA_TEST_PASSWORD=... npx playwright test tests/e2e/specs/ai-agent-selection.spec.ts --project=chromium`: 통과
- 독립 브라우저 스크립트에서 히스토리 turn 카드의 Markdown 응답 문단을 실제 마우스 드래그로 선택했을 때 선택 문자열이 생성됨을 확인했다.
