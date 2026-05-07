# 인증·설정 중복 호출 제거와 컨테이너 액션/Compose 오류 안내 보강

- 날짜: 2026-05-07
- ID: 032

## 사용자 요청

- 화면 새로고침 시 `/auth/check` 이후 `/api/auth/session`이 중복으로 호출되는 문제를 수정해달라는 요청이었다.
- `/api/system/settings`가 연속으로 두 번 호출되는 원인을 파악하고 수정해야 했다.
- 컨테이너별 액션은 현재 상태에 따라 활성화/비활성화되어야 했다.
- 서버 화면에서 Compose 파일 등록 시 `Compose validation failed.`만 보이지 말고 상세 검증 오류를 사용자에게 보여줘야 했다.

## 변경 파일

- `devlog.md`
- `devlog/2026-05-07/032-auth-settings-container-action-compose-errors.md`
- `src/app/layout.sidebar/view.ts`
- `src/app/component.nav.sidebar/view.ts`
- `src/app/page.servers/view.ts`
- `src/app/page.servers/view.pug`
- `src/app/page.services/view.ts`
- `src/app/page.services/view.pug`
- `tests/api/test_auth_setup.py`
- `tests/api/test_system_settings_dynamic_menu.py`

## 작업 내용

- `layout.sidebar`에서 별도로 호출하던 `/api/auth/session`을 제거하고, `service.init()`에서 이미 수행한 `/auth/check` 결과만 사용하도록 정리했다.
- `/api/system/settings` 중복 호출 원인은 모바일/데스크톱용 `wiz-component-nav-sidebar` 인스턴스가 동시에 생성되면서 각각 fetch를 수행하던 구조였다. 사이드바 모듈 레벨 캐시와 공유 promise를 추가해 한 번만 읽도록 바꿨다.
- 서버 화면의 컨테이너/서비스 액션 버튼은 현재 상태에 따라 활성화 여부를 계산하도록 변경했다. 실행 불가 상태에서는 버튼을 비활성화하고 tooltip 문구도 상태에 맞게 분리했다.
- 서버 화면의 Compose 등록 실패 메시지는 `details` 배열을 풀어서 경로별 오류를 함께 보여주도록 바꿨다.
- 서비스 생성 화면도 같은 형식의 Compose 검증 상세를 그대로 보여주도록 오류 포맷을 맞췄다.

## 검증

- `/opt/conda/envs/docker-infra/bin/python -m py_compile tests/api/test_auth_setup.py tests/api/test_system_settings_dynamic_menu.py`: 통과
- `/opt/conda/envs/docker-infra/bin/python -m unittest tests.api.test_auth_setup.AuthSetupStaticContractTest tests.api.test_system_settings_dynamic_menu.SystemSettingsStaticContractTest tests.api.test_wiz_structure_contract tests.api.test_node_reporter tests.api.test_playwright_setup tests.api.test_ssh_managed`: 통과
- `wiz_project_build(projectName="main", clean=false)`: 통과
- `git -C /root/docker-infra/project/main diff --check`: 통과
- 참고: `tests/api/test_auth_setup.py` 전체 live 실행 시 환경 상태에 따라 기존과 무관한 2건(`empty_password_login`, `protected_dashboard_redirects_without_session`)이 실패했다. 이번 변경 검증은 정적 계약과 빌드 기준으로 확인했다.
