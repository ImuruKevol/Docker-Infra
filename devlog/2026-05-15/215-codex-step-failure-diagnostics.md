# 215. custom Codex 설치 실패 원인 로그 보강

- 날짜: 2026-05-15
- 리뷰 ID: ismjwijqevuqjalzluaiuezfxbdfprcf

## 원 요청

installer `codex` 단계가 `runtime environment file prepared`, `verifying installer payload checksums` 이후 바로 `result=failed exit_code=1`로 종료되어 설치가 진행되지 않는다고 보고했다.

## 변경 파일

- `installer/install.sh`
  - installer log를 stderr로 출력하도록 변경해 command substitution 내부의 `fail` 메시지가 숨겨지지 않게 했다.
  - checksum 검증 실패 시 `sha256sum -c`의 실제 오류와 `installer payload checksum verification failed` 메시지를 남기도록 했다.
  - custom Codex 단계에서 감지한 host architecture와 선택한 payload 경로를 로그로 남기도록 했다.
- `tests/api/test_installer_contract.py`
  - custom Codex architecture/payload 선택 로그 계약을 추가했다.
- `devlog.md`
  - 이번 작업 기록을 추가했다.

## 확인 결과

- `bash -n installer/install.sh && bash -n installer/preinstall.sh && bash -n installer/cleanup.sh`: 통과
- `/opt/conda/envs/docker-infra/bin/python -m unittest tests.api.test_installer_contract tests.api.test_system_settings_dynamic_menu tests.api.test_auth_setup tests.api.test_playwright_setup`: 통과, 23개 중 2개 skip
- `sha256sum -c installer/payload/checksums.sha256`: 통과
- `/opt/conda/envs/docker-infra/bin/python -m py_compile tests/api/test_installer_contract.py`: 통과
- 임시 `INSTALL_BASE`, `ENV_DIR`, `DATA_ROOT`, `LOG_DIR`로 `bash installer/install.sh --step codex` 실행: 통과

## 남은 리스크

- 운영 host가 arm64이면 `installer/payload/codex-bin/linux-aarch64/codex`가 필요하다. 현재 workspace에서 arm64 cross build를 시도했지만 target OpenSSL 개발 패키지가 없어 완료하지 못했다.
