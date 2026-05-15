# 214. 공식 Codex와 custom CLI 설치 경로 분리 및 architecture 검증

- 날짜: 2026-05-15
- 리뷰 ID: ismjwijqevuqjalzluaiuezfxbdfprcf

## 원 요청

installer `codex` 단계에서 `/opt/docker-infra/codex/bin/codex: cannot execute binary file: Exec format error`가 발생하므로 공식 `@openai/codex` 설치 버전과 custom CLI가 꼬이지 않도록 수정해 달라고 요청했다.

## 변경 파일

- `installer/install.sh`
  - 공식 npm `codex`는 `DOCKER_INFRA_SYSTEM_CODEX_BIN`에 기록하고, custom CLI는 `/opt/docker-infra/codex-custom/bin/docker-infra-codex`에 설치하도록 분리했다.
  - custom payload를 host architecture별 경로에서 선택하도록 했다.
  - ELF machine 값을 확인해 host architecture와 payload binary가 맞지 않으면 `Exec format error` 대신 명확한 architecture mismatch 오류를 내도록 했다.
  - 공식 `codex` 설치 후 실제 경로를 runtime env에 반영하고, custom 설치 후 custom 경로를 `DOCKER_INFRA_CODEX_BIN`에 반영하도록 했다.
  - 이전 실패 설치에서 남을 수 있는 `/opt/docker-infra/codex/bin/codex` legacy 값을 새 custom 경로로 보정하도록 했다.
- `installer/preinstall.sh`
  - installer env에 custom binary 단일 파일 경로 대신 payload directory를 기록하도록 변경했다.
- `installer/docker-infra.env.example`
  - 공식 Codex와 custom Codex CLI 기본 경로를 분리했다.
- `installer/cleanup.sh`
  - custom Codex CLI 설치 디렉토리 `/opt/docker-infra/codex-custom` 정리를 추가했다.
- `installer/installer.html`, `installer/README.md`, `docs/docker-infra-deployment.md`
  - custom Codex CLI가 host architecture별 payload로 설치된다는 내용을 반영했다.
- `installer/payload/codex-bin/linux-x86_64/codex`, `installer/payload/checksums.sha256`
  - x86_64 custom binary payload를 architecture별 경로로 이동하고 checksum을 갱신했다.
- `tests/api/test_installer_contract.py`
  - 공식/custom Codex 경로 분리, architecture 검증, payload 경로 계약을 추가했다.
- `devlog.md`
  - 이번 작업 기록을 추가했다.

## 확인 결과

- `bash -n installer/install.sh && bash -n installer/preinstall.sh && bash -n installer/cleanup.sh`: 통과
- `/opt/conda/envs/docker-infra/bin/python -m unittest tests.api.test_installer_contract`: 통과
- `/opt/conda/envs/docker-infra/bin/python -m unittest tests.api.test_installer_contract tests.api.test_system_settings_dynamic_menu tests.api.test_auth_setup tests.api.test_playwright_setup`: 통과, 23개 중 2개 skip
- `/opt/conda/envs/docker-infra/bin/python -m py_compile installer/installer_api.py tests/api/test_installer_contract.py`: 통과
- `sha256sum -c installer/payload/checksums.sha256`: 통과
- `od -An -j18 -N2 -tu2 installer/payload/codex-bin/linux-x86_64/codex`: `62` 확인
- 기존 충돌 경로 `/opt/docker-infra/codex/bin/codex`, legacy payload `payload/codex-bin/codex`, `DOCKER_INFRA_SYSTEM_CODEX_BIN=/opt/docker-infra/codex` 참조 제거 확인: 통과

## 남은 리스크

- 현재 installer payload에는 `linux-x86_64` custom binary만 포함되어 있다. 운영 host가 arm64이면 `linux-aarch64` payload binary를 추가해야 custom CLI 설치가 완료된다.
