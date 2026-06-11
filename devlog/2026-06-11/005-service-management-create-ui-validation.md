# 005 서비스 관리 생성 UI 레이아웃과 필수값 검증 보정

- 날짜: 2026-06-11
- 리뷰 ID: hhxtqfhtxsmqabkdfkqaljcwelvrfozn

## 사용자 원 요청

- 서비스 관리 화면에서 새 서비스 만들기 버튼이 중복으로 두 개 있으므로, 맨 위 헤더의 새 서비스 버튼을 삭제할 것.
- 새 서비스 만들기 화면과 템플릿 생성 화면의 레이아웃을 통일할 것.
- 각 번호별 `템플릿 N개`, `변수 N개` 같은 뱃지를 삭제할 것.
- 템플릿 custom select 목록과 README 팝오버가 떠 있다는 인식이 명확하도록 border 등을 보강할 것.
- 템플릿, 서비스 이름에 빨간 별을 붙여 필수값임을 알릴 것.
- DDNS 사용 시 앞 주소 기본값 `service`를 설정하지 말고 비워두며, 빨간 별을 붙여 필수값임을 알릴 것.
- 필수값은 생성 전 validation 체크할 것.
- 생성 요약 부분은 화면에서 제거하고 생성 버튼을 누르면 뜨는 모달에 표시할 것.

## 변경 파일

- `src/app/page.services/view.pug`
- `src/app/page.services.create/view.pug`
- `src/app/page.services.create/view.ts`
- `src/app/component.search.select/view.html`
- `tests/e2e/specs/services.spec.ts`
- `devlog.md`
- `devlog/2026-06-11/005-service-management-create-ui-validation.md`

## 변경 내용

- 서비스 관리 상단 헤더의 `새 서비스` 버튼을 제거하고, 서비스 보드 내부의 생성 버튼만 남겼다.
- 새 서비스 만들기 화면을 템플릿 편집 화면과 같은 상단 액션/카드형 섹션 구조로 재배치했다.
- 템플릿/변수 개수 뱃지와 번호형 단계 UI를 제거했다.
- 템플릿, 서비스 이름, DDNS 앞 주소에 필수 빨간 별 표시를 추가했다.
- 공통 검색 select 드롭다운과 템플릿 README 팝오버의 border, ring, shadow, header 배경을 강화했다.
- DDNS 앞 주소가 비어 있을 때 서비스 이름이나 `service`로 자동 채우던 fallback을 제거했다.
- 템플릿 필수 변수와 DDNS 앞 주소를 생성 전 validation으로 차단하도록 보강했다.
- 인라인 생성 요약 섹션을 제거하고 생성 전 확인 모달 안에 요약을 표시하도록 변경했다.
- 서비스 E2E 스펙을 헤더 생성 버튼 제거와 독립 생성 페이지 흐름 기준으로 갱신했다.

## 검증 결과

- 성공: WIZ project build `main`
- 확인: `season-wiz-project=main`, `season-wiz-devmode=true` 쿠키를 추가해 `https://infra-dev.nanoha.kr/services`, `/services/create`에 접근했으나 인증 세션이 없어 `/access`로 리다이렉트됐다.
- 확인: `npx playwright test tests/e2e/specs/services.spec.ts --project=chromium` 실행 결과 `DOCKER_INFRA_TEST_PASSWORD` 미설정으로 1건 skip.
