# 208. custom Codex CLI를 installer binary payload로 전환

- 날짜: 2026-05-15
- 리뷰 ID: ismjwijqevuqjalzluaiuezfxbdfprcf

## 원 요청

custom Codex CLI는 운영 host에서 release build하지 말고, 빌드된 결과물만 가져가면 된다고 요청했다.

## 변경 파일

- `installer/payload/codex-bin/codex`
  - 기존 custom Codex CLI 빌드 산출물을 strip한 실행 파일로 installer payload에 포함했다.
- `installer/payload/codex-custom.tar.zst`
  - 운영 host source build가 필요 없도록 payload에서 제거했다.
- `installer/payload/checksums.sha256`
  - `codex-bin/codex` 기준으로 checksum을 갱신했다.
- `installer/install.sh`
  - Codex 설치 단계에서 source archive 추출과 `cargo build` fallback을 제거하고, payload binary만 설치하도록 변경했다.
  - Rust/Cargo/build toolchain package를 apt 설치 목록에서 제거했다.
- `installer/preinstall.sh`
  - installer env에 `CODEX_CUSTOM_BIN=$INSTALLER_ROOT/payload/codex-bin/codex`를 기록하도록 변경했다.
- `installer/installer.html`
  - Codex 단계 설명과 apt 단계 설명을 binary/runtime 설치 기준으로 정리했다.
- `installer/README.md`, `docs/docker-infra-deployment.md`
  - installer가 빌드 완료 Codex CLI binary를 포함하며 운영 host에서 Rust/Cargo build를 수행하지 않는다고 문서화했다.
- `tests/api/test_installer_contract.py`
  - Codex payload가 binary-only인지 확인하고, `cargo build`, `rustc`, `cargo`, source archive 참조가 install script에 남지 않도록 검증을 추가했다.
- `devlog.md`
  - 이번 작업 기록을 추가했다.

## 확인 결과

- `installer/payload/codex-bin/codex --version`: `codex-cli 0.0.0` 확인
- `(cd installer/payload && sha256sum -c checksums.sha256)`: 통과
- 임시 경로를 지정한 `installer/install.sh --step codex`: payload binary 설치 및 `codex --version` 통과
- `bash -n installer/install.sh`: 통과
- `bash -n installer/preinstall.sh`: 통과
- `/opt/conda/envs/docker-infra/bin/python -m py_compile installer/installer_api.py tests/api/test_installer_contract.py`: 통과
- `/opt/conda/envs/docker-infra/bin/python -m unittest tests.api.test_installer_contract`: 7개 통과
- `/opt/conda/envs/docker-infra/bin/python -m unittest tests.api.test_installer_contract tests.api.test_auth_setup tests.api.test_playwright_setup`: 19개 통과
- `wiz_project_build(projectName="main", clean=false)`: 통과

## 남은 리스크

- 포함된 Codex binary는 현재 개발 host의 Linux x86_64 glibc/OpenSSL 3 runtime에 맞는 실행 파일이다. 운영 host가 다른 아키텍처이거나 OpenSSL runtime ABI가 다르면 별도 binary를 준비해야 한다.
