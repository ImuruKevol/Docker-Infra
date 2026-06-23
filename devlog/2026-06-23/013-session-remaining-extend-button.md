# 사이드바 세션 남은 시간 카드에 연장 버튼 추가

- 날짜: 2026-06-23
- 리뷰 ID: frimboczhlupqfdreydhasskgdwxphqv
- 원 요청: "세션 남은 시간 카드의 오른쪽에 아이콘 대신 연장을 뜻하는 아이콘을 추가해서 버튼을 누르면 연장할 수 있도록 해줘."

## 변경 파일

- `src/route/api-auth-session/controller.py`
- `src/app/component.nav.sidebar/view.ts`
- `src/app/component.nav.sidebar/view.pug`
- `tests/api/test_auth_setup.py`

## 상세

- `/api/auth/session`에 `POST` 동작을 추가해 현재 인증 토큰의 세션 만료 시간을 현재 세션 정책 기준으로 연장하도록 했다.
- 세션 연장 성공 시 WIZ 세션과 보조 인증 쿠키를 함께 갱신하도록 했다.
- 사이드바 세션 남은 시간 카드 오른쪽의 hourglass 아이콘을 `fa-arrow-rotate-right` 아이콘 버튼으로 교체했다.
- 버튼 클릭 중에는 spinner 상태를 표시하고, 성공 응답의 새 세션 남은 시간을 즉시 카드에 반영하도록 했다.

## 검증

- `/opt/conda/envs/docker-infra/bin/python -m py_compile src/route/api-auth-session/controller.py src/model/struct/auth.py src/app/page.system/api.py` 성공
- `git diff --check -- src/route/api-auth-session/controller.py src/app/component.nav.sidebar/view.ts src/app/component.nav.sidebar/view.pug tests/api/test_auth_setup.py` 성공
- `/opt/conda/envs/docker-infra/bin/python -m unittest tests.api.test_auth_setup.AuthSetupStaticContractTest tests.api.test_system_settings_dynamic_menu.SystemSettingsStaticContractTest` 성공
- `wiz_project_build(projectName="main", clean=false)` 성공
