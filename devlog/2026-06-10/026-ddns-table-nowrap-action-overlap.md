# DDNS 관리 서버 표 nowrap과 작업 컬럼 겹침 보정

## 사용자 요청

- 리뷰 ID: `qcpfhrvsszgacnarudpqctzlgkhcypki`
- 제목: UI 정리
- 원문 요청: "도메인 관리 화면 DDNS 관리 서버 - 상태, Dispatcher 요청, IP 컬럼에 줄바꿈 방지 처리 추가 - 등록 컬럼과 작업 컬럼이 겹쳐서 보이고 있음"

## 변경 파일

- `src/app/page.domains/view.pug`
  - DDNS 관리 서버 표의 최소 폭을 `1100px`로 조정했다.
  - 상태, Dispatcher 요청, IP 헤더와 셀에 `whitespace-nowrap`를 적용했다.
  - Dispatcher 요청/IP 값에는 `truncate`와 `title`을 적용해 줄바꿈 없이 표시하고 전체 값은 hover로 확인 가능하게 했다.
  - 등록 컬럼을 `w-24`, 작업 컬럼을 `w-36`으로 넓히고 작업 버튼 wrapper에 `flex-nowrap`/`whitespace-nowrap`를 적용했다.
- `tests/api/test_domain_management_ui.py`
  - DDNS 표 폭, nowrap 헤더, 등록/작업 컬럼 계약을 새 레이아웃 기준으로 갱신했다.
- `devlog.md`
- `devlog/2026-06-10/026-ddns-table-nowrap-action-overlap.md`

## 확인 결과

- 성공: `wiz_project_build(projectName="main", clean=false)`
- 성공: `/opt/conda/envs/docker-infra/bin/python -m unittest tests.api.test_domain_management_ui` -> `OK`
- 성공: `curl -k -I -H 'Cookie: season-wiz-project=main; season-wiz-devmode=true' https://infra-dev.nanoha.kr/domains` -> `200 OK`
- 성공: Playwright Chromium 1440x900 실제 브라우저에서 `/domains` 로그인 후 DDNS 관리 서버 표를 측정했다.
- 확인: 상태/Dispatcher 요청/IP 헤더와 셀의 computed `white-space`가 `nowrap`으로 확인됐다.
- 확인: 등록 셀과 작업 셀의 `overlap=false`로 확인됐다.
- 확인: DDNS API 호출/수정/삭제 버튼 3개가 모두 32x32로 렌더링되고 viewport 안에 표시됐다.

## 남은 리스크

- DDNS 서버 API 컬럼은 긴 URL을 계속 `break-all`로 처리한다. 이번 요청 범위가 아니어서 별도 변경하지 않았다.
- 실제 삭제/수정/강제 갱신 액션은 누르지 않고 화면 렌더링과 비파괴 측정만 수행했다.
- 작업 시작 전부터 프로젝트에 다수의 미커밋 변경이 있어 이번 요청 관련 파일만 수정했다.
