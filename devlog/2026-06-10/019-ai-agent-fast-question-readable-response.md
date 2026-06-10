# AI Agent 단순 질문 fast path와 답변 가독성 보강

- 날짜: 2026-06-10
- ID: 019
- 리뷰 ID: buqanzpqiscxrtoaakdvceufhfxqhhlz

## 사용자 요청

간단한 질문만 했는데 몇 가지 문제가 있어.
- 처음 TODO 만드는 시간이 너무 오래걸림. 개선할 수 있으면 개선하기.
- 생각 과정이 여전히 스트리밍되지 않고 있음.
- 첨부한 스크린샷과 같이 결과 response가 가독성이 너무 떨어져서 읽기가 너무 힘듬.

## 변경 파일

- `src/angular/app/app.component.ts`
- `src/angular/app/app.component.scss`
- `src/model/struct/ai_assistant.py`
- `src/model/struct/codex_runtime.py`
- `tests/api/test_wiz_structure_contract.py`
- `devlog.md`
- `devlog/2026-06-10/019-ai-agent-fast-question-readable-response.md`

## 변경 내용

- 단순 질문은 `/plan` AI 호출 없이 즉시 하나의 TODO로 실행되도록 프론트 fast path를 추가했다.
- 백엔드 `plan_chat`에도 같은 단순 질문 fast path를 추가해 API 직접 호출에서도 초기 TODO 생성 지연을 줄였다.
- 스트림 대기 중 `몇 초 경과` 상태 문구 대신 현재 처리 단계를 나타내는 진행 이벤트를 표시하도록 변경했다.
- Codex 런타임 무응답 구간에서도 `agent.progress` 이벤트를 주기적으로 내보내도록 보강했다.
- 최종 답변 시작 시 진행 로그를 assistant 본문에서 제거해 결과 response와 진행 로그가 섞이지 않게 했다.
- 긴 비구조 답변은 Markdown 섹션/불릿으로 정리하고, AI Agent 답변 영역의 줄 간격과 리스트 간격을 보강했다.
- 회귀 방지를 위해 fast path, 진행 로그 제거, `초 경과` 문구 제거 계약을 테스트에 추가했다.

## 검증

- `/opt/conda/envs/docker-infra/bin/python -m py_compile src/model/struct/ai_assistant.py src/model/struct/codex_runtime.py tests/api/test_wiz_structure_contract.py`
- `/opt/conda/envs/docker-infra/bin/python -m unittest tests.api.test_wiz_structure_contract.WizStructureContractTest.test_ai_agent_progress_lines_do_not_hide_missing_answer`
- `git diff --check -- src/angular/app/app.component.ts src/angular/app/app.component.scss src/model/struct/ai_assistant.py src/model/struct/codex_runtime.py tests/api/test_wiz_structure_contract.py`
- `wiz_project_build(projectName="main", clean=false)`

위 항목은 모두 통과했다.

추가 확인:

- `/opt/conda/envs/docker-infra/bin/python -m unittest tests.api.test_ai_agent_history`
  - 통과했다.
- `/opt/conda/envs/docker-infra/bin/python -m unittest tests.api.test_wiz_structure_contract`
  - 실패했다. 현재 작업과 무관한 기존 구조 계약 실패가 남아 있다.
  - 대표 실패: `page.domains`의 `routeZoneId` 계약 불일치, 여러 `src/model/struct/*.py` 파일의 300라인 제한 초과, `src/app/page.servers/api.py:625`의 try/except 내부 `wiz.response`, `page.servers/view.scss`의 container query 계약 불일치.
