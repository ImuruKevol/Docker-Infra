# 141. 다중 도메인 AI 생성과 배포 후 AI 런타임 복구 플로우 추가

- 날짜: 2026-05-12
- 리뷰 ID: hufvrianlhobxsyvrorjmbvwffdkjioy

## 원 요청

AI 흐름에 대해 더 보완이 필요해. 서비스별로 도메인을 여러 개 사용할 가능성도 있고, 자동으로 AI가 알아서 채워넣어야 하는 값들도 있는 등 서비스 생성에서부터 Docker Infra 환경에 맞도록 배포하는 것까지 일련의 흐름이 거의 완벽해야해. AI를 이용해서 서비스 배포 후 에러가 났을 때 에러 로그나 현재 상태를 자동으로 파악해서 수정을 하게 할 수 있는 기능도 필요해. 서비스 상태에서 컨테이너 목록 중 정상 상태가 아닌 것이 있다면 AI가 자동으로 검사하고 수정할 수 있도록 하고, 필요한 MCP 도구가 있다면 판단해서 추가해줘.

## 변경 파일

- `src/model/struct/ai_assistant.py`
  - AI 출력 계약에 `form.domains[]`를 추가하고, 단일 도메인 필드와 호환되도록 첫 번째 도메인을 legacy 필드에 미러링한다.
  - 서비스 생성/수정 프롬프트에 다중 도메인, 자동 값 채움, Docker Infra 배포 전제 조건을 명시했다.
  - 배포 후 런타임 진단/복구용 `repair_runtime` 흐름을 추가했다. 컨테이너 상태, stack task 오류, container inspect/logs를 수집해 AI 수정안을 만들고, 요청 시 저장 후 백그라운드 재배포를 시작한다.
- `src/model/struct/services_wizard.py`
  - `domains` 배열을 정규화해 생성/preflight에 전달한다.
- `src/model/struct/services.py`
  - 서비스 생성 시 여러 `service_domains` row를 저장한다.
- `src/model/struct/services_update.py`
  - 서비스 수정 시 여러 도메인을 upsert하고 제거된 도메인은 정리한다.
- `src/model/struct/services_preflight.py`
  - 다중 도메인 중복, 형식, SSL/nginx 사전 점검을 처리한다.
- `src/app/page.services/api.py`
  - `ai_runtime_repair` API를 추가했다.
- `src/app/page.services/view.ts`, `src/app/page.services/view.pug`
  - 실행 상태 영역에 `AI 검사/수정` 액션을 추가했다. 비정상 컨테이너, task error, desired/running 불일치가 있을 때 활성화된다.
- `tools/docker_infra_mcp.py`, `src/model/struct/codex_runtime.py`
  - Codex MCP에 `container_logs`, `service_stack_status` 도구를 추가하고 런타임 설정에 노출했다.
- `tests/api/test_services_preflight.py`
  - 다중 도메인, 런타임 복구 API, 새 MCP 도구 연결을 정적 계약에 추가했다.

## 확인 결과

- `python -m py_compile src/model/struct/ai_assistant.py src/model/struct/codex_runtime.py src/model/struct/services_wizard.py src/model/struct/services.py src/model/struct/services_update.py src/model/struct/services_preflight.py tools/docker_infra_mcp.py tests/api/test_services_preflight.py src/app/page.services/api.py`: 통과
- `python -m unittest tests.api.test_services_preflight`: 11개 통과
- Docker Infra MCP stdio 초기화 및 `tools/list`: `container_logs`, `service_stack_status` 포함 확인
- `wiz_project_build(projectName="main", clean=false)`: 통과
- 로컬 fake Responses API와 새 MCP 도구 목록을 붙인 `codex exec` smoke 테스트: 종료 코드 0, 최종 응답 `{"ok": true, "source": "fake-runtime-repair-smoke"}` 확인

## 남은 리스크

- 실제 운영 AI 모델 호출 및 실제 장애 컨테이너 자동 복구는 토큰/실제 장애 대상이 없어 수행하지 않았다.
- AI 런타임 복구는 Compose 수정안을 저장하고 재배포를 시작하므로, 잘못된 모델 판단을 막기 위해 UI 확인 모달과 기존 preflight 검증에 의존한다.
- 다중 도메인 편집 UI는 기존 단일 도메인 UI와 호환되는 범위에서 AI/백엔드 처리를 먼저 보강했다.
