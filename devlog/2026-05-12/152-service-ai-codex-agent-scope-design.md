# 152. 서비스 AI Codex Agent 입력·권한·MCP scope 설계와 allowlist 적용

- 날짜: 2026-05-12
- 리뷰 ID: eagmfkotirfxmsmreeesotzsltdqnohi

## 사용자 원 요청

AI에 넘겨야 할 것, AI의 허용 범위 정의, AI가 실행할 MCP 등을 먼저 확실하게 설계해달라고 요청했다. Docker Infra에서 서비스 생성 시 사용자가 원하는 것만 입력하면 AI가 서비스 구성을 만들고 오류 수정까지 지원하는 방향에서, Docker Infra가 제공해야 할 정보와 AI가 접근 가능한 MCP/수정 범위를 명확히 정의해야 한다는 요청이었다.

## 변경 파일

- `README.md`
- `docs/service-ai-codex-agent-design.md`
- `docs/docker-infra-development-todo.md`
- `docs/docker-infra-remaining-todo.md`
- `src/model/struct/ai_assistant.py`
- `src/model/struct/codex_runtime.py`
- `tools/docker_infra_mcp.py`
- `devlog.md`
- `devlog/2026-05-12/152-service-ai-codex-agent-scope-design.md`

## 변경 요약

- 서비스 AI/Codex Agent 설계 문서를 추가해 AI 입력 payload, 출력 JSON 계약, Docker Infra 책임, 작업 scope, scope별 MCP allowlist, 런타임 검사/수정 플로우, 남은 구현 과제를 정리했다.
- README와 TODO 문서에 서비스 AI 설계 문서를 연결했다.
- AI context에 `ai_permission_scope`와 `mcp_guidance.enabled_tools`를 포함하도록 서비스 초안, preflight 보정, 런타임 검사/수정 context를 정리했다.
- Codex runtime이 요청 scope에 맞는 MCP tool만 `enabled_tools`로 주입하도록 변경했다.
- Docker Infra MCP 서버가 context의 `mcp_enabled_tools`를 기준으로 `tools/list`와 `tools/call`을 제한하도록 보강했다.

## 확인 결과

- `/opt/conda/envs/docker-infra/bin/python -m py_compile src/model/struct/ai_assistant.py src/model/struct/codex_runtime.py tools/docker_infra_mcp.py`: 통과
- `/opt/conda/envs/docker-infra/bin/python -m unittest tests.api.test_services_preflight`: 11개 통과
- `DOCKER_INFRA_MCP_CONTEXT_JSON={"mcp_enabled_tools":["infra_context"]}` 조건에서 MCP `tools/list`가 `infra_context`만 반환하고 `docker_search` 호출이 차단되는 것을 확인했다.
- `wiz_project_build(projectName="main", clean=false)`: 통과

## 남은 리스크

- 실제 운영 AI 모델 호출과 실제 서비스 런타임 수정은 수행하지 않았다.
- `operator_debug` scope와 `ssh_command`의 UI/API 노출 여부는 아직 정책 결정만 남겨두었다.
- 위험 MCP 실행 결과를 audit log에 구조화 저장하는 후속 구현이 필요하다.
