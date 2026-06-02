# 016. 주요 화면 상세 상태 URL 라우팅 명시화

## 사용자 요청

ReviewOps `fjcyarlcfbhrogcvtjdxrilhsrjxphhu` / "라우팅 구조 대 개편"

현재 화면들이 `/services`처럼 목록 URL만 사용하고 상세 선택 상태를 URL에 반영하지 않아 AI Agent가 현재 보고 있는 대상을 파악하기 어렵다. 서비스 상세는 `/services/{id}`처럼 명확한 라우팅 구조로 개선하고, 서비스 관리 외 다른 화면도 같은 방향으로 정리해달라는 요청.

## 변경 파일

- `src/angular/app/app-routing.module.ts`
- `src/portal/season/libs/service.ts`
- `src/app/page.dashboard/view.pug`
- `src/app/page.services/view.ts`
- `src/app/page.services/view.pug`
- `src/app/page.services.create/view.ts`
- `src/app/page.servers/view.ts`
- `src/app/page.servers/view.pug`
- `src/app/page.domains/view.ts`
- `src/app/page.domains/view.pug`
- `src/app/page.images/view.ts`
- `src/app/page.macros/view.ts`
- `src/app/page.operations/view.ts`
- `src/app/page.system/view.ts`
- `src/app/page.templates/view.ts`
- `tests/api/test_wiz_structure_contract.py`
- `tests/api/test_domain_management_ui.py`
- `tests/api/test_services_preflight.py`

## 변경 내용

- WIZ Angular 라우터에 상세 alias를 추가했다.
  - `/services/:service_id`, `/services/:service_id/:detail_tab`
  - `/servers/:node_id`, `/servers/:node_id/:detail_tab`
  - `/domains/:zone_id`
  - `/images/local/:node_id`, `/images/harbor/:project_name/:repository_name`
  - `/macros/:macro_id`, `/operations/:operation_id`
  - `/system/:section/:subsection`, `/templates/:template_id`
- 기존 query parameter 진입은 유지하면서 화면 초기화 시 path 기반 라우트로 정규화되게 했다.
- 목록에서 상세 선택, 상세 탭 변경, 작업 로그 모달 열기/닫기, 시스템 설정 탭 변경 시 URL이 현재 화면 상태를 반영하도록 동기화했다.
- 대시보드/서버/도메인/서비스 생성 화면의 서비스 상세 링크를 `/services/{id}` 기반으로 바꿨다.
- 라우팅 유틸리티(`routeTo`, `routeSegment`, `encodeRouteSegment` 등)를 공통 `Service`에 추가했다.

## 확인

- `wiz_project_build(projectName="main", clean=false)`: 통과.
- `/opt/conda/envs/docker-infra/bin/python -m unittest tests.api.test_wiz_structure_contract.WizStructureContractTest.test_frontend_detail_routes_are_explicit tests.api.test_domain_management_ui.DomainManagementUiStaticContractTest.test_certificate_service_links_open_service_detail tests.api.test_services_preflight.ServicesPreflightStaticContractTest.test_service_detail_operator_runtime_summary_is_wired`: 통과.
- devmode 쿠키(`season-wiz-project=main`, `season-wiz-devmode=true`)로 다음 URL HTTP 200 확인:
  - `/services`, `/services/test-route-id`
  - `/servers/test-node/terminal`
  - `/domains/test-zone`
  - `/images/local/test-node`
  - `/images/harbor/test-project/test-repo`
  - `/macros/test-macro`
  - `/operations/test-operation`
  - `/system/ai/hermes`
  - `/templates/test-template`
- 전체 `tests/api/test_wiz_structure_contract.py tests/api/test_domain_management_ui.py tests/api/test_services_preflight.py` 묶음 실행은 기존 구조 계약 위반으로 실패했다. 실패 내용은 다수 model 파일 300줄 초과와 `src/app/page.servers/api.py:625`의 `wiz.response` try/except 내부 호출이며, 이번 라우팅 변경 범위와 직접 관련된 검증 3건은 통과했다.
