# AI Agent 빈 채팅의 이전 세션 재사용 방지

## 사용자 원 요청

ReviewOps 리뷰 `fgybpixqijmclqfyrzvinrbpouodgytx`의 요청:

AI Agent 채팅 세션이 이상하게 동작하고 있어.
현재 히스토리를 보면 히스토리가 나오고, 그 해당 채팅 세션마다 어떤 요청과 응답이 왔는지 떠.
근데 나는 분명히 새로운 채팅에서 시작했는데, 전혀 다른 이전 요청들과 채팅 세션이 묶여있는 버그가 있어.

## 변경 파일

- `src/angular/app/app.component.ts`
  - AI Agent 세션 ID 맵을 `localStorage` 대신 현재 페이지 인스턴스 메모리에만 보관하도록 변경.
  - 빈 채팅 UI가 브라우저에 남은 이전 `session_id`를 자동 복원해 새 요청을 과거 히스토리 세션에 붙이는 경로를 제거.
  - 히스토리의 "이어서 대화"와 헤더의 새 세션 버튼은 현재 인스턴스의 세션 맵을 통해 기존 동작을 유지.
- `devlog.md`, `devlog/2026-06-08/002-ai-agent-new-chat-session-isolation.md`
  - 작업 이력 기록.

## 확인 결과

- `src/angular/app/app.component.ts`에서 `docker-infra.ai-agent.sessions.v1` localStorage 사용 경로가 더 이상 남아 있지 않음을 확인.
- `wiz_project_build(projectName="main", clean=false)` 성공.
- WIZ 검증 쿠키 `season-wiz-project=main`, `season-wiz-devmode=true`를 포함해 확인:
  - `GET https://infra-dev.nanoha.kr/access` 200
  - `GET https://infra-dev.nanoha.kr/api/ai-agent/status` 200

## 남은 리스크

- 실제 AI provider 호출을 통한 다중 브라우저/새로고침 재현 테스트는 수행하지 못함.
- 현재 작업 전부터 `src/angular/app/app.component.ts`를 포함해 여러 파일에 미커밋 변경이 있었으며, 이번 작업은 세션 저장 방식 변경에만 한정함.
