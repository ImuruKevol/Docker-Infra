# 관리 화면 헤더/저장 버튼/모달 표시 방식 공통화

## 사용자 요청

- 리뷰 ID: `qcpfhrvsszgacnarudpqctzlgkhcypki`
- 제목: UI 정리
- 원문 요청: "작업 시작"
- 리뷰어 요청: "각 메뉴 화면별 목록 화면, 상세 화면, 모달들을 전부 전수조사해서 저장 버튼의 위치, 뒤로가기 버튼의 위치, 헤더의 표시 방식, 모달의 헤더/푸터 표시 방식 등 당연히 통일이 되어야 하는 것들에 대해 통일하는 작업을 진행해줘. 현재는 전부 제각각이라 통일성있는 디자인 설정이 필요해. 알아서 판단 하에 글로벌 스타일로 지정해야하는 부분이 있다면 글로벌 스타일로 만들어서 지정하는 등 작업도 진행해줘."

## 변경 파일

- `src/angular/app/app.component.scss`
  - `infra-shell` 하위 sticky 헤더의 내부 정렬을 전역 규칙으로 고정했다.
  - 상세 화면의 `fa-arrow-left` 뒤로가기/목록 버튼 폭과 정렬을 공통화했다.
  - 직접 구현한 fixed 모달 패널의 radius, shadow, header/footer 배경과 footer 버튼 최소 크기를 공통화했다.
- `src/app/page.system/view.pug`
  - General/관리자 비밀번호/자동 백업 저장 버튼을 우측 액션 영역으로 정렬했다.
  - General 저장 버튼을 카드 하단 액션 영역처럼 보이도록 구분선을 추가했다.
- `src/portal/season/app/modal/view.pug`
  - 공통 확인 모달을 header/body/footer 구조의 `dialog` 패턴으로 재작성했다.
  - dark mode, 상태 아이콘, footer 버튼 정렬을 관리 화면 모달과 맞췄다.
- `src/portal/season/app/modal/view.ts`
  - 상태별 아이콘 wrapper와 아이콘 클래스를 분리했다.
  - 확인 버튼 높이, 최소 폭, 색상 클래스를 관리 화면 버튼 체계에 맞췄다.
- `devlog.md`
- `devlog/2026-06-10/022-ui-consistency-global-modal-actions.md`

## 확인 결과

- 성공: `wiz_project_build(projectName="main", clean=false)`
- 성공: `curl -k -I -H 'Cookie: season-wiz-project=main; season-wiz-devmode=true' https://infra-dev.nanoha.kr/dashboard` -> `200 OK`
- 성공: `curl -k -I -H 'Cookie: season-wiz-project=main; season-wiz-devmode=true' https://infra-dev.nanoha.kr/system` -> `200 OK`
- 성공: `curl -I -H 'Cookie: season-wiz-project=main; season-wiz-devmode=true' http://127.0.0.1:3001/dashboard` -> `200 OK`
- 성공: `/opt/conda/envs/docker-infra/bin/python -m unittest tests.api.test_system_settings_dynamic_menu tests.api.test_playwright_setup` -> `OK (skipped=2)`

## 남은 리스크

- 인증 세션이 없는 환경이라 실제 로그인 후 모든 메뉴를 브라우저로 클릭 순회하는 검증은 수행하지 못했다.
- 기존 작업 트리에 다수의 미커밋 변경이 있어 이번 작업은 UI 공통 스타일과 시스템/공통 모달 파일로 범위를 제한했다.
