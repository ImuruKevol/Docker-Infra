# AI Agent API 액션 체이닝과 템플릿 서비스 생성 검증

## 사용자 원 요청

템플릿을 생성하고, 그 템플릿으로 서비스를 생성하고, 정상적으로 떴는지 확인하고, 정상적으로 안 떴으면 디버깅까지 진행하는 일련의 흐름을 전부 확인해달라는 요청. 관리자 인증 정보는 검증에만 사용하고 기록하지 않음.

## 변경 파일

- `src/angular/app/app.component.ts`
  - `api_request` client action 결과를 `save_as` 별칭으로 저장하고 이후 action의 `{{alias.path}}` 참조를 해석하도록 보강.
  - WIZ page API에 중첩 payload가 유지되도록 `api_request` POST body를 JSON으로 전송.
  - API action 결과는 wrapper가 아닌 `data` 객체로 저장해 `{{created_service.result.service.id}}` 같은 체이닝이 동작하도록 수정.
  - Compose 템플릿의 `{{ variable_name }}` placeholder가 action 참조 해석 과정에서 지워지지 않도록 미해결 placeholder를 보존.
- `src/model/struct/ai_assistant.py`
  - AI Agent client action 출력 형식과 시스템 프롬프트에 `save_as`/`{{alias.path}}` 체이닝 규칙을 추가.
- `tests/api/test_wiz_structure_contract.py`
  - AI Agent API action 체이닝, JSON payload 전송, 미해결 placeholder 보존 규칙을 확인하는 계약 테스트 추가.
- `devlog.md`, `devlog/2026-06-02/002-ai-agent-template-service-flow.md`
  - 작업 이력 기록.

## 확인 결과

- `wiz_project_build(projectName="main", clean=false)` 성공.
- 선택 계약 테스트 성공:
  - `test_ai_agent_openapi_catalog_covers_main_menus`
  - `test_ai_agent_destructive_actions_can_run_after_explicit_confirmation`
  - `test_ai_agent_api_requests_can_chain_json_results`
- 브라우저 검증 성공:
  - 실제 로그인 후 `/api/ai-agent/status`, `/api/ai-agent/capabilities` 확인.
  - AI Agent UI TODO 실행 경로로 템플릿 저장, 템플릿 기반 서비스 초안 생성, preflight, 서비스 생성, 백그라운드 배포, 상태 갱신 action을 순차 실행.
  - 최종 검증 서비스 `Codex Agent UI Service mpw10w1g` 생성.
  - 서비스 ID: `f93f0e84-c70a-4e14-8302-703b282bb065`
  - 템플릿 namespace: `codex_agent_ui_mpw10w1g`
  - 서비스 namespace: `codex_agent_ui_service_mpw10w1g_90f7d6`
  - 런타임: desired 1 / running 1, task error 0.
  - 브라우저로 `http://172.16.0.226:28784` 접속해 nginx welcome page 200 응답 확인.
- 실제 Codex AI Agent 채팅 헬스 체크도 성공했고, 템플릿 저장 및 서비스 생성/배포 API 작업 사용 가능 답변을 받음.
- 검증 중 만든 중간 실패/프로브 서비스와 템플릿은 정리했고, 최종 검증 서비스와 템플릿만 남김.

## 남은 리스크

- 전체 구조 테스트는 기존 oversized model file 규칙 위반과 기존 `page.servers/api.py:625` 응답 위치 이슈 때문에 전체 실행 시 실패가 남아 있음.
- 최종 검증 서비스는 사용자 확인을 위해 남겨두었으므로, 더 이상 필요 없으면 서비스/템플릿 정리가 필요함.
