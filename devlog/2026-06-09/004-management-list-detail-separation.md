# 관리 화면 목록/상세 렌더링 완전 분리

- 날짜: 2026-06-09
- ID: 004
- 리뷰 ID: hfpghzwqjqivdepiamtcifekwsgcunwt

## 사용자 요청

목록화면과 상세 화면은 완전히 분리가 되어야 해.

## 변경 파일

- `src/app/page.services/view.ts`
- `src/app/page.services/view.pug`
- `src/app/page.servers/view.ts`
- `src/app/page.servers/view.pug`
- `src/app/page.templates/view.ts`
- `src/app/page.templates/view.pug`
- `src/app/page.macros/view.ts`
- `src/app/page.macros/view.pug`
- `src/app/page.operations/view.ts`
- `src/app/page.operations/view.pug`

## 작업 내용

- 서비스/서버/템플릿/매크로 화면에 목록 화면 여부와 상세 화면 여부를 구분하는 helper를 추가했다.
- 목록 경로에서는 보드 목록과 공통 페이지네이션만 렌더링하고, 상세/편집 경로에서는 상세 콘텐츠만 렌더링하도록 `*ngIf` 조건을 분리했다.
- 상세 화면 상단에 목록 복귀 버튼을 추가하고, 복귀 시 선택 상태/상세 로딩 상태/관련 갱신 상태를 정리하도록 했다.
- 작업 로그는 상세 오버레이가 열릴 때 목록 섹션을 언마운트해 목록과 상세가 동시에 남지 않도록 조정했다.

## 확인 결과

- `wiz_project_build(projectName="main", clean=false)` 성공.
- devmode 쿠키 `season-wiz-project=main`, `season-wiz-devmode=true` 포함 후 `http://127.0.0.1:3001/services`, `/services/sample-service`, `/servers`, `/templates/sample-template`, `/macros`, `/macros/sample-macro`, `/operations`, `/operations/sample-operation` HEAD 요청 200 확인.

## 남은 리스크

- 인증된 브라우저 세션이 없어 실제 데이터가 있는 상태에서 목록에서 상세로 이동하고 다시 목록으로 복귀하는 클릭 검증은 수행하지 못했다.
