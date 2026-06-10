# 콘솔 UI 전수 점검과 select/작업 로그/도메인 레이아웃 보정

- 날짜: 2026-06-09
- ID: 007
- 리뷰 ID: hfpghzwqjqivdepiamtcifekwsgcunwt

## 사용자 요청

작업 로그, 모델 선택 custom select 등 부분에서 스타일이 굉장히 많이 깨지고 있어.
관리자 패스워드는 "------"니까 모든 화면들을 한 번씩 전부 확인하면서 UI/UX적으로 개선할만한 점이 있는지, 디자인적으로 좀 더 예쁘게 바꿀 수 있는 부분들이 있는지 확실하고 상세하게 전수조사해서 수정해줘.

## 변경 파일

- `src/angular/app/app.component.scss`
- `src/app/component.search.select/view.html`
- `src/app/component.search.select/view.ts`
- `src/app/page.operations/view.pug`
- `src/app/page.domains/view.pug`
- `devlog.md`
- `devlog/2026-06-09/007-console-ui-audit-select-operation-domain.md`

## 작업 내용

- 공통 버튼 스타일이 `dark:hover:bg-zinc-950` 같은 상태 클래스까지 매칭해 작업 로그 row를 어둡게 칠하던 selector를 정확한 class token 매칭으로 변경했다.
- `wiz-component-search-select` 패널을 실제 trigger 버튼 기준으로 배치하고, fixed containing block 영향으로 우측 화면 밖으로 밀리던 문제를 absolute 레이어 방식으로 정리했다.
- select 패널 폭을 최대 560px로 제한하고 긴 설명은 2줄 clamp 처리해 모델/템플릿 선택 UI가 과하게 넓어지지 않게 했다.
- 작업 로그 목록 row hover/focus 상태를 정리하고, 상세 화면을 상태 배지, 메타 카드, 출력 로그 패널 구조로 재배치했다.
- 도메인 관리 테이블의 최소 폭과 작업 버튼을 축소해 1440px 화면에서 버튼이 화면 밖으로 나가지 않도록 조정했다.

## 확인 결과

- `wiz_project_build(projectName="main", clean=false)` 3회 성공.
- Playwright로 devmode 쿠키(`season-wiz-project=main`, `season-wiz-devmode=true`)와 관리자 로그인 후 `/dashboard`, `/services`, `/services/create`, `/servers`, `/templates`, `/macros`, `/operations`, `/domains`, `/images`, `/system/general`, `/system/ai/codex` 순회 확인.
- `/operations` 목록 row 배경이 투명 상태로 유지되고 상세 진입 시 `출력 로그` 헤더가 표시되는 것을 확인했다.
- `/domains` 로딩 완료 후 clipping 없음 확인.
- `/services/create`, `/system/ai/codex`의 custom select open 상태에서 패널이 viewport 안에 표시되는 것을 확인했다.

## 남은 리스크

- 일부 화면의 데이터 로딩은 실제 백엔드 응답 시간에 따라 3-6초 정도 걸릴 수 있어, 스크린샷 검증에서는 충분한 대기 시간을 두고 확인했다.
- absolute 방식의 select 패널은 fixed 좌표 밀림은 해소하지만, 향후 overflow-hidden 컨테이너 안에 select를 새로 배치할 경우 추가 확인이 필요하다.
