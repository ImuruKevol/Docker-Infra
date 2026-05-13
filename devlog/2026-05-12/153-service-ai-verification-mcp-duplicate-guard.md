# 153. 서비스 AI 보완 검토와 배포 검증 MCP·중복 배포 방지 보강

- 날짜: 2026-05-12
- 리뷰 ID: eagmfkotirfxmsmreeesotzsltdqnohi

## 사용자 원 요청

더 보완할 내용이 없는지 다시 검토하고, 특히 추가로 만들어야 할 MCP가 있는지 확인해달라고 요청했다. AI 검사/수정은 백그라운드 작업으로 전환해 컨테이너 안정화, 도메인/IP/port 정상 동작, 사용자 요구 기능 동작을 기다린 뒤 AI를 다시 호출해 검증해야 할 것 같다고 했다. 또한 서비스를 AI로 생성할 때 에러가 나면 중복 컨테이너가 생기는 로직 확인도 요청했다.

## 변경 파일

- `docs/service-ai-codex-agent-design.md`
- `docs/docker-infra-development-todo.md`
- `docs/docker-infra-remaining-todo.md`
- `src/app/page.services.create/view.ts`
- `src/model/struct/ai_assistant.py`
- `src/model/struct/codex_runtime.py`
- `src/model/struct/services_wizard.py`
- `src/model/struct/services_deploy.py`
- `src/model/struct/local_command_catalog.py`
- `tools/docker_infra_mcp.py`
- `tests/api/test_services_preflight.py`
- `devlog.md`
- `devlog/2026-05-12/153-service-ai-verification-mcp-duplicate-guard.md`

## 변경 요약

- 서비스 AI 설계에 `post_deploy_verification` scope를 추가하고 배포 후 백그라운드 operation에서 stack/container 안정화, DNS/TCP/HTTP probe, AI 재검증, 재수정/재배포 반복으로 이어지는 검증 루프를 정의했다.
- 추가 MCP로 `dns_lookup`, `tcp_connect_check`, `http_probe`를 구현했다. probe 도구는 context의 `allowed_probe_hosts` 또는 등록 노드 host만 대상으로 허용한다.
- Codex runtime과 AI runtime context에 새 probe MCP를 연결하고, MCP context에 `allowed_probe_hosts`를 전달하도록 했다.
- AI 생성 재시도 중복을 줄이기 위해 서비스 생성 화면 payload에 `create_session_id`를 포함하고, backend에서 같은 생성 세션이면 기존 service row를 반환하도록 했다.
- 같은 서비스에 pending/running 배포 operation이 있으면 새 background deploy thread를 만들지 않고 기존 operation을 반환하도록 했다.
- `docker stack deploy`에 `--prune`을 추가해 AI 수정으로 Compose service key가 바뀐 경우 이전 stack service가 남아 중복 컨테이너처럼 보이는 문제를 줄였다.
- 정적 계약 테스트에 새 MCP, 생성 세션 idempotency, deploy operation dedupe, stack prune 검사를 추가했다.

## 확인 결과

- `/opt/conda/envs/docker-infra/bin/python -m py_compile src/model/struct/ai_assistant.py src/model/struct/codex_runtime.py src/model/struct/services_wizard.py src/model/struct/services_deploy.py src/model/struct/local_command_catalog.py tools/docker_infra_mcp.py tests/api/test_services_preflight.py`: 통과
- `/opt/conda/envs/docker-infra/bin/python -m unittest tests.api.test_services_preflight`: 11개 통과
- MCP smoke: `mcp_enabled_tools=["dns_lookup","http_probe"]`, `allowed_probe_hosts=["example.com"]` 조건에서 허용 tool만 노출되고 미허용 host probe가 차단되는 것을 확인했다.
- `wiz_project_build(projectName="main", clean=false)`: 통과

## 남은 리스크

- 배포 후 자동 검증 operation 자체는 이번 작업에서 설계와 MCP 기반만 마련했고, 전체 백그라운드 AI 재검증 루프는 후속 구현이 필요하다.
- 실제 운영 도메인, 외부 IP, 서비스 기능 시나리오에 대한 live probe는 수행하지 않았다.
- 사용자가 원하는 기능을 판정할 `function_assertion` schema와 브라우저 기반 검증 MCP는 아직 설계 후보로 남아 있다.
