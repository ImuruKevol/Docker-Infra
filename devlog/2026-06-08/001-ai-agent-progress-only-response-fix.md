# AI Agent 진행 로그만 남는 응답 표시 회귀 수정

## 사용자 원 요청

스크린샷처럼 AI Agent 응답 시간이 67초로 표시되지만 실제 응답 본문이 표시되지 않고 멈춘 문제를 확인하고 보완해달라는 요청.

## 변경 파일

- `src/angular/app/app.component.ts`
  - AI Agent 메시지에서 진행 로그와 실제 답변 본문을 분리해 추적하도록 내부 상태를 추가.
  - status/heartbeat 진행 로그만 누적된 경우를 실제 답변으로 보지 않도록 `agentMessageHasAnswerContent` 기준을 적용.
  - 스트림이 본문 없이 종료되면 동기 `chat` fallback을 실행하고, fallback 답변을 기존 진행 로그 아래에 표시하도록 수정.
  - 스트림 오류가 진행 로그 뒤에 발생해도 오류 메시지를 본문에 강제로 붙이고 오류 카드로 표시하도록 수정.
- `tests/api/test_wiz_structure_contract.py`
  - 진행 로그만 있는 메시지가 빈 응답 처리/fallback/error 표시를 숨기지 않는 계약 테스트 추가.
- `devlog.md`, `devlog/2026-06-08/001-ai-agent-progress-only-response-fix.md`
  - 작업 이력 기록.

## 확인 결과

- 선택 계약 테스트 성공:
  - `test_ai_agent_progress_lines_do_not_hide_missing_answer`
  - `test_ai_agent_api_requests_can_chain_json_results`
- `wiz_project_build(projectName="main", clean=false)` 성공.
- 브라우저 검증 성공:
  - `https://infra-dev.nanoha.kr/access`에 devmode/project 쿠키를 적용하고 로그인.
  - `/api/ai-agent/stream`이 provider/status 이벤트만 보내고 종료되는 상황을 모킹.
  - 진행 로그 아래에 `/api/ai-agent/chat` fallback 답변이 표시되는 것을 확인.
  - 스트림 오류 이벤트가 진행 로그 뒤에 와도 `ai-agent-message-error` 카드에 오류 본문이 표시되는 것을 확인.

## 남은 리스크

- 전체 테스트 실행은 기존 oversized model file 규칙 위반, live dashboard 인증 401, `page.servers/api.py:625` 응답 위치 이슈 때문에 여전히 실패 가능성이 있음.
- 실제 외부 AI provider가 장시간 응답하지 않는 경우 대기 자체는 유지되지만, 이번 수정으로 종료/오류 이후 본문 없이 멈춘 것처럼 보이는 상태는 방지함.
