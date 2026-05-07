# 시스템 설정 화면과 동적 메뉴 구현

- **ID**: 013
- **날짜**: 2026-05-06
- **유형**: 시스템 설정/API/UI

## 사용자 원 요청

사용자가 작업을 이어서 진행해 달라고 요청했다.

## 작업 요약

TODO P3-03의 시스템 설정과 동적 메뉴를 구현했다. `/system` 화면에 browser title, favicon URL, logo URL 일반 설정과 Harbor/GitLab/Cloudflare 연동 설정을 추가했다. 연동 설정은 enabled 상태, 일반 field, secret field를 저장하며 secret은 기존 `system_settings` secret 저장 방식을 사용해 조회 시 masked value만 표시한다.

sidebar navigation은 `/api/system/settings`의 `integration.{name}.enabled` 값을 읽어 동적으로 메뉴를 필터링한다. 현재 Cloudflare disabled 상태에서는 도메인 메뉴를, Harbor disabled 상태에서는 이미지 메뉴를 숨긴다. GitLab enabled 값은 이후 GitLab build button visibility에 사용할 수 있도록 저장 구조와 UI를 갖췄다.

기존 settings API의 boolean 처리도 보강했다. 문자열 `"false"`가 Python truthy 값으로 처리되어 secret flag가 잘못 켜질 수 있는 문제를 막기 위해 명시적인 boolean parser를 추가했다.

## 변경 파일 목록

### Source app/API

- `src/app/page.system/api.py`: 일반 설정 load/save와 연동 설정 save API 추가
- `src/app/page.system/view.pug`: 일반 설정 입력, 연동 enabled toggle, secret 입력/masked 상태 표시 UI 추가
- `src/app/page.system/view.ts`: settings load, general save, integration save 처리 추가
- `src/app/component.nav.sidebar/view.ts`: integration enabled 값 기반 dynamic menu filtering 추가
- `src/route/api-system-settings/controller.py`: `is_secret` boolean parser 보강
- `src/app/page.dashboard/api.py`: P3-03 완료 상태 반영

### Docs/tests

- `tests/api/test_system_settings_dynamic_menu.py`: settings boolean parser, system UI selector, dynamic menu, secret masking 검증 추가
- `docs/docker-infra-runtime.md`: 시스템 설정 key, secret masking, dynamic menu 정책 문서화
- `README.md`: P3-03 구현 상태 반영

### 작업 기록

- `devlog.md`: 013 항목 추가
- `devlog/2026-05-06/013-system-settings-dynamic-menu.md`: 상세 작업 기록 추가

## 검증

- `/opt/conda/envs/docker-infra/bin/python -m py_compile src/app/page.system/api.py src/route/api-system-settings/controller.py tests/api/test_system_settings_dynamic_menu.py` 실행: 성공
- `/opt/conda/envs/docker-infra/bin/python -m unittest discover tests/api` 실행: no-DB 환경에서 41개 중 34개 통과, live API/Swagger와 DB integration 7개는 환경변수 미설정으로 skip
- `docker compose -f docker/compose/test.yaml --profile api up -d postgres`로 테스트 PostgreSQL 실행 후 `scripts/docker_infra_migrate.py up` 실행: `001`, `002` 적용 성공
- 동일 DB 환경으로 `/opt/conda/envs/docker-infra/bin/python -m unittest discover tests/api` 실행: 46개 중 42개 통과, live API/Swagger 4개는 `DOCKER_INFRA_BASE_URL` 미설정으로 skip
- `npx playwright test --list` 실행: Chromium 기준 2개 spec 파일, 5개 테스트 discovery 성공
- `/opt/conda/envs/docker-infra/bin/wiz project build --project main` 실행: 성공
- `git diff --check` 실행: 통과

## Cleanup

검증에 사용한 PostgreSQL 테스트 container, network, volume은 `docker compose -f docker/compose/test.yaml --profile api down -v`로 제거했다. 통합 테스트가 만든 integration settings와 secret row는 `test_run_id` 기준 cleanup helper가 삭제했다. 검증 중 생성된 `.runtime`, `__pycache__`, 임시 파일도 삭제했다. 실제 운영 DB row, Swarm resource, proxy 실제 설정, DNS/Harbor/GitLab 리소스는 생성하지 않았다.
