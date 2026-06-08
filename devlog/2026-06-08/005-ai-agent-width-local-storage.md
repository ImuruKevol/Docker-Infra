# AI Agent 패널 width 로컬 스토리지 보존

## 사용자 원 요청

AI Agent 부분의 width를 사용자가 조정했을 때, 그 width 값을 로컬 스토리지에 저장해서 보존되도록 해달라는 요청.

## 변경 파일

- `src/angular/app/app.component.ts`
  - AI Agent dock width 저장 key를 추가.
  - `ngOnInit`에서 localStorage에 저장된 width를 복원.
  - resize 중 width 계산을 공통 clamp helper로 정리.
  - resize mouseup 종료 시 clamp된 width를 localStorage에 저장.
  - localStorage 접근 실패 시 화면 동작을 막지 않도록 예외를 무시.
- `tests/api/test_ai_agent_history.py`
  - width 저장 key, 복원/저장 helper, localStorage get/set, resize 종료 저장 호출이 유지되는지 정적 계약 테스트에 추가.
- `devlog.md`, `devlog/2026-06-08/005-ai-agent-width-local-storage.md`
  - 작업 이력 기록.

## 확인 결과

- 선택 계약 테스트 성공:
  - `/opt/conda/envs/docker-infra/bin/python -m unittest tests/api/test_ai_agent_history.py`
- WIZ 빌드 성공:
  - `wiz_project_build(projectName="main", clean=false)`
- 빌드 산출물 확인:
  - `build/dist/build/main.js`에 `docker-infra.ai-agent.dock-width`, `restoreAgentDockWidth`, `stopAgentResize(true)` 포함 확인.
- 요청 링크 접근 확인:
  - `season-wiz-project=main`, `season-wiz-devmode=true` 쿠키를 적용한 `https://infra-dev.nanoha.kr/dashboard` 요청이 200 응답.

## 남은 리스크

- 실제 브라우저에서 드래그 후 새로고침하는 수동 시각 검증은 수행하지 않음.
- 전체 테스트는 실행하지 않았으며, 기존 미커밋 변경과 기존 테스트 리스크는 별도 상태로 남아 있음.
