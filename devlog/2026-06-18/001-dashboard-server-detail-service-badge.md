# 대시보드 서버 상세 이동과 서비스 상태 배지 정리

- 날짜: 2026-06-18
- ID: 001
- 리뷰 ID: ermofvydqanxipipwcypegbstdoouuzl

## 사용자 원본 요청

작업 시작

리뷰 요청:
- Servers 섹션에서 서버 보기 버튼을 통해 서버 목록으로는 갈 수 있는데 해당 서버 상세 화면으로 바로 이동할 수 있는 기능이 없음. 추가 필요.
- 서비스 목록 섹션에서 각 서비스별 상태 뱃지 제거

## 변경 파일

- `src/app/page.dashboard/view.pug`
  - Servers 섹션의 각 서버 행에 서버 상세 화면으로 이동하는 `상세` 링크를 추가했다.
  - 서비스 목록 섹션의 각 서비스 행에서 상태 뱃지를 제거했다.
- `src/app/page.dashboard/view.ts`
  - 서버 상세 라우터 링크 배열을 반환하는 `nodeDetailRoute` 헬퍼를 추가했다.

## 확인 결과

- `wiz_project_build(projectName="main", clean=false)` 성공.
- 변경 범위는 `page.dashboard` Source 앱과 devlog에 한정했다.
