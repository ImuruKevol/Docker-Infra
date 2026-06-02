# Swagger 기반 AI Agent 메뉴별 API 작업 카탈로그와 실행 액션 연결

- **ID**: 007
- **날짜**: 2026-06-01
- **유형**: 기능 추가

## 작업 요약
OpenAPI 문서에 `x-ai-agent` 확장 카탈로그를 추가해 대시보드, 서비스, 서버, 도메인, 이미지, 매크로, 작업 이력, 템플릿, 시스템 메뉴의 주요 API 작업을 Agent가 참조할 수 있게 했다.
AI Agent 컨텍스트와 `/api/ai-agent/capabilities` 응답에 이 카탈로그를 노출하고, 프론트 실행기는 `api_request` 액션을 받아 카탈로그에 등록된 operation만 호출하도록 연결했다.

## 원문 요청사항
```text
# ReviewOps Codex 작업 요청

아래 요청을 현재 프로젝트 루트에서 처리하세요. 필요한 파일을 직접 수정하고, 마지막 응답은 한국어로 간결하게 작성하세요.
스트리밍 응답은 사용하지 않습니다. 작업이 끝난 뒤 변경 요약, 확인한 내용, 남은 리스크만 정리하세요.
이 작업의 세션 단위는 아래 리뷰 ID입니다. 리뷰 ID가 같으면 같은 Codex 히스토리 맥락으로 이어서 처리하세요.

## 사용자 요청

매크로 화면 뿐만이 아니라 대시보드, 서비스 관리, 도메인 관리 등 모든 메뉴에 대해 기능을 연결해야해.
아예 Swagger를 추가하고, 그 Swagger를 기반으로 AI Agent가 동작할 수 있도록 연결하는 것도 좋을 것 같아.

## 리뷰 요약

- 리뷰 ID: wsymtidsrimcycxuxkiohaxivncfmbix
- 제목: AI Agent 기능 개선
- 요청 링크: https://infra-dev.nanoha.kr/dashboard
- Codex 요청자: 권태욱
- 프로젝트 루트: /root/docker-infra
- Codex 세션 ID: 019e81ae-403c-7e10-9161-bec31cd1efa4
- 스크린샷 컨텍스트: 없음
- 에이전트 작업 지시서 컨텍스트: 포함됨
- HTML 문서 생성 규칙 컨텍스트: 없음
- HTML 문서 설정 컨텍스트: 없음
- HTML 프로젝트 인스트럭션 파일: 없음
- 첨부파일 컨텍스트: 0개

## 세션 처리

저장된 Codex 세션을 resume해 이전 대화 맥락을 우선 사용하세요. 이전 Codex 히스토리는 이 요청에 포함되지 않습니다.

## 에이전트 작업 지시서

# 에이전트 작업 지시서

## 리뷰 정보

- 리뷰 ID: wsymtidsrimcycxuxkiohaxivncfmbix
- 제목: AI Agent 기능 개선
- 상태: in_progress
- 우선순위: high
- 분류: design
- 프로젝트: Docker Infra DEV
- 프로젝트 종류: web_service
- 요청 링크: https://infra-dev.nanoha.kr/dashboard
- 화면: 1440x900
- 캡처 방식: browser-display-capture-element
- 스크린샷 첨부: yes
- 리뷰 첨부 파일: 0개

## 리뷰어 요청 내용

현재 AI Agent에 채팅을 하면 그냥 답변만 해주고 있음. 간단한 화면 이동은 할 수 있는 것 같은데, 제일 필요한 기능이 동작하지 않음.
"서버 상태를 한눈에 확인할 수 있는 매크로를 추가해줘" 라고 채팅을 치면 AI Agent가 직접 화면 이동 및 컨트롤을 하면서 실제 이 서비스를 컨트롤할 수 있어야 함. 모든 화면에 대해 이런 동작을 할 수 있도록 분석하고 기능을 추가해줘.
```

## 변경 파일 목록
- `docs/api/openapi.json`
  - `ai-agent` 태그와 `/api/ai-agent/status`, `/api/ai-agent/capabilities`, `/api/ai-agent/chat` 계약을 추가했다.
  - `x-ai-agent.operations`에 9개 주요 메뉴의 55개 Agent 실행 가능 operation을 등록했다.
  - 기존 `LocalMasterNode` 예제에 필수 필드 `private_host`, `public_ip`를 보강해 정적 OpenAPI 예제 검증이 통과하도록 했다.
- `src/model/struct/ai_assistant.py`
  - OpenAPI 문서의 `x-ai-agent` 카탈로그를 읽는 `openapi_capabilities()`를 추가하고, status/chat context에 Swagger 기반 작업 목록을 포함했다.
  - `api_request` 액션 타입과 `operation_id`, `params`, `body` 정규화를 추가했다.
- `src/route/api-ai-agent/controller.py`
  - `/api/ai-agent/capabilities` 경로를 추가했다.
- `src/angular/app/app.component.ts`
  - Agent capability operation 목록을 로드하고, `api_request` 액션을 카탈로그 operation 기준으로 검증한 뒤 same-origin API 호출로 실행하도록 했다.
  - destructive safety operation은 프론트 실행기에서 자동 실행하지 않도록 유지했다.
- `tests/api/test_ai_agent_history.py`, `tests/api/test_openapi_contract.py`
  - AI Agent OpenAPI capability 노출, 프론트 `api_request` 실행기, 메뉴별 operation 카탈로그 커버리지를 검증했다.
- `devlog.md`, `devlog/2026-06-01/007-ai-agent-openapi-operation-catalog.md`
  - 작업 이력을 기록했다.

## 검증 결과
- `/opt/conda/envs/docker-infra/bin/python -m py_compile src/model/struct/ai_assistant.py src/route/api-ai-agent/controller.py tests/api/test_ai_agent_history.py tests/api/test_openapi_contract.py` 성공.
- `/opt/conda/envs/docker-infra/bin/python -m unittest tests.api.test_ai_agent_history.AIAgentHistoryStaticContractTest` 성공.
- `PYTHONPATH=tests/api /opt/conda/envs/docker-infra/bin/python -m unittest tests.api.test_openapi_contract.OpenApiContractTest.test_static_openapi_contains_initial_contract tests.api.test_openapi_contract.OpenApiContractTest.test_static_openapi_contains_p1_common_components tests.api.test_openapi_contract.OpenApiContractTest.test_ai_agent_openapi_catalog_covers_main_menus tests.api.test_openapi_contract.OpenApiContractTest.test_static_response_examples_match_declared_schemas` 성공.
- `python -m json.tool docs/api/openapi.json` 성공.
- `git diff --check -- docs/api/openapi.json src/model/struct/ai_assistant.py src/route/api-ai-agent/controller.py src/angular/app/app.component.ts tests/api/test_ai_agent_history.py tests/api/test_openapi_contract.py` 성공.
- `wiz_project_build(clean=false, projectName=main)` 성공.
- 쿠키 `season-wiz-project=main`, `season-wiz-devmode=true`를 포함한 로컬 curl 검증을 시도했으나, 현재 로컬 `127.0.0.1:3000`은 미실행, `127.0.0.1:80`은 해당 WIZ 라우트 404로 실제 브라우저/API 런타임 검증은 수행하지 못했다.
