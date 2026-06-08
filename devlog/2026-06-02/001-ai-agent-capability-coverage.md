# AI Agent 기능 보완

## 원 요청

"현재 이 서비스에서 화면을 통해 사용할 수 있는 기능들은 전부 AI Agent로 가능해야해. 부족한 점이 있는지, 로직상 최적화할 부분이 있는지, 설계에 보완해야할 점이 있는지 등을 모두 상세하게 분석하고 보완해줘."

- 리뷰 ID: `klffpnhvpdesiwbdgxbcrjlcfoeilcnh`
- 요청 링크: `https://infra-dev.nanoha.kr/access`

## 변경 파일

- `docs/api/openapi.json`
  - AI Agent 실행 카탈로그를 174개 작업으로 확장했다.
  - 서비스 생성/관리, 서버, 도메인, 이미지, 매크로, 작업 이력, 템플릿, 시스템 설정, AI Agent 히스토리, 파일 트리 조작 API를 카탈로그에 추가했다.
  - `/api/ai-agent/capabilities` 응답 schema 예시를 실제 런타임의 `operation_id` 형식에 맞췄다.
- `src/angular/app/app.component.ts`
  - destructive 작업이 영구적으로 차단되던 로직을 보완해, AI 응답이 확인 필요 상태가 아니고 현재 사용자 요청에 삭제/초기화 등 명시적 확인이 있는 경우 실행 가능하게 했다.
- `src/model/struct/ai_assistant.py`
  - AI Agent 시스템 프롬프트에 OpenAPI 카탈로그 작업을 우선 사용하도록 지시를 강화했다.
- `tests/api/test_openapi_contract.py`
  - 카탈로그가 주요 화면 기능과 신규 상세 작업을 포함하는지 검증을 보강했다.
- `tests/api/test_wiz_structure_contract.py`
  - destructive 작업이 확인 후에도 무조건 차단되지 않도록 구조 검증을 추가했다.

## 확인한 내용

- 페이지 `api.py` 함수 목록과 AI Agent 카탈로그를 대조했고, 스트리밍/파일 업로드/로그인처럼 브라우저 `api_request`로 직접 실행하기 부적합한 작업을 제외한 화면 API를 카탈로그에 반영했다.
- `ddns_unavailable`은 `page.domains/api.py` 내부 helper라 카탈로그 대상에서 제외했다.
- 파일 업로드류는 현재 AI Agent `api_request`가 `application/x-www-form-urlencoded` 실행 방식이므로 직접 바이너리 업로드 작업으로 등록하지 않았다.

## 검증 결과

- 성공: `PYTHONPATH=tests/api /opt/conda/envs/docker-infra/bin/python -m unittest`로 OpenAPI 정적 계약 관련 6개 테스트와 AI Agent destructive 구조 테스트 1개를 통과했다.
- 성공: `/opt/conda/envs/docker-infra/bin/wiz` 빌드 MCP 실행 결과 프로젝트 `main` 빌드가 성공했다.
- 성공: 쿠키 `season-wiz-project=main; season-wiz-devmode=true`를 포함해 로컬 `/openapi.json`을 조회했고 AI Agent 작업 수가 174개로 확인됐다.
- 제한: 인증 세션이 없어 로컬 `/api/ai-agent/capabilities` 직접 호출은 `401 AUTHENTICATION_REQUIRED`로 확인됐다.
- 참고: `tests.api.test_wiz_structure_contract` 전체 실행은 기존 대형 model 파일 line 수 제한 및 기존 `page.servers/api.py` 응답 위치 검증 실패로 통과하지 않았다. 이번 변경 확인용 신규 destructive 구조 테스트는 단독 통과했다.
