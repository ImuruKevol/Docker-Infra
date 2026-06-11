# 007 서비스/템플릿 생성 화면 세로 흐름과 레이어 검증 보정

- 날짜: 2026-06-11
- 리뷰 ID: hhxtqfhtxsmqabkdfkqaljcwelvrfozn

## 사용자 원 요청

- 새 서비스 만들기 화면을 직접 확인해 레이아웃, 디자인, 버튼 동작, z-index 문제를 모두 확인할 것.
- 좌우를 번갈아 보는 흐름이 아니라 위에서 아래로 내려가는 흐름으로 수정할 것.
- 같은 문제가 있는 템플릿 생성 화면도 함께 수정할 것.

## 변경 파일

- `src/app/page.services.create/view.pug`
- `src/app/page.templates/view.pug`
- `src/app/component.search.select/view.html`
- `src/app/component.search.select/view.ts`
- `devlog.md`
- `devlog/2026-06-11/007-service-template-create-vertical-flow-browser-validation.md`

## 변경 내용

- 새 서비스 만들기 화면의 기본 정보, 템플릿 변수, DDNS 설정, 생성 전 확인 모달 항목을 세로 입력 흐름으로 정리했다.
- 템플릿 생성 화면의 작성 방식 선택, AI 초안 작성, 직접 작성, Namespace/이름, 표준 가이드/에디터, Preview 영역을 세로 흐름으로 정리했다.
- 템플릿 생성/편집 카드 내부의 상단 액션 영역과 탭 영역이 큰 화면에서 좌우로 벌어지지 않도록 조정했다.
- 공통 검색 select 드롭다운을 absolute/fixed 레이어가 아닌 인라인 패널로 바꾸고 border/ring/shadow를 강화해 카드 stacking context에 덮이지 않도록 했다.
- 서비스 생성 화면의 README 패널도 인라인 패널로 바꿔 다음 카드에 가려지지 않도록 했다.

## 검증 결과

- 성공: WIZ project build `main`
- 성공: 실제 브라우저에서 `season-wiz-project=main`, `season-wiz-devmode=true` 쿠키를 추가하고 `https://infra-dev.nanoha.kr` 인증 후 검증.
- 확인: `/services/create`에서 템플릿 select, README 패널, DDNS 사용/사용 안 함, DDNS suffix select, 생성 버튼 필수값 검증 모달을 클릭 확인.
- 확인: `/templates`에서 새 템플릿, 기반 템플릿 select, 직접 작성, README/Compose/기본값/Schema/Preview 탭, 방식 변경, AI 초안 작성, AI 기반 템플릿 select를 클릭 확인.
- 확인: 열린 select 패널과 README 패널은 `elementFromPoint` 기준으로 최상단 요소가 패널 내부임을 확인.
- 확인: 서비스 생성의 DDNS 앞 주소 기본값은 빈 값이며, 서비스 이름 누락 시 생성 전 validation 모달이 표시됨.
