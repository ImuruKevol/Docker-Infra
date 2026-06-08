# AI Agent 진행 요약 스트리밍과 완료 이벤트 처리 재정비

## 사용자 원 요청

AI Agent가 `후보 MCP 액션`, `AI Agent 응답을 기다리는 중입니다` 같은 정적 문구만 보여주고 있어 중간 진행 흐름이 스트리밍되지 않으며, 항상 `스트림 응답을 동기 호출로 다시 확인하는 중입니다` 상태만 보이고 최종 응답이 표시되지 않는 문제를 관련 영역 전반에서 재정비해달라는 요청.

## 변경 파일

- `src/model/struct/ai_assistant.py`
  - 일반 Agent 스트림에 `thinking` 이벤트를 추가해 요청 해석, MCP/API 후보 확인, Agent 실행, 응답 정리 단계를 순차적으로 전달.
  - heartbeat 이벤트도 단순 대기 문구가 아니라 Agent가 MCP 조회와 응답 생성을 계속 진행 중이라는 진행 요약으로 변환.
  - 원문 chain-of-thought가 아니라 사용자에게 안전한 실행 단계 요약만 노출하도록 구성.
- `src/angular/app/app.component.ts`
  - `thinking`, `progress`, `phase` 이벤트를 AI Agent 메시지 진행 로그로 표시.
  - heartbeat는 본문 로그를 계속 늘리지 않고 현재 상태 표시만 갱신.
  - status/progress 이벤트만 받고 terminal 이벤트 없이 끝난 스트림은 동기 fallback 재호출로 빠지지 않고 스트림 미완료 오류를 명확히 표시.
  - fallback이 실제로 필요한 빈 스트림에서는 fallback 확인 상태를 진행 로그에도 남긴 뒤 최종 답변 아래로 이어 붙이도록 유지.
- `tests/api/test_wiz_structure_contract.py`
  - thinking 이벤트 처리, stream incomplete fallback 억제, heartbeat 진행 요약 계약을 확인.
- `devlog.md`, `devlog/2026-06-08/003-ai-agent-thinking-stream-final-response.md`
  - 작업 이력 기록.

## 확인 결과

- 선택 계약 테스트 성공:
  - `test_ai_agent_progress_lines_do_not_hide_missing_answer`
  - `test_ai_agent_api_requests_can_chain_json_results`
- `wiz_project_build(projectName="main", clean=false)` 성공.
- 브라우저 검증 성공:
  - `https://infra-dev.nanoha.kr/access`에 devmode/project 쿠키를 적용하고 로그인.
  - 모킹된 SSE에서 `thinking` 이벤트와 `delta`/`complete`/`done` 최종 응답이 함께 표시되는지 확인.
  - terminal 이벤트 없이 status/thinking만 받고 종료된 스트림이 `chat` fallback으로 재호출되지 않고 미완료 오류로 표시되는지 확인.
  - 위 미완료 케이스에서 `스트림 응답을 동기 호출로 다시 확인하는 중입니다`가 표시되지 않는지 확인.

## 남은 리스크

- 실제 외부 Agent CLI 자체가 제공하는 raw reasoning/chain-of-thought는 노출하지 않고, 안전한 실행 단계 요약만 표시함.
- 실제 Agent provider가 긴 시간 응답하지 않는 경우 heartbeat 기반 진행 요약은 계속 표시되지만 최종 응답 생성 시간은 provider/CLI 상태에 영향을 받음.
- 전체 테스트 실행은 기존 oversized model file 규칙 위반, live dashboard 인증 401, `page.servers/api.py:625` 응답 위치 이슈 때문에 여전히 실패 가능성이 있음.
