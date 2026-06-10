# Docker Infra 배포 설치 기준

- 문서 상태: 배포 준비용 installer 초안
- 기준일: 2026-05-20

## 설치 방식

운영 배포는 개발용 PostgreSQL 컨테이너를 사용하지 않는다. `preinstall.sh`로 nginx와 설치 화면을 먼저 띄우고, 설치 화면 또는 `install.sh`로 host PostgreSQL, OS 패키지, PIP 패키지, Node.js LTS/npm runtime, WIZ bundle, systemd service, 관리자 비밀번호와 초기 시스템 설정을 순서대로 구성한다. Codex, Claude Code, 헤르메스 Agent CLI는 기본 설치에 포함하지 않고, 설치 완료 후 관리자가 시스템 설정에서 설치/업데이트 스크립트를 실행한다.

`project/main/installer/`는 단독 반출 가능한 설치 단위다. `payload/`에는 WIZ bundle archive, Python requirements, checksum 파일이 포함되며, 운영 host는 개발 workspace 없이 이 디렉터리만으로 설치를 진행한다. 설치 중 payload를 사용하기 전 `sha256sum -c`로 무결성을 확인한다.

소스 변경 후 installer의 WIZ bundle payload만 최신 코드로 갱신할 때는 WIZ root에서 다음 관리 스크립트를 실행한다. 이 스크립트는 현재 `bundle/` directory를 `payload/wiz-bundle.tar.zst`로 다시 묶고 `payload/checksums.sha256`을 갱신한다.

```bash
./update-wiz-bundle.sh
```

이미 Docker Infra가 설치된 원격 서버는 전체 installer를 다시 가져가지 않고 갱신된 archive만 복사해 WIZ service 파일과 service process만 교체할 수 있다. `update-wiz-service.sh`도 WIZ root에 둔다.

```bash
scp project/main/installer/payload/wiz-bundle.tar.zst user@host:/tmp/
ssh user@host 'cd /root/docker-infra && sudo ./update-wiz-service.sh /tmp/wiz-bundle.tar.zst'
```

```bash
sudo project/main/installer/preinstall.sh
sudo /opt/docker-infra/installer/install.sh --step all
```

설치 화면은 기본적으로 `http://<host>:8088`에서 열리며, installer nginx site를 통해 local installer API를 호출한다.

## 단계

| 단계 | 내용 |
|---|---|
| `apt` | `nginx`, `postgresql`, `docker.io`, `docker-compose-plugin`, `certbot`, `network-manager`, runtime package 설치 |
| `env` | `/etc/docker-infra/docker-infra.env` 생성, `/var/lib/docker-infra` runtime directory 준비 |
| `postgres` | `docker_infra` role/database/schema 생성 및 password 설정 |
| `python` | `requirements.txt`의 WIZ/Python runtime dependency 설치 |
| `node` | NodeSource LTS setup으로 Node.js/npm runtime만 설치 |
| `bundle` | installer payload의 WIZ bundle archive에서 `bundle/config`, `bundle/public`, `bundle/plugin`, `bundle/project/main/bundle`만 `/opt/docker-infra/wiz`로 배포 |
| `migrate` | `src/model/db/migration.py`의 migration을 적용해 운영 DB 테이블을 준비 |
| `service` | `wiz.docker-infra.service`를 등록하고 `EnvironmentFile=/etc/docker-infra/docker-infra.env` drop-in을 추가 |
| `setup` | installer HTML의 관리자 password, local master, service root, 백업 저장소 선택을 `/api/system/setup`으로 적용 |
| `nginx` | nginx reverse proxy를 `127.0.0.1:3000` WIZ service로 연결 |
| `verify` | PostgreSQL, WIZ service, `/api/system/setup`의 DB 설정 및 초기 설정 완료 상태 확인 |
| `cleanup` | 설치 완료 후 installer API daemon, installer nginx site, HTML/payload, 임시 setup 파일 삭제 |

## 설치 파일 정리

중간 설치 실패나 재설치를 위해 `installer/cleanup.sh`를 제공한다. 이 script는 apt, pip, npm, PostgreSQL, Node.js package를 제거하지 않고, installer/WIZ 배포가 만든 file artifact만 정리한다.

```bash
sudo /opt/docker-infra/installer/cleanup.sh --scope preinstall
sudo /opt/docker-infra/installer/cleanup.sh --scope install
sudo /opt/docker-infra/installer/cleanup.sh --scope all
```

- `preinstall`: installer API service, installer nginx site, installer HTML/payload, env 제거
- `install`: WIZ service unit/drop-in, app nginx site, deployed bundle, runtime env 제거
- `--purge-data`, `--purge-logs`: 명시한 경우에만 runtime data/log directory까지 제거

## 환경변수 파일

운영 service는 systemd `EnvironmentFile`과 WIZ root의 `config.env` symlink를 같이 사용한다. 앱 코드의 `config/docker_infra.py`도 같은 값을 읽으므로 daemon, CLI migration, WIZ runtime의 설정 출처가 일치한다.

주요 값:

- `DOCKER_INFRA_DB_*`: host PostgreSQL 접속 정보
- `DOCKER_INFRA_SECRET_KEY`: session/암호화용 secret
- `DOCKER_INFRA_DATA_DIR`, `DOCKER_INFRA_SSH_KEY_DIR`, `DOCKER_INFRA_BACKUP_HARBOR_DATA_DIR`: 운영 데이터 저장 경로
- `DOCKER_INFRA_SYSTEM_CODEX_BIN`: 시스템 설정 설치 스크립트 또는 관리자가 설치한 Codex CLI 경로
- `DOCKER_INFRA_CLAUDE_CODE_BIN`: Claude Code CLI 경로
- `DOCKER_INFRA_HERMES_AGENT_BIN`: 헤르메스 에이전트 CLI 경로
- `DOCKER_INFRA_CODEX_INSTALL_SCRIPT`, `DOCKER_INFRA_CLAUDE_CODE_INSTALL_SCRIPT`, `DOCKER_INFRA_HERMES_AGENT_INSTALL_SCRIPT`: 시스템 설정에서 실행할 Agent별 설치 스크립트 override
- `DOCKER_INFRA_CLAUDE_CODE_INSTALL_URL`, `DOCKER_INFRA_CLAUDE_CODE_INSTALL_CHANNEL`: Claude Code 설치 스크립트 URL과 release channel override
- `DOCKER_INFRA_HERMES_AGENT_INSTALL_URL`, `DOCKER_INFRA_HERMES_AGENT_INSTALL_CHANNEL`: Hermes Agent 설치 스크립트 URL과 release channel override
- `CODEX_HOME`: Codex 로그인 세션 저장 경로
- `CLAUDE_HOME`, `HERMES_HOME`: 각 Agent CLI의 Docker Infra 고정 세션/설정 저장 경로
- `DOCKER_INFRA_DDNS_PUBLIC_IP_URLS`: DDNS 갱신 시 공인 IP를 조회할 HTTP endpoint 목록
- `DOCKER_INFRA_DDNS_STATE_FILE`: NetworkManager dispatcher가 마지막으로 DDNS API에 보낸 IP를 저장하는 파일
- `DOCKER_INFRA_DDNS_DISPATCHER_*`: Ubuntu 24.04 NetworkManager dispatcher 설치 경로와 자동 설치 여부

Agent CLI는 installer가 자동 설치하지 않는다. 관리자는 시스템 설정의 AI Agent 탭에서 Codex, Claude Code, 헤르메스 설치/업데이트 스크립트를 실행하고 모델만 선택한다. 실행 파일 탐색, Agent HOME, 명령 템플릿은 Docker Infra 기본값으로 고정한다. AI 실행은 Agent CLI와 Docker Infra MCP 기반으로만 수행하며 Docker Infra는 LLM provider API를 직접 호출하지 않는다. MCP 권한은 `agent_full_control_except_critical_destruction` 기준으로 운영되며, Agent는 등록 서버를 넓게 제어할 수 있지만 Docker Infra 자체 삭제, control service/container 제거, OS shutdown/reboot/wipe/format, OS critical path 재귀 삭제는 차단된다.

## 최초 관리자 비밀번호

관리자 password와 초기 시스템 설정은 제품 접속 화면이 아니라 installer HTML에서 입력한다. installer API는 입력 payload를 `/etc/docker-infra/initial-setup.json`에 `0600` 권한으로 임시 저장한 뒤 `install.sh --step setup`에서 local WIZ service의 `/api/system/setup`으로 전달하고, 성공하면 해당 파일을 삭제한다.

제품의 `/access` 화면은 더 이상 설정 마법사를 제공하지 않는다. `operator_auth`가 비어 있거나 local master/system setting이 완성되지 않은 경우 `/access`는 installer URL만 안내한다.

설치 이후 관리자 password 변경은 시스템 설정의 General 탭에서 처리한다.

## 민감정보 처리 기준

- `/root/docker-infra/config.env`와 `/root/docker-infra/domain.txt`는 로컬 통합 secret 파일이므로 저장소, 문서, devlog, 테스트 출력에 값을 남기지 않는다.
- installer는 운영 DB password와 secret key를 `/etc/docker-infra/docker-infra.env`에 `0640` 권한으로 저장하고, 이 파일을 GitHub 업로드 대상으로 보지 않는다.
- PostgreSQL role password 설정은 password 원문이 shell debug log나 process argument에 남지 않도록 표준 입력으로 SQL을 전달한다.
- installer HTML의 관리자 password payload는 `initial-setup.json`에 `0600` 권한으로 임시 저장하고 `setup` 성공 후 삭제한다.
- SSH private key, API token, DDNS key, AI Agent 세션/설정 secret 원문은 API 응답, operation log, audit log, installer log, devlog에 기록하지 않는다.

## DDNS 공인 IP 갱신

도메인 관리 화면에서 DDNS 서버 API를 등록하면 서비스 도메인 배포 시 Docker Infra는 공인 IP를 조회한 뒤 다음 계약으로 중간 DDNS API를 호출한다.

```bash
curl -sS -X POST "http://ddns.nanoha.kr/api/ddns/update" \
  -H "Content-Type: application/json" \
  -H "X-DDNS-Key: <issued-ddns-key>" \
  -d '{"hostname":"app.sub.season.co.kr","ip":"203.0.113.10","record_type":"A"}'
```

서비스 도메인이 DDNS로 등록되면 Ubuntu 24.04 기준 NetworkManager dispatcher script도 함께 설치된다. Dispatcher는 네트워크 up, DHCP 변경, connectivity 변경 이벤트에서 공인 IP를 다시 조회하고, `DOCKER_INFRA_DDNS_STATE_FILE`에 저장된 마지막 전송 IP와 다를 때만 DDNS API를 호출한다.

## 설치 관리자 종료

`verify`가 성공한 뒤 installer HTML의 `설치 관리자 정리` 단계를 실행한다. 이 단계는 별도 cleanup script를 예약한 후 `docker-infra-installer.service`, `/etc/nginx/sites-available/docker-infra-installer.conf`, `/opt/docker-infra/installer`, `/etc/docker-infra/initial-setup.json`을 제거한다.

## 남은 운영 확인

- 실제 도메인/HTTPS 배포 시 `DOCKER_INFRA_SESSION_COOKIE_SECURE=true`로 바꾸고 nginx TLS server block을 별도로 적용한다.
- installer API는 설치 전용이므로 배포 완료 후 `cleanup` 단계 실행 여부를 확인한다.
- 기존 운영 DB에서 재설치하는 경우 `install.sh --step migrate` 전에 DB backup을 먼저 수행한다.
