# AI Agent 응답 시간과 히스토리 상세 표시 개선

- **ID**: 004
- **날짜**: 2026-06-01
- **유형**: 개선

## 작업 요약
AI Agent 응답 payload와 히스토리 metadata에 `duration_ms`를 저장하도록 보강했다.
채팅 응답 카드 하단에는 응답 시간을 회색 작은 글씨로 표시하고, 히스토리 상세에서도 같은 응답 시간을 확인할 수 있도록 했다.
히스토리 상세 응답은 기존 채팅창과 같은 Markdown 렌더러로 표시하고, 저장된 `suggested_actions` 기반 다음 동작 목록도 다시 실행하거나 입력창에 넣을 수 있게 표시했다.

## 원문 요청사항
```text
AI Agent 응답 시 시간이 얼마나 걸렸는지도 응답 카드 아래에 회색 작은 글씨로 표시해줘. 물론 히스토리에도 같이 저장이 되어야 해.
그리고 히스토리에서 상세에 응답이 마크다운 원문이 그대로 나오는데, 실제 채팅창에서처럼 스타일을 적용해서 보여주도록 해줘. 그리고 채팅 창에 표시되던 다음 동작 목록도 각 히스토리 상세에 표시해줘야해.
```

## 변경 파일 목록
- `src/model/struct/ai_assistant.py`: 일반/스트리밍 AI Agent 응답에 `duration_ms` 추가.
- `src/model/struct/ai_history.py`: 히스토리 저장 metadata/response payload와 조회/CSV export에 `duration_ms` 반영.
- `src/angular/app/app.component.ts`: 채팅/히스토리 응답 시간 표시 helper, 히스토리 Markdown 렌더링, 히스토리 다음 동작 복원 helper 추가.
- `src/angular/app/app.component.pug`: 채팅 응답 시간, 히스토리 상세 응답 Markdown, 히스토리 다음 동작 UI 추가.
- `src/angular/app/app.component.scss`: 응답 시간 메타 텍스트와 히스토리 Markdown/다음 동작 스타일 보강.
- `tests/api/test_ai_agent_history.py`: 응답 시간 저장/표시와 히스토리 상세 표시 계약 추가.
- `devlog.md`, `devlog/2026-06-01/004-ai-agent-duration-history-detail.md`: 작업 이력 기록.

## 검증 결과
- `/opt/conda/envs/docker-infra/bin/python -m py_compile src/model/struct/ai_history.py src/model/struct/ai_assistant.py` 성공.
- `/opt/conda/envs/docker-infra/bin/python -m unittest tests.api.test_ai_agent_history` 성공.
- `git diff --check` 대상 파일 검사 성공.
- `wiz_project_build(clean=false)` 성공.
