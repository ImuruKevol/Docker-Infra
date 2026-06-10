# AI Agent Claude/Hermes 스트림 TODO/진행 이벤트 연동

- 날짜: 2026-06-10
- ID: 023
- 리뷰 ID: buqanzpqiscxrtoaakdvceufhfxqhhlz

## 사용자 요청

Claude/Hermes의 공식 문서들도 찾아보고 Codex의 todo_list 이벤트와 같은 부분들을 적용해줘.

## 확인한 근거

- Claude Code 공식 문서에서 `stream-json` 출력과 partial message 스트리밍, `TodoWrite`에서 `TaskCreate`/`TaskUpdate`/`TaskList`로 이전된 TODO 도구 흐름을 확인했다.
- Hermes 공식 문서와 로컬 Hermes 0.15.1 CLI를 확인해, CLI one-shot에는 Codex/Claude 같은 JSON TODO 스트림 옵션이 없고 ACP/TUI gateway/API server에서 `tool.progress`/`hermes.tool.progress` 이벤트를 제공한다는 점을 확인했다.
- 로컬 CLI 도움말로 `claude --output-format stream-json`, `--include-partial-messages`, `--mcp-config` 옵션과 `hermes acp`, `hermes chat --query` 경로를 확인했다.

## 변경 파일

- `src/model/struct/codex_runtime.py`
- `src/model/struct/ai_assistant.py`
- `tests/api/test_wiz_structure_contract.py`
- `devlog.md`
- `devlog/2026-06-10/023-ai-agent-claude-hermes-stream-events.md`

## 변경 내용

- non-Codex Agent도 `complete_json_stream` 경로에서 subprocess stdout JSON 라인을 즉시 `runtime_event`로 전달하도록 변경했다.
- Claude Code 실행 명령을 `--print --output-format stream-json --verbose --include-partial-messages` 기반으로 구성해 중간 tool/todo 이벤트를 받을 수 있게 했다.
- Claude `TodoWrite`, `TaskCreate`, `TaskUpdate`, `tool_result`를 UI용 `todo_update` 이벤트로 변환하는 정규화 로직을 추가했다.
- Hermes `tool.progress`/`hermes.tool.progress` 계열 이벤트를 UI의 `thinking` 진행 이벤트로 변환하도록 추가했다.
- Claude stream-json 최종 `result` 이벤트와 assistant text block을 최종 응답 텍스트 추출 대상으로 반영했다.
- 회귀 방지를 위해 Claude/Hermes 스트림 이벤트 처리와 Claude partial stream 옵션을 구조 계약 테스트에 추가했다.

## 검증

- 성공: `/opt/conda/envs/docker-infra/bin/python -m py_compile src/model/struct/ai_assistant.py src/model/struct/codex_runtime.py tests/api/test_wiz_structure_contract.py`
- 성공: `/opt/conda/envs/docker-infra/bin/python -m unittest tests.api.test_wiz_structure_contract.WizStructureContractTest.test_ai_agent_progress_lines_do_not_hide_missing_answer`
- 성공: `/opt/conda/envs/docker-infra/bin/python -m unittest tests.api.test_ai_agent_history`
- 성공: `git diff --check -- src/model/struct/ai_assistant.py src/model/struct/codex_runtime.py tests/api/test_wiz_structure_contract.py`
- 성공: `wiz_project_build(projectName="main", clean=false)`

## 남은 리스크

- Claude/Hermes 계정 인증이 없는 런타임에서 실제 장시간 Agent 호출을 끝까지 실행하는 검증은 수행하지 못했다.
- Hermes CLI one-shot은 공식 문서 기준으로 구조화된 TODO 스트림이 없어, 현재는 Hermes의 progress/ACP/API 계열 이벤트가 들어오는 경우에만 UI 진행 표시로 반영된다.
