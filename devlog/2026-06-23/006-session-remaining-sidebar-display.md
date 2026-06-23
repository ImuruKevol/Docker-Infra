# 사이드바 세션 표시를 설정값에서 남은 시간으로 변경

- 날짜: 2026-06-23
- 리뷰 ID: frimboczhlupqfdreydhasskgdwxphqv
- 원 요청: "현재 브라우저에서 세션이 얼마나 남았는지 표시를 해야지 왜 설정이 몇시간이라는걸 표시를 하니?"

## 변경 파일

- `src/model/struct/auth.py`
- `src/app/component.nav.sidebar/view.ts`
- `src/app/component.nav.sidebar/view.pug`
- `tests/api/test_auth_setup.py`

## 상세

- 인증 세션 응답에 `remaining_seconds`, `remaining_label`을 추가해 현재 세션 만료까지 남은 시간을 내려주도록 했다.
- 사이드바 표시는 설정된 지속시간이 아니라 현재 브라우저 세션의 남은 시간 기준으로 변경했다.
- 사이드바는 `/api/auth/session` 응답의 `session.remaining_seconds`를 기준으로 30초마다 남은 시간을 갱신한다.
- 표시 문구를 `세션 남은 시간`으로 변경했다.

## 검증

- `/opt/conda/envs/docker-infra/bin/python -m py_compile ...` 성공
- `/opt/conda/envs/docker-infra/bin/python -m unittest tests.api.test_auth_setup.AuthSetupStaticContractTest tests.api.test_system_settings_dynamic_menu.SystemSettingsStaticContractTest` 성공
- `wiz_project_build(projectName="main", clean=false)` 성공
- Playwright Chromium에 `season-wiz-project=main`, `season-wiz-devmode=true` 쿠키를 넣어 `/access`에 세션 시간 문구가 보이지 않음을 확인
