# 271. 서비스 상세 서버 바로가기 버튼 위치와 새로고침 버튼 정리

- 날짜: 2026-05-20
- 리뷰 ID: gssucnzbkwpxnpoduqmnfmfzudkzbsom
- 요청: 서비스 상세 화면에서 헤더 우측 상단의 서버 바로가기 버튼을 왼쪽 하단에 있는 서비스 주소 바로가기 버튼 오른쪽으로 옮기고 구분이 되도록 색상을 바꿔줘. 그리고 새로고침 버튼은 삭제해줘.

## 변경 파일

- `src/app/page.services/view.pug`
- `devlog.md`
- `devlog/2026-05-20/271-service-detail-server-shortcut-placement.md`

## 변경 내용

- 서비스 상세 헤더 우측 액션 영역에 있던 서버 상세 바로가기 링크를 서비스 주소 바로가기 옆으로 이동했다.
- 서버 상세 바로가기 링크를 서비스 주소 링크와 구분되도록 indigo 계열 배경/테두리/텍스트 색상으로 변경했다.
- 서비스 상세 헤더 우측 액션 영역의 새로고침 버튼을 제거했다.

## 검증

- `wiz_project_build(projectName="main", clean=false)` 성공.

## 남은 리스크

- 실제 브라우저 화면에서 픽셀 단위 배치 검증은 수행하지 않았다.
