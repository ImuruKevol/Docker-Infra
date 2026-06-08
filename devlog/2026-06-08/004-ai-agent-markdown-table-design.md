# AI Agent 응답 Markdown 테이블 디자인 적용

## 사용자 원 요청

AI Agent 응답 시 `table` 태그가 들어가는 경우 border 등 디자인이 적용되지 않아 보기 불편하므로, 응답 중 table 태그에 디자인을 적용해달라는 요청.

## 변경 파일

- `src/angular/app/app.component.scss`
  - `[innerHTML]`로 삽입되는 AI Agent Markdown 테이블에도 스타일이 적용되도록 `::ng-deep` selector를 추가.
  - 테이블 래퍼, `table`, `th`, `td`, 마지막 셀/행, 짝수 행 배경에 border, 배경, padding, 줄바꿈 스타일을 적용.
  - 다크 모드에서도 삽입 테이블 border/background/color가 적용되도록 deep selector를 보강.
- `tests/api/test_ai_agent_history.py`
  - AI Agent Markdown 테이블 deep selector와 행 배경 스타일이 유지되는지 정적 계약 테스트에 추가.
- `devlog.md`, `devlog/2026-06-08/004-ai-agent-markdown-table-design.md`
  - 작업 이력 기록.

## 확인 결과

- 선택 계약 테스트 성공:
  - `/opt/conda/envs/docker-infra/bin/python -m unittest tests/api/test_ai_agent_history.py`
- WIZ 빌드 성공:
  - `wiz_project_build(projectName="main", clean=false)`
- 빌드 산출물 확인:
  - `build/dist/build/main.js`에 AI Agent Markdown table deep selector와 border 스타일이 포함됨.
- 요청 링크 접근 확인:
  - `season-wiz-project=main`, `season-wiz-devmode=true` 쿠키를 적용한 `https://infra-dev.nanoha.kr/dashboard` 요청이 200 응답.

## 남은 리스크

- 실제 AI Agent 응답 테이블의 시각 확인은 운영/개발 화면의 실제 응답 데이터 생성 상태에 영향을 받음.
- 전체 테스트는 실행하지 않았으며, 기존 미커밋 변경과 기존 테스트 리스크는 별도 상태로 남아 있음.
