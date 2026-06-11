# 011 템플릿 목록 생성 화면 노출 컬럼 추가

- 날짜: 2026-06-11
- 리뷰 ID: akzftdlktpeogugonbrxquomuwxujxzo

## 사용자 원 요청

- 템플릿 목록에 서비스 생성 화면에 노출 여부도 추가.
- Namespace 다음에 컬럼 추가.

## 변경 파일

- `src/app/page.templates/view.pug`
- `devlog.md`
- `devlog/2026-06-11/011-template-list-enabled-column.md`

## 변경 내용

- 템플릿 목록 테이블에서 Namespace 다음에 `생성 화면` 컬럼을 추가했다.
- `item.enabled !== false` 기준으로 `노출`/`숨김` 뱃지를 표시하고, 눈/눈 가림 아이콘으로 상태를 구분했다.
- 신규 컬럼을 고정 폭으로 두고 태그 컬럼은 남은 영역을 계속 사용하도록 테이블 최소 폭을 조정했다.

## 검증 결과

- 성공: WIZ project build `main`
- 확인: `season-wiz-project=main`, `season-wiz-devmode=true` 쿠키를 추가한 Playwright 확인을 시도했으나 로컬 서버가 인증 화면(`/access`)으로 리다이렉트되어 인증 후 화면 검증은 수행하지 못했다.
- 확인: `생성 화면`, `item.enabled`, `fa-eye`, `fa-eye-slash` 렌더링 참조가 템플릿 목록에 반영됐는지 검색으로 확인했다.
