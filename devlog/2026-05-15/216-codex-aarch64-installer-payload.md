# 216. custom Codex CLI aarch64 installer payload 추가

- 날짜: 2026-05-15
- 리뷰 ID: ismjwijqevuqjalzluaiuezfxbdfprcf

## 원 요청

라즈베리파이 테스트 host가 `aarch64`이므로 custom Codex CLI도 해당 architecture로 빌드해 installer에 포함해 달라고 요청했다.

## 변경 파일

- `installer/payload/codex-bin/linux-aarch64/codex`
  - `aarch64-unknown-linux-gnu` target으로 빌드한 custom Codex CLI binary를 추가했다.
  - `aarch64-linux-gnu-strip`으로 debug symbol을 제거한 실행 파일만 payload에 포함했다.
- `installer/payload/checksums.sha256`
  - `codex-bin/linux-aarch64/codex` checksum을 추가했다.
- `tests/api/test_installer_contract.py`
  - installer payload 계약에 `linux-aarch64` binary와 checksum 포함 여부를 추가했다.
- `installer/README.md`
  - self-contained installer payload가 `linux-x86_64`, `linux-aarch64` custom CLI binary를 포함한다고 명시했다.
- `docs/docker-infra-deployment.md`
  - 배포 문서의 payload 설명에 architecture별 custom CLI binary 포함을 반영했다.
- `devlog.md`
  - 이번 작업 기록을 추가했다.

## 확인 결과

- `cargo build --target aarch64-unknown-linux-gnu -p codex-cli --bin codex`: 통과
- `file installer/payload/codex-bin/linux-aarch64/codex`: `ELF 64-bit LSB pie executable, ARM aarch64`, stripped 확인
- `od -An -j18 -N2 -tu2 installer/payload/codex-bin/linux-aarch64/codex`: `183` 확인
- `bash -n installer/install.sh && bash -n installer/preinstall.sh && bash -n installer/cleanup.sh`: 통과
- `sha256sum -c installer/payload/checksums.sha256`: 통과
- `/opt/conda/envs/docker-infra/bin/python -m unittest tests.api.test_installer_contract`: 통과
- 임시 `INSTALL_BASE`, `ENV_DIR`, `DATA_ROOT`, `LOG_DIR`로 `bash installer/install.sh --step codex` 실행: x86_64 payload 설치 및 `codex-cli 0.0.0` 확인

## 남은 리스크

- aarch64 binary는 cross build 산출물이라 현재 x86_64 host에서는 직접 실행 검증하지 못했다. 실제 Raspberry Pi host에서 `install.sh --step codex` 실행 검증이 필요하다.
- custom CLI가 dynamic link 방식으로 빌드되어 Raspberry Pi host에 Ubuntu/Debian 계열의 glibc와 OpenSSL 3 runtime library가 있어야 한다.
