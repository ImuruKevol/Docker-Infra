# AI Agent 코드블럭 강조선 제거와 히스토리 페이지네이션 추가

- **ID**: 010
- **날짜**: 2026-06-01
- **유형**: UI 개선

## 작업 요약
AI Agent 코드블럭 왼쪽 강조선으로 보이던 inset shadow를 제거했다.
AI Agent 히스토리 API가 이미 `limit`/`offset`을 지원하고 있어, 프론트에서 20건 단위 페이지 상태와 이전/다음 페이지 이동 컨트롤을 추가했다.

## 원문 요청사항
```text
- 코드블럭의 왼쪽 border는 삭제해줘.
- 히스토리 목록에 페이지네이션을 적용해줘.
```

## 변경 파일 목록
- `src/angular/app/app.component.ts`
  - `agentHistoryPageSize`, `agentHistoryOffset` 상태를 추가하고 히스토리 조회 시 `limit`/`offset`을 전달하도록 변경했다.
  - 페이지 범위 표시, 현재/전체 페이지 계산, 이전/다음 페이지 이동 메서드를 추가했다.
  - 기간 삭제 후 히스토리 재조회는 첫 페이지부터 다시 불러오도록 조정했다.
- `src/angular/app/app.component.pug`
  - 히스토리 조회/검색은 첫 페이지로 초기화해 조회하도록 변경했다.
  - 히스토리 목록 하단에 범위, 현재 페이지, 이전/다음 버튼을 표시하는 페이지네이션 UI를 추가했다.
- `src/angular/app/app.component.scss`
  - 코드블럭 왼쪽 강조선 역할을 하던 inset shadow를 제거했다.
  - 히스토리 페이지네이션 레이아웃, 버튼, 다크모드 스타일을 추가했다.
- `tests/api/test_ai_agent_history.py`
  - 히스토리 페이지네이션과 코드블럭 왼쪽 강조선 제거를 정적 계약으로 검증하도록 보강했다.
- `devlog.md`, `devlog/2026-06-01/010-ai-agent-history-pagination-codeblock-border.md`
  - 작업 이력을 기록했다.

## 검증 결과
- `python -m py_compile tests/api/test_ai_agent_history.py` 성공.
- `/opt/conda/envs/docker-infra/bin/python -m unittest tests.api.test_ai_agent_history.AIAgentHistoryStaticContractTest` 성공.
- `wiz_project_build(clean=false, projectName=main)` 성공.
- `git diff --check -- src/angular/app/app.component.ts src/angular/app/app.component.pug src/angular/app/app.component.scss tests/api/test_ai_agent_history.py` 성공.
- 빌드 산출물 `build/dist/build/main.js`에서 `ai-agent-history-pagination` 포함과 `box-shadow: inset 3px 0 0 #f97316` 제거를 확인했다.
- 쿠키 `season-wiz-project=main`, `season-wiz-devmode=true`를 포함해 `https://infra-dev.nanoha.kr/dashboard` 요청 시 `200 text/html; charset=utf-8` 응답을 확인했다.
