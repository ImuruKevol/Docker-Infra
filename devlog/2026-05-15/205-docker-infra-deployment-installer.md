# 205. Docker Infra 운영 배포 installer와 설치 문서 추가

- 날짜: 2026-05-15
- 리뷰 ID: ismjwijqevuqjalzluaiuezfxbdfprcf

## 원 요청

Docker Infra 서비스를 배포해야 하며, 개발용 컨테이너 DB 대신 설치형 PostgreSQL로 전환해야 한다. WIZ bundle 파일 추출 명령을 이용해 배포하고, daemon 실행에 사용하는 환경변수 파일을 installer에 반영해야 한다. 추가 apt/pip 패키지를 정리해 all-in-one shell installer로 만들고, custom Codex CLI도 반드시 포함해야 한다. DB table과 초기 기본 데이터, 관리자 password 미설정 시 설치 마법사 동작도 확인해야 한다. 설치용 HTML을 두고 `preinstall`, `install` 두 단계로 나누는 방식도 고려해 달라고 요청했다.

## 변경 파일

- `installer/preinstall.sh`
  - nginx, Python, 설치 HTML, token 기반 installer API systemd service를 먼저 구성하는 preinstall script를 추가했다.
- `installer/install.sh`
  - apt package 설치, host PostgreSQL role/database/schema 구성, PIP dependency 설치, custom Codex CLI build/install, `wiz bundle --project=main` 기반 bundle-only 배포, DB migration, WIZ systemd service 등록, nginx proxy, setup API verification을 단계별/전체 실행할 수 있게 했다.
- `installer/installer_api.py`
  - 설치 HTML에서 token으로 각 installer step을 실행하고 log/status를 조회하는 local API를 추가했다.
- `installer/installer.html`
  - 설치 token 입력, 단계별 실행, 전체 실행, log/status 확인 UI를 추가했다.
- `installer/docker-infra.env.example`
  - 운영 DB, data directory, custom Codex CLI, `CODEX_HOME` 환경변수 template을 추가했다.
- `installer/README.md`
  - preinstall/install 실행 방법을 정리했다.
- `docs/docker-infra-deployment.md`
  - 운영 배포 설치 기준, 단계, 환경변수 파일, 최초 관리자 password 확인 기준을 문서화했다.
- `docs/docker-infra-runtime.md`
  - 운영 설치에서 host PostgreSQL과 systemd `EnvironmentFile`을 사용하는 기준을 추가했다.
- `README.md`
  - 운영 설치 명령과 배포 문서 링크를 추가했다.
- `tests/api/test_installer_contract.py`
  - installer 파일, 실행 권한, 배포 단계, token API, custom Codex CLI/env template 계약을 정적 테스트로 추가했다.
- `devlog.md`
  - 이번 작업 기록을 추가했다.

## 확인 결과

- `bash -n installer/install.sh`: 통과
- `bash -n installer/preinstall.sh`: 통과
- `installer/install.sh --help`: 통과
- `/opt/conda/envs/docker-infra/bin/python -m py_compile installer/installer_api.py tests/api/test_installer_contract.py`: 통과
- `/opt/conda/envs/docker-infra/bin/python -m unittest tests.api.test_installer_contract`: 6개 통과
- `wiz_project_build(projectName="main", clean=false)`: 통과

## 남은 리스크

- 실제 운영 host에서 apt 설치, PostgreSQL 생성, custom Codex CLI release build, WIZ service 등록까지 end-to-end로 실행하지는 않았다.
- installer API는 설치 전용 권한 작업을 수행하므로 배포 완료 후 service/site 중지 또는 방화벽 제한이 필요하다.
- 운영 HTTPS 적용 시 `DOCKER_INFRA_SESSION_COOKIE_SECURE=true`와 별도 TLS nginx 설정을 반영해야 한다.
