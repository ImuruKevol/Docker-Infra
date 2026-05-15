# 207. installer 단독 payload와 설치 관리자 self-cleanup 추가

- 날짜: 2026-05-15
- 리뷰 ID: ismjwijqevuqjalzluaiuezfxbdfprcf

## 원 요청

installer 안에 WIZ bundle과 custom Codex CLI가 포함되어 있지 않아, `installer/` 디렉터리만 따로 가져가도 완전하게 설치되도록 수정해 달라고 요청했다. 또한 설치 완료 후 마지막 단계에서 HTML을 통해 installer API service daemon과 installer HTML 등을 삭제하고, installer가 자기 자신을 정리하며 종료되도록 요청했다.

## 변경 파일

- `installer/payload/wiz-bundle.tar.zst`
  - `wiz bundle --project=main` 결과물을 installer 내부 payload로 포함했다.
- `installer/payload/codex-custom.tar.zst`
  - custom Codex CLI source를 installer 내부 payload로 포함했다. 빌드 산출물과 git metadata는 제외했다.
- `installer/payload/requirements.txt`, `installer/payload/checksums.sha256`
  - Python dependency 입력 파일과 payload 무결성 확인용 checksum을 추가했다.
- `installer/preinstall.sh`
  - preinstall 시 payload 디렉터리를 `/opt/docker-infra/installer/payload`로 함께 복사하고, installer env에 payload archive 경로를 기록하도록 했다.
  - payload 압축 해제를 위해 최소 package에 `zstd`를 추가했다.
- `installer/install.sh`
  - WIZ bundle은 installer payload archive를 우선 사용하고, custom Codex CLI도 payload source/binary를 우선 사용하도록 했다.
  - payload 사용 전 `sha256sum -c`로 무결성을 확인하도록 했다.
  - `cleanup` step을 추가해 installer service, nginx site, HTML/payload, token, 임시 initial setup 파일을 제거하도록 했다.
- `installer/installer_api.py`
  - installer API에서 `cleanup` step 실행을 허용했다.
- `installer/installer.html`
  - 마지막 설치 단계로 `설치 관리자 정리` 버튼을 추가하고, cleanup 실행 후 installer API 종료를 안내하도록 했다.
- `installer/README.md`, `docs/docker-infra-deployment.md`, `README.md`
  - installer 디렉터리가 단독 설치 단위이며 payload와 cleanup 단계를 포함한다는 기준을 문서화했다.
- `tests/api/test_installer_contract.py`
  - payload 파일 존재, checksum 검증, cleanup step, payload copy/env 계약을 정적 테스트에 추가했다.
- `devlog.md`
  - 이번 작업 기록을 추가했다.

## 확인 결과

- `/opt/conda/envs/docker-infra/bin/wiz bundle --project=main`: 통과
- `bash -n installer/install.sh`: 통과
- `bash -n installer/preinstall.sh`: 통과
- `/opt/conda/envs/docker-infra/bin/python -m py_compile installer/installer_api.py tests/api/test_installer_contract.py`: 통과
- `tar --zstd -tf installer/payload/wiz-bundle.tar.zst`: 통과
- `tar --zstd -tf installer/payload/codex-custom.tar.zst`: 통과
- `(cd installer/payload && sha256sum -c checksums.sha256)`: 통과
- `/opt/conda/envs/docker-infra/bin/python -m unittest tests.api.test_installer_contract`: 6개 통과
- `/opt/conda/envs/docker-infra/bin/python -m unittest tests.api.test_installer_contract tests.api.test_auth_setup tests.api.test_playwright_setup`: 18개 통과
- 임시 경로를 지정한 `installer/install.sh --step bundle`: packaged WIZ bundle payload 배포 통과
- `wiz_project_build(projectName="main", clean=false)`: 통과

## 남은 리스크

- 실제 Ubuntu 운영 host에서 `preinstall`부터 `cleanup`까지 end-to-end 실행하지는 않았다.
- custom Codex CLI는 source payload로 포함되어 target host에서 release build한다. 운영 host에서 Cargo registry 접근 또는 build cache가 없으면 build 시간이 길어지거나 실패할 수 있다.
- `cleanup`은 `/opt/docker-infra/installer` 계열 경로에서만 실행되도록 제한했다. 다른 경로에 수동 설치한 경우 `INSTALL_BASE`/`INSTALLER_ROOT` 값을 맞춰야 한다.
