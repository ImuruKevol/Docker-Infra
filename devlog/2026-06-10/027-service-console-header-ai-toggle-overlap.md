# 서비스 상세 콘솔 모달 헤더와 생성 화면 AI 버튼 겹침 보정

- 날짜: 2026-06-10
- ID: 027
- 리뷰 ID: tkepasiemvbovqtixtyuuigpollhdtyv

## 사용자 원본 요청

서비스 관리 상세에서 컨테이너별 웹 터미널, 로그 모달의 헤더 부분 색상이 글로벌 색상으로 적용되어 글자가 보이지 않고, 서비스 생성 화면 오른쪽 하단의 서비스 생성 버튼 위에 AI Agent 열기 버튼이 있어 UI 이슈가 발생하므로 실제 브라우저로 확인하고 수정 요청.

## 변경 파일

- `src/app/page.services/view.pug`
- `src/angular/app/app.component.pug`
- `src/angular/app/app.component.ts`
- `src/angular/app/app.component.scss`

## 변경 내용

- 컨테이너 웹 터미널/로그 모달에 전용 콘솔 모달 클래스와 헤더/상태 배지 클래스를 추가했다.
- 글로벌 모달 헤더 스타일보다 구체적인 예외 스타일을 추가해 콘솔 모달 헤더를 어두운 배경과 밝은 텍스트로 고정했다.
- `/services/create` 라우트에서만 AI Agent 토글 버튼을 하단 액션바 위로 올리는 클래스 바인딩과 스타일을 추가했다.

## 검증 결과

- `wiz_project_build(projectName=main, clean=false)` 성공.
- 실제 브라우저로 원격 DEV에서 재현 확인:
  - `/services/create`에서 AI Agent 토글과 `생성` 버튼이 겹치는 것을 확인했다.
  - 서비스 상세 컨테이너 터미널 모달에서 헤더가 흰 배경으로 적용되어 제목이 보이지 않는 것을 확인했다.
- 실제 브라우저로 로컬 WIZ 서버(`http://127.0.0.1:3001`)에서 수정 후 확인:
  - `/services/create` AI Agent 토글: `y=748~804`, 생성 버튼: `y=848~888`, `overlap=false`.
  - 터미널 모달 헤더 배경: `rgb(9, 9, 11)`, 제목 색상: `rgb(244, 244, 245)`.
  - 로그 모달 헤더 배경: `rgb(9, 9, 11)`, 제목 색상: `rgb(244, 244, 245)`.
  - 스크린샷: `/tmp/docker-infra-services-create-after.png`, `/tmp/docker-infra-terminal-after.png`, `/tmp/docker-infra-logs-after.png`.
