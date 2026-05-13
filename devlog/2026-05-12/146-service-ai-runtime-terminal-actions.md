# 146. AI 런타임 검사 사용자 프롬프트와 컨테이너 터미널 조치 도구 추가

- 날짜: 2026-05-12
- 리뷰 ID: zjcknbgqlnbbrsgddfrzcrdgivrbcbyq

## 원 요청

AI 검사 및 수정을 할 때 터미널 권한을 이용해서 컨테이너를 직접 stop하고 지우거나 하는 기능도 필요해.
그리고 프롬프트를 추가로 넣어서 사용자가 직접 현재 문제에 대해서 추가 메세지를 줄 수도 있어야 해.

## 변경 파일

- `src/app/page.services/view.ts`
  - AI 런타임 검사/수정을 바로 실행하지 않고 입력 모달을 열도록 변경했다.
  - 사용자 추가 메시지와 컨테이너 터미널 조치 허용 값을 API payload에 포함한다.
- `src/app/page.services/view.pug`
  - 추가 메시지 textarea, 컨테이너 중지/삭제 허용 체크박스, 현재 문제 요약이 있는 AI 런타임 검사 모달을 추가했다.
- `src/model/struct/ai_assistant.py`
  - 사용자 추가 메시지를 `operator_message`와 `intent`로 AI 컨텍스트에 반영한다.
  - 컨테이너 터미널 조치가 허용된 경우 `container_action` MCP 도구를 사용하도록 시스템 프롬프트와 MCP 가이드를 보강했다.
- `src/model/struct/codex_runtime.py`
  - Codex MCP context에 `terminal_actions`를 전달하고 `container_action` 도구를 활성화했다.
- `tools/docker_infra_mcp.py`
  - 명시적으로 허용된 AI 요청에서만 `stop`, `restart`, `remove`를 수행하는 `container_action` 도구를 추가했다.
- `tests/api/test_services_preflight.py`
  - 사용자 프롬프트, 터미널 조치 허용, `container_action` 연결 계약을 정적 테스트에 추가했다.
- `devlog.md`
- `devlog/2026-05-12/146-service-ai-runtime-terminal-actions.md`

## 확인 결과

- `/opt/conda/envs/docker-infra/bin/python -m py_compile src/model/struct/ai_assistant.py src/model/struct/codex_runtime.py tools/docker_infra_mcp.py src/app/page.services/api.py tests/api/test_services_preflight.py`: 통과
- `/opt/conda/envs/docker-infra/bin/python -m unittest tests.api.test_services_preflight`: 11개 통과
- `wiz_project_build(projectName="main", clean=false)`: 통과
- MCP 도구 목록에 `container_action` 포함 확인
- `container_action`은 요청에서 허용되지 않으면 차단되는 것 확인

## 남은 리스크

- 실제 운영 AI 모델 호출과 실제 컨테이너 stop/remove는 대상 장애 서비스에서 수행하지 않았다.
