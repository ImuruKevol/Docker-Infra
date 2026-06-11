# 008 custom select overlay 복원과 README 버튼 배치 보정

- 날짜: 2026-06-11
- 리뷰 ID: hhxtqfhtxsmqabkdfkqaljcwelvrfozn

## 사용자 원 요청

- custom select를 인라인 레이어로 바꾸면 열 때마다 화면이 요동치므로 overlay 방식으로 둘 것.
- custom select는 width 100% 대신 적당한 폭으로 제한할 것.
- 새 서비스 만들기 화면에서 select 오른쪽에 README 버튼을 위치시킬 것.

## 변경 파일

- `src/app/component.search.select/view.html`
- `src/app/component.search.select/view.ts`
- `src/app/page.services.create/view.pug`
- `src/app/page.templates/view.pug`
- `devlog.md`
- `devlog/2026-06-11/008-custom-select-overlay-readme-placement.md`

## 변경 내용

- 공통 custom select 패널을 인라인이 아닌 absolute overlay로 복원해 열고 닫을 때 주변 레이아웃 높이가 변하지 않도록 했다.
- select 패널 폭을 최대 560px로 제한하고 viewport 경계를 기준으로 좌우 정렬을 보정했다.
- 서비스 생성 화면의 템플릿 select를 `max-w-xl` 폭으로 제한하고 README 버튼을 오른쪽에 배치했다.
- 템플릿 생성 화면의 기반 템플릿 select들도 `max-w-xl` 폭 제한을 적용했다.
- 서비스 생성 템플릿 카드의 stacking을 올려 overlay 패널이 다음 카드에 묻히지 않도록 했다.

## 검증 결과

- 성공: WIZ project build `main`
- 성공: 실제 브라우저에서 인증 후 `season-wiz-project=main`, `season-wiz-devmode=true` 쿠키로 검증.
- 확인: `/services/create`에서 템플릿 select 폭 제한, README 버튼 오른쪽 배치, select/README 오픈 시 서비스 이름 필드 y좌표 변화 없음.
- 확인: `/services/create`에서 select 패널과 README 패널이 absolute이고 `elementFromPoint` 기준 최상단 패널로 확인됨.
- 확인: `/templates` 새 템플릿 화면에서 기반 템플릿 select 폭 제한, select 오픈 시 AI/직접 작성 영역 y좌표 변화 없음.
