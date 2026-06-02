# AI Agent TODO 목록 표시 간소화와 우측 잘림 보정

- **ID**: 017
- **날짜**: 2026-06-01
- **유형**: UI 개선

## 작업 요약
AI Agent TODO 패널에서 회색 설명 텍스트를 제거하고 TODO 항목만 깔끔하게 보이도록 정리했다.
완료/진행 상태 라벨은 항목 오른쪽 끝에 한 줄로 고정하고, TODO 항목이 패널 오른쪽에서 잘리지 않도록 width/min-width/box-sizing을 보강했다.

## 원문 요청사항
```text
TODO 항목들은 첨부한 스크린샷 기준으로 회색으로 써있는 설명은 제거하고, 초록색 TODO 목록만 깔끔하게 리스팅해서 보여줄 것. 완료 표시도 굳이 다음 줄로 줄바꿈하지 말고 오른쪽 끝에 표시하도록 할 것. 그리고 TODO 항목의 오른쪽이 살짝 잘리는 스타일 버그가 있음.
```

## 변경 파일 목록
- `src/angular/app/app.component.pug`
  - TODO header의 summary 표시와 항목별 detail 문구 렌더링 제거.
  - TODO title과 상태 라벨만 표시하도록 구조 정리.
- `src/angular/app/app.component.scss`
  - TODO 항목 기본 스타일을 녹색 목록 카드로 정리.
  - 상태 라벨을 오른쪽 끝에 고정하고 줄바꿈을 방지.
  - 패널/목록/항목 width, min-width, box-sizing, overflow를 보강해 오른쪽 잘림 방지.
  - dark mode TODO 색상 보정.
- `src/angular/app/app.component.ts`
  - 더 이상 사용하지 않는 `agentTodoDetail` helper 제거.
- `tests/api/test_ai_agent_history.py`
  - TODO summary/detail 미표시와 상태 라벨 우측 배치 스타일 계약 추가.
- `devlog.md`
- `devlog/2026-06-01/017-ai-agent-todo-list-cleanup.md`

## 검증 결과
- 성공: `/opt/conda/envs/docker-infra/bin/python -m unittest tests/api/test_ai_agent_history.py`
- 성공: `git diff --check -- src/angular/app/app.component.ts src/angular/app/app.component.pug src/angular/app/app.component.scss tests/api/test_ai_agent_history.py`
- 성공: `wiz_project_build(projectName="main", clean=false)`
- 성공: DEV 쿠키(`season-wiz-project=main`, `season-wiz-devmode=true`)를 적용한 `https://infra-dev.nanoha.kr/main.js`에서 TODO 스타일 반영 확인.

## 남은 리스크
- 실제 AI Agent 실행으로 TODO가 생성된 상태의 브라우저 스크린샷 회귀 검증은 수행하지 않았다.
