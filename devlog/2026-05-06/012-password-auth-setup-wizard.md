# Password-only 인증과 설치 마법사 구현

- **ID**: 012
- **날짜**: 2026-05-06
- **유형**: 인증/setup/API/UI

## 사용자 원 요청

사용자가 "P3-01, P3-02 작업을 진행해줘"라고 요청했다.

## 작업 요약

TODO P3-01의 password-only 인증을 구현했다. 사용자 ID 없이 password만 받는 login API, PBKDF2-SHA256 password hash 저장, DB에는 hash만 저장하는 session token, 실패 횟수 기반 rate limit, logout/session revoke를 추가했다. WIZ base controller에는 `docker_infra_session` cookie 이름과 `HttpOnly`, `SameSite=Lax`, `Secure` 정책 설정을 추가하고, DB가 설정된 환경에서는 setup 완료와 인증 session 없이는 보호 page/API에 접근하지 못하도록 했다.

TODO P3-02의 최초 설치 마법사를 구현했다. `/api/system/setup`에서 fresh DB setup status를 조회하고, setup 요청 시 관리자 password 설정, template root 생성, Docker/Swarm/proxy 감지 결과 저장, 기본 proxy 선택, local master node 자동 등록을 수행한다. local master 등록은 SSH port, username, password/key 입력 없이 `nodes.is_local_master=true` row로 생성한다. `/access` 화면은 setup 전에는 wizard를, setup 후에는 password-only login을 표시하도록 바꿨다.

## 변경 파일 목록

### Migration/model

- `src/model/docker_infra/migrations/002_auth_setup.sql`: `operator_auth`, `auth_sessions`, `auth_login_attempts` table과 index/updated_at trigger 추가
- `src/model/docker_infra/migrations/002_auth_setup.down.sql`: P3 auth/setup table rollback SQL 추가
- `src/model/docker_infra/auth.py`: password hash/verify, login rate limit, session create/current/logout, cleanup helper 추가
- `src/model/docker_infra/setup.py`: setup status, Docker/Swarm/proxy 감지, setup complete, local master 등록, cleanup helper 추가
- `src/controller/base.py`: session cookie 정책과 setup/auth access guard 추가

### API routes/source API

- `src/route/api-auth-login/`: `/api/auth/login` route 추가
- `src/route/api-auth-logout/`: `/api/auth/logout` route 추가
- `src/route/api-auth-session/`: `/api/auth/session` route 추가
- `src/route/api-system-setup/`: `/api/system/setup` route 추가
- `src/app/page.access/api.py`: access page용 setup status, setup, login, logout, session API 연결

### UI/docs/tests

- `src/app/page.access/view.pug`: setup wizard와 password-only login 화면 구성
- `src/app/page.access/view.ts`: setup status 로드, setup submit, login 처리 추가
- `src/app/component.nav.sidebar/view.pug`: logout button 추가
- `src/app/component.nav.sidebar/view.ts`: logout API 호출 추가
- `src/app/page.dashboard/api.py`: P3-01/P3-02 완료 상태 반영
- `docs/api/openapi.json`: auth/session/setup API와 response schema 추가, login placeholder 501 제거
- `tests/api/test_auth_setup.py`: auth/setup 정적 검증과 PostgreSQL integration 검증 추가
- `tests/api/test_migration_schema.py`: migration 002와 schema version 002 반영
- `tests/api/test_openapi_contract.py`: P3 auth/setup path/schema 계약 검증 추가
- `tests/api/test_playwright_setup.py`: setup wizard E2E selector 검증 추가
- `tests/fixtures/api_client.py`: password-only login fixture를 `/api/auth/login`으로 전환
- `tests/e2e/helpers/auth.ts`, `tests/e2e/specs/access.spec.ts`: setup 전/후 access 화면 흐름 반영
- `docs/docker-infra-runtime.md`: P3 auth/setup API, cookie 정책, access guard, cleanup 기준 문서화
- `README.md`: P3 구현 상태와 migration/setup 명령 반영

### 작업 기록

- `devlog.md`: 012 항목 추가
- `devlog/2026-05-06/012-password-auth-setup-wizard.md`: 상세 작업 기록 추가

## 검증

- `/opt/conda/envs/docker-infra/bin/python -m json.tool docs/api/openapi.json` 실행: 성공
- `/opt/conda/envs/docker-infra/bin/python -m py_compile src/model/docker_infra/auth.py src/model/docker_infra/setup.py src/model/docker_infra/migration.py src/controller/base.py src/app/page.access/api.py src/route/api-auth-login/controller.py src/route/api-auth-logout/controller.py src/route/api-auth-session/controller.py src/route/api-system-setup/controller.py tests/api/test_auth_setup.py tests/api/test_migration_schema.py tests/api/test_openapi_contract.py` 실행: 성공
- `/opt/conda/envs/docker-infra/bin/python -m unittest discover tests/api` 실행: no-DB 환경에서 38개 중 32개 통과, live API/Swagger와 DB integration 6개는 환경변수 미설정으로 skip
- `docker compose -f docker/compose/test.yaml --profile api up -d postgres`로 테스트 PostgreSQL 실행 후 `scripts/docker_infra_migrate.py up` 실행: `001`, `002` 적용 성공
- 동일 DB에서 `scripts/docker_infra_migrate.py status` 실행: `001`, `002` 적용 상태와 checksum 일치 확인
- 동일 DB 환경으로 `/opt/conda/envs/docker-infra/bin/python -m unittest tests.api.test_auth_setup.AuthSetupIntegrationTest` 실행: 2개 통과
- 동일 DB 환경으로 `/opt/conda/envs/docker-infra/bin/python -m unittest discover tests/api` 실행: 42개 중 38개 통과, live API/Swagger 4개는 `DOCKER_INFRA_BASE_URL` 미설정으로 skip
- 동일 DB에서 `scripts/docker_infra_migrate.py down --version 002` 실행: `002` rollback 성공
- `npx playwright test --list` 실행: Chromium 기준 2개 spec 파일, 5개 테스트 discovery 성공
- `/opt/conda/envs/docker-infra/bin/wiz project build --project main` 실행: 성공
- `git diff --check` 실행: 통과

## Cleanup

검증에 사용한 PostgreSQL 테스트 container, network, volume은 `docker compose -f docker/compose/test.yaml --profile api down -v`로 제거했다. 통합 테스트가 만든 setup settings, local master node, auth session, login attempt, password hash row는 `test_run_id` 기준 cleanup helper가 삭제했다. 검증 중 생성된 `.runtime`, `__pycache__`, 임시 OpenAPI 출력 파일도 삭제했다. 실제 운영 DB row, Swarm resource, proxy 실제 설정, DNS/Harbor/GitLab 리소스는 생성하지 않았다.
