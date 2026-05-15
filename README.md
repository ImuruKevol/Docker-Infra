# Docker Infra

Docker Infra는 미니 PC나 데스크탑 형태의 단일 운영 장비에 패키징해 판매하는 것을 전제로 한 Docker 서비스 운영 도구입니다. 대상 사용자는 개발자가 아니라 전산 담당자 또는 일반 관리자입니다. 사용자는 IP, port, domain, image tag 정도만 알아도 서버 등록, 서비스 배포, 도메인 연결, 인증서 적용, 이미지 정리를 처리할 수 있어야 합니다.

## 제품 방향

- Docker Infra가 실행되는 서버를 자동으로 마스터 노드로 등록합니다.
- nginx는 Ubuntu 24.04 기본 nginx로 고정합니다.
- nginx 설정 원문은 고급 모드에만 두고, 일반 사용자는 서비스-도메인 연결 마법사로 설정합니다.
- 소스 저장소 연동, Docker build, registry push 흐름은 제공하지 않습니다.
- 서비스 배포는 이미 존재하는 이미지를 선택해 Docker Compose 기반으로 실행합니다.
- Harbor는 외부 연동 화면이 아니라 선택형 내장 서비스 이미지 백업/버전 관리 시스템으로 사용합니다.
- 긴 작업 결과는 lightweight operation log, audit log, streaming output으로 보여줍니다.

## 핵심 흐름

### 최초 구성

처음 접속한 관리자는 다음만 선택합니다.

1. 관리자 비밀번호
2. 서비스 백업 시스템 구성 여부

백업 시스템은 기본 비활성화입니다. 활성화하면 마스터 노드에 로컬 Harbor를 설치/실행하고, Docker Infra가 백업 저장소 용량과 상태를 관리합니다.

### 서버 관리

서버 추가 시 사용자는 서버 이름, IP/host, SSH port, SSH 계정, 최초 비밀번호만 입력합니다. Docker Infra는 password 접속 확인 후 관리용 SSH key와 fingerprint를 준비하고, DB에는 key file 경로와 fingerprint만 저장합니다.

### 서비스 관리

서비스 생성은 마법사 중심입니다.

- AI 초안, Compose 직접 작성, 서버 Compose 가져오기 중 하나로 서비스 초안을 준비
- Compose 초안에서 서비스 이름, 설명, 구성요소, 이미지, 포트, 환경변수, 볼륨을 추출
- 공개 도메인과 연결 포트 선택
- SSL 방식은 업로드 인증서 또는 certbot 자동 발급 기준으로 처리
- 저장 전 이미지, 포트, 볼륨, 도메인, nginx 설정을 자동 사전 점검
- 실행 서버는 자동 배치를 기본값으로 사용

Compose YAML과 nginx config 원문은 고급 모드에서만 편집합니다.

### 도메인과 인증서

도메인 화면은 Cloudflare DNS record와 업로드 인증서를 관리합니다. 서비스 화면은 선택한 도메인, 내부 port, SSL 방식으로 nginx 연결을 자동 생성합니다. 인증서가 없으면 서비스 화면에서 certbot 무료 인증서 발급을 실행할 수 있습니다.

### 이미지와 백업

이미지 화면은 서버별 로컬 이미지와 서비스별 백업 이미지를 다룹니다. 로컬 이미지는 사용/미사용, 크기, 생성일, 마지막 사용일 기준으로 정리할 수 있습니다. 백업 시스템을 활성화한 경우 서비스 이미지 digest를 기준으로 중복 없이 내부 Harbor에 보관하고 복원할 수 있습니다.

## WIZ 프로젝트 구조

주요 경로는 다음과 같습니다.

```text
project/main/
  config/
  src/
    app/
    controller/
    model/
    route/
  docs/
  devlog.md
  devlog/
```

WIZ source app과 route는 `src/app`, `src/route` 아래에 두고, 화면 API는 각 app의 `api.py`에서 WIZ 응답 규칙을 지켜 작성합니다. 도메인 로직은 `src/model/struct.py` 진입점을 통해 호출합니다.

## Runtime Data

운영 데이터는 WIZ workspace의 `data/` 아래에 둡니다.

| 용도 | 경로 |
|---|---|
| 시스템 favicon/logo | `/root/docker-infra/data/system-assets/` |
| 도메인 인증서 | `/root/docker-infra/data/domain-certificates/` |
| 내장 백업 Harbor | `/root/docker-infra/data/backup-harbor/` 또는 운영 volume |
| 서비스 Compose 파일 | `.runtime/dev/services` |

## 개발 명령

개발 DB:

```bash
docker compose -f docker/compose/development.yaml up -d postgres
```

API 테스트:

```bash
docker compose -f docker/compose/test.yaml --profile api run --rm api-tests
```

nginx sandbox:

```bash
docker compose -f docker/compose/test.yaml --profile proxy run --rm proxy-sandbox
```

WIZ 빌드:

```bash
wiz_project_build
```

운영 설치:

```bash
sudo project/main/installer/preinstall.sh
sudo /opt/docker-infra/installer/install.sh --step all
```

`project/main/installer/`는 WIZ bundle과 custom Codex CLI payload를 포함하는 단독 설치 디렉터리입니다. 설치 과정에서 Node.js LTS/npm과 공식 `@openai/codex`도 함께 설치합니다. 초기 관리자 비밀번호와 local master 설정은 제품 `/access` 화면이 아니라 installer HTML에서 완료하며, `verify` 성공 후 installer HTML의 정리 단계로 설치 관리자 daemon과 HTML을 제거합니다. 중간 설치 실패 시 `installer/cleanup.sh --scope preinstall|install|all`로 file artifact만 정리할 수 있습니다.

## 보안 원칙

- 관리자 password는 hash로 저장합니다.
- SSH 최초 비밀번호는 연결과 key 설치에만 사용하고 저장하지 않습니다.
- Cloudflare token과 backup system secret은 암호화 저장합니다.
- API 응답, devlog, operation log에는 password/token 원문을 남기지 않습니다.
- 위험 작업은 audit log에 요청 대상과 결과를 남깁니다.

## 문서

- 전체 설계: `docs/docker-infra-design.md`
- 런타임 기준: `docs/docker-infra-runtime.md`
- 배포 설치 기준: `docs/docker-infra-deployment.md`
- 서비스 AI/Codex Agent 설계: `docs/service-ai-codex-agent-design.md`
- 전체 TODO: `docs/docker-infra-development-todo.md`
- 남은 TODO: `docs/docker-infra-remaining-todo.md`
