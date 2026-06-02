# AI Agent 스트리밍 채팅 UI 정리

- **ID**: 015
- **날짜**: 2026-05-29
- **유형**: 기능 보강

## 작업 요약
전역 AI Agent 채팅을 SSE 스트림 기반으로 전환해 provider/status/delta/complete 이벤트를 순차 표시하도록 수정했다.
우측 도킹 패널에서 현재 화면 카드와 최근 동작 카드를 제거하고, 경로와 화면 제목만 입력창 바로 위 요약 영역에 표시하도록 정리했다.
추천 질문은 대화가 비어 있을 때만 메시지 영역 중앙에 표시하고, 클릭 즉시 질문을 실행하도록 변경했다.

## 원문 요청사항
```text
설정했어. 내가 직접 질문을 던져보니 "헤르메스 에이전트 최종 응답이 비어 있습니다." 라는 응답이 왔어. 일단 vs code나 codex 등에서 agent를 사용하는 것처럼 응답들이 스트리밍되어 보여져야 해.

그리고 현재 화면 카드에 있는건 경로, 화면 정보만 짧게 내용만 채팅 input 바로 위쪽에 요약해서 현재 컨텍스트를 보여주도록 수정해줘. 그러고 나면 현재 화면 카드는 삭제하고, 최근 동작 카드는 삭제해줘.

추천 질문에 대해서는 대화가 비어있을 때만 대화창 가운데에 정렬해서 보여주도록 해줘. 클릭하면 input에 채워지는게 아니라 바로 질문이 실행되도록.

그리고 메세지 입력 textarea는 resize none으로 해줘.
```

## 변경 파일 목록
- `src/route/api-ai-agent/controller.py`: `/api/ai-agent/stream` SSE 응답 경로 추가.
- `src/model/struct/ai_assistant.py`: 전역 채팅 스트림 이벤트 생성, 최종 응답 chunk delta 분할, 일반 텍스트 fallback 처리 추가.
- `src/model/struct/codex_runtime.py`: 빌드 산출물 재생성으로 Agent home이 사라지지 않도록 `.runtime/agents` 기준 경로를 실제 프로젝트 루트로 고정.
- `src/angular/app/app.component.pug`: 현재 화면/최근 동작 카드 제거, 빈 대화 추천 질문 중앙 배치, 입력창 위 컨텍스트 요약 추가.
- `src/angular/app/app.component.ts`: 채팅 호출을 스트림 처리로 전환하고 추천 질문 클릭 즉시 실행하도록 변경.
- `src/angular/app/app.component.scss`: 추천 질문 중앙 배치, 스트림 상태, 컨텍스트 요약, `textarea resize: none` 스타일 추가.
- `devlog.md`, `devlog/2026-05-29/015-ai-agent-streaming-chat-ui.md`: 작업 이력 기록.

## 검증 결과
- `python -m py_compile src/model/struct/codex_runtime.py src/model/struct/ai_assistant.py src/route/api-ai-agent/controller.py` 성공.
- `wiz_project_build(clean=false)` 성공.
- Playwright 브라우저 테스트에서 `/system` Agent 패널이 열리고 현재 화면/최근 동작 카드가 사라진 것, 추천 질문 5개가 빈 대화 중앙에 표시되는 것, 입력창 위 `/system · 시스템 설정` 요약이 표시되는 것, textarea `resize`가 `none`인 것을 확인했다.
- 추천 질문 클릭 시 사용자 메시지가 즉시 생성되고 추천 질문 영역이 사라지는 것을 확인했다.
- 현재 Hermes API Key가 안정 런타임 경로에는 없어 스트림은 오류 이벤트로 종료되지만, 오류가 채팅 메시지로 표시되는 것을 확인했다.

## 남은 리스크
- 이번 빌드 전에 `bundle/.runtime`에 있던 Hermes `.env`는 빌드 재생성으로 사라졌고, 이제 Agent home은 `/root/docker-infra/project/main/.runtime/agents/hermes`로 고정했다. Gemini API Key는 시스템 설정에서 한 번 더 저장해야 실제 응답 스트리밍까지 검증할 수 있다.
- Hermes CLI 자체가 token-by-token 출력 스트림을 제공하지 않아, 현재 구현은 Agent 완료 응답을 SSE delta로 나누어 표시한다.
