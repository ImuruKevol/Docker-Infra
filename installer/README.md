# Docker Infra Installer

[한국어](#한국어) | [English](#english)

## 한국어

### 목적

`project/main/installer/`는 Ubuntu 24.04 운영 서버에 Docker Infra를 설치하기 위한 단독 설치 단위입니다. 개발 workspace 없이도 설치할 수 있도록 WIZ bundle archive, Python requirements, checksum 파일을 `payload/`에 포함합니다.

### 빠른 실행

```bash
sudo project/main/installer/preinstall.sh
```

위 명령은 nginx, installer HTML, local installer API를 `/opt/docker-infra/installer`에 복사하고 기본 `8088` 포트에 설치 화면을 엽니다.

```text
http://<host>:8088
```

설치 화면에서 관리자 비밀번호, 중심 서버 공개 주소, 서비스 루트, 백업 시스템 사용 여부를 입력한 뒤 전체 설치를 실행합니다. CLI로도 같은 설치를 실행할 수 있습니다.

```bash
sudo /opt/docker-infra/installer/install.sh --step all
```

`verify`가 성공한 뒤 설치 화면의 `설치 관리자 정리` 단계 또는 다음 명령을 실행합니다.

```bash
sudo /opt/docker-infra/installer/install.sh --step cleanup
```

### 설치 단계

| 단계 | 내용 |
|---|---|
| `all` | `cleanup`을 제외한 운영 설치 단계를 순서대로 실행 |
| `apt` | nginx, PostgreSQL, Docker, Compose plugin, certbot, NetworkManager, Python, zstd 등 OS package 설치 |
| `env` | `/etc/docker-infra/docker-infra.env` 생성과 `/var/lib/docker-infra` runtime directory 준비 |
| `postgres` | PostgreSQL role, database, schema 생성과 password 설정 |
| `python` | payload의 `requirements.txt`로 Python/WIZ runtime dependency 설치 |
| `node` | NodeSource LTS setup으로 Node.js/npm 설치 후 공식 `@openai/codex` global 설치 |
| `bundle` | payload의 `wiz-bundle.tar.zst`를 검증하고 `/opt/docker-infra/wiz`로 배포 |
| `migrate` | 배포된 bundle의 DB migration 적용 |
| `service` | `wiz.docker-infra.service` systemd unit 등록, env drop-in 추가, WIZ service 시작 |
| `setup` | installer HTML이 저장한 초기 설정을 `/api/system/setup`에 적용 |
| `nginx` | Docker Infra 앱 reverse proxy를 nginx에 등록 |
| `verify` | PostgreSQL, WIZ service, setup 완료 상태 확인 |
| `cleanup` | installer API daemon, installer nginx site, HTML/payload, 임시 setup 파일 제거 |

### Payload 갱신

소스 변경 후 installer payload의 WIZ bundle만 최신 상태로 갱신할 때는 WIZ workspace root에서 실행합니다.

```bash
./update-wiz-bundle.sh
```

이 스크립트는 현재 `bundle/` directory를 `project/main/installer/payload/wiz-bundle.tar.zst`로 다시 묶고 `payload/checksums.sha256`을 갱신합니다. 설치 중 payload는 사용 전에 `sha256sum -c checksums.sha256`로 검증됩니다.

이미 설치된 서버에는 갱신된 archive만 복사해 WIZ service 파일과 process만 교체할 수 있습니다.

```bash
scp project/main/installer/payload/wiz-bundle.tar.zst user@host:/tmp/
ssh user@host 'cd /root/docker-infra && sudo ./update-wiz-service.sh /tmp/wiz-bundle.tar.zst'
```

### 파일 정리

설치 실패, 재설치 준비, installer 제거에는 `cleanup.sh`를 사용합니다. 이 스크립트는 apt, pip, npm, PostgreSQL, Node.js package를 제거하지 않고 Docker Infra installer/deployment file artifact만 제거합니다.

```bash
sudo /opt/docker-infra/installer/cleanup.sh --scope preinstall
sudo /opt/docker-infra/installer/cleanup.sh --scope install
sudo /opt/docker-infra/installer/cleanup.sh --scope all
```

| scope | 제거 대상 |
|---|---|
| `preinstall` | installer API service, installer nginx site, installer HTML/payload, installer env, 임시 setup 파일 |
| `install` | WIZ service unit/drop-in, 앱 nginx site, 배포된 WIZ bundle, runtime env |
| `all` | `install` 정리 후 `preinstall` 정리 |

`--purge-data`와 `--purge-logs`는 명시한 경우에만 runtime data/log directory까지 제거합니다.

### 보안 기준

- 관리자 비밀번호와 초기 설정은 `/etc/docker-infra/initial-setup.json`에 `0600` 권한으로 임시 저장되고, `setup` 성공 후 삭제됩니다.
- 운영 DB password와 secret key는 installer가 생성하거나 `/etc/docker-infra/docker-infra.env`에서 읽습니다. 이 파일은 GitHub 업로드 대상이 아닙니다.
- PostgreSQL role password 설정은 shell debug log나 process argument에 원문을 남기지 않는 방식으로 처리합니다.
- installer log, operation log, devlog에는 password, token, SSH private key 원문을 남기지 않습니다.
- 설치 완료 후 `cleanup` 단계로 installer API와 HTML/payload를 제거해야 합니다.

## English

### Purpose

`project/main/installer/` is the self-contained install unit for deploying Docker Infra on an Ubuntu 24.04 production host. It carries the WIZ bundle archive, Python requirements, and checksum file in `payload/` so the production host does not need the development workspace.

### Quick Start

```bash
sudo project/main/installer/preinstall.sh
```

This copies nginx config, the installer HTML, and the local installer API into `/opt/docker-infra/installer`, then exposes the installer page on port `8088` by default.

```text
http://<host>:8088
```

Enter the admin password, master advertise address, service root, and backup system option in the installer page, then run the full install. The same flow is available from the CLI:

```bash
sudo /opt/docker-infra/installer/install.sh --step all
```

After `verify` succeeds, run the installer cleanup step from the page or with:

```bash
sudo /opt/docker-infra/installer/install.sh --step cleanup
```

### Steps

| Step | Description |
|---|---|
| `all` | Runs every production install step in order, excluding `cleanup` |
| `apt` | Installs nginx, PostgreSQL, Docker, Compose plugin, certbot, NetworkManager, Python, zstd, and related OS packages |
| `env` | Creates `/etc/docker-infra/docker-infra.env` and prepares `/var/lib/docker-infra` runtime directories |
| `postgres` | Creates the PostgreSQL role, database, schema, and role password |
| `python` | Installs Python/WIZ runtime dependencies from payload `requirements.txt` |
| `node` | Installs Node.js/npm from NodeSource LTS and the official `@openai/codex` global package |
| `bundle` | Verifies `wiz-bundle.tar.zst` and deploys it into `/opt/docker-infra/wiz` |
| `migrate` | Applies DB migrations from the deployed bundle |
| `service` | Registers `wiz.docker-infra.service`, adds the env drop-in, and starts the WIZ service |
| `setup` | Applies the initial installer settings through `/api/system/setup` |
| `nginx` | Configures the nginx reverse proxy for Docker Infra |
| `verify` | Checks PostgreSQL, WIZ service, and setup completion status |
| `cleanup` | Removes the installer API daemon, installer nginx site, HTML/payload, and temporary setup file |

### Refreshing the Payload

After source changes, refresh only the installer WIZ bundle payload from the WIZ workspace root:

```bash
./update-wiz-bundle.sh
```

The script repacks the current `bundle/` directory into `project/main/installer/payload/wiz-bundle.tar.zst` and rewrites `payload/checksums.sha256`. The installer verifies the payload with `sha256sum -c checksums.sha256` before using it.

For an already installed server, copy only the refreshed archive and replace the WIZ service files/process:

```bash
scp project/main/installer/payload/wiz-bundle.tar.zst user@host:/tmp/
ssh user@host 'cd /root/docker-infra && sudo ./update-wiz-service.sh /tmp/wiz-bundle.tar.zst'
```

### Cleanup

Use `cleanup.sh` for failed installs, reinstall preparation, or installer removal. It removes Docker Infra installer/deployment file artifacts only. It does not uninstall apt, pip, npm, PostgreSQL, or Node.js packages.

```bash
sudo /opt/docker-infra/installer/cleanup.sh --scope preinstall
sudo /opt/docker-infra/installer/cleanup.sh --scope install
sudo /opt/docker-infra/installer/cleanup.sh --scope all
```

| Scope | Removes |
|---|---|
| `preinstall` | Installer API service, installer nginx site, installer HTML/payload, installer env, temporary setup file |
| `install` | WIZ service unit/drop-in, app nginx site, deployed WIZ bundle, runtime env |
| `all` | `install` cleanup followed by `preinstall` cleanup |

`--purge-data` and `--purge-logs` remove runtime data/log directories only when explicitly passed.

### Security Notes

- The admin password and initial settings are temporarily stored in `/etc/docker-infra/initial-setup.json` with `0600` permissions and deleted after successful `setup`.
- The production DB password and secret key are generated by the installer or read from `/etc/docker-infra/docker-infra.env`. That file must not be uploaded to GitHub.
- PostgreSQL role password setup avoids writing the plaintext password into shell debug logs or process arguments.
- Installer logs, operation logs, and devlogs must not contain plaintext passwords, tokens, or SSH private keys.
- After installation, run `cleanup` to remove the installer API and HTML/payload files.
