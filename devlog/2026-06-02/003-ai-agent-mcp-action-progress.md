# AI Agent MCP 액션 카탈로그와 진행 스트리밍 개선

## 사용자 원 요청

AI Agent가 각 화면에서 어떤 API/MCP 액션을 실행해야 하는지 정리되지 않았고, 간단한 서비스 삭제 요청도 오래 기다린 뒤 응답 시간이 실제 대기와 다르게 표시되는 문제를 개선해달라는 요청. 응답 대기 중 Agent 진행 흐름도 스트리밍 형태로 보여달라는 요청.

## 변경 파일

- `src/model/struct/ai_agent_actions.py`
  - 화면별 Docker Infra MCP 액션 카탈로그를 추가.
  - 서비스/템플릿/서버 등 화면별 OpenAPI operation을 `docker_infra.<screen>.<action>` 도구 형태로 그룹화.
  - 서비스 이름 기반 `service_id` 해석 규칙과 체이닝 예시를 카탈로그에 포함.
- `src/model/struct/ai_assistant.py`
  - `/api/ai-agent/capabilities` 응답과 Agent 컨텍스트에 MCP 액션 카탈로그를 포함.
  - TODO 계획 단계에서 별도 LLM 호출을 제거해 초기 대기 시간을 줄임.
  - 서비스 삭제처럼 명확한 요청은 내장 액션으로 즉시 `services.delete`에 연결.
  - 일반 Agent 스트림에서 MCP 액션 매칭 진행 상태를 status 이벤트로 노출.
- `src/angular/app/app.component.ts`
  - status/heartbeat 이벤트를 채팅 본문에 진행 로그 형태로 누적 표시.
  - `api_request` 실행 시 `service_name`을 `service_id`로 자동 해석.
  - 기존 API action 체이닝, JSON payload 전송, placeholder 보존 로직과 연동.
- `src/app/page.services/api.py`
  - 서비스 삭제 자체는 성공했는데 후속 서비스 카탈로그 refresh가 실패할 경우 전체 삭제 응답이 실패로 보이지 않도록 warning으로 분리.
- `docs/api/openapi.json`
  - AI Agent capabilities schema/example에 `AIAgentActionCatalog` 추가.
- `tests/api/test_openapi_contract.py`, `tests/api/test_wiz_structure_contract.py`
  - MCP 액션 카탈로그, 서비스 이름 해석, 진행 로그 표시, action 체이닝 계약을 확인.
- `devlog.md`, `devlog/2026-06-02/003-ai-agent-mcp-action-progress.md`
  - 작업 이력 기록.

## 확인 결과

- `wiz_project_build(projectName="main", clean=false)` 성공.
- 선택 계약 테스트 성공:
  - `test_ai_agent_openapi_catalog_covers_main_menus`
  - `test_ai_agent_destructive_actions_can_run_after_explicit_confirmation`
  - `test_ai_agent_api_requests_can_chain_json_results`
- 브라우저 검증 성공:
  - 실제 로그인 후 AI Agent status/capabilities 확인.
  - capabilities에 `docker_infra.services.delete` MCP 액션 포함 확인.
  - 임시 서비스 `Codex Delete Probe mpw27cih` 생성 후 AI Agent UI에 `"Codex Delete Probe mpw27cih" 서비스를 삭제해줘` 요청.
  - 진행 로그가 채팅 본문에 표시되고 TODO가 성공 상태로 종료됨.
  - 삭제 후 서비스 목록에서 임시 서비스가 사라진 것을 확인.
- 이전 검증용 `Codex Agent UI Service mpw10w1g` 서비스는 삭제 완료했고, 연결된 검증용 템플릿도 정리함.

## 남은 리스크

- 전체 테스트 실행은 기존 oversized model file 규칙 위반, live dashboard 인증 401, `page.servers/api.py:625` 응답 위치 이슈 때문에 여전히 실패 가능성이 있음.
- 일부 복잡한 화면 요청은 여전히 AI provider 판단이 필요하므로 MCP 카탈로그 매칭 상태는 보여주지만 provider 응답 시간 자체는 외부 Agent 상태에 영향을 받을 수 있음.
