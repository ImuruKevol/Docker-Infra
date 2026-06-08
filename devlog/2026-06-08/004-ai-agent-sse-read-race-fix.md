# AI Agent SSE read race로 최종 응답 누락되는 문제 수정

## 사용자 원 요청

AI Agent UI에서 실제 Codex 계정으로 테스트해도 진행 로그만 표시되고 `AI Agent 응답 스트림이 완료되지 않았고 표시할 본문이 없습니다.`로 끝나는 문제를 실제 브라우저 테스트로 확인하고, Agent가 정상 동작하도록 수정해달라는 요청.

## 변경 파일

- `src/angular/app/app.component.ts`
  - `streamAgentChat`의 SSE reader tick 처리에서 매초 새 `reader.read()`를 만드는 구조를 제거.
  - 하나의 pending `readPromise`만 유지하고, 실제 read 결과를 소비한 뒤에만 다음 read를 생성하도록 수정.
  - 이로써 오래 대기한 뒤 도착한 `delta`/`complete`/`done` chunk가 이전에 버려진 read promise로 들어가 프론트에서 누락되는 race를 방지.
- `tests/api/test_wiz_structure_contract.py`
  - SSE reader가 pending read를 재사용하는 계약을 추가.
- `devlog.md`, `devlog/2026-06-08/004-ai-agent-sse-read-race-fix.md`
  - 작업 이력 기록.

## 확인 결과

- 선택 계약 테스트 성공:
  - `test_ai_agent_progress_lines_do_not_hide_missing_answer`
- `wiz_project_build(projectName="main", clean=false)` 성공.
- 실제 브라우저 검증 성공:
  - `https://infra-dev.nanoha.kr/access`에서 로그인 후 AI Agent UI를 열고 실제 Codex Agent 요청 실행.
  - `현재 AI Agent 상태를 짧게 알려줘` 요청에서 진행 요약, 최종 응답 본문, suggested action, TODO 완료 표시 확인.
  - `AI Agent 응답 스트림이 완료되지 않았고 표시할 본문이 없습니다.`와 `스트림 응답을 동기 호출로 다시 확인하는 중입니다.`가 표시되지 않는지 확인.
- 진단 확인:
  - 같은 요청의 원본 SSE에는 `delta`/`complete`/`done`이 정상 포함되어 있었고, 기존 프론트 파서의 overlapping read가 final chunk 누락 원인임을 확인.

## 남은 리스크

- 실제 Agent provider가 긴 시간 응답하지 않는 경우 응답 시간 자체는 provider/CLI 상태에 영향을 받음.
- 전체 테스트 실행은 기존 oversized model file 규칙 위반, live dashboard 인증 401, `page.servers/api.py:625` 응답 위치 이슈 때문에 여전히 실패 가능성이 있음.
