# 마이그레이션 모달 custom search-select 유지 보정

## 요청

- 리뷰 ID: `rwckyzwrnxhehtpkgyujeowghxhklfjx`
- 제목: 서비스 관리 화면 상세 수정
- 원 요청: "왜 native select로 바꿔? custom search-select로 유지하면서 버그를 고쳐야지."

## 변경 사항

- 마이그레이션 모달의 이동할 서버 선택 UI를 `wiz-component-search-select`로 되돌렸다.
- 공통 search-select가 드롭다운 input에 포커스를 줄 때 `preventScroll`을 사용해 모달 내부 컨텐츠가 위로 밀리는 현상을 막았다.
- 마이그레이션 모달 컨테이너를 `overflow-visible`로 바꿔 search-select 드롭다운이 모달 하단에서 잘리지 않도록 했다.
- 마이그레이션 정적 계약 테스트에 custom search-select 유지, native select 미사용, 드롭다운 포커스/overflow 보정 계약을 추가했다.

## 변경 파일

- `src/app/component.search.select/view.ts`
- `src/app/page.services/view.pug`
- `src/app/page.services/view.ts`
- `tests/api/test_service_migration.py`
- `devlog.md`
- `devlog/2026-06-12/002-migration-custom-search-select-fix.md`

## 검증

- 성공: `wiz_project_build(projectName="main", clean=false)`
- 성공: `python -m unittest tests.api.test_service_migration -q`
- 성공: `python -m unittest tests.api.test_services_preflight.ServicesPreflightStaticContractTest.test_service_release_contract_is_wired tests.api.test_services_preflight.ServicesPreflightStaticContractTest.test_service_edit_wizard_contract_is_wired -q`
- 성공: `git diff --check`
- 성공: Playwright 브라우저 검증
  - `season-wiz-project=main`, `season-wiz-devmode=true` 쿠키와 제공된 검증 비밀번호로 로컬 WIZ 서버 로그인.
  - 마이그레이션 모달에서 `hasCustomSearchSelect=true`, `hasNativeSelect=false`, `hasPauseOption=false` 확인.
  - 드롭다운 측정: `triggerWithinModal=true`, `panelWithinViewport=true`, `panelBelowTrigger=true`, `optionCount=3`.
  - 스크린샷: `.runtime/reviewops-migration-modal-custom-select-fixed.png`
