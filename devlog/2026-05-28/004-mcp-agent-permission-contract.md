# Docker Infra MCP Agent 권한 계약 상세화

- 날짜: 2026-05-28
- 리뷰 ID: cxaqmytxjrdnjjdcuazqouethjqeipfv
- 요청: Agent 기반으로 전환함에 따라 이 Docker Infra에 정의된 MCP에 대해 좀 더 상세한 정의가 필요해. 그리고 권한 자체는 Docker Infra 자체를 삭제하거나 OS에 치명적인 문제를 일으키는 동작과 같은 것들만 아니면 모든 권한을 허용할거야.

## 변경 요약

- Docker Infra MCP에 `agent_full_control_except_critical_destruction` 권한 모드를 추가하고 `infra_context` 및 `docker-infra://mcp/contract` resource로 tool별 권한, side effect, critical guard를 노출했다.
- Agent runtime의 기본 MCP 도구 노출을 scope별 축소가 아니라 전체 도구 노출로 변경하고, Codex sandbox를 full-control 실행에 맞췄다.
- SSH 명령 차단 기준을 기존 일반 destructive 차단에서 Docker Infra 자체 삭제, control service/container 제거, OS 종료/재부팅/wipe/format, OS critical path 재귀 삭제로 좁혔다.
- 서비스/템플릿 AI 권한 context와 설계 문서를 새 MCP 권한 모델에 맞춰 정리했다.

## 변경 파일

- docs/compose-template-standard.md
- docs/docker-infra-deployment.md
- docs/docker-infra-development-todo.md
- docs/docker-infra-remaining-todo.md
- docs/service-ai-codex-agent-design.md
- src/model/struct/ai_assistant.py
- src/model/struct/codex_runtime.py
- src/model/struct/template_ai.py
- tests/api/test_services_preflight.py
- tools/docker_infra_mcp.py

## 확인

- `/opt/conda/envs/docker-infra/bin/python -m py_compile tools/docker_infra_mcp.py src/model/struct/codex_runtime.py src/model/struct/ai_assistant.py src/model/struct/template_ai.py`
- `/opt/conda/envs/docker-infra/bin/python -m unittest tests.api.test_services_preflight.ServicesPreflightStaticContractTest`
- `/opt/conda/envs/docker-infra/bin/python -m unittest tests.api.test_system_settings_dynamic_menu.SystemSettingsStaticContractTest tests.api.test_services_preflight.ServicesPreflightStaticContractTest tests.api.test_installer_contract.InstallerContractTest tests.api.test_backup_registry_nodes.BackupRegistryNodeStaticContractTest`
- WIZ build `main` 성공
- 이전 restrictive MCP 문구 정적 검색에서 잔존 없음 확인

## 남은 리스크

- 실제 Codex/Claude Code/헤르메스 Agent가 MCP를 통해 등록 서버에서 mutation 명령을 수행하는 live 검증은 하지 않았다.
- Critical guard는 명령 문자열 기반 보호이므로 복잡한 shell indirection까지 완전히 판별하지는 못한다.
