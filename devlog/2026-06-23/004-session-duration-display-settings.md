# 로그인 세션 지속시간 표시와 설정 저장 추가

- 날짜: 2026-06-23
- 리뷰 ID: frimboczhlupqfdreydhasskgdwxphqv
- 원 요청: "세션 지속시간이 몇으로 되어있는지는 모르겠는데, 퇴근하고 다음날 새로고침하면 세션이 풀려있어. 세션 지속시간이 설정되어있다면 화면에 표시하고, 시스템 설정에 지속시간을 설정할 수 있도록 해줘."

## 변경 파일

- `src/model/struct/auth.py`
- `src/controller/user.py`
- `src/app/page.access/api.py`
- `src/app/page.access/view.ts`
- `src/app/page.access/view.pug`
- `src/app/page.system/api.py`
- `src/app/page.system/view.ts`
- `src/app/page.system/view.pug`
- `src/route/api-auth-login/controller.py`
- `src/route/api-auth-session/controller.py`
- `src/route/api-auth-logout/controller.py`
- `src/route/api-system-setup/controller.py`
- `tests/api/test_auth_setup.py`
- `tests/api/test_system_settings_dynamic_menu.py`

## 상세

- 인증 세션 지속시간을 `system_settings`의 `auth.session_ttl_hours` 값으로 읽고 저장하도록 추가했다.
- 기본값은 기존 동작과 같은 12시간이며, 시스템 설정 General 탭에서 1~720시간 범위로 조정한다.
- `/access` 로그인 화면에 현재 세션 지속시간을 표시한다.
- Flask 세션 쿠키 만료 이후에도 설정된 지속시간까지 DB 세션 토큰을 확인할 수 있도록 보조 HttpOnly 쿠키를 발급하고, 보호 페이지 진입 시 기존 WIZ 세션을 복구한다.

## 검증

- `/opt/conda/envs/docker-infra/bin/python -m py_compile ...` 성공
- `/opt/conda/envs/docker-infra/bin/python -m unittest tests.api.test_auth_setup.AuthSetupStaticContractTest tests.api.test_system_settings_dynamic_menu.SystemSettingsStaticContractTest` 성공
- `wiz_project_build(projectName="main", clean=false)` 성공
- `curl`에 `season-wiz-project=main`, `season-wiz-devmode=true` 쿠키를 넣어 `/api/auth/session`의 `session_policy` 응답 확인
- Playwright Chromium에 동일 쿠키를 넣어 `/access`에서 "세션 지속시간 12시간" 표시 확인
