# 전역 AI Agent 플로팅 채팅 추가

- **ID**: 013
- **날짜**: 2026-05-29
- **유형**: 기능 추가

## 작업 요약
선택된 AI Agent를 모든 화면에서 호출할 수 있도록 Angular 루트에 오른쪽 하단 플로팅 채팅 위젯을 추가했다.
현재 라우트, 화면 텍스트, 포커스, 모달, 최근 클릭/입력 이벤트, 조작 가능한 요소 ref를 수집해 Agent 요청 컨텍스트로 전달하고, Agent가 반환한 안전한 클라이언트 액션을 화면에서 실행하도록 연결했다.

## 원문 요청사항
```text
작업을 진행해줘.

현재 시스템 설정에서 AI Agent를 설정할 수 있음.
선택한 Agent를 이용해서 모든 페이지에 대해 항상 오른쪽 하단에 말풍선같은 버튼 아이콘을 추가해서 Agent 채팅창을 부를 수 있게 해줘. 채팅창은 화면 이동과 아예 별개로 오른쪽에 항상 떠있을 수 있게 해야 해. 그리고 현재 화면이 뭔지, 현재 어떤 동작을 했는지, 어떤 모달이 열렸는지 등을 모두 Agent에서 파악할 수 있도록 해야해.
그리고 그걸 기반으로 사용자가 질문을 던지거나 특정 동작을 요청하면 그에 맞는 동작을 할 수 있어야 해.
```

## 변경 파일 목록
- `src/angular/app/app.component.pug`: 전역 AI Agent 버튼, 채팅 패널, 메시지 입력 UI 추가.
- `src/angular/app/app.component.scss`: 플로팅 버튼/패널/메시지/반응형/다크모드 스타일 추가.
- `src/angular/app/app.component.ts`: 전역 상태 유지, 화면/이벤트/모달/인터랙션 컨텍스트 수집, Agent API 호출, 반환된 클라이언트 액션 실행 로직 추가.
- `src/model/struct/ai_assistant.py`: 채팅 상태 조회와 일반 UI 채팅 실행 메서드, UI 컨텍스트용 시스템 프롬프트, 액션 정규화 로직 추가.
- `src/route/api-ai-agent/app.json`: `/api/ai-agent/<path:path>` 사용자 인증 라우트 추가.
- `src/route/api-ai-agent/controller.py`: `status`, `chat` 엔드포인트 라우팅과 요청 JSON 파싱 추가.
- `devlog.md`, `devlog/2026-05-29/013-ai-agent-floating-chat.md`: 작업 이력 기록.

## 검증 결과
- `python -m py_compile src/model/struct/ai_assistant.py src/route/api-ai-agent/controller.py` 성공.
- 새 라우트 추가 후 `wiz_project_build(clean=true)` 성공.
- 최종 프론트 변경 후 `wiz_project_build(clean=false)` 성공.
- `curl -b 'season-wiz-project=main; season-wiz-devmode=true' https://infra-dev.nanoha.kr/api/ai-agent/status`로 라우트가 인증 레이어까지 도달하는 것을 확인했다. 인증 없는 요청이라 응답 본문은 `code=401`, `AUTHENTICATION_REQUIRED`가 정상적으로 반환됐다.

## 남은 리스크
- 실제 Agent 응답과 브라우저 액션 실행은 로그인 세션과 Agent CLI 설정이 필요해 인증된 브라우저 세션에서 최종 확인이 필요하다.
- 파괴적 요청은 Agent 프롬프트와 클라이언트의 `requires_confirmation` 처리로 제한했지만, 반환 액션의 안전성은 선택 Agent의 지시 준수에 의존한다.
