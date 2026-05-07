# Docker Infra 개발 TODO

- 문서 상태: 실행 TODO 초안
- 기준일: 2026-05-06
- 기준 설계: `docs/docker-infra-design.md`
- 전제: 현재 `project/main`의 샘플 페이지, 샘플 모델, 샘플 devlog는 포맷 참고용이며 실제 구현 시작 전에 정리한다.

## 1. 개발 원칙

### 1.0 실행 환경

Docker Infra 개발과 검증은 `docker-infra` conda 환경을 기준으로 한다.

| 항목 | 경로 |
|---|---|
| Python | `/opt/conda/envs/docker-infra/bin/python` |
| WIZ | `/opt/conda/envs/docker-infra/bin/wiz` |

자동화, 테스트, 빌드 명령은 기본 shell의 `python` 또는 `wiz`에 의존하지 말고 위 경로를 우선 사용한다.

권장 명령:

```bash
/opt/conda/envs/docker-infra/bin/wiz run --port 3001
DOCKER_INFRA_BASE_URL=http://127.0.0.1:3001 /opt/conda/envs/docker-infra/bin/python -m unittest discover tests/api
DOCKER_INFRA_BASE_URL=http://127.0.0.1:3001 npm run e2e
/opt/conda/envs/docker-infra/bin/wiz project build --project main
```

`config.env`와 `domain.txt`는 workspace root의 민감 설정 파일이다. 테스트와 문서화 과정에서는 key 존재 여부만 redacted 형태로 확인하고 값은 출력하지 않는다.

### 1.1 구현 전 정리 원칙

실제 기능 구현을 시작하기 전에 샘플 프로젝트 흔적을 정리한다.

- 샘플 page/component/layout 중 Docker Infra에 쓰지 않는 화면 제거
- 샘플 게시판, 멤버, 마이페이지, 데모 계정 모델 제거
- 샘플 devlog는 포맷만 참고하고 Docker Infra 작업 이력과 분리
- Docker Infra 설계 문서와 TODO 문서는 유지
- 정리 작업 자체는 새 devlog로 기록

정리 후에는 `README.md`, `devlog.md`, `src/`, `docs/`가 Docker Infra 기준으로만 설명되어야 한다.

Reference: 설계 문서 §2, §3, §18

### 1.2 API 계약 우선

모든 기능은 API 계약을 먼저 정의하고 구현한다.

- OpenAPI 3.x 스펙을 프로젝트에서 생성하거나 정적 파일로 제공
- `/openapi.json`과 Swagger UI 경로 제공
- API request/response schema에 예시와 error response 포함
- API 테스트는 OpenAPI schema와 실제 응답을 대조
- 내부 service 함수를 직접 호출하는 테스트를 기본 검증으로 인정하지 않음

Reference: 설계 문서 §4.1, §12, §16

### 1.3 테스트 원칙

스모크 테스트만으로 완료 처리하지 않는다. 기능 완료 조건에는 운영에 가까운 데이터와 파일, DB row, Docker/Swarm 상태를 사용하는 검증이 포함되어야 한다.

- API 동작 테스트는 반드시 실행 중인 WIZ 서버의 실제 HTTP request/response 기반으로 작성한다.
- UI 동작 테스트는 반드시 Playwright로 실제 브라우저를 띄워 버튼 클릭, 입력, 화면 전환, 로그 스트리밍까지 확인한다.
- 화면 테스트는 시나리오별 입력값, 요청 결과, URL 이동, 화면 메시지/selector 상태를 함께 검증한다.
- WIZ `wiz` 객체가 runtime에 주입되므로 model/service 함수를 `sys.path`로 직접 import해서 호출하는 함수 단위 테스트는 동작 검증으로 인정하지 않는다.
- `tests/api`는 `from docker_infra...`, `wiz.model(...)` 직접 호출, fake executor 주입으로 성공 처리하지 않는다. 필요한 경우 파일 구조/계약 정적 검사는 별도 static test로만 제한한다.
- 테스트는 구현 코드를 중복 작성하지 않고 공개 API와 UI만 사용한다.
- DB row, 파일, Docker stack, proxy 설정, DNS record, 이미지 tag를 생성한 테스트는 성공/실패/중단 시 cleanup 수행
- 테스트 데이터에는 `test_run_id`와 `namespace`를 반드시 포함
- stale 테스트 데이터 cleanup 명령을 별도로 제공

Reference: 설계 문서 §5.2, §7.3, §9.3, §12.2

### 1.4 테스트 데이터 규칙

테스트 namespace 형식:

```text
di_test_{yyyymmdd}_{short_uuid}
```

테스트 리소스 naming:

```text
stack: di_test_{short_uuid}
service namespace: di_test_{short_uuid}
domain: di-test-{short_uuid}.{staging_zone}
image tag: test-{yyyymmdd}-{short_uuid}
job label: test_run_id={uuid}
file root: {test_template_root}/di_test_{short_uuid}
```

cleanup 순서:

1. 실행 중인 Job cancel 또는 완료 대기
2. Docker stack/service 제거
3. proxy 설정 제거 및 reload
4. Cloudflare 테스트 record 제거
5. Harbor 테스트 image/tag 제거
6. GitLab 테스트 clone/build workspace 제거
7. template/service 파일 디렉토리 제거
8. DB row 제거
9. stale lock/test metadata 제거

Reference: 설계 문서 §5.1, §7.3, §9.3, §10, §11, §12

### 1.5 관리자용 UI/UX 원칙

Docker Infra의 주 사용자는 Docker/Kubernetes 개발자가 아니라 전산 담당자 또는 일반 관리자다. IP, port, 도메인 같은 기본 개념은 이해하지만 Compose, Swarm, nginx/apache2, Harbor/GitLab/Cloudflare API 세부 동작은 몰라도 사용할 수 있어야 한다.

작업:

- 화면은 기술 리소스 목록보다 "무엇을 할 수 있는지"와 "다음에 무엇을 해야 하는지"를 먼저 보여준다.
- 직접 입력은 password, 서버 IP/host, 공개 도메인처럼 운영자가 반드시 알아야 하는 값으로 제한한다.
- advertise address, proxy 종류, template root, compose filename, command id, token 검증 명령 같은 값은 자동 감지 또는 기본값을 우선 사용하고 고급 설정으로 숨긴다.
- 영어 내부 용어는 운영자가 이해할 수 있는 한국어 상태로 치환한다. 예: `docker.info` 대신 `Docker 상태 확인`, `swarm.nodes` 대신 `Swarm 서버 목록 확인`.
- 연동이 비활성화되어도 메뉴를 숨기지 않는다. 대신 관련 자동화 버튼만 숨기거나 비활성화하고, 수동 관리/로컬 조회 기능은 유지한다.
- 위험 작업은 단일 버튼으로 실행하지 않고 요약, 영향 범위, 확인 모달, Job 이력까지 연결한다.
- 각 화면은 비어 있을 때 "등록된 항목 없음"으로 끝내지 않고 바로 실행 가능한 다음 작업을 제공한다.
- 추가/수정처럼 현재 화면의 주 흐름을 끊는 입력 폼은 목록 옆 고정 패널에 노출하지 않고 모달 또는 wizard modal로 분리한다.

완료 조건:

- Docker/Swarm/Compose 원문을 몰라도 서버 등록, 서비스 생성, 도메인 연결, 이미지 확인의 기본 흐름을 진행할 수 있다.
- 기본 화면에서 raw command, raw stdout/stderr, Compose 원문 편집기가 먼저 보이지 않는다.
- 고급 설정을 열었을 때만 기술 세부값을 조정할 수 있다.
- Playwright 테스트는 화면 텍스트와 주요 버튼이 관리자용 한국어 흐름으로 표시되는지 확인한다.

Reference: 설계 문서 §6, §8, §9, §10, §11, §13, §14

## 2. P0. 샘플 프로젝트 정리와 개발 기반

### TODO P0-01. 샘플 소스 정리

Reference: 설계 문서 §2, §3, §18

작업:

- `src/app/page.posts*`, `page.members`, `page.mypage`, 샘플 dashboard 구현 제거 또는 Docker Infra 화면으로 교체
- 샘플 사용자 모델과 게시판 portal 패키지 제거
- 유지할 WIZ framework/core 패키지와 제거할 sample package 목록 확정
- README를 Docker Infra 프로젝트 설명으로 교체
- 샘플 devlog를 정리하고 Docker Infra devlog 체계만 남김

완료 조건:

- 앱 첫 화면이 샘플 게시판/멤버 관리가 아니라 Docker Infra 초기 설치 또는 대시보드로 진입
- 샘플 데모 계정, 게시판, 포스트 API가 라우팅되지 않음
- devlog에는 Docker Infra 작업만 남거나 샘플 이력이 별도 archive로 분리

테스트:

- API: 샘플 API 경로 호출 시 404 또는 제거된 경로 응답 확인
- UI: Playwright로 기존 샘플 메뉴가 보이지 않는지 확인
- cleanup: 생성 데이터 없음

### TODO P0-02. 프로젝트 구조 재정의

Reference: 설계 문서 §4.1, §5.1

작업:

- backend API 모듈 구조 정의
- model/db, model/struct, route/api 구조를 Docker Infra 도메인 기준으로 재배치
- frontend route/page 구조 정의
- `tests/api`, `tests/e2e`, `tests/fixtures`, `tests/cleanup` 디렉토리 추가
- `docs/api/` 또는 Swagger 스펙 위치 결정

완료 조건:

- 신규 기능이 도메인별 모듈로 배치됨
- API 테스트와 Playwright 테스트가 실행 가능한 기본 구조를 가짐

테스트:

- API: `/health` 또는 `/api/system/health` 계약 테스트
- UI: Playwright로 앱 shell 로드 확인
- cleanup: 테스트 health check는 DB/file 생성 금지

### TODO P0-03. 개발/테스트 환경 compose 정리

Reference: 설계 문서 §5, §12

작업:

- PostgreSQL 16 개발 compose와 테스트 compose 분리
- 테스트용 template root, artifact root, log root를 임시 경로로 설정
- 테스트 DB schema reset 또는 test namespace cleanup 방식 확정
- Docker/Swarm 연동 테스트 profile 정의
- nginx/apache2 sandbox 설정 디렉토리 정의

완료 조건:

- 로컬 개발, API 테스트, Swarm 통합 테스트가 서로 다른 설정으로 실행됨
- 테스트 중 생성되는 파일 경로가 운영 기본 경로와 분리됨

테스트:

- API: 테스트 설정으로 앱 실행 후 `/api/system/health` 응답의 DB 연결 상태 확인
- cleanup: 테스트 root 삭제, 테스트 DB row 삭제

## 3. P1. API 계약, Swagger, 테스트 하네스

### TODO P1-01. OpenAPI/Swagger 기반 추가

Reference: 설계 문서 §4.1, §12, §16

작업:

- OpenAPI 스펙 생성 방식 선택
- `/openapi.json` 제공
- Swagger UI 제공
- 공통 error schema 정의
- pagination, job status, secret masking response schema 정의

완료 조건:

- 브라우저에서 Swagger UI 접근 가능
- 모든 공개 API가 OpenAPI에 포함됨
- schema validation 실패 시 테스트가 실패함

테스트:

- API: `/openapi.json` 호출 후 필수 path, component schema, security schema 비교
- API: Swagger UI HTML 로드와 OpenAPI URL 연결 확인
- UI: Playwright로 Swagger UI 열고 대표 endpoint가 표시되는지 확인
- cleanup: 생성 데이터 없음

### TODO P1-02. API 테스트 공통 클라이언트

Reference: 설계 문서 §5.2, §12.2, §16

작업:

- HTTP client fixture 작성
- password-only login fixture 작성
- OpenAPI response validation helper 작성
- `test_run_id` 생성 fixture 작성
- cleanup finalizer와 stale cleanup CLI 작성

완료 조건:

- 테스트가 내부 Python/TypeScript service 함수를 직접 호출하지 않음
- 모든 변경성 테스트가 cleanup finalizer를 등록함
- 중간 실패 시에도 cleanup 실행

테스트:

- API: 의도적으로 테스트 row/file을 만들고 fixture 종료 시 삭제 확인
- API: cleanup 실패를 재시도하고 실패 리소스 목록을 출력하는지 확인
- cleanup: 테스트가 만든 검증용 row/file 삭제

### TODO P1-03. Playwright 테스트 기반 추가

Reference: 설계 문서 §14, §15, §16

작업:

- Playwright 설정 추가
- 테스트용 앱 URL, 패스워드, test_run_id 환경변수 정의
- 로그인 helper 작성
- 공통 cleanup hook 작성
- 스크린샷/trace 저장 위치 정의

완료 조건:

- headless 브라우저에서 로그인부터 기본 shell 진입까지 검증
- 실패 시 trace와 screenshot이 저장됨

테스트:

- UI: 로그인 화면, 잘못된 패스워드, 정상 패스워드, 로그아웃 확인
- UI: 메뉴 표시가 연동 설정에 따라 달라지는지 fixture별 확인
- cleanup: UI 테스트가 만든 설정 row 원복

## 4. P2. 데이터 모델과 마이그레이션

### TODO P2-01. PostgreSQL 연결과 migration 체계

Reference: 설계 문서 §5

작업:

- PostgreSQL 연결 설정 구현
- migration 실행/rollback 명령 추가
- schema version table 추가
- 테스트 DB 또는 테스트 schema 초기화 방식 구현

완료 조건:

- 빈 DB에서 migration으로 전체 schema 생성 가능
- migration 재실행이 idempotent하게 동작
- rollback 또는 down migration 정책 문서화

테스트:

- API: migration 후 `/api/system/health`가 DB schema version 반환
- API: migration 재실행 후 schema version 중복 생성 없음
- DB cleanup: 테스트 schema drop 또는 migration test DB 제거

### TODO P2-02. 핵심 테이블 구현

Reference: 설계 문서 §5.1

작업:

- `system_settings`
- `integration_harbor`
- `integration_gitlab`
- `cloudflare_zones`
- `nodes`, `node_credentials`, `node_metrics`
- `templates`, `template_versions`
- `services`, `service_domains`, `compose_versions`
- `images`, `image_builds`
- `jobs`, `job_steps`, `job_logs`
- `proxy_configs`, `certificates`
- `electron_setting_backups`

완료 조건:

- 모든 table에 created/updated timestamp 포함
- 변경성 entity에는 `test_run_id` 또는 metadata 확장 필드 제공
- secret column은 평문 저장되지 않음

테스트:

- API: 대표 CRUD endpoint로 row 생성/조회/수정/삭제 검증
- API: secret 저장 후 조회 응답에서 masked value만 반환되는지 확인
- cleanup: 생성 row를 API 또는 cleanup helper로 삭제

## 5. P3. 인증, 설치 마법사, 시스템 설정

### TODO P3-01. Password-only 인증 구현

Reference: 설계 문서 §3, §16

작업:

- ID 없는 password login 구현
- password hash 저장
- session cookie 정책 적용
- rate limit 구현
- logout 구현

완료 조건:

- 로그인 request에 ID 필드가 필요 없음
- 사용자 계층, role, permission API가 존재하지 않음
- session cookie에 보안 속성 적용

테스트:

- API: setup password 설정 후 login 성공
- API: 잘못된 password 연속 실패 시 rate limit 응답
- API: user/role/permission 관련 endpoint가 없음을 확인
- UI: Playwright로 login/logout, rate limit 메시지 확인
- cleanup: 설정 row와 session row 삭제

### TODO P3-02. 설치 마법사

Reference: 설계 문서 §6.1, §6.2, §13

작업:

- 최초 구동 여부 감지
- Docker Infra 실행 서버의 Docker daemon, Swarm manager, advertise address 확인
- nginx/apache2 설치 상태 확인
- 기본 proxy 선택
- template root 설정
- 관리자 패스워드 설정

완료 조건:

- 설치 전에는 wizard 외 메뉴 접근 제한
- 설치 완료 후 local master node가 자동 등록
- 마스터 노드 SSH 정보 입력 단계가 없음

테스트:

- API: fresh DB에서 setup status 조회
- API: setup 요청 후 local master node row 생성 확인
- API: 같은 setup 재요청 시 conflict 응답
- UI: Playwright로 wizard 입력, 검증 실패, 성공 완료 확인
- cleanup: setup 관련 settings/nodes row 삭제, 생성 파일 제거

### TODO P3-03. 시스템 설정과 동적 메뉴

Reference: 설계 문서 §3, §13, §14

작업:

- 일반 설정: favicon, browser title, logo image
- Harbor/GitLab 설정 저장과 연결 테스트
- favicon/logo 업로드와 runtime 즉시 반영
- Cloudflare 설정을 시스템 화면이 아니라 도메인 화면으로 분리
- generic settings API의 secret masking 유지

완료 조건:

- 일반 설정이 로그인 화면, sidebar, 브라우저 title/favicon에 실제 반영됨
- 업로드 파일이 WIZ workspace data 디렉토리에 저장됨
- Harbor/GitLab 연결 테스트가 성공/실패 원인을 화면에 보여줌

테스트:

- API: 설정 저장/조회/수정/삭제
- API: generic secret 응답 masking 비교
- API: Harbor/GitLab 연결 테스트
- UI: Playwright로 설정 저장 후 title/logo/favicon 적용 확인
- cleanup: 설정 row와 업로드 파일 삭제

## 6. P4. Job Queue와 로그

### TODO P4-01. Job/Step/Log 모델과 API

Reference: 설계 문서 §3, §12

작업:

- Job 생성 API
- Step 상태 전이
- log append와 stream 구분
- status 조회, 목록, 상세
- cancel/retry API

완료 조건:

- pending/running/succeeded/failed/canceled 상태 전이가 명확함
- job detail에서 step과 log를 함께 조회 가능
- failed job retry 시 이전 로그와 새 로그가 구분됨

테스트:

- API: job 생성 후 step 순서와 상태 전이 검증
- API: 실패 step retry 후 response와 log 이력 비교
- API: cancel 요청 후 running job이 canceled로 종료되는지 확인
- cleanup: job/step/log row 삭제

### TODO P4-02. Secret masking과 로그 보존

Reference: 설계 문서 §5.2, §10.3, §12.2, §16

작업:

- masking 대상 secret registry 구현
- stdout/stderr 저장 전 masking
- 로그 다운로드 API
- 로그 검색 API

완료 조건:

- password/token/private key가 로그에 평문 저장되지 않음
- masking 후에도 디버깅 가능한 context가 남음

테스트:

- API: secret 포함 명령 로그 입력 후 저장 로그가 masking되는지 비교
- API: 로그 검색과 다운로드 결과도 masking 유지
- cleanup: log row 삭제

## 7. P5. Local Master, 서버 관리, Node Reporter

### TODO P5-01. Local Executor

Reference: 설계 문서 §4.1, §6.1, §6.2

작업:

- Docker Infra 실행 host에서 명령 실행 abstraction 구현
- Docker CLI, Swarm, proxy configtest 명령 adapter 구현
- 명령 timeout, stdout/stderr capture, exit code 저장
- destructive command allowlist 정책 구현

완료 조건:

- local master 제어에 SSH 정보가 필요 없음
- 명령 실행 결과가 Job log로 연결 가능

테스트:

- API: local command check endpoint로 Docker version 조회
- API: 실패 명령 exit code와 stderr 반환 검증
- cleanup: 생성 데이터 없음

### TODO P5-02. Local Master 자동 등록과 Swarm init

Reference: 설계 문서 §6.1, §6.2

작업:

- 설치 완료 시 local master node row 생성
- `docker info`로 Swarm 상태 확인
- 필요 시 `docker swarm init` 실행
- `docker_infra_overlay` network 생성

완료 조건:

- local master가 `is_local_master=true`로 하나만 존재
- 이미 Swarm manager인 경우 init을 재실행하지 않음
- overlay network가 없으면 생성, 있으면 재사용

테스트:

- API: setup 후 local master 조회
- API: Swarm init idempotency 확인
- 운영 통합: 실제 Docker daemon에서 overlay network 생성 확인
- cleanup: 테스트 Swarm 환경이면 stack/network 제거, DB row 삭제

### TODO P5-03. 슬레이브 노드 등록과 join

Reference: 설계 문서 §6.2, §16

작업:

- SSH credential 저장
- 최초 등록은 password 접속 확인으로 시작하고 DB에는 password를 저장하지 않음
- 관리용 SSH key file이 없으면 자동 생성하고 remote `authorized_keys`에 등록
- SSH check API
- Docker daemon 상태 check
- join token 조회
- slave `docker swarm join` 실행
- node label/availability 저장

완료 조건:

- SSH fingerprint를 확인하고 저장
- 이후 check/join/API 명령은 DB의 key file과 fingerprint 정보를 기준으로 실행
- join 성공 후 Swarm node ID가 DB에 저장됨
- 실패 시 job log와 사용자 메시지가 분리됨

테스트:

- API: 테스트 SSH 서버 또는 dev slave VM/container 대상으로 check 성공/실패 비교
- API: join job 생성부터 완료까지 step/log 검증
- 운영 통합: 실제 Swarm node 목록에 slave가 표시되는지 확인
- cleanup: `docker node rm`, credential row 삭제

### TODO P5-04. Node Reporter와 서버 상세

Reference: 설계 문서 §6.3, §6.4

작업:

- 상태 수집 인증 token 발급
- metric ingestion API
- CPU/memory/storage/container summary 저장
- 서버 상세 API
- container 목록 API
- 서버 상세 탭 UI: 개요 / 매크로 / 웹 터미널
- 서버 전용 shell macro 저장/실행 UI
- 서버 상세에서는 전역 매크로 + 서버 전용 매크로를 검색 가능한 선택 UI로 즉시 실행

완료 조건:

- 자동 상태 수집기가 주기적으로 metric을 전송
- 서버 상세에서 최신 metric과 컨테이너 상태가 함께 표시
- 서버 상세에서 Monaco 기반 서버 전용 macro 편집과 서버별 macro 실행이 가능
- 서버 상세 매크로 탭에서 실행 결과가 modal이 아니라 탭 내부 결과 패널에 누적 표시됨
- 서버 상세 웹 터미널은 버튼을 눌렀을 때만 PTY 세션을 연결함

테스트:

- API: reporter token으로 metric POST 후 latest metric 조회
- API: 오래된 metric과 최신 metric 정렬 비교
- UI: Playwright로 서버 상세 dashboard, container 목록 확인
- cleanup: metric/node row 삭제

## 8. P6. Compose, 템플릿, 파일 저장소

### TODO P6-01. Compose 검증기

Reference: 설계 문서 §7.1, §7.2

작업:

- YAML parser 기반 Compose 로드
- namespace regex 검증
- `container_name`, `hostname` 금지
- fixed overlay network 강제
- deploy 기본 정책 보강
- healthcheck 또는 Job health check 요구

완료 조건:

- invalid Compose가 정확한 field path와 함께 거절됨
- valid Compose는 보강된 normalized Compose를 반환

테스트:

- API: valid Compose 검증 response snapshot 비교
- API: 금지 필드별 error code와 message 비교
- API: deploy 정책 자동 보강 결과 비교
- cleanup: 생성 데이터 없음

### TODO P6-02. Template Catalog

Reference: 설계 문서 §8

작업:

- template 디렉토리 스캔
- `values.schema.json`, `values.default.yaml` 검증
- template CRUD API
- template version 관리
- 기본 DB/WAS/cache/queue 템플릿 추가

완료 조건:

- 템플릿 목록과 상세를 API로 조회 가능
- 템플릿 렌더링 결과가 Compose 검증기를 통과
- 템플릿 파일과 DB metadata가 동기화됨

테스트:

- API: 템플릿 생성/조회/수정/버전 생성/삭제
- API: 렌더링 후 normalized Compose 비교
- UI: Playwright로 템플릿 목록, Monaco 편집, 저장 확인
- cleanup: template file tree와 DB row 삭제

### TODO P6-03. Service File Store와 `.history`

Reference: 설계 문서 §7.3, §9.3

작업:

- service namespace 디렉토리 생성
- Compose/config/env/files 저장
- `.history` snapshot 생성
- file browser API: list, read, write, upload, download, delete
- checksum 저장

완료 조건:

- 서비스 파일 원본은 filesystem에 저장
- DB에는 path/checksum/version만 저장
- 변경 시 이전 파일이 `.history`에 남음

테스트:

- API: 서비스 파일 생성 후 file tree와 DB metadata 비교
- API: 파일 수정 후 `.history` snapshot 생성 확인
- API: 다운로드 content checksum 비교
- UI: Playwright로 파일 생성, Monaco 편집, 다운로드 버튼 확인
- cleanup: service directory와 DB row 삭제

### TODO P6-04. AI Compose 생성

Reference: 설계 문서 §8

작업:

- AI 생성 요청 schema 정의
- prompt/version metadata 저장
- 생성 결과 검증기 연결
- 사용자 확인 전 자동 배포 금지

완료 조건:

- AI 결과는 draft 상태로만 저장
- 검증 실패 항목이 UI에 표시됨
- draft를 사용자가 저장해야 서비스 생성 가능

테스트:

- API: stubbed AI provider로 deterministic Compose 생성 후 검증 결과 비교
- API: invalid AI result가 draft로 저장되지만 deploy 불가한지 확인
- UI: Playwright로 AI 생성, 수정, 저장 동작 확인
- cleanup: draft file과 DB row 삭제

## 9. P7. 서비스 생성, 배포, 로드밸런싱

### TODO P7-01. 서비스 CRUD

Reference: 설계 문서 §9.1

작업:

- 서비스 namespace/name 생성
- domain/proxy/SSL 입력 저장
- placement, replica, rolling update/rollback 정책 저장
- service detail API

완료 조건:

- namespace가 `^[a-z0-9_]+$` 규칙을 따름
- 서비스 생성 시 Compose file store와 DB metadata가 함께 생성됨
- domain/proxy 설정 누락 시 배포 전 validation error 반환

테스트:

- API: 서비스 생성 request/response schema 비교
- API: invalid namespace, duplicate namespace, missing port error 비교
- UI: Playwright로 서비스 생성 form validation과 저장 확인
- cleanup: service row와 directory 삭제

### TODO P7-02. `docker stack deploy` Job

Reference: 설계 문서 §7.2, §9.2, §12.1

작업:

- deploy Job 생성
- Compose 검증/보강
- image pull 또는 build stage 연결
- `docker stack deploy` 실행
- service/task 상태 polling
- routing mesh/VIP 연결 확인
- health check 실행

완료 조건:

- deploy Job이 표준 Step 순서를 따름
- replica 수만큼 task가 running 상태인지 확인
- published port로 접근했을 때 Swarm load balancing 경로를 통과

테스트:

- API: 테스트 Compose를 서비스로 생성 후 deploy Job 완료까지 polling
- 운영 통합: 실제 Swarm에서 replica 2개 이상 배포
- API: published port에 여러 번 요청해 응답과 health 상태 비교
- API: deploy Job step/log response를 expected sequence와 비교
- cleanup: `docker stack rm`, service files, DB row 삭제

### TODO P7-03. Rollback

Reference: 설계 문서 §9.3, §12

작업:

- Compose version 목록 API
- 특정 version restore API
- stack redeploy
- proxy/SSL 설정 rollback 연결

완료 조건:

- rollback 전후 Compose checksum이 예상대로 변경됨
- rollback Job도 단계별 로그를 보존

테스트:

- API: v1 배포, v2 수정 배포, v1 rollback 후 response 비교
- 운영 통합: rollback 후 published endpoint가 v1 응답으로 돌아오는지 확인
- cleanup: stack/service/files/DB row 삭제

## 10. P8. Proxy, DNS, SSL

### TODO P8-01. nginx/apache2 감지

Reference: 설계 문서 §11.2, §13

작업:

- nginx version/config dir/configtest/reload command 감지
- apache2 version/config dir/configtest/reload command 감지
- 둘 다 있는 경우 기본 proxy 설정
- 슬레이브 proxy는 관리하지 않음

완료 조건:

- Docker Infra 실행 서버 기준으로만 감지
- 감지 결과가 시스템 설정과 proxy 생성에 반영됨

테스트:

- API: sandbox command fixture로 nginx/apache2 감지 결과 비교
- 운영 통합: 실제 설치된 proxy가 있으면 version/configtest 실행
- UI: Playwright로 proxy 상태 표시 확인
- cleanup: 설정 row 원복

### TODO P8-02. Proxy 설정 생성/검증/reload

Reference: 설계 문서 §9.2, §11.3

작업:

- nginx server block 생성
- apache2 vhost 생성
- upstream은 local master published port 사용
- configtest 후 reload
- 실패 시 이전 설정 복원

완료 조건:

- proxy 설정이 컨테이너 IP가 아니라 published port를 바라봄
- configtest 실패 시 reload하지 않음
- 설정 이력이 DB에 저장됨

테스트:

- API: proxy config preview response 비교
- API: sandbox configtest 성공/실패 케이스 검증
- 운영 통합: 테스트 서비스 배포 후 proxy를 통해 health endpoint 접근
- UI: Playwright로 proxy 설정 미리보기, 적용, 실패 메시지 확인
- cleanup: proxy config file 제거, reload, DB row 삭제

### TODO P8-03. Cloudflare DNS

Reference: 설계 문서 §11.1, §14

작업:

- zone CRUD
- DNS record list/create/update/delete
- service domain과 record 연결
- Cloudflare 비활성화 시 수동 domain/proxy 모드 유지

완료 조건:

- DNS record는 Docker Infra 실행 서버 public IP를 바라봄
- zone별 token과 Zone ID를 도메인 화면에서 관리 가능
- sync 후 `cloudflare_dns_records`와 마지막 동기화 상태가 DB에 저장됨
- Cloudflare zone이 없어도 도메인 화면은 수동/캐시 모드로 유지됨

테스트:

- API: staging Cloudflare zone에 테스트 record 생성/수정/삭제
- API: zone sync 후 record cache/last_sync 반영 확인
- UI: Playwright로 zone 추가, 동기화, record 수정 흐름 확인
- cleanup: 테스트 DNS record 삭제, zone setting row 삭제

### TODO P8-04. SSL 인증서

Reference: 설계 문서 §11.4, §16

작업:

- 구매 인증서 upload
- cert/key/chain 저장과 암호화/권한 설정
- certbot staging 발급 Job
- 만료일 조회와 갱신 Job

완료 조건:

- private key가 API 응답과 로그에 노출되지 않음
- proxy 설정에 인증서 경로가 반영됨
- certbot Job 로그와 상태가 보존됨

테스트:

- API: self-signed 테스트 인증서 업로드 후 metadata 조회
- API: private key masking 확인
- 운영 통합: proxy TLS endpoint 접근
- cleanup: 인증서 파일, proxy config, DB row 삭제

## 11. P9. 이미지, GitLab, Harbor

### TODO P9-01. Harbor 연동

Reference: 설계 문서 §10.1, §13, §14

작업:

- Harbor 설정 저장
- project/repository/tag 목록 조회
- image metadata cache
- 위험 작업 분리

완료 조건:

- Harbor disabled 시 이미지 메뉴가 local image 목록 중심으로 표시
- secret이 masking됨
- 기본 Harbor project는 시스템 설정 기반

테스트:

- API: staging Harbor에서 project/image/tag 목록 조회
- API: disabled 상태 response와 메뉴 상태 비교
- UI: Playwright로 이미지 목록 필터/상세 확인
- cleanup: 테스트 tag 삭제, cache row 삭제

### TODO P9-02. GitLab 프로젝트와 빌드 흐름

Reference: 설계 문서 §10.2, §10.3, §12

작업:

- GitLab token 설정
- 프로젝트 목록 조회
- Compose path 입력
- `config.env` 조회/수정
- build server 선택
- 빌드 스크립트 실행
- Harbor push 연결

완료 조건:

- 빌드 Job이 clone, env edit, build, push step 로그를 남김
- `config.env` 원문 secret은 로그에 남지 않음
- 빌드 산출 image/tag가 Harbor metadata와 연결됨

테스트:

- API: staging GitLab 프로젝트 목록 조회
- API: 테스트 repository clone 후 Compose path와 `config.env` response 비교
- 운영 통합: 테스트 image build 후 staging Harbor push 확인
- UI: Playwright로 프로젝트 선택, env 편집, 빌드 실행, 로그 확인
- cleanup: clone workspace, Harbor test tag, image_build row, job row 삭제

### TODO P9-03. 로컬 이미지 목록

Reference: 설계 문서 §6.3, §10.1, §14

작업:

- local master image list
- slave node image list
- image metadata normalize
- Harbor metadata와 local image mapping

완료 조건:

- 서버별 로컬 이미지 목록이 조회됨
- Harbor disabled 상태에서도 이미지 관리가 동작

테스트:

- API: local Docker image 목록 response schema 비교
- API: test image pull 후 목록에 나타나는지 확인
- UI: Playwright로 서버별 이미지 목록 확인
- cleanup: test image remove, cache row 삭제

## 12. P10. 화면 구현

### TODO P10-01. 앱 shell과 메뉴

Reference: 설계 문서 §14, §16

작업:

- Docker Infra 전용 sidebar/menu 구성
- 설치 전/설치 후 route guard
- integration enabled 상태별 버튼/안내 제어
- 샘플 화면 제거
- Cloudflare/Harbor disabled 상태에서도 도메인/이미지 메뉴 유지
- disabled integration은 "자동 연동 꺼짐, 수동 관리 가능" 상태로 표시

완료 조건:

- 메뉴는 서버, 서비스, 도메인, 이미지, 템플릿, 시스템, 도구 다운로드만 표시
- 사용자 관리 메뉴가 없음
- 도메인/이미지 메뉴는 연동 disabled 상태에서도 접근 가능
- GitLab disabled 시 빌드 버튼은 숨기되 이미지 목록/로컬 이미지 기능은 유지

테스트:

- UI: Playwright로 설치 전 wizard, 설치 후 dashboard route 확인
- UI: integration 상태별 메뉴 표시 snapshot 비교
- cleanup: 설정 row 원복

### TODO P10-02. 서버 관리 화면

Reference: 설계 문서 §6.2, §6.3, §6.4

작업:

- 서버 목록
- 서버 등록/수정 modal: 역할 선택 없이 IP/host, SSH 계정, 최초 연결 password, SSH port만 입력
- 목록 카드 안에서 중심 서버/일반 서버 구성을 함께 표시하고 중심 서버를 항상 최상단에 고정
- 등록 시 password 접속 확인, fingerprint 확인, 관리용 SSH key 생성/등록, key 접속 확인을 한 번에 처리
- 등록 후 SSH check, Docker check, Swarm join을 단계 흐름으로 연결
- 서버 상세 CPU/memory/storage는 1/3/5/10초 자동 갱신 선택을 지원하고, container/service 목록은 수동 갱신으로 분리
- 서버 상세 첫 진입은 저장된 최근 상태로 즉시 렌더링하고, 실제 metric/container refresh는 background로 분리
- 컨테이너 포트 포워딩은 raw string이 아니라 관리자가 읽기 쉬운 매핑 형식으로 표시
- 컨테이너 상태값은 실행/중지/재시작/이상 같은 운영 의미 중심 한국어 badge로 표시
- 등록 서비스 컨테이너와 미등록 컨테이너를 분리하고, 등록 서비스는 서비스 단위 일괄 실행/재시작/중지를 제공
- 미등록 컨테이너는 섹션 상단 공용 `Compose 등록` 버튼으로 서버 파일 트리 modal을 열어, 한 Compose 기준으로 서비스 초안을 자동 등록
- 컨테이너 run/restart/stop은 모두 확인 modal 후 실행
- reporter token 발급 UI는 기본 운영 화면에서 제거하고, 실제 상태 갱신 방식(로컬/SSH)을 명시
- 서버 상세 metrics/container/image
- 서버 상세 탭: 개요 / 매크로 / 웹 터미널
- 서버 상세 매크로 탭에서는 검색 가능한 select 방식으로 전역 매크로와 서버 전용 매크로를 실행
- xterm 웹 터미널은 connect 버튼을 눌렀을 때만 연결

### TODO P10-02A. 전역 매크로 관리 화면

Reference: 설계 문서 §6.3

작업:

- 좌측 사이드 메뉴에 `/macros` 전용 메뉴 추가
- 전역 매크로 목록/검색/상세 화면
- Monaco editor 기반 전역 매크로 추가/수정 modal
- 웹 사이트 dark mode와 동기화되는 Monaco theme
- macOS `Cmd+S`, Windows/Linux `Ctrl+S` 저장 단축키

완료 조건:

- 전역 매크로는 서버 상세가 아니라 별도 메뉴에서 관리 가능
- 전역 매크로 수정 modal은 현재 사이트 다크모드 상태를 그대로 따름
- 단축키 저장이 운영자 입력 흐름을 끊지 않고 동작

테스트:

- UI: Playwright로 `/macros` 진입, 목록/상세/추가 버튼 노출 확인
- UI: 서버 상세 매크로 탭에서 전역 매크로 선택 UI 노출 확인
- cleanup: 테스트용 macro row 삭제

완료 조건:

- local master는 자동 표시되고 삭제 불가
- local master는 Docker Infra 실행 서버로 자동 동기화되고 별도 관리자/일반 역할 선택이 없음
- slave는 IP/host 입력 후 등록/수정/점검/Swarm 연결을 같은 화면에서 순서대로 진행 가능
- join job 결과와 실패 이유가 raw stderr보다 쉬운 메시지와 Job 링크로 표시됨
- 서버 상세가 최신 metric만 주기적으로 갱신하고, container/service 데이터는 불필요하게 재조회하지 않음
- reporter 개념을 몰라도 화면만 보고 현재 상태가 어떻게 갱신되는지 이해할 수 있음
- 미등록 컨테이너를 Compose 파일과 연결해 서비스 관리 대상으로 편입할 수 있음

테스트:

- UI: Playwright로 서버 등록 form validation과 SSH check 버튼 동작 확인
- UI: 서버 상세 metric 자동 갱신 선택과 container table 표시 확인
- UI: xterm input/output 기본 동작 확인
- cleanup: 테스트 node/metric/session row 삭제

### TODO P10-03. 서비스 관리 화면

Reference: 설계 문서 §7, §9

작업:

- 서비스 목록/상세
- 생성 modal wizard: 기본 웹 서비스 템플릿 또는 직접 Compose 작성으로 시작
- Monaco Compose editor
- 서비스 디렉토리 파일 브라우저와 파일 내용 미리보기
- deploy/rollback 버튼
- Job log viewer
- namespace/name/port/domain은 최소 입력으로 받고 Compose filename/network/deploy 기본 정책은 자동 보강
- Compose 원문 편집기는 고급 설정으로 이동

완료 조건:

- Compose validation error가 editor 위치와 함께 표시
- 서비스 저장 시 DB row, service domain, compose file, `.history` snapshot이 함께 생성됨
- 서비스 상세에서 현재 Compose, domain, version, 관련 job을 한 번에 확인할 수 있음
- deploy Job 로그가 실시간으로 갱신
- 파일 브라우저에서 생성/업로드/다운로드 가능

테스트:

- UI: Playwright로 서비스 생성, Compose 수정, 저장, deploy 실행
- UI: Job log viewer에서 step 상태 변화 확인
- UI: 파일 브라우저 CRUD 확인
- cleanup: stack/service/files/DB row 삭제

### TODO P10-04. 도메인, 이미지, 템플릿, 시스템 화면

Reference: 설계 문서 §8, §10, §11, §13, §14

작업:

- Cloudflare zone/record 화면
- Harbor/local image 화면
- GitLab build 화면
- 템플릿 catalog/editor 화면
- 시스템 설정 화면
- 운영 도구 화면은 raw command runner가 아니라 Docker 상태 점검, Swarm 상태 점검, proxy 설정 검사 같은 목적형 진단 버튼으로 구성
- 설치 마법사와 시스템 설정은 자동 감지 결과를 기본값으로 사용하고 고급 설정을 접은 상태로 제공

완료 조건:

- disabled integration은 관련 액션 버튼을 숨김
- disabled integration이어도 수동 domain/proxy, local image 조회 기능은 유지
- secret 입력 후 조회 시 masking 표시
- 실제 API 응답과 화면 상태가 일치
- 첫 화면에 command id, token, raw stdout/stderr가 직접 노출되지 않음

테스트:

- UI: Playwright로 각 화면 CRUD와 validation 확인
- UI: secret masking, integration toggle, 목록 refresh 확인
- cleanup: 테스트 설정/파일/cache row 삭제

## 13. P11. Electron App

### TODO P11-01. Electron 로컬 모드

Reference: 설계 문서 §15.1

작업:

- SSH profile 관리
- ProxyJump 설정
- SSH key/fingerprint 관리
- 파일 전송
- shell macro 저장/실행
- local setting backup export/import

완료 조건:

- Docker Infra URL 없이 로컬 기능 사용 가능
- local secret은 OS keychain 또는 암호화 저장소 사용

테스트:

- API 아님: Electron IPC contract 테스트
- UI: Playwright 또는 Electron test runner로 profile 생성, SSH check, macro 실행 확인
- cleanup: local profile, key fixture, transferred file 삭제

### TODO P11-02. Electron 원격 모드

Reference: 설계 문서 §15.2, §16

작업:

- Docker Infra URL 등록
- password-only login
- Web API 기능 embedded 또는 native UI 연동
- Job log 조회
- local mode 기능 유지

완료 조건:

- 원격 모드에서 웹 서비스 기능과 로컬 SSH 기능을 함께 사용
- 원격 password/session이 안전하게 저장됨

테스트:

- API: Electron 원격 client가 Swagger 계약과 같은 endpoint를 호출
- UI: Electron 테스트로 로그인, 서비스 목록, Job detail 확인
- cleanup: Electron 설정 백업 row와 local config 삭제

## 14. P12. 운영 통합과 릴리즈

### TODO P12-01. 운영형 통합 테스트 시나리오

Reference: 설계 문서 §9.2, §10, §11, §12

작업:

- disposable PostgreSQL
- 실제 Docker Swarm local master
- nginx 또는 apache2 sandbox
- staging Cloudflare zone
- staging Harbor
- staging GitLab repository
- 테스트 domain과 image tag 자동 cleanup

완료 조건:

- GitLab Compose 기반 build부터 Harbor push, stack deploy, health check, DNS, proxy, SSL까지 하나의 Job으로 검증
- 실패 시에도 cleanup report가 남음

테스트:

- API: end-to-end deploy request 후 Job 최종 succeeded 확인
- API: 각 step log와 expected order 비교
- UI: Playwright로 service detail, job log, endpoint 상태 확인
- cleanup: DNS/image/stack/proxy/files/DB row 삭제

### TODO P12-02. 관측성과 운영 도구

Reference: 설계 문서 §6.4, §12.2

작업:

- health endpoint
- readiness endpoint
- metrics endpoint
- stale test cleanup command
- orphan resource detector
- backup/restore command 검토

완료 조건:

- 운영자가 현재 시스템 상태와 미정리 리소스를 확인 가능
- 테스트 실패 후 cleanup 재실행 가능

테스트:

- API: health/readiness/metrics response 비교
- API: 의도적으로 orphan resource metadata 생성 후 detector가 찾는지 확인
- cleanup: orphan fixture 제거

## 15. 기능 완료 기준

각 TODO는 다음 조건을 만족해야 완료로 처리한다.

- 설계 문서 reference와 구현 범위가 devlog에 기록됨
- OpenAPI 스펙이 변경되었으면 API 테스트가 함께 변경됨
- API 테스트가 request/response schema와 expected body를 비교함
- Playwright 테스트가 사용자 흐름을 실제 브라우저에서 검증함
- DB/file/Docker/DNS/Harbor 리소스 생성 테스트는 cleanup을 증명함
- secret masking 테스트가 포함됨
- 실패 로그가 Job log 또는 테스트 artifact로 남음
- `git diff --check`와 프로젝트 빌드가 통과함

## 16. 우선 구현 순서

1. P0 샘플 정리
2. P1 Swagger와 테스트 하네스
3. P2 DB schema와 migration
4. P3 설치 마법사와 password-only 인증
5. P4 Job Queue
6. P5 local master와 서버 관리
7. P6 Compose/템플릿/파일 저장소
8. P7 서비스 배포와 Swarm 로드밸런싱
9. P8 proxy/DNS/SSL
10. P9 이미지/GitLab/Harbor
11. P10 전체 화면
12. P11 Electron
13. P12 운영형 통합 테스트와 릴리즈
