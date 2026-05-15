# Docker Infra Runtime Notes

- 문서 상태: 구조 단순화 반영
- 기준일: 2026-05-08

## 1. 실행 환경

Docker Infra는 WIZ 프로젝트 `main`에서 실행한다. 제품 패키징 기준은 Ubuntu 24.04 host이며, nginx는 기본 설치 경로와 daemon 이름을 고정한다.

운영 설치는 `installer/preinstall.sh`와 `installer/install.sh` 기준으로 진행한다. 운영 PostgreSQL은 host package로 설치하고, 아래 compose PostgreSQL은 개발/테스트 전용으로 유지한다.

| 환경 | Compose file | Profile | 설명 |
|---|---|---|---|
| 개발 DB | `docker/compose/development.yaml` | 없음 | 로컬 개발용 PostgreSQL 16 |
| API 테스트 | `docker/compose/test.yaml` | `api` | 테스트용 PostgreSQL 16 |
| Swarm 통합 테스트 | `docker/compose/test.yaml` | `swarm` | Docker socket을 사용하는 통합 테스트 |
| nginx sandbox | `docker/compose/test.yaml` | `proxy` | nginx 설정 생성/검증 sandbox |

권장 실행 명령:

```bash
docker compose -f docker/compose/development.yaml up -d postgres
docker compose -f docker/compose/test.yaml --profile api run --rm api-tests
docker compose -f docker/compose/test.yaml --profile proxy run --rm proxy-sandbox
```

## 2. Runtime Directory

생성 산출물은 WIZ workspace의 `data/`와 프로젝트 `.runtime/` 아래에 둔다.

| 용도 | 경로 |
|---|---|
| 시스템 이미지 업로드 | `/root/docker-infra/data/system-assets/` |
| 도메인 인증서 | `/root/docker-infra/data/domain-certificates/` |
| 내장 백업 Harbor data | `/root/docker-infra/data/backup-harbor/` 또는 운영 volume |
| 서비스 Compose 파일 | `.runtime/dev/services` |
| 개발 artifact | `.runtime/dev/artifacts` |
| 테스트 artifact | `.runtime/test/artifacts` |
| 개발 log | `.runtime/dev/logs` |
| 테스트 log | `.runtime/test/logs` |

`data/`에는 운영 데이터가 들어가므로 devlog나 테스트 fixture에 password/token을 남기지 않는다.

## 3. config.env

서비스는 daemon 형태로 실행되므로 필요한 값은 실제 `config.env`에 존재해야 한다. 환경변수를 코드에서 사용할 때는 주입 경로를 먼저 확인한다.

운영 설치에서는 `/etc/docker-infra/docker-infra.env`를 systemd `EnvironmentFile`로 등록하고, WIZ bundle root의 `config.env`는 같은 파일을 가리키는 symlink로 둔다.

필수 범위:

- database connection
- session secret과 cookie 설정
- local executor allowlist
- system asset/data directory
- backup system data directory
- Cloudflare token encryption key
- SSH key directory
- nginx command allowlist

nginx 경로와 daemon 이름은 사용자 설정값이 아니라 Ubuntu 24.04 기본값으로 처리한다.

## 4. 설치와 인증

최초 구성은 제품 `/access` 화면이 아니라 installer HTML에서 처리한다. installer는 service 시작 후 `/api/system/setup`에 관리자 비밀번호, local master, 백업 시스템 선택을 전달한다.

| API | 용도 |
|---|---|
| `GET /api/system/setup` | 설치 완료 여부, local master, Docker/Swarm/nginx 감지 상태 조회 |
| `POST /api/system/setup` | 관리자 비밀번호 저장, local master 등록, 백업 시스템 선택 저장 |
| `POST /api/auth/login` | ID 없이 password만 제출하는 단일 관리자 로그인 |
| `GET /api/auth/session` | 현재 session 상태 조회 |
| `POST /api/auth/logout` | session revoke와 cookie clear |

session cookie name, secure, SameSite 같은 설정은 base controller가 아니라 `config/boot.py`의 `before_request`, `after_request`, `bootstrap` 흐름에서 관리한다.

운영 중 관리자 비밀번호 변경은 시스템 설정의 General 탭에서 현재 비밀번호를 확인한 뒤 `operator_auth`의 단일 관리자 비밀번호 hash를 갱신한다.

Browser title, favicon, logo는 session API에 포함하지 않는다. Angular 앱 부트 시 `/api/system/appearance`를 1회 호출하고 runtime cache에 저장한다.

`/access` 화면은 password login만 제공한다. 초기 설정이 끝나지 않은 경우 제품 내부 setup form을 노출하지 않고 installer URL을 안내한다.

## 5. 시스템 설정

`/system` 화면은 다음을 관리한다.

- Browser title
- Favicon upload
- Logo upload
- 내장 백업 시스템 상태
- 백업 storage 사용량과 남은 용량
- 미사용 이미지 정리 정책
- 서비스가 사용하지 않는 이미지 정리 실행
- 위험 작업 audit log

Favicon과 Logo는 URL을 설정값으로 저장하지 않는다. 업로드 시 WIZ root `data/system-assets/` 아래의 고정 파일을 교체하고, 브라우저는 고정 endpoint를 요청한다.

등록 서버 밖의 registry 연동, 소스 저장소 연동, nginx 경로 편집, SSL 인증서 업로드는 시스템 설정에서 제공하지 않는다.

## 6. Operation Log

별도 다단계 작업 큐는 사용하지 않는다. 긴 작업은 API에서 직접 실행하고 필요한 출력만 streaming 또는 polling으로 화면에 표시한다.

저장 단위:

| 로그 | 목적 |
|---|---|
| `operation_logs` | 배포, nginx reload, certbot, 이미지 삭제, 백업 정리 결과 요약 |
| `audit_logs` | 위험 작업의 요청, 대상, 결과 |
| streaming output | 매크로, 터미널, 배포, certbot 등 화면 표시용 실시간 출력 |

operation log에는 secret 원문을 저장하지 않는다. 실패 응답은 사용자가 바로 조치할 수 있는 메시지와 내부 오류 요약을 함께 제공한다.

## 7. Local Executor

Local Executor는 Docker Infra host에서 명령을 실행한다. 명령은 allowlist 기반으로 제한한다.

| Command ID | 예시 | 분류 |
|---|---|---|
| `docker.info` | `docker info --format '{{json .}}'` | safe |
| `docker.version` | `docker version --format '{{json .}}'` | safe |
| `swarm.info` | `docker info --format '{{json .Swarm}}'` | safe |
| `swarm.nodes` | `docker node ls --format '{{json .}}'` | safe |
| `nginx.configtest` | `nginx -t` | safe |
| `nginx.reload` | `systemctl reload nginx` | destructive allowlist 필요 |
| `container.start` | `docker start` | destructive allowlist 필요 |
| `container.stop` | `docker stop` | destructive allowlist 필요 |
| `container.restart` | `docker restart` | destructive allowlist 필요 |

실행 결과는 `status`, `exit_code`, `stdout`, `stderr`, `duration_ms`, `timed_out`, `operation_id`를 포함한다.

## 8. 서버 API

서버 등록은 password를 이용해 최초 접속 가능성을 확인한 뒤 관리용 SSH key를 준비한다. password는 DB에 저장하지 않는다.

| API | 용도 |
|---|---|
| `GET /api/nodes` | 서버 목록과 요약 상태 |
| `POST /api/nodes` | 서버 등록, SSH check, key 준비 |
| `PATCH /api/nodes/{id}` | 서버 정보 수정과 재점검 |
| `GET /api/nodes/{id}` | 서버 상세 기본 정보 |
| `GET /api/nodes/{id}/metrics` | CPU, memory, storage 최신 metric |
| `GET /api/nodes/{id}/containers` | 컨테이너 목록 |
| `POST /api/nodes/{id}/containers/{container_id}/action` | start/stop/restart |
| `POST /api/nodes/{id}/join` | Swarm join 실행 |
| `WS /api/nodes/{id}/terminal` | SSH PTY 중계 |

상세 화면에서 자동 갱신은 metric 전용 API만 사용한다.

## 9. 서비스 API

서비스 생성은 마법사 payload를 기준으로 동작한다.

| API | 용도 |
|---|---|
| `GET /api/services` | 서비스 목록 |
| `POST /api/services/wizard/preview` | form 값으로 Compose/nginx/도메인 연결 미리보기 |
| `POST /api/services` | 서비스 생성 |
| `GET /api/services/{id}` | 서비스 상세 |
| `PATCH /api/services/{id}` | 서비스 수정 |
| `POST /api/services/{id}/deploy` | 배포 실행 |
| `POST /api/services/{id}/rollback` | Compose/image 버전 기준 rollback |
| `GET /api/services/{id}/operations` | 서비스 operation history |
| `POST /api/services/{id}/domains` | 서비스와 도메인 연결 |
| `PATCH /api/services/{id}/domains/{domain_id}` | 도메인 연결 수정 |
| `DELETE /api/services/{id}/domains/{domain_id}` | 도메인 연결 삭제 |

배포 output은 operation_id 기준으로 streaming 또는 polling한다.

## 10. nginx, 도메인, SSL

nginx 기본값:

- daemon: `nginx`
- main config: `/etc/nginx/nginx.conf`
- sites available: `/etc/nginx/sites-available`
- sites enabled: `/etc/nginx/sites-enabled`
- config test: `nginx -t`
- reload: `systemctl reload nginx`

서비스-도메인 연결은 폼으로 처리한다.

1. 등록 도메인 선택 또는 신규 도메인 추가
2. 내부 port 선택
3. SSL 방식 선택
4. 연결 미리보기 표시
5. `service_domains` 저장
6. nginx server block 생성
7. `nginx -t`
8. reload
9. 실패 시 이전 설정 복원

원문 nginx config 편집은 고급 모드에만 제공한다.

도메인 API:

| API | 용도 |
|---|---|
| `GET /api/domains` | 도메인 목록 |
| `POST /api/domains` | 도메인 등록 |
| `POST /api/domains/{id}/sync` | Cloudflare DNS record 동기화 |
| `POST /api/domains/{id}/records` | DNS record 생성 |
| `PATCH /api/domains/{id}/records/{record_id}` | DNS record 수정 |
| `DELETE /api/domains/{id}/records/{record_id}` | DNS record 삭제 |
| `POST /api/domains/{id}/certificates` | 인증서 업로드와 분석 |
| `GET /api/domains/{id}/certificates` | 인증서 상태 조회 |

## 11. 내장 백업 시스템

백업 시스템은 사용자가 등록하는 외부 registry가 아니라 마스터 노드에 Docker Infra가 직접 실행하는 선택형 Harbor다.

| API | 용도 |
|---|---|
| `GET /api/system/backup` | 상태, 용량, 사용량 |
| `POST /api/system/backup/enable` | Harbor Compose 실행 |
| `POST /api/system/backup/disable` | 백업 시스템 중지 |
| `POST /api/system/backup/restart` | 재시작 |
| `POST /api/system/backup/cleanup-unused` | 미사용 백업 이미지 삭제 |
| `GET /api/services/{id}/backups` | 서비스별 백업 버전 |
| `POST /api/services/{id}/backups` | 현재 서비스 이미지 백업 |
| `POST /api/services/{id}/backups/{backup_id}/restore` | 백업 버전 복원 |

사용자는 Harbor 계정과 token을 직접 다루지 않는다.

## 12. 이미지와 서비스 초안

이미지 화면은 로컬 이미지와 백업 이미지를 구분한다.

- 로컬 이미지: 서버별 repository/tag/size/created/last used/use status
- 백업 이미지: 서비스별 백업 버전, digest, size, created
- 삭제 전 영향 서비스 표시
- 일괄 삭제는 확인 모달과 audit log 필요

서비스 생성은 AI 초안, Compose 직접 작성, 서버 Compose 가져오기 중 하나로 시작한다. Compose 원문은 생성 화면의 초안 입력과 서비스 상세의 고급 관리 화면에서만 직접 수정한다.

## 13. 테스트 방향

P0 이후 테스트는 다음 기준으로 재작성한다.

- 최초 구성 마법사
- 서버 추가와 SSH key 준비
- 서비스 생성 마법사
- 도메인 연결과 nginx preview
- 인증서 업로드
- certbot 실행 output
- 로컬 이미지 삭제
- 백업 시스템 enable/disable
- 서비스 이미지 백업과 복원

테스트 cleanup은 더 이상 다단계 작업 큐 cancel/wait에 의존하지 않는다. 생성한 DB row, Docker container/stack, nginx sandbox file, DNS record, data directory fixture를 직접 정리한다.
