# 세션 지속시간 표시 위치를 로그인 화면에서 사이드바로 이동

- 날짜: 2026-06-23
- 리뷰 ID: frimboczhlupqfdreydhasskgdwxphqv
- 원 요청: "아니 로그인 화면에 표시하는게 무슨 의미가 있냐 빡대가리야; 로그인 화면에서는 지워. 그리고 로그인 후에 왼쪽 사이드바에서 메뉴 부분 위에 표시하도록 해줘."

## 변경 파일

- `src/app/page.access/view.ts`
- `src/app/page.access/view.pug`
- `src/app/component.nav.sidebar/view.ts`
- `src/app/component.nav.sidebar/view.pug`
- `tests/api/test_auth_setup.py`

## 상세

- 로그인 화면의 세션 지속시간 표시 UI와 관련 프론트 상태/포맷 메서드를 제거했다.
- 로그인 후 표시되는 왼쪽 사이드바에서 메뉴 목록 바로 위에 세션 지속시간 카드를 추가했다.
- 사이드바가 `/api/auth/session`의 `session_policy`를 읽어 현재 설정된 세션 지속시간을 표시하도록 했다.
- 정적 계약 테스트를 로그인 화면 미표시와 사이드바 표시 기준으로 갱신했다.

## 검증

- `/opt/conda/envs/docker-infra/bin/python -m unittest tests.api.test_auth_setup.AuthSetupStaticContractTest tests.api.test_system_settings_dynamic_menu.SystemSettingsStaticContractTest` 성공
- `/opt/conda/envs/docker-infra/bin/python -m py_compile ...` 성공
- `wiz_project_build(projectName="main", clean=false)` 성공
- Playwright Chromium에 `season-wiz-project=main`, `season-wiz-devmode=true` 쿠키를 넣어 `/access`에서 세션 지속시간 문구가 보이지 않음을 확인
