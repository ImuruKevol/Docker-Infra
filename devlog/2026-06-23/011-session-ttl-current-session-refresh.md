# 세션 지속시간 변경 시 현재 세션 만료 시간 갱신

- 날짜: 2026-06-23
- 리뷰 ID: frimboczhlupqfdreydhasskgdwxphqv
- 원 요청: "유지 시간을 240시간으로 시스템 설정에 설정했는데 화면에 표시되는건 6시간 58분 남음이라 표시되고 있어. 이거 맞아?"

## 변경 파일

- `src/model/struct/auth.py`
- `src/app/page.system/api.py`
- `src/app/page.system/view.ts`
- `src/app/component.nav.sidebar/view.ts`
- `tests/api/test_auth_setup.py`
- `tests/api/test_system_settings_dynamic_menu.py`

## 상세

- 세션 지속시간 설정 저장 시 현재 브라우저의 활성 세션 `expires_at`을 새 TTL 기준으로 갱신하도록 했다.
- 보조 인증 쿠키도 갱신된 만료 시간 기준으로 다시 설정해 브라우저 쿠키 만료와 DB 세션 만료를 맞췄다.
- 세션 레코드 metadata에 적용된 TTL을 기록하고, 기존 세션처럼 TTL metadata가 없는 활성 세션은 현재 정책 기준으로 한 번 보정하도록 했다.
- 시스템 설정 저장 성공 후 사이드바에 세션 갱신 이벤트를 보내 남은 시간 표시가 즉시 새 값으로 바뀌게 했다.

## 검증

- `/opt/conda/envs/docker-infra/bin/python -m py_compile src/model/struct/auth.py src/app/page.system/api.py` 성공
- `git diff --check -- src/model/struct/auth.py src/app/page.system/api.py src/app/page.system/view.ts src/app/component.nav.sidebar/view.ts tests/api/test_auth_setup.py tests/api/test_system_settings_dynamic_menu.py` 성공
- `/opt/conda/envs/docker-infra/bin/python -m unittest tests.api.test_auth_setup.AuthSetupStaticContractTest tests.api.test_system_settings_dynamic_menu.SystemSettingsStaticContractTest` 성공
- `wiz_project_build(projectName="main", clean=false)` 성공
