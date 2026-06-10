# 컨테이너 파일 미리보기 모달 overflow 보정

- 날짜: 2026-06-10
- ID: 028
- 리뷰 ID: nouorpvnookelikecxsawaoeexhtndmj

## 사용자 원본 요청

컨테이너 파일 탭에서 내부 파일을 열면 첨부 스크린샷처럼 overflow 영향으로 파일 내용이 제대로 보이지 않는 문제를 수정 요청.

## 변경 파일

- `src/app/page.services/view.pug`
- `src/app/page.services/view.ts`
- `devlog.md`
- `devlog/2026-06-10/028-container-file-preview-modal-overflow.md`

## 변경 내용

- 컨테이너 내부 파일 트리를 `selectMode`로 전환해 파일 트리 컴포넌트 내부 고정 모달 대신 서비스 페이지 최상위 파일 미리보기 모달을 사용하도록 변경했다.
- 컨테이너 파일 선택 이벤트를 받아 파일 경로와 내용을 전역 미리보기 모달에 표시하는 핸들러를 추가했다.
- 파일 미리보기 모달에 viewport 기준 최대 높이, flex 레이아웃, 제목 말줄임, 가로 스크롤 가능한 `wrap=off` textarea를 적용했다.

## 검증 결과

- `wiz_project_build(projectName=main, clean=false)` 성공.
- `git diff --check -- src/app/page.services/view.pug src/app/page.services/view.ts` 통과.
- `season-wiz-project=main`, `season-wiz-devmode=true` 쿠키로 `http://127.0.0.1:3001/services`, `http://127.0.0.1:3001/dashboard` HTTP 200 확인.
- 인증된 실제 서비스 상세 데이터로 파일을 여는 브라우저 검증은 별도 로그인 세션이 없어 수행하지 못했다.
