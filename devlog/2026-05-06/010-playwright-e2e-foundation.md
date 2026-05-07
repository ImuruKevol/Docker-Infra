# Playwright E2E 테스트 기반 추가

- **ID**: 010
- **날짜**: 2026-05-06
- **유형**: E2E 테스트 하네스

## 사용자 원 요청

사용자가 작업을 이어서 진행해 달라고 요청했다.

## 작업 요약

TODO P1-03의 Playwright 테스트 기반을 추가했다. `@playwright/test`를 프로젝트 dev dependency로 추가하고, `playwright.config.ts`에서 앱 URL, output root, trace/screenshot/video 저장 정책, optional webServer command를 정의했다.

인증 구현은 P3 단계 예정이므로 E2E 테스트는 `DOCKER_INFRA_BASE_URL`이 없으면 skip되며, password-only 인증이 아직 501 placeholder이면 정상 password flow 테스트도 구현 대기 상태로 skip할 수 있게 구성했다. 접근 화면에는 안정적인 E2E selector를 위해 password input과 submit button에 `data-testid`와 `aria-label`을 추가했다.

공통 helper는 environment, auth, cleanup으로 나누었고, UI 테스트가 만든 리소스 marker와 cleanup registry를 `.runtime/e2e` 아래에서 관리하도록 했다.

## 변경 파일 목록

### Playwright/package

- `package.json`: `@playwright/test` dev dependency와 `e2e`, `e2e:list`, `e2e:install` script 추가
- `playwright.config.ts`: Chromium project, base URL/env, trace/screenshot/video artifact 설정 추가

### E2E tests

- `tests/e2e/README.md`: 환경변수, 명령, artifact 위치, cleanup 원칙 문서화
- `tests/e2e/helpers/env.ts`: E2E 환경변수와 skip helper 추가
- `tests/e2e/helpers/auth.ts`: access page/login helper 추가
- `tests/e2e/helpers/cleanup.ts`: UI 테스트 cleanup registry와 marker helper 추가
- `tests/e2e/specs/access.spec.ts`: password-only access 화면, 빈 password validation, password submit flow 테스트 추가
- `tests/e2e/specs/shell.spec.ts`: dashboard shell/navigation, UI cleanup marker 테스트 추가

### API/static tests

- `tests/api/test_playwright_setup.py`: Playwright package/script/config/spec/selectors 정적 검증 추가

### Source app/docs

- `src/app/page.access/view.pug`: E2E용 `data-testid`, `aria-label`, submit button type 추가
- `src/app/page.dashboard/api.py`: P1-03 완료 상태를 반영하도록 checklist 갱신
- `docs/docker-infra-runtime.md`: Playwright E2E 환경변수와 실행 명령 문서화

### 작업 기록

- `devlog.md`: 010 항목 추가
- `devlog/2026-05-06/010-playwright-e2e-foundation.md`: 상세 작업 기록 추가

## 검증

- `/opt/conda/envs/docker-infra/bin/python -m unittest discover tests/api` 실행: 29개 중 25개 통과, live API/Swagger 4개는 `DOCKER_INFRA_BASE_URL` 미설정으로 skip
- `/opt/conda/envs/docker-infra/bin/python -m py_compile tests/api/test_playwright_setup.py src/app/page.dashboard/api.py` 실행: 성공
- `npx playwright test --list` 실행: Chromium 기준 2개 spec 파일, 5개 테스트 discovery 성공
- `/opt/conda/envs/docker-infra/bin/wiz project build --project main` 실행: 성공
- `git diff --check` 실행: 통과
- 검증 중 생성된 `.runtime`과 `__pycache__` 삭제 완료

## Cleanup

이번 작업은 실제 DB row, Docker container, Docker volume, Swarm resource, proxy 실제 설정, DNS/Harbor/GitLab 리소스를 생성하지 않았다. Playwright discovery가 만든 `.runtime/e2e` report와 Python bytecode cache는 삭제했다.
