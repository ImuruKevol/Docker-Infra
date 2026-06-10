# 로그인 이후 콘솔 디자인 리프레시

- 날짜: 2026-06-09
- ID: 006
- 리뷰 ID: hfpghzwqjqivdepiamtcifekwsgcunwt

## 사용자 요청

현재 디자인 자체가 좀 많이 구려. 로그인 화면만 놔두고 사이드바, 각 화면들의 디자인 전체를 싹 갈아엎어줘. 디자인 자체가 좀 많이 투박하고 구식같은 느낌이 들어.

## 변경 파일

- `src/app/layout.sidebar/view.pug`
- `src/app/component.nav.sidebar/view.pug`
- `src/app/component.nav.sidebar/view.ts`
- `src/angular/app/app.component.scss`

## 작업 내용

- 로그인 이후 레이아웃에 `infra-shell` 전용 루트를 추가하고 사이드바 폭, 배경, 모바일 오버레이, 콘텐츠 여백을 재정리했다.
- 사이드바 브랜드 영역, 언어/다크모드 패널, 메뉴 active/hover 상태, 로그아웃 버튼 스타일을 현대적인 콘솔 톤으로 변경했다.
- `infra-shell` 하위에만 적용되는 공통 CSS를 추가해 헤더, 카드, 테이블, row hover, 입력 폼, 버튼 스타일을 전역적으로 리프레시했다.
- 로그인 화면(`page.access`, `layout.empty`)은 수정하지 않고 새 공통 CSS도 `infra-shell` 내부로 스코프를 제한했다.

## 확인 결과

- `wiz_project_build(projectName="main", clean=false)` 성공.
- devmode 쿠키 `season-wiz-project=main`, `season-wiz-devmode=true` 포함 후 `/dashboard`, `/services`, `/servers`, `/system`, `/templates`, `/macros`, `/operations`, `/images`, `/access` HEAD 요청 200 확인.
- `git diff --check` 통과.

## 남은 리스크

- 인증된 브라우저 세션이 없어 실제 데이터가 채워진 화면에서의 시각적 품질과 반응형 배치는 직접 캡처 검증하지 못했다.
