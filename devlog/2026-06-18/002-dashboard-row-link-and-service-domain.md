# 대시보드 서버/서비스 목록 행 표시 방식 보정

- 날짜: 2026-06-18
- ID: 002
- 리뷰 ID: ermofvydqanxipipwcypegbstdoouuzl

## 사용자 원본 요청

- servers 섹션에 상세 링크 버튼을 추가하지 말고 서비스 목록 섹션처럼 수정해줘.
- 서비스 목록 섹션에 2번째, 4번째 줄 날짜 부분은 삭제해줘. 그리고 "도메인 N개" 뱃지의 내용을 현재 기준 2번째 줄에 표시된 도메인 정보로 바꿔줘.

## 변경 파일

- `src/app/page.dashboard/view.pug`
  - Servers 섹션의 별도 상세 버튼을 제거하고, 서비스 목록처럼 서버 행 전체를 상세 화면 링크로 변경했다.
  - 서비스 목록 행의 보조 설명 줄과 날짜 줄을 제거했다.
  - 서비스 목록의 `도메인 N개` 뱃지를 실제 대표 도메인 표시로 변경했다.

## 확인 결과

- `wiz_project_build(projectName="main", clean=false)` 성공.
- `git diff --check` 성공.
