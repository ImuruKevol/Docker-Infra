# AI Agent 사이드바 채팅 구조와 응답/동작 정책 개선

- **ID**: 001
- **날짜**: 2026-06-01
- **유형**: 개선

## 작업 요약
AI Agent 사이드바 내부의 단일 채팅 카드 래퍼를 제거하고, 채팅 영역이 사이드바 본문 자체로 동작하도록 정리했다.
Agent 요청 컨텍스트에 구체 화면 요약을 포함하고, 응답은 구체 화면명과 개조식 구성을 우선하도록 지침을 강화했다.
자동 화면 동작은 사용자가 명시적으로 UI 조작을 요청한 경우에만 실행되도록 프론트엔드 필터와 백엔드 프롬프트를 함께 보강했다.

## 원문 요청사항
```text
- 채팅 부분이 사이드바에 카드 형식으로 들어가있는데, 카드가 하나밖에 없으므로 그냥 카드 형식은 제거하고 채팅이 AI Agent 사이드바를 의미하도록 할 것
- 답변으로 "현재 화면에서 감지된 ~~~~" 이라고 뜨는데, 그냥 "현재 화면"이라고 응답하지 말고 어떤 화면인지 정확하게 언급하도록 할 것.
- 답변이 그냥 글만 쭉 나열되어 있는데, 가능하면 응답은 개조식으로 깔끔하게 정리해서 응답하도록 할 것
- 마지막에 "화면 동작 1건을 실행했습니다." 라고 하는데 왜 화면이 이동한건지 모르겠음. 확실하게 의미가 있는 동작만 하도록 개선할 것.
```

## 변경 파일 목록
- `src/angular/app/app.component.pug`: 채팅 카드/섹션 헤더 래퍼 제거.
- `src/angular/app/app.component.scss`: 사이드바 본문과 메시지 영역 스타일을 카드 없는 구조로 조정.
- `src/angular/app/app.component.ts`: 화면 컨텍스트 요약을 Agent payload에 포함하고, 명시적 UI 조작 요청일 때만 `client_actions`를 실행하도록 필터링.
- `src/model/struct/ai_assistant.py`: 구체 화면명 언급, 개조식 응답, 정보성 요청의 `client_actions` 금지 지침 추가.
- `devlog.md`, `devlog/2026-06-01/001-ai-agent-sidebar-response-action-policy.md`: 작업 이력 기록.

## 검증 결과
- `python -m py_compile src/model/struct/ai_assistant.py src/route/api-ai-agent/controller.py` 성공.
- `wiz_project_build(clean=false)` 성공.
- 실제 브라우저 `/images/local` 화면에서 AI Agent 사이드바 확인: `.ai-agent-chat-card` 0개, `.ai-agent-section-title` 0개, 메시지 부모가 `.ai-agent-dock-body`임을 확인.
- Agent 응답이 `이미지 관리 . 서버 로컬 저장소 . local-master` 화면명을 포함하고, list item 2개로 개조식 렌더링되며, 자동 화면 동작 상태 메시지가 발생하지 않음을 확인.
