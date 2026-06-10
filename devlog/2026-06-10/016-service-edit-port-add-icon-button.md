# 서비스 수정 구성 탭 포트 추가 버튼 아이콘화

- 날짜: 2026-06-10
- 리뷰 ID: zsrwyfbkctvcgdzkpqnohoqnsknjuibh
- 요청: 서비스 수정 모달 구성 탭의 `+ 포트` 버튼에서 텍스트를 삭제하고 `+`만 남김.

## 변경 파일

- `src/app/page.services/view.pug`
- `devlog.md`
- `devlog/2026-06-10/016-service-edit-port-add-icon-button.md`

## 변경 내용

- 구성 탭 연결 포트 컬럼의 포트 추가 버튼을 `+` 아이콘만 보이는 정사각 버튼으로 변경했다.
- 화면 텍스트는 제거하되 `aria-label`과 `title`은 `포트 추가`로 유지했다.

## 확인 결과

- `wiz_project_build(projectName="main", clean=false)` 성공.
- `curl -I`에 `season-wiz-project=main; season-wiz-devmode=true` 쿠키를 포함해 `/access`, `/services` 경로 모두 `200 OK` 확인.
