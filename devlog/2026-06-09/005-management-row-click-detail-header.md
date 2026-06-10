# 관리 목록 row 클릭 이동과 상세 헤더 정리

- 날짜: 2026-06-09
- ID: 005
- 리뷰 ID: hfpghzwqjqivdepiamtcifekwsgcunwt

## 사용자 요청

- 목록 화면들에는 상세 버튼을 따로 두지 말고, 그냥 해당 row를 클릭하면 이동이 되도록 해야해.
- 상세 화면들의 레이아웃 및 디자인 등이 너무 어색해.

## 변경 파일

- `src/app/page.services/view.pug`
- `src/app/page.servers/view.pug`
- `src/app/page.templates/view.pug`
- `src/app/page.macros/view.pug`
- `src/app/page.operations/view.pug`

## 작업 내용

- 서비스/서버/템플릿/매크로 목록 테이블의 `작업` 컬럼과 상세/편집 버튼을 제거했다.
- 목록 row 자체에 클릭, Enter, Space 키 이동을 적용하고 focus ring과 aria-label을 추가했다.
- 서비스/서버/템플릿/매크로 상세 화면의 별도 목록 버튼 줄을 제거하고, 상세 헤더 내부에 목록 복귀 버튼과 화면 라벨을 배치했다.
- 작업 로그 상세는 dim overlay 모달 대신 페이지형 상세 섹션으로 조정했다.

## 확인 결과

- `wiz_project_build(projectName="main", clean=false)` 성공.
- devmode 쿠키 `season-wiz-project=main`, `season-wiz-devmode=true` 포함 후 `http://127.0.0.1:3001/services`, `/services/sample-service`, `/servers`, `/templates/sample-template`, `/macros`, `/macros/sample-macro`, `/operations`, `/operations/sample-operation` HEAD 요청 200 확인.
- `git diff --check` 통과.

## 남은 리스크

- 인증된 브라우저 세션이 없어 실제 데이터 row 클릭과 상세 화면의 시각적 배치까지 브라우저에서 직접 검증하지는 못했다.
