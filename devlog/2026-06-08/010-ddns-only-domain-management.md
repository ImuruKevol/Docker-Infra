# 도메인 관리를 DDNS 전용 흐름으로 단순화

- 날짜: 2026-06-08
- ID: 010
- 리뷰 ID: wmidmxmacideroaomknwjpmugxraddqf

## 사용자 원 요청

작업 시작

리뷰어 요청:

- Cloudflare API를 활용한 도메인 직접 관리 기능은 전부 제거한다.
- 서비스 생성 시에도 관련 내용을 제거해서 오로지 DDNS로만 지정할 수 있게 한다.
- 도메인 관리 화면 UI를 개선한다. 현재 등록 컬럼에 갯수 뱃지와 API 호출 버튼이 겹치는 등 UI가 깨져 있다.

## 변경 파일

- `README.md`
- `docs/api/openapi.json`
- `docs/docker-infra-deployment.md`
- `docs/docker-infra-design.md`
- `docs/docker-infra-development-todo.md`
- `docs/docker-infra-runtime.md`
- `docs/service-ai-codex-agent-design.md`
- `src/app/page.dashboard/view.pug`
- `src/app/page.domains/api.py`
- `src/app/page.domains/view.pug`
- `src/app/page.domains/view.ts`
- `src/app/page.services.create/api.py`
- `src/app/page.services.create/view.pug`
- `src/app/page.services.create/view.ts`
- `src/app/page.services/api.py`
- `src/app/page.services/view.pug`
- `src/app/page.services/view.ts`
- `src/model/struct/ai_assistant.py`
- `src/model/struct/domains.py`
- `src/model/struct/domains_cloudflare.py`
- `src/model/struct/domains_ddns.py`
- `src/model/struct/infra_catalog.py`
- `src/model/struct/infra_catalog_registry.py`
- `src/model/struct/services.py`
- `src/model/struct/services_delete.py`
- `src/model/struct/services_preflight.py`
- `src/model/struct/services_update.py`
- `src/model/struct/services_wizard.py`
- `tests/api/test_domain_management_ui.py`
- `tests/api/test_openapi_contract.py`
- `tests/api/test_services_preflight.py`
- `tests/api/test_system_settings_dynamic_menu.py`
- `devlog.md`
- `devlog/2026-06-08/010-ddns-only-domain-management.md`

## 작업 내용

- 도메인 관리 화면을 DDNS 관리 서버와 등록된 DDNS 레코드 중심으로 재구성하고 Cloudflare zone/record/인증서 직접 관리 UI를 제거했다.
- DDNS 서버 테이블의 등록 레코드 컬럼과 작업 컬럼 폭을 분리해 갯수 뱃지와 API 호출 버튼이 겹치지 않게 했다.
- 도메인 API에서 Cloudflare zone, DNS record, 인증서 직접 관리 액션을 제거하고 DDNS endpoint 저장/삭제/수동 호출/dispatcher 등록만 남겼다.
- 서비스 생성/수정/AI 컨텍스트/사전 점검에서 도메인은 DDNS endpoint 하위 suffix만 허용하도록 조정했다.
- 대시보드 도메인 요약과 API 카탈로그/문서를 DDNS 기준으로 갱신했다.

## 확인 결과

- `py_compile` 주요 변경 Python 파일: 통과
- `python -m json.tool docs/api/openapi.json`: 통과
- `python -m unittest tests.api.test_domain_management_ui tests.api.test_system_settings_dynamic_menu`: 통과, 2건 skip
- `python -m unittest tests.api.test_services_preflight.ServicesPreflightStaticContractTest.test_service_delete_uses_ddns_unregister_and_skips_legacy_dns tests.api.test_services_preflight.ServicesPreflightStaticContractTest.test_p7_nginx_and_domain_certificate_contract_is_wired`: 통과
- `wiz_project_build(clean=false)`: 통과
- `curl -H 'Cookie: season-wiz-project=main; season-wiz-devmode=true' https://infra-dev.nanoha.kr/dashboard`: HTTP 200
- `curl -H 'Cookie: season-wiz-project=main; season-wiz-devmode=true' -X POST https://infra-dev.nanoha.kr/wiz/api/page.domains/load`: HTTP 200, 인증 없음 응답(401 payload) 확인

## 남은 리스크

- `tests.api.test_openapi_contract`는 로컬 환경에 `openapi_validator` 모듈이 없어 import 단계에서 실행하지 못했다.
- `tests.api.test_services_preflight` 전체 실행은 현재 작업 전부터 수정 중인 서비스 생성 단일 흐름 계약(`deploy_service_background` 등) 기대값과 맞지 않아 일부 실패한다.
