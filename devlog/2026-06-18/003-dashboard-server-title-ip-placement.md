# 대시보드 서버 목록 제목과 IP 표시 위치 보정

- 날짜: 2026-06-18
- ID: 003
- 리뷰 ID: ermofvydqanxipipwcypegbstdoouuzl

## 사용자 원본 요청

- Servers 섹션의 이름을 "서버 목록"으로 변경해줘.
- Servers 섹션에서 각 서버의 2번째 줄을 제거하고, IP는 첫 번째줄 서버 이름 옆으로 옮겨줘.

## 변경 파일

- `src/app/page.dashboard/view.pug`
  - Servers 카드 제목을 `서버 목록`으로 변경했다.
  - 서버 행의 두 번째 줄을 제거하고 `node.host`를 서버명 옆에 표시하도록 변경했다.

## 확인 결과

- `wiz_project_build(projectName="main", clean=false)` 성공.
- `git diff --check` 성공.
