# AI Agent Codex todo_list 스트림 기반 TODO 적용

- 날짜: 2026-06-10
- ID: 020
- 리뷰 ID: buqanzpqiscxrtoaakdvceufhfxqhhlz

## 사용자 요청

내가 알기로 Codex 자체에 요청 하나를 날려도 그 중간 응답에 todo 만드는 기능이 있는걸로 알고있는데, 확실하게 찾아보고 확인해서 적용해줘. "간단한 질문"이라는 것의 판단 기준이 없기 때문에 즉시 1개 todo로 실행되는건 전혀 맞지 않아.

## 확인한 근거

- OpenAI Codex 공식 문서에서 `codex exec --json`이 JSONL 이벤트 스트림을 출력하고, `item.*` 이벤트의 item type에 plan updates가 포함된다는 점을 확인했다.
- 로컬 Codex CLI 0.135.0으로 실제 read-only 실행을 수행해 `item.type: "todo_list"`와 `items[{text, completed}]` 이벤트가 발생하는 것을 확인했다.

## 변경 파일

- `src/angular/app/app.component.ts`
- `src/model/struct/ai_assistant.py`
- `tests/api/test_wiz_structure_contract.py`
- `devlog.md`
- `devlog/2026-06-10/020-ai-agent-codex-todo-list-stream.md`

## 변경 내용

- AI Agent 채팅 흐름에서 선행 `/plan` 호출과 TODO별 재실행 루프를 중단하고, 원 사용자 요청을 한 번의 Codex 스트림으로 실행하도록 변경했다.
- Codex 런타임의 `todo_list`/`plan_update` 이벤트를 `todo_update` SSE 이벤트로 변환해 프론트 TODO 패널에 반영하도록 추가했다.
- 프론트에서 `todo_update` 이벤트를 받아 Codex가 만든 TODO 텍스트와 완료 상태를 표시하도록 구현했다.
- 이전에 추가했던 "간단한 질문" fast path를 프론트와 백엔드에서 제거했다.
- 회귀 방지를 위해 fast path 부재, `todo_update` 처리, Codex TODO/plan update 프롬프트 계약을 테스트에 반영했다.

## 검증

- `codex exec --json --sandbox read-only ...` 실제 실행으로 `todo_list` 이벤트 확인
- `/opt/conda/envs/docker-infra/bin/python -m py_compile src/model/struct/ai_assistant.py src/model/struct/codex_runtime.py tests/api/test_wiz_structure_contract.py`
- `/opt/conda/envs/docker-infra/bin/python -m unittest tests.api.test_wiz_structure_contract.WizStructureContractTest.test_ai_agent_progress_lines_do_not_hide_missing_answer`
- `/opt/conda/envs/docker-infra/bin/python -m unittest tests.api.test_ai_agent_history`
- `git diff --check -- src/angular/app/app.component.ts src/model/struct/ai_assistant.py tests/api/test_wiz_structure_contract.py`
- `wiz_project_build(projectName="main", clean=false)`

모두 통과했다.
