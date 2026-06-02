# AI Agent 렌더 루프 방지와 코드블럭/히스토리 상세 사이드바 개선

- **ID**: 008
- **날짜**: 2026-06-01
- **유형**: UI 안정화

## 작업 요약
AI Agent 패널 내부 DOM 변경이 다시 화면 컨텍스트 갱신과 전체 렌더링을 유발하지 않도록 MutationObserver 범위와 컨텍스트 갱신 조건을 조정했다.
채팅과 히스토리 응답의 코드블럭을 툴바가 있는 박스형 UI로 렌더링하고 복사 버튼을 연결했으며, 히스토리 상세는 히스토리 목록 아래가 아니라 Agent 채팅 사이드바 왼쪽의 별도 사이드바로 분리했다.

## 원문 요청사항
```text
- 화면에 뭔가 렌더링 요청이 계속 무한루프되고 있어. 스크롤도 계속 풀리고, 텍스트 선택도 계속 풀리고 있어.
- 스크린샷 아랫부분처럼 코드블럭에 대해서는 스타일이 제대로 처리되지 않아서 화면 구성이 깨지고 있어. 히스토리 뿐만 아니라 채팅 부분도 동일한 문제가 발생하고 있어.
- 코드블럭은 박스를 치거나 해서 다른 내용들과 확실하게 구분이 되도록 해줘. 복사 버튼도 추가하고.
- 히스토리 상세는 히스토리 목록 아래에 표시하지 말고 사이드바를 채팅 사이드바 왼쪽에 하나 더 만들어서 표시하도록 해줘.
```

## 변경 파일 목록
- `src/angular/app/app.component.ts`
  - Agent 패널 내부 mutation을 컨텍스트 갱신 대상에서 제외하고, 실제 컨텍스트 요약 값이 바뀐 경우에만 `service.render()`를 호출하도록 변경했다.
  - 화면 텍스트 수집 시 `.ai-agent-surface` 스타일을 직접 변경하지 않고 복제 DOM에서 제거해 수집하도록 수정했다.
  - Markdown 코드블럭에 복사 버튼을 포함하고, 이벤트 위임으로 복사 상태를 표시하도록 연결했다.
- `src/angular/app/app.component.pug`
  - 히스토리 상세 패널을 Agent 도크 왼쪽의 별도 `ai-agent-history-detail-dock` 사이드바로 이동했다.
- `src/angular/app/app.component.scss`
  - 히스토리 상세 3열 레이아웃과 반응형 행 레이아웃을 추가했다.
  - 코드블럭 박스, 툴바, 복사 버튼, 다크모드 스타일을 추가했다.
- `tests/api/test_ai_agent_history.py`
  - 렌더 루프 방지 토큰, 히스토리 상세 사이드바, 코드블럭 복사 UI 정적 계약을 보강했다.
- `devlog.md`, `devlog/2026-06-01/008-ai-agent-render-code-history-detail.md`
  - 작업 이력을 기록했다.

## 검증 결과
- `python -m py_compile tests/api/test_ai_agent_history.py` 성공.
- `/opt/conda/envs/docker-infra/bin/python -m unittest tests.api.test_ai_agent_history.AIAgentHistoryStaticContractTest` 성공.
- `wiz_project_build(clean=false, projectName=main)` 성공.
- `git diff --check -- src/angular/app/app.component.ts src/angular/app/app.component.pug src/angular/app/app.component.scss tests/api/test_ai_agent_history.py` 성공.
- 쿠키 `season-wiz-project=main`, `season-wiz-devmode=true`를 포함해 `https://infra-dev.nanoha.kr/dashboard` 요청 시 `200 text/html; charset=utf-8` 응답을 확인했다.
