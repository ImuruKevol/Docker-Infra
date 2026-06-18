# 대시보드 서버 목록 등록 수 표시 적용

- 날짜: 2026-06-18
- ID: 004
- 리뷰 ID: ermofvydqanxipipwcypegbstdoouuzl

## 사용자 원본 요청

서버 목록 섹션에 "137개 기록 파일"이라고 써있는 의미 없는 부분은 삭제하고 서비스 목록 섹션처럼 몇 개가 등록되어있는지 표시하도록 수정해줘.

## 변경 파일

- `src/app/page.dashboard/view.pug`
  - 서버 목록 보조 문구를 기록 파일 수 대신 `Docker Infra 기준 N개` 등록 수 표시로 변경했다.
- `src/app/page.dashboard/view.ts`
  - 더 이상 사용하지 않는 `metricHistoryText` 헬퍼를 제거했다.

## 확인 결과

- `wiz_project_build(projectName="main", clean=false)` 성공.
- `git diff --check` 성공.
- `metricHistoryText` 참조가 남아 있지 않음을 확인했다.
