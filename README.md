# Docker Infra

[한국어](#한국어) | [English](#english)

## 한국어

### 개요

Docker Infra는 Ubuntu 24.04 기반 단일 운영 장비에서 Docker 서비스를 운영하기 위한 WIZ 웹 서비스입니다. 대상 사용자는 개발자가 아니라 전산 담당자 또는 일반 관리자입니다. IP, port, domain, image tag 정도만 알고 있어도 서버 등록, 서비스 배포, 도메인 연결, 인증서 적용, 이미지 정리를 처리할 수 있도록 하는 것이 목표입니다.

현재 기준의 제품 방향은 다음과 같습니다.

- Docker Infra가 실행되는 서버를 자동으로 local master로 등록합니다.
- nginx는 Ubuntu 24.04 기본 nginx와 sites 디렉터리를 기준으로 사용합니다.
- Compose YAML과 nginx 원문은 고급 모드에 두고, 기본 흐름은 마법사와 폼으로 제공합니다.
- 소스 저장소 연동, Docker build, registry push 파이프라인은 제공하지 않습니다.
- 서비스는 이미 존재하는 Docker image를 선택해 Docker Compose/Swarm 기반으로 배포합니다.
- Harbor는 외부 registry 관리 화면이 아니라 선택형 내장 이미지 백업/버전 관리 시스템으로 사용합니다.
- 긴 작업 결과는 operation log, audit log, polling/stream output으로 확인합니다.

### 핵심 기능

| 영역 | 현재 기능 |
|---|---|
| 최초 구성 | installer HTML에서 관리자 비밀번호, local master, 서비스 루트, 백업 시스템 선택을 설정 |
| 인증 | ID 없는 단일 관리자 password-only 로그인, session cookie 기반 인증 |
| 서버 관리 | local master 자동 등록, 원격 서버 SSH password 최초 확인, 관리용 SSH key 설치, fingerprint 저장, Docker/Swarm 상태 확인 |
| 서비스 관리 | AI 초안, Compose 직접 작성, 서버 Compose 가져오기, 파일 기반 Compose 템플릿 기반 생성/수정 |
| 배포 | 이미지/포트/볼륨/도메인 사전 점검, 자동 배치, stack deploy, 배포 상태 polling, rollback, 서버 마이그레이션 |
| 도메인/SSL | Cloudflare DNS record, DDNS endpoint, 업로드 인증서, certbot 무료 인증서, nginx server block 자동 생성/검증/rollback |
| 이미지/백업 | 서버별 로컬 이미지 목록/정리, 내장 Harbor 백업, 서비스 이미지 백업/복원, 컨테이너 snapshot 기반 이관 |
| 시스템 설정 | 브라우저 title, favicon/logo, AI Agent 설정과 설치 스크립트 실행, 백업 정책, 이미지 정리 정책 |
| AI 보조 | Codex/Claude Code/헤르메스 Agent 기반 서비스 생성/수정/검증/복구 보조, Compose 템플릿 초안 생성 |

### 범위와 비범위

Docker Infra는 운영자가 이미 준비된 이미지를 안정적으로 배포하고 관리하는 데 집중합니다. Kubernetes, 멀티 마스터 Swarm, 사용자/RBAC, 소스 빌드 파이프라인, 일반 사용자가 직접 관리하는 외부 registry 프로젝트, 다른 웹서버 선택 기능은 현재 범위에 포함하지 않습니다.

### 프로젝트 구조

```text
project/main/
  config/                 # Docker Infra runtime config
  src/
    app/                  # WIZ Angular pages, layouts, components
    controller/           # 인증/권한 controller
    model/                # DB, struct, runtime business logic
    route/                # REST route handlers
    portal/season/        # WIZ portal package
  docs/                   # 설계, 런타임, 배포 문서
  installer/              # 운영 설치 파일과 payload
  tests/                  # API/E2E/static contract tests
  devlog.md
  devlog/
```

Source app과 route는 `src/app`, `src/route` 아래에 둡니다. 화면 전용 API는 각 app의 `api.py`에서 WIZ 응답 규칙을 지켜 작성하고, 도메인 로직은 `src/model/struct.py` 진입점을 통해 호출합니다.

### 런타임 데이터

운영 데이터는 저장소 소스와 분리합니다.

| 용도 | 개발/기본 경로 | 운영 installer 경로 |
|---|---|---|
| 시스템 favicon/logo | `/root/docker-infra/data/system-assets/` | `/var/lib/docker-infra/data/system-assets/` |
| 도메인 인증서 | `/root/docker-infra/data/domain-certificates/` | `/var/lib/docker-infra/data/domain-certificates/` |
| 관리용 SSH key | `/root/docker-infra/data/ssh/` 또는 config 값 | `/var/lib/docker-infra/ssh/` |
| 내장 Harbor data | `/root/docker-infra/data/backup-harbor/` | `/var/lib/docker-infra/backup-harbor/` |
| 서비스 Compose 파일 | `.runtime/dev/services` | installer setup의 service root |
| Codex home | runtime env/default | `/var/lib/docker-infra/codex-home/` |

Codex, Claude Code, 헤르메스 Agent CLI는 installer 기본 설치에 포함하지 않습니다. 운영 설치 후 관리자가 시스템 설정의 AI Agent 탭에서 각 Agent 설치/업데이트 스크립트를 실행합니다.

### 운영 설치

대상 OS는 Ubuntu 24.04입니다. installer는 `preinstall`과 `install` 두 단계로 나뉩니다.

```bash
sudo project/main/installer/preinstall.sh
```

위 명령은 nginx, installer HTML, local installer API를 준비합니다. 기본 설치 화면은 다음 주소에서 열립니다.

```text
http://<host>:8088
```

설치 화면에서 관리자 비밀번호와 초기 설정을 입력한 뒤 전체 설치를 실행하거나, CLI로 같은 단계를 실행할 수 있습니다.

```bash
sudo /opt/docker-infra/installer/install.sh --step all
```

주요 단계는 `apt`, `env`, `postgres`, `python`, `node`, `bundle`, `migrate`, `service`, `setup`, `nginx`, `verify`, `cleanup`입니다. `verify`가 성공한 뒤 installer 화면의 정리 단계 또는 다음 명령으로 설치 관리자 파일을 제거합니다.

```bash
sudo /opt/docker-infra/installer/install.sh --step cleanup
```

중간 실패나 재설치 파일 정리는 다음 스크립트를 사용합니다. 이 스크립트는 apt, pip, npm, PostgreSQL, Node.js package를 제거하지 않습니다.

```bash
sudo /opt/docker-infra/installer/cleanup.sh --scope preinstall
sudo /opt/docker-infra/installer/cleanup.sh --scope install
sudo /opt/docker-infra/installer/cleanup.sh --scope all
```

소스 변경 후 installer payload의 WIZ bundle만 갱신할 때는 WIZ workspace root에서 실행합니다.

```bash
./update-wiz-bundle.sh
```

이미 설치된 서버는 갱신된 archive만 복사한 뒤 WIZ service 파일과 process만 교체할 수 있습니다.

```bash
scp project/main/installer/payload/wiz-bundle.tar.zst user@host:/tmp/
ssh user@host 'cd /root/docker-infra && sudo ./update-wiz-service.sh /tmp/wiz-bundle.tar.zst'
```

### 개발과 검증

이 프로젝트의 Python/WIZ 자동화는 Docker Infra conda 환경의 실행 파일을 우선 사용합니다.

```bash
/opt/conda/envs/docker-infra/bin/python -m unittest discover tests/api
/opt/conda/envs/docker-infra/bin/wiz project build --project main
```

개발 DB와 테스트 compose는 다음 명령으로 실행합니다.

```bash
docker compose -f docker/compose/development.yaml up -d postgres
docker compose -f docker/compose/test.yaml --profile api run --rm api-tests
docker compose -f docker/compose/test.yaml --profile proxy run --rm proxy-sandbox
```

installer 계약만 빠르게 확인할 때는 다음을 사용합니다.

```bash
/opt/conda/envs/docker-infra/bin/python -m unittest tests/api/test_installer_contract.py
bash -n installer/preinstall.sh installer/install.sh installer/cleanup.sh
(cd installer/payload && sha256sum -c checksums.sha256)
```

### 보안 원칙

- 관리자 password는 hash로 저장하고 원문을 DB/API/devlog/log에 남기지 않습니다.
- 원격 서버 최초 SSH password는 key 설치와 연결 확인에만 사용하고 저장하지 않습니다.
- 관리용 SSH private key 파일은 runtime data directory에 두며 GitHub 업로드 대상에 포함하지 않습니다.
- Cloudflare token, DDNS key, AI Agent 세션/설정 secret, backup system secret은 암호화 저장하거나 runtime data directory에 두고 API 응답에서는 마스킹합니다.
- operation log, audit log, installer log에는 password/token/key 원문을 남기지 않는 것을 기준으로 합니다.
- `/root/docker-infra/config.env`와 `/root/docker-infra/domain.txt`는 로컬 통합 secret 파일이므로 저장소, 문서, devlog, 최종 응답에 값을 출력하지 않습니다.

### 문서

- 전체 설계: `docs/docker-infra-design.md`
- 런타임 기준: `docs/docker-infra-runtime.md`
- 배포 설치 기준: `docs/docker-infra-deployment.md`
- Compose 템플릿 표준: `docs/compose-template-standard.md`
- 서비스 AI/Codex Agent 설계: `docs/service-ai-codex-agent-design.md`
- 전체 TODO: `docs/docker-infra-development-todo.md`
- 남은 TODO: `docs/docker-infra-remaining-todo.md`

### 라이선스

MIT License. 자세한 내용은 `LICENSE`를 확인하세요.

## English

### Overview

Docker Infra is a WIZ web service for operating Docker services on a single Ubuntu 24.04 host. It is designed for IT operators and general administrators rather than application developers. The goal is to let an operator register servers, deploy services, connect domains, apply certificates, and clean images with only practical knowledge of IP addresses, ports, domains, and image tags.

The current product direction is:

- The host running Docker Infra is automatically registered as the local master.
- nginx is fixed to the default Ubuntu 24.04 nginx layout and service name.
- Compose YAML and raw nginx config stay in advanced mode. The default workflow uses forms and wizards.
- Source repository integration, Docker build, and registry push pipelines are out of scope.
- Services are deployed from existing Docker images with Docker Compose/Swarm.
- Harbor is used as an optional built-in image backup and version store, not as a generic external registry console.
- Long-running work is surfaced through operation logs, audit logs, polling, and stream output.

### Main Features

| Area | Current support |
|---|---|
| Initial setup | Installer HTML sets the admin password, local master, service root, and backup system option |
| Authentication | Single password-only admin login with session cookies |
| Servers | Automatic local master registration, first SSH password check, managed SSH key installation, fingerprint storage, Docker/Swarm checks |
| Services | AI draft, direct Compose authoring, server Compose import, file-based Compose templates |
| Deployment | Image/port/volume/domain preflight, automatic placement, stack deploy, deployment polling, rollback, server migration |
| Domains/SSL | Cloudflare DNS records, DDNS endpoints, uploaded certificates, certbot certificates, automatic nginx server block generation and rollback |
| Images/backup | Local image inventory and cleanup, built-in Harbor backup, service image backup/restore, container snapshot migration |
| System settings | Browser title, favicon/logo, AI Agent settings and install-script execution, backup and image cleanup policies |
| AI assistant | Codex/Claude Code/Hermes Agent based service creation/editing/verification/repair support, Compose template drafting |

### Scope

Docker Infra focuses on deploying and operating already-built images. Kubernetes, multi-master Swarm, user/RBAC management, source build pipelines, generic external registry administration, and alternative web server selection are not part of the current scope.

### Project Layout

```text
project/main/
  config/                 # Docker Infra runtime config
  src/
    app/                  # WIZ Angular pages, layouts, components
    controller/           # auth/permission controllers
    model/                # DB, struct, runtime business logic
    route/                # REST route handlers
    portal/season/        # WIZ portal package
  docs/                   # design, runtime, deployment docs
  installer/              # production installer files and payload
  tests/                  # API/E2E/static contract tests
  devlog.md
  devlog/
```

Source apps and routes live under `src/app` and `src/route`. Page-local APIs follow WIZ response conventions in each app's `api.py`, while domain logic is reached through `src/model/struct.py`.

### Runtime Data

Runtime data is kept outside source files.

| Purpose | Dev/default path | Installer path |
|---|---|---|
| System favicon/logo | `/root/docker-infra/data/system-assets/` | `/var/lib/docker-infra/data/system-assets/` |
| Domain certificates | `/root/docker-infra/data/domain-certificates/` | `/var/lib/docker-infra/data/domain-certificates/` |
| Managed SSH keys | `/root/docker-infra/data/ssh/` or config value | `/var/lib/docker-infra/ssh/` |
| Built-in Harbor data | `/root/docker-infra/data/backup-harbor/` | `/var/lib/docker-infra/backup-harbor/` |
| Service Compose files | `.runtime/dev/services` | Service root selected during installer setup |
| Codex home | runtime env/default | `/var/lib/docker-infra/codex-home/` |

Codex, Claude Code, and Hermes Agent CLIs are not part of the default installer flow. After installation, an administrator runs each Agent install/update script from the System settings AI Agent tab.

### Production Install

The target OS is Ubuntu 24.04. The installer has a `preinstall` phase and an `install` phase.

```bash
sudo project/main/installer/preinstall.sh
```

This starts nginx, the installer HTML, and the local installer API. The default installer page is:

```text
http://<host>:8088
```

Enter the admin password and initial settings in the installer page, then run the full install from the page or with the CLI:

```bash
sudo /opt/docker-infra/installer/install.sh --step all
```

The deployment steps are `apt`, `env`, `postgres`, `python`, `node`, `bundle`, `migrate`, `service`, `setup`, `nginx`, `verify`, and `cleanup`. After `verify` succeeds, remove the installer through the page or with:

```bash
sudo /opt/docker-infra/installer/install.sh --step cleanup
```

For failed installs or file-artifact rollback, use:

```bash
sudo /opt/docker-infra/installer/cleanup.sh --scope preinstall
sudo /opt/docker-infra/installer/cleanup.sh --scope install
sudo /opt/docker-infra/installer/cleanup.sh --scope all
```

To refresh only the installer WIZ bundle payload after source changes, run this from the WIZ workspace root:

```bash
./update-wiz-bundle.sh
```

For an already installed server, copy only the refreshed archive and replace the WIZ service files/process:

```bash
scp project/main/installer/payload/wiz-bundle.tar.zst user@host:/tmp/
ssh user@host 'cd /root/docker-infra && sudo ./update-wiz-service.sh /tmp/wiz-bundle.tar.zst'
```

### Development and Verification

Use the Docker Infra conda environment explicitly for Python and WIZ automation.

```bash
/opt/conda/envs/docker-infra/bin/python -m unittest discover tests/api
/opt/conda/envs/docker-infra/bin/wiz project build --project main
```

Development and test compose commands:

```bash
docker compose -f docker/compose/development.yaml up -d postgres
docker compose -f docker/compose/test.yaml --profile api run --rm api-tests
docker compose -f docker/compose/test.yaml --profile proxy run --rm proxy-sandbox
```

Fast installer contract checks:

```bash
/opt/conda/envs/docker-infra/bin/python -m unittest tests/api/test_installer_contract.py
bash -n installer/preinstall.sh installer/install.sh installer/cleanup.sh
(cd installer/payload && sha256sum -c checksums.sha256)
```

### Security Notes

- The admin password is stored as a hash and must not be written as plaintext to DB/API/devlog/log output.
- The first SSH password for remote nodes is used only for key setup and connection verification. It is not stored.
- Managed SSH private key files belong in the runtime data directory and must not be uploaded to GitHub.
- Cloudflare tokens, DDNS keys, AI Agent session/config secrets, and backup system secrets are encrypted at rest or kept in the runtime data directory and masked in API responses.
- Operation logs, audit logs, and installer logs should not contain plaintext passwords, tokens, or keys.
- `/root/docker-infra/config.env` and `/root/docker-infra/domain.txt` are local integration secret files. Their values must not be copied into the repository, docs, devlogs, tests, or final responses.

### Documentation

- Design: `docs/docker-infra-design.md`
- Runtime notes: `docs/docker-infra-runtime.md`
- Deployment installer: `docs/docker-infra-deployment.md`
- Compose template standard: `docs/compose-template-standard.md`
- Service AI/Codex Agent design: `docs/service-ai-codex-agent-design.md`
- Full TODO: `docs/docker-infra-development-todo.md`
- Remaining TODO: `docs/docker-infra-remaining-todo.md`

### License

MIT License. See `LICENSE`.
