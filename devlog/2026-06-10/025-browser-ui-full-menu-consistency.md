# 실제 브라우저 메뉴 순회 기반 UI 액션 정렬 보정

## 사용자 요청

- 리뷰 ID: `qcpfhrvsszgacnarudpqctzlgkhcypki`
- 제목: UI 정리
- 원문 요청: "PW: [redacted] 모든 메뉴 및 화면들을 실제 브라우저로 상세하게 전수조사해서 적용해줘."
- 민감정보: 비밀번호 값은 devlog에 기록하지 않았다.

## 변경 파일

- `src/angular/app/app.component.scss`
  - `infra-shell` 하위 `h-8 w-8` 아이콘 버튼이 실제 브라우저에서 24px로 줄어드는 케이스를 막도록 32px 고정 규칙을 추가했다.
- `src/app/page.dashboard/view.pug`
  - 대시보드 카드 헤더의 단순 텍스트 링크를 32px 높이의 아이콘+텍스트 액션 버튼으로 통일했다.
- `src/app/page.domains/view.pug`
  - DDNS 관리 서버/등록 레코드 표의 최소 폭과 컬럼 폭을 1440px 화면 기준으로 줄여 액션 컬럼이 잘리지 않도록 했다.
  - DDNS 액션 버튼 간격을 줄이고, `Dispatcher 요청` 헤더 문구는 기존 정적 계약과 맞췄다.
- `tests/api/test_domain_management_ui.py`
  - DDNS 전용 도메인 화면의 새 표 폭/액션 간격 계약을 검증하도록 정적 테스트 기대값을 갱신했다.
- `devlog.md`
- `devlog/2026-06-10/025-browser-ui-full-menu-consistency.md`

## 확인 결과

- 성공: `wiz_project_build(projectName="main", clean=false)`
- 성공: `/opt/conda/envs/docker-infra/bin/python -m unittest tests.api.test_domain_management_ui tests.api.test_system_settings_dynamic_menu tests.api.test_playwright_setup` -> `OK (skipped=2)`
- 성공: `curl -k -I -H 'Cookie: season-wiz-project=main; season-wiz-devmode=true' https://infra-dev.nanoha.kr/dashboard` -> `200 OK`
- 성공: `curl -k -I -H 'Cookie: season-wiz-project=main; season-wiz-devmode=true' https://infra-dev.nanoha.kr/domains` -> `200 OK`
- 성공: `curl -k -I -H 'Cookie: season-wiz-project=main; season-wiz-devmode=true' https://infra-dev.nanoha.kr/system` -> `200 OK`
- 성공: Playwright Chromium 1440x900 실제 브라우저에서 `/access` 로그인 후 `/dashboard`, `/servers`, `/services`, `/services/create`, `/domains`, `/images`, `/templates`, `/macros`, `/operations`, `/system` H1 렌더링을 확인했다.
- 성공: 위 전체 메뉴 순회에서 `overflow=false`, `badIconCount=0`으로 확인했다.
- 성공: `/domains` focused 검증에서 DDNS API/수정/삭제 아이콘 액션이 각각 32x32로 렌더링되고 화면 overflow가 없음을 확인했다.
- 성공: 대표 모달 검증에서 dashboard node charts, domains DDNS add, servers add, macros add 모달의 닫기/취소/저장 버튼 크기와 footer 정렬이 공통 기준으로 렌더링됨을 확인했다.

## 남은 리스크

- 이미지 관리의 프로젝트 생성 모달은 현재 데이터/상태에서 버튼이 보이지 않아 열람 검증하지 못했다.
- 실제 저장/삭제/배포 같은 파괴적 또는 상태 변경 액션은 누르지 않고, 목록/상세 진입과 비파괴 모달 열람 중심으로 검증했다.
- 작업 시작 전부터 프로젝트에 다수의 미커밋 변경이 있어 이번 요청과 직접 관련된 UI 파일 및 정적 계약 테스트만 수정했다.
