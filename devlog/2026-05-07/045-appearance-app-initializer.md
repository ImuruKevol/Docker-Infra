# appearance 로딩을 auth 체크에서 분리하고 Angular 초기 1회 로드로 최적화

- 날짜: 2026-05-07
- ID: 045

## 사용자 요청

- "Browser title, favicon, logo는 /auth/check에서 가져오면 안돼."
- "화면이 로드될 때 한 번만 로드되도록 Angular의 자체 지원 기능을 사용하던지 해서 최적화해줘"

## 변경 파일

- `docs/docker-infra-runtime.md`
- `src/angular/app/app.module.ts`
- `src/angular/app/appearance.initializer.ts`
- `src/app/component.nav.sidebar/view.ts`
- `src/app/page.access/view.ts`
- `src/app/page.system/view.ts`
- `src/portal/season/libs/appearance.ts`
- `src/portal/season/libs/src/auth.ts`
- `src/portal/season/route/auth/controller.py`
- `src/route/api-system-appearance/app.json`
- `src/route/api-system-appearance/controller.py`
- `tests/api/test_system_settings_dynamic_menu.py`

## 작업 내용

- `Browser title`, `favicon`, `logo` 조회를 `/auth/check` 세션 동기화 응답에서 제거했다.
- 공개용 branding 전용 API `/api/system/appearance`를 추가해 일반 설정만 반환하도록 분리했다.
- Angular `APP_INITIALIZER`를 추가해 앱 부트 시 `/api/system/appearance`를 1회만 호출하고, 이후에는 localStorage/runtime cache를 재사용하도록 바꿨다.
- 공용 `AppearanceRuntime`를 추가해 title, favicon, logo 적용과 `docker-infra:appearance-changed` 이벤트 발행 로직을 한 곳으로 통합했다.
- sidebar, access, system 화면이 더 이상 `service.auth.appearance`나 `/auth/check`에 의존하지 않고 공용 runtime을 사용하도록 정리했다.
- `Auth`는 세션 확인만 담당하도록 단순화했고, `/auth/check` 실패 시에도 문자열 payload 때문에 추가 예외가 나지 않도록 방어 로직을 보강했다.
- 런타임 문서와 정적/라이브 테스트를 새 구조 기준으로 갱신했다.

## 검증

- `PYTHONPATH=. DOCKER_INFRA_TEST_PASSWORD='____' /opt/conda/envs/docker-infra/bin/python -m unittest tests.api.test_system_settings_dynamic_menu tests.api.test_wiz_structure_contract`: 통과
- `/opt/conda/envs/docker-infra/bin/python -m compileall src/angular src/app src/model src/route src/portal/season/libs src/portal/season/route/auth`: 통과
- `wiz_project_build(projectName="main", clean=false)`: 통과
- `systemctl restart wiz.docker-infra`: 완료
- live smoke:
  - `curl -X POST http://127.0.0.1:3001/auth/check -H 'content-type: application/json' -d '{}'`: `appearance` 없이 `status`, `session`만 응답 확인
  - `curl http://127.0.0.1:3001/api/system/appearance`: `appearance.browser_title`, `favicon_url`, `logo_url` 응답 확인
- `git diff --check`: 통과
