# AI 백그라운드 검증 조회와 일반 사용자용 MCP 권한 확장

- 날짜: 2026-05-12
- 리뷰 ID: eagmfkotirfxmsmreeesotzsltdqnohi
- 요청: "AI 검증은 백그라운드로 진행하되, 화면 상으로 백그라운드 작업에 대해 언제든지 조회를 할 수 있어야 해. 그리고 이 Docker Infra는 사용자 층이 개발에 대한 지식이 거의 없는 일반 사용자라서 AI와 MCP에 보다 더 많은 권한을 허용하는게 맞아. 이를 고려해서 AI에 대한 허용 범위와 MCP를 다시 설정해줘."

## 변경 파일

- `src/model/struct/ai_assistant.py`
- `src/model/struct/services_deploy.py`
- `src/model/struct/codex_runtime.py`
- `tools/docker_infra_mcp.py`
- `src/app/page.services/api.py`
- `src/app/page.services/view.ts`
- `src/app/page.services/view.pug`
- `src/app/page.services.create/view.ts`
- `tests/api/test_services_preflight.py`
- `docs/service-ai-codex-agent-design.md`
- `docs/docker-infra-remaining-todo.md`
- `docs/docker-infra-development-todo.md`
- `devlog.md`
- `devlog/2026-05-12/154-service-ai-background-verification-permissions.md`

## 작업 내용

- `service.ai.verify` 백그라운드 operation을 추가하고, 중복 실행 중이면 기존 operation을 반환하도록 했다.
- 배포 성공 후 AI 검증 operation을 자동 시작하도록 `deploy_background` payload에 `start_ai_verification` 흐름을 연결했다.
- AI 검증 worker가 런타임 안정화 대기, DNS/TCP/HTTP 검증용 AI 호출, 필요 시 AI 수정/재배포, 재검증을 반복하도록 구현했다.
- 서비스 상세 화면에 백그라운드 작업 배너를 추가하고, `pending/running` operation을 처리 로그 모달에서 polling하도록 수정했다.
- 수동 AI 검사/수정 버튼은 SSE 스트림 대신 백그라운드 operation을 시작하고 해당 로그를 조회하도록 변경했다.
- 일반 사용자 자동 처리 전제를 반영해 AI MCP 허용 범위에 `server_port_check`, `server_collect`, `ssh_command`를 기본 포함했다.
- `ssh_command`는 허용하되 Docker stop/restart/rm 등 파괴적 명령은 MCP에서 계속 차단하도록 보강했다.
- 생성 화면에서 배포를 시작할 때도 AI 검증이 함께 백그라운드로 시작되도록 연결했다.

## 확인 결과

- `/opt/conda/envs/docker-infra/bin/python -m py_compile ...` 통과
- `/opt/conda/envs/docker-infra/bin/python -m unittest project/main/tests/api/test_services_preflight.py` 통과, 11개 테스트
- MCP smoke test에서 `ssh_command` 노출과 파괴적 Docker 명령 차단 확인
- WIZ project build 통과

## 남은 리스크

- 실제 서비스의 사용자 기능 검증은 현재 HTTP status/body 일부와 AI 판단에 의존한다. 로그인, 클릭, 폼 제출 같은 브라우저 상호작용 검증은 별도 `browser_probe` MCP가 필요할 수 있다.
- `service.ai.verify`는 백그라운드 thread 기반이므로 프로세스 재시작 중이던 작업 복구 정책은 별도 설계가 필요하다.
