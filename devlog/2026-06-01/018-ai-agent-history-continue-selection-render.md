# AI Agent 히스토리 세션 이어서 대화와 선택 중 렌더 지연

- **ID**: 018
- **날짜**: 2026-06-01
- **유형**: 기능 추가 / 버그 수정

## 작업 요약
AI Agent 히스토리에서 특정 세션을 채팅 화면으로 복원해 이어서 질문할 수 있는 버튼을 추가했다.
히스토리 턴의 질문/응답을 기존 채팅 메시지 배열로 변환하고 같은 세션 ID를 활성 세션으로 지정해 다음 요청이 같은 세션 맥락으로 전송되도록 했다.
또한 AI Agent 영역에서 텍스트를 드래그 선택 중일 때 `service.render()`를 지연해 선택 블록이 풀리는 렌더링 문제를 완화했다.

## 원문 요청사항
```text
히스토리에서 해당 채팅 세션에 요청을 이어서 할 수 있는 기능을 추가해줘. 버튼같은걸 누르면 해당 세션의 질문 및 응답이 그대로 채팅 화면으로 이동되면서 이어서 요청을 할 수 있도록.
---
번외로 AI Agent 컴포넌트 부분들에만 렌더링 관련 버그가 있어. 마우스로 텍스트를 블록을 쳐서 복사하려고 하는데, 자꾸 렌더링이 갱신되면서 블록 상태가 풀리는 버그가 있어.
```

## 변경 파일 목록
- `src/angular/app/app.component.ts`
  - `continueAgentHistory()` 추가로 히스토리 세션을 채팅 메시지로 복원하고 활성 세션 ID를 재사용.
  - 히스토리 상세 로딩과 채팅 메시지 변환 helper 추가.
  - AI Agent 영역 텍스트 선택 중에는 렌더를 지연하는 `renderAgentView()` wrapper 추가.
- `src/angular/app/app.component.pug`
  - 히스토리 상세 및 목록에 `이어서 대화` 버튼 추가.
- `src/angular/app/app.component.scss`
  - 히스토리 이어서 대화 버튼/아이콘 버튼 스타일과 dark mode 보정 추가.
- `tests/api/test_ai_agent_history.py`
  - 히스토리 이어서 대화 UI와 선택 중 렌더 지연 정적 계약 추가.
- `devlog.md`
- `devlog/2026-06-01/018-ai-agent-history-continue-selection-render.md`

## 검증 결과
- 성공: `/opt/conda/envs/docker-infra/bin/python -m unittest tests/api/test_ai_agent_history.py`
- 성공: `git diff --check -- src/angular/app/app.component.ts src/angular/app/app.component.pug src/angular/app/app.component.scss tests/api/test_ai_agent_history.py`
- 성공: `wiz_project_build(projectName="main", clean=false)`
- 성공: DEV 쿠키(`season-wiz-project=main`, `season-wiz-devmode=true`)를 적용한 `https://infra-dev.nanoha.kr/main.js`에서 기능/렌더 지연 코드 반영 확인.

## 남은 리스크
- 실제 브라우저에서 히스토리 세션을 이어서 열고 텍스트 선택 상태가 유지되는지까지의 수동 E2E 검증은 수행하지 않았다.
