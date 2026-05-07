# Docker Infra 개발/테스트 실행 환경

- 기준일: 2026-05-07
- 범위: P0-03 개발/테스트 compose, 테스트 리소스 격리 정책, P6-01 Compose 검증 정책

## Compose 파일

| 용도 | 파일 | 기본 profile | 설명 |
|---|---|---|---|
| 개발 DB | `docker/compose/development.yaml` | 없음 | 로컬 개발용 PostgreSQL 16을 named volume으로 유지 |
| API 테스트 | `docker/compose/test.yaml` | `api` | 테스트용 PostgreSQL 16을 tmpfs로 실행 |
| Swarm 통합 테스트 | `docker/compose/test.yaml` | `swarm` | Docker socket을 사용하는 통합 테스트용 docker CLI |
| Proxy sandbox | `docker/compose/test.yaml` | `proxy` | nginx/apache2 설정 디렉토리 sandbox 검증 |

권장 실행 명령:

```bash
docker compose -f docker/compose/development.yaml up -d postgres
docker compose -f docker/compose/test.yaml --profile api up -d postgres
docker compose -f docker/compose/test.yaml --profile swarm run --rm docker-cli
docker compose -f docker/compose/test.yaml --profile proxy run --rm proxy-sandbox
```

## Runtime Root 정책

운영 기본 경로와 테스트 경로를 섞지 않는다.

| 용도 | 개발 경로 | 테스트 경로 |
|---|---|---|
| Template root | `.runtime/dev/templates` | `.runtime/test/templates` |
| Artifact root | `.runtime/dev/artifacts` | `.runtime/test/artifacts` |
| Log root | `.runtime/dev/logs` | `.runtime/test/logs` |
| nginx sandbox | `docker/sandbox/nginx/conf.d` | `docker/sandbox/nginx/conf.d` |
| apache2 sandbox | `docker/sandbox/apache2/sites-enabled` | `docker/sandbox/apache2/sites-enabled` |

`.runtime/`은 생성 산출물 전용이며 git에 포함하지 않는다.

## DB Reset 정책

P2 migration 전까지 테스트 DB는 disposable PostgreSQL 컨테이너로 취급한다.

1. `docker compose -f docker/compose/test.yaml --profile api down -v`로 테스트 DB를 제거한다.
2. `docker compose -f docker/compose/test.yaml --profile api up -d postgres`로 빈 PostgreSQL 16과 `docker_infra_test` schema를 다시 만든다.
3. P2 migration 이후에는 schema migration과 `test_run_id`/namespace 기반 stale row cleanup을 추가한다.

## Migration 명령

P2부터 PostgreSQL migration은 `scripts/docker_infra_migrate.py`로 실행한다.

필수 런타임 설정:

```bash
# /root/docker-infra/config.env
DOCKER_INFRA_DATABASE_URL=postgresql://docker_infra_test:<redacted>@127.0.0.1:15432/docker_infra_test
DOCKER_INFRA_DB_SCHEMA=docker_infra_test
DOCKER_INFRA_SECRET_KEY=<redacted>
```

WIZ backend는 `project/main/config/docker_infra.py`를 통해 workspace root의 `config.env`를 직접 읽는다. `wiz.docker-infra` systemd service는 `/etc/systemd/system/wiz.docker-infra.service`의 `EnvironmentFile=-/root/docker-infra/config.env`로 같은 파일을 주입한다.

명령:

```bash
/opt/conda/envs/docker-infra/bin/python scripts/docker_infra_migrate.py status
/opt/conda/envs/docker-infra/bin/python scripts/docker_infra_migrate.py up
/opt/conda/envs/docker-infra/bin/python scripts/docker_infra_migrate.py down --version 001
```

Rollback 정책:

- down migration은 명시된 version 또는 가장 최근에 적용된 migration 1개만 되돌린다.
- 공유 개발 DB에서는 down을 실행하지 않고 새 migration으로 forward-fix한다.
- disposable 테스트 DB에서는 `docker compose ... down -v`로 DB를 제거하는 방식을 우선 사용한다.
- down SQL은 destructive하므로 실행 전 대상 DB가 테스트/개발 DB인지 확인한다.

## 파일 Cleanup

테스트가 만든 파일은 `.runtime/test/` 아래에만 생성한다. 로컬 파일 cleanup은 다음 명령을 사용한다.

```bash
/opt/conda/envs/docker-infra/bin/python tests/cleanup/reset_test_environment.py
```

이 helper는 project-local `.runtime/test` 하위만 삭제한다. 운영 기본 경로인 `/opt/templates`, `/var/log`, proxy 실제 설정 경로는 삭제 대상이 아니다.

## API 테스트 하네스

공통 API 테스트 코드는 `tests/fixtures/`와 `tests/cleanup/` 아래에 둔다.

| 파일 | 역할 |
|---|---|
| `tests/fixtures/api_client.py` | `DOCKER_INFRA_BASE_URL` 기반 HTTP client와 password-only login fixture |
| `tests/fixtures/openapi_response.py` | OpenAPI response schema 조회와 payload 검증 |
| `tests/fixtures/test_ids.py` | `test_run_id`, namespace, stack/domain/image tag naming helper |
| `tests/cleanup/cleanup_registry.py` | 테스트 cleanup finalizer와 retry/report |
| `tests/cleanup/stale_cleanup.py` | `.runtime/test` marker 기반 stale resource cleanup CLI |

Live API 테스트 환경변수:

```bash
export DOCKER_INFRA_BASE_URL=http://127.0.0.1:3001
export DOCKER_INFRA_TEST_PASSWORD='<redacted>'
export DOCKER_INFRA_TEST_RUN_ID="$(uuidgen)"
```

API 동작 테스트는 실행 중인 WIZ 서버의 HTTP 응답만 검증한다. `src/model/struct`를 직접 import하거나 fake executor를 주입하는 함수 단위 테스트는 WIZ runtime의 `wiz` 객체 주입, controller filter, route binding을 우회하므로 완료 검증으로 사용하지 않는다.

stale 테스트 리소스 cleanup:

```bash
/opt/conda/envs/docker-infra/bin/python tests/cleanup/stale_cleanup.py --older-than-hours 24
```

## Playwright E2E

Playwright 설정은 `playwright.config.ts`에 둔다. 기본 artifact root는 `.runtime/e2e`이며 실패 시 trace, screenshot, video를 남긴다.

| 환경변수 | 설명 |
|---|---|
| `DOCKER_INFRA_BASE_URL` | 실행 중인 Docker Infra 앱 URL |
| `DOCKER_INFRA_TEST_PASSWORD` | password-only login 테스트 비밀번호 |
| `DOCKER_INFRA_TEST_RUN_ID` | UI 테스트 리소스 marker에 기록할 test run id |
| `DOCKER_INFRA_E2E_OUTPUT_ROOT` | 기본값 `.runtime/e2e` |
| `DOCKER_INFRA_E2E_START_CMD` | Playwright가 앱을 직접 시작해야 할 때 사용할 명령 |

권장 명령:

```bash
npm run e2e:list
DOCKER_INFRA_BASE_URL=http://127.0.0.1:3001 npm run e2e
```

## Password-only 인증과 설치 마법사

P3부터 최초 설치와 인증 API는 PostgreSQL migration 적용 후 사용한다.

| API | 용도 |
|---|---|
| `GET /api/system/setup` | 설치 완료 여부, local master, Docker/Swarm/proxy 감지 상태 조회 |
| `POST /api/system/setup` | 관리자 비밀번호 설정, template root 생성, 기본 proxy 저장, local master row 등록 |
| `POST /api/auth/login` | ID 없이 password만 제출하는 단일 운영자 로그인 |
| `GET /api/auth/session` | 현재 session 상태 조회 |
| `POST /api/auth/logout` | 현재 session revoke와 cookie session clear |

세션 cookie는 `docker_infra_session` 이름을 사용하고 `HttpOnly`, `SameSite=Lax`, `Secure` 정책 값을 WIZ request lifecycle(`config/boot.py`의 `bootstrap`, `before_request`, `after_request`)에서 설정한다. 로컬 HTTP 개발에서는 `DOCKER_INFRA_SESSION_COOKIE_SECURE=true`를 지정할 때만 Secure flag를 강제한다.

설치 전에는 `/access`, `/api/system/setup`, `/api/auth/*`, `/api/system/health`, Swagger/OpenAPI 경로만 열어 둔다. 보호 페이지와 API는 `user` controller에서 인증을 확인하고, 미인증 사용자는 `/access` 페이지에서 설치/로그인 흐름으로 처리한다.

설치 API는 local master를 `nodes.is_local_master=true`로 등록하며 SSH port, username, password/key 입력을 요구하지 않는다. 테스트가 만든 setup row/session/node는 `test_run_id` 기준으로 cleanup한다.

## 시스템 설정과 적용

`/system` 화면은 일반 설정과 Harbor/GitLab 연동 설정을 관리한다.

| 설정 영역 | 저장 위치 | 설명 |
|---|---|---|
| `general.browser_title` | `system_settings` | 브라우저 title 기본값 |
| `general.favicon_url` | `system_settings` | favicon URL |
| `general.logo_url` | `system_settings` | sidebar/logo image URL |
| Harbor | `integration_harbor` | URL, 계정, password, enabled |
| GitLab | `integration_gitlab` | URL, token, enabled |
| Cloudflare Zone | `cloudflare_zones` | domain별 Zone ID, API Token, enabled, usable_for_service |
| Cloudflare Record Cache | `cloudflare_dns_records` | zone별 DNS record cache와 마지막 동기화 값 |

일반 설정은 Angular `APP_INITIALIZER`가 앱 부트 시 `/api/system/appearance`를 1회 호출해 localStorage/runtime cache에 반영한다. 이후 로그인 화면과 운영 화면은 이 cache와 `docker-infra:appearance-changed` 이벤트를 사용해 title, favicon, logo를 갱신한다. favicon/logo 업로드 파일은 WIZ workspace `data/system-assets/` 아래에 저장하고 `/api/system/assets/*`로 제공한다.

`/api/system/settings`는 generic key-value/secret 저장 API로 유지하며 secret 조회 응답은 계속 masking한다. 반면 `/system` page API는 운영자 화면 편집을 위해 Harbor/GitLab secret의 현재 값을 복호화해 반환할 수 있다.

sidebar menu는 더 이상 Harbor/Cloudflare enabled 상태에 따라 메뉴를 숨기지 않는다. Harbor disabled여도 이미지 화면은 로컬 이미지 중심으로 유지하고, Cloudflare zone이 없거나 token이 없어도 도메인 화면은 수동/캐시 모드로 계속 동작한다.

## Job Queue와 로그

P4-01부터 Job/Step/Log API는 기존 `jobs`, `job_steps`, `job_logs` table을 사용한다.

| API | 용도 |
|---|---|
| `GET /api/jobs` | job 목록 조회 |
| `POST /api/jobs` | job 생성과 step 초기화 |
| `GET /api/jobs/{job_id}` | step과 log를 포함한 job 상세 조회 |
| `POST /api/jobs/{job_id}/status` | job 상태 전이 |
| `POST /api/jobs/{job_id}/steps/{step_ref}/status` | step 상태 전이 |
| `POST /api/jobs/{job_id}/logs` | `stdout`, `stderr`, `system` stream log append |
| `POST /api/jobs/{job_id}/cancel` | pending/running job cancel |
| `POST /api/jobs/{job_id}/retry` | failed job을 새 job으로 재시도 |

상태 전이는 명시적으로 제한한다. Job은 `pending -> running/canceled`, `running -> succeeded/failed/canceled`만 허용하고 terminal 상태에서는 직접 재전이하지 않는다. Step도 `pending -> running/skipped/canceled`, `running -> succeeded/failed/canceled`만 허용한다.

Retry는 기존 failed job row를 재사용하지 않고 새 job을 만든다. 새 job metadata에는 `retry_of`와 `retry_attempt`를 기록하며, 이전 job log와 retry job log가 별도 `job_id`로 구분된다. 테스트가 만든 job/step/log row는 `test_run_id` 기준으로 cleanup한다.

## Secret masking과 로그 보존

P4-02부터 Job log는 DB 저장 전에 secret masking을 적용한다.

| 대상 | 처리 |
|---|---|
| System settings secret | `system_settings`의 암호화된 secret 값을 registry로 읽어 정확히 일치하는 값을 `********`로 치환 |
| Runtime secret | log append body의 `secret_values` 또는 metadata의 `secret_values`로 전달된 값을 저장 전에 치환 |
| 명령 인자 context | `password=`, `token=`, `private_key=` 같은 민감 key assignment의 값만 masking |
| Private key block | PEM private key block 전체를 masking |

로그 API:

| API | 용도 |
|---|---|
| `POST /api/jobs/{job_id}/logs/search` | masking된 저장 로그를 query/stream/limit 조건으로 검색 |
| `GET /api/jobs/{job_id}/logs/download` | job log를 plain text download payload로 반환 |

검색 query에 secret 원문이 들어와도 query 자체를 먼저 masking한 뒤 저장 로그를 검색한다. 다운로드 응답은 DB에 저장된 masking message만 조합하므로 password/token/private key 원문을 다시 복원하지 않는다.

## Local Executor

P5-01부터 Docker Infra 실행 host의 local command는 `src/model/struct/local_executor.py` abstraction을 통해 실행한다.

| Adapter | 명령 예 | 기본 정책 |
|---|---|---|
| `docker.version` | `docker version --format '{{json .}}'` | safe |
| `docker.info` | `docker info --format '{{json .}}'` | safe |
| `swarm.info` | `docker info --format '{{json .Swarm}}'` | safe |
| `swarm.nodes` | `docker node ls --format '{{json .}}'` | safe |
| `proxy.nginx.configtest` | `nginx -t` | safe |
| `proxy.apachectl.configtest` | `apachectl configtest` | safe |
| `swarm.init`, `swarm.network.ensure`, `docker.container.start`, `docker.container.stop`, `docker.container.restart`, proxy reload | Docker/Proxy 상태 변경 | `config.env`의 `DOCKER_INFRA_LOCAL_EXECUTOR_ALLOWLIST` 필요 |

Check API:

| API | 용도 |
|---|---|
| `GET /api/system/local-command/check?target=docker.version` | local command check 실행 |
| `POST /api/system/local-command/check` | target, timeout, params, optional job log 연결 값을 body로 전달 |

실행 결과는 `status`, `exit_code`, `stdout`, `stderr`, `duration_ms`, `timed_out`를 포함한다. `job_id`가 전달되면 stdout/stderr/system summary를 Job log에 append할 수 있으며, 기존 Job log masking 경로를 그대로 사용한다. 실패 명령도 예외로 숨기지 않고 `status=error`, `exit_code`, `stderr`를 응답해 이후 worker/debug 화면에서 같은 형태로 다룰 수 있게 한다.

## Local Master와 Slave Join

P5-02/P5-03부터 서버 관리는 `src/model/struct/nodes.py` 서비스가 담당한다.

Local master ensure:

| API | 용도 |
|---|---|
| `POST /api/system/local-master/ensure` | local Docker daemon이 Swarm manager인지 확인하고 필요 시 init 실행 |
| `GET /api/system/local-master/ensure` | 기본 옵션으로 local master 상태 보장 |

동작:

- `docker.info`로 Swarm 상태를 먼저 읽는다.
- 이미 manager이면 `swarm.init`을 재실행하지 않는다.
- `docker_infra_overlay` network를 inspect하고 없을 때만 생성한다.
- `nodes.is_local_master=true` row는 하나만 유지한다.
- `swarm.init`과 overlay network 생성은 destructive adapter라 `DOCKER_INFRA_LOCAL_EXECUTOR_ALLOWLIST`가 필요하다.

Slave node API:

| API | 용도 |
|---|---|
| `GET /api/nodes` | node 목록 조회 |
| `POST /api/nodes` | slave node 등록과 SSH credential/fingerprint 저장 |
| `GET /api/nodes/{node_id}` | node와 credential 보유 여부 조회 |
| `POST /api/nodes/{node_id}/check` | SSH 접속과 remote Docker daemon 상태 확인 |
| `POST /api/nodes/{node_id}/join` | Swarm join job 생성과 단계별 실행 |

Credential 정책:

- `node_credentials.password_enc`, `private_key_enc`, `passphrase_enc`는 `pgp_sym_encrypt`로 저장한다.
- API 응답에는 secret 원문을 반환하지 않고 `has_password`, `has_private_key`, `has_passphrase`, `ssh_fingerprint`만 표시한다.
- SSH config alias 기반 접속은 `auth_type=ssh_config`로 저장할 수 있다.

Join job 단계:

| Step | 처리 |
|---|---|
| SSH check | `ssh <host> true` |
| Docker daemon check | remote `docker info --format '{{json .}}'` |
| Join token fetch | local `docker swarm join-token -q worker/manager` |
| Swarm join | remote `docker swarm join --token ... manager:2377` |
| Swarm verify | remote Docker info 재조회 후 `swarm_node_id` 저장 |

remote node가 이미 Swarm에 속해 있으면 join token fetch와 join command를 skip하고 verify만 수행한다. join token은 Job log masking의 runtime secret으로 전달되어 로그에 평문 저장되지 않는다.

운영 통합 확인:

- local host는 이미 Swarm manager로 확인되었고 `docker_infra_overlay` overlay network를 생성/확인했다.
- `mini3`는 passwordless SSH와 Docker daemon check가 성공했고 이미 active worker라 join job이 idempotent하게 성공했다.
- `mini2`는 passwordless SSH는 성공했지만 remote Docker CLI가 없어 실패 job과 stderr log 경로를 확인했다.

## Node Reporter와 서버 상세

P5-04부터 Reporter token과 metric ingestion API를 제공한다.

Reporter API:

| API | 용도 |
|---|---|
| `POST /api/nodes/{node_id}/reporter-token` | node reporter token 발급 |
| `POST /api/reporter/metrics` | reporter bearer token으로 CPU/memory/storage/container metric 전송 |
| `GET /api/nodes/{node_id}/metrics` | reported_at 기준 최신순 metric 조회 |
| `GET /api/nodes/{node_id}/containers` | 최신 metric의 container 목록 조회 |
| `GET /api/nodes/{node_id}` | node 상세, reporter 상태, latest metric 포함 조회 |

Reporter token 정책:

- token 원문은 발급 응답에서만 표시한다.
- DB에는 `node_credentials.metadata.token_hash`만 저장한다.
- metric ingestion은 `Authorization: Bearer <token>` 또는 `X-Reporter-Token`으로 인증한다.
- `/api/reporter/*` 경로는 session 없이 열려 있지만 reporter token 검증을 통과해야 한다.

Metric payload:

```json
{
  "node_id": "00000000-0000-0000-0000-000000000000",
  "cpu_percent": 25.5,
  "memory": {"used_percent": 64.5, "used_bytes": 1024, "total_bytes": 2048},
  "storage": {"used_percent": 47.0, "used_bytes": 4096, "total_bytes": 8192},
  "containers": {
    "summary": {"running": 1, "exited": 0},
    "items": [
      {"id": "container-1", "name": "web", "image": "nginx:latest", "state": "running", "ports": "80/tcp"}
    ]
  },
  "reported_at": "2026-05-07T00:05:00Z"
}
```

서버 관리 화면(`/servers`)은 중심 서버를 최상단에 고정한 node 목록, 최신 CPU/memory/storage, 등록 서비스 컨테이너 묶음, 미등록 컨테이너 목록을 표시한다. 첫 진입과 node 전환은 DB에 저장된 최근 metric/container snapshot으로 먼저 그린 뒤, 실제 metric refresh와 live container refresh를 background로 다시 실행해 체감 로딩 시간을 줄인다. 자동 갱신은 1초, 3초, 5초, 10초 주기로 CPU/memory/storage만 다시 조회하고, 컨테이너/서비스 목록은 사용자가 명시적으로 갱신할 때만 다시 읽는다. 컨테이너 포트는 `호스트 포트 -> 컨테이너 포트/protocol` badge로 정리하고 IPv6 표시는 생략한다. 등록 서비스는 서비스 단위 일괄 실행/재시작/중지를 지원하고, 미등록 컨테이너는 섹션 상단의 공용 `Compose 등록` 버튼으로 서버 파일 트리 modal을 열어 `docker-compose.yaml` 또는 `docker-compose.yml`을 골라 서비스 초안으로 등록할 수 있다. Playwright spec은 `servers-node-list`, `servers-detail`, `servers-containers-table` selector로 서버 상세 dashboard와 container 목록 렌더링을 확인한다.

## Compose 검증기

P6-01부터 `/api/compose/validate`는 서비스 생성 전에 Compose YAML을 parser 기반으로 로드하고 Docker Infra 배포 정책에 맞게 검증/정규화한다.

검증 API:

| API | 용도 |
|---|---|
| `POST /api/compose/validate` | `namespace`, `filename`, `content` 또는 `compose` object를 받아 검증 결과와 normalized Compose 반환 |

검증 정책:

- `namespace`는 `^[a-z0-9_]+$` 규칙을 따른다.
- filename은 `docker-compose.yaml` 또는 `docker-compose.yml`만 허용한다.
- service의 `container_name`, `hostname`은 거절한다.
- service network는 `docker_infra_overlay`만 허용하고, 누락 시 normalized Compose에 자동 추가한다.
- top-level `networks.docker_infra_overlay.external=true`를 보장한다.
- `deploy.replicas`, `deploy.update_config`, `deploy.rollback_config`, `deploy.restart_policy` 기본값을 보강하되 기존 운영자 값을 덮어쓰지 않는다.
- service별 Compose `healthcheck` 또는 요청 payload의 Job health check 설정이 필요하다.

검증 실패 응답은 `COMPOSE_VALIDATION_FAILED`와 함께 `details[].path`, `details[].error_code`, `details[].message`를 반환한다. 이 API는 DB row나 파일을 만들지 않아 테스트 cleanup 대상이 없다.

서비스 관리 화면(`/services`)은 서비스 목록, 선택된 서비스의 Compose/domain/version/job 요약, 서비스 디렉토리 파일 브라우저를 제공한다. 새 서비스 생성은 우측 고정 입력 패널이 아니라 modal wizard로 열리며, `기본 웹 서비스`와 `직접 Compose 작성` 두 흐름으로 시작한다. 기본 입력값은 이름, namespace, port, domain 수준으로 제한하고 Compose filename, overlay network, deploy/rollback 정책은 자동으로 보강한다. 고급 Compose 편집은 명시적으로 펼쳤을 때만 수정 가능하다.
