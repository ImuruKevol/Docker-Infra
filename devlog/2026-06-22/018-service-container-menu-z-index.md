# 018. 서비스 컨테이너 메뉴 z-index 보정

## 원 요청

- 리뷰 ID: `kmdgruktrnujxsiakyaeutwuyxbaxzik`
- 요청: 첨부 스크린샷처럼 컨테이너 컨텍스트 메뉴의 z-index가 낮아 무료 SSL 인증서 섹션 밑으로 깔리는 문제 수정.

## 변경 파일

- `src/app/page.services/view.pug`
  - 실행 상태 카드 섹션에 `service-runtime-section relative` 클래스를 추가해 컨테이너 메뉴가 열릴 때 섹션 자체를 상위 stacking context로 올릴 수 있게 했다.
- `src/app/page.services/view.scss`
  - `.service-runtime-section:has(.service-runtime-container-menu[open])`에 `z-index: 30`을 추가해 뒤따르는 무료 SSL 인증서 섹션보다 위에 표시되도록 했다.
- `tests/api/test_services_preflight.py`
  - 컨테이너 메뉴 z-index 보정용 섹션 클래스와 스타일 계약을 추가했다.

## 확인 결과

- 첨부 스크린샷을 확인해 메뉴가 무료 SSL 섹션 아래로 깔리는 stacking context 문제로 판단했다.
- `python -m unittest tests.api.test_services_preflight.ServicesPreflightStaticContractTest.test_service_detail_operator_runtime_summary_is_wired` 성공.
- WIZ build(`clean=false`) 성공.

## 남은 리스크

- 실제 브라우저에서 로그인 후 동일 서비스 상세 화면을 직접 조작하는 검증은 수행하지 않았다.
- 작업 전부터 존재하던 다른 파일 변경과 미추적 파일은 유지했다.
