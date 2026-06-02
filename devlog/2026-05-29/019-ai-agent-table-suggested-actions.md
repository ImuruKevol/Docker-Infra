# AI Agent Markdown 테이블과 후속 동작 버튼 추가

- **ID**: 019
- **날짜**: 2026-05-29
- **유형**: 기능 추가

## 작업 요약
AI Agent 채팅 응답 Markdown 렌더러에 표 문법을 추가하고, 응답별 다음 동작 추천 버튼을 표시하도록 확장했다.
추천 동작은 바로 실행 버튼과 입력창에 넣기 버튼을 각각 제공하며, 백엔드 응답 계약에 `suggested_actions`를 추가했다.

## 원문 요청사항
```text
테이블 문법은 지원이 되어야 할 것 같아.
그리고 답변을 할 때 답변에 따른 다음에 실행할 동작도 추천해주도록 해줘. 그 추천 동작들은 버튼 식으로 보여주고, 해당 동작에 대한 버튼을 누르면 바로 채팅으로 보내서 실행이 되도록. 물론 바로 실행하기와 그냥 채팅 input으로 보내는 기능이 각각 있어야 해.
```

## 변경 파일 목록
- `src/angular/app/app.component.ts`: Markdown table 렌더링, 추천 동작 정규화, 실행/입력창 전송 핸들러 추가.
- `src/angular/app/app.component.pug`: 응답 메시지 하단에 다음 동작 버튼 UI 추가.
- `src/angular/app/app.component.scss`: Markdown table 스타일과 추천 동작 버튼 스타일 추가.
- `src/model/struct/ai_assistant.py`: Agent 출력 계약과 응답 payload에 `suggested_actions` 추가.
- `devlog.md`, `devlog/2026-05-29/019-ai-agent-table-suggested-actions.md`: 작업 이력 기록.

## 검증 결과
- `python -m py_compile src/model/struct/ai_assistant.py src/route/api-ai-agent/controller.py` 성공.
- `wiz_project_build(clean=false)` 성공.
- 실제 브라우저 `/images/local` 화면에서 AI Agent 응답 확인: table 1개, body row 2개, 추천 동작 2개, 실행 버튼 2개, 입력 버튼 2개 렌더링.
- 입력창에 넣기 버튼으로 textarea에 prompt가 채워지고, 바로 실행 버튼으로 동일 prompt가 새 사용자 메시지로 전송됨을 확인.
