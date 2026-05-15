# 210. installer 진행 단계별 file artifact cleanup script 추가

- 날짜: 2026-05-15
- 리뷰 ID: ismjwijqevuqjalzluaiuezfxbdfprcf

## 원 요청

`preinstall`, `install` 진행 상태에 따라 설치된 것들을 삭제할 수 있는 script를 추가해 달라고 요청했다. 단, preinstall/install 과정에서 설치하는 apt, pip, npm package는 삭제할 필요가 없고, nginx 설정 파일과 HTML처럼 file 형태로 추가되는 것들만 삭제하도록 요청했다.

## 변경 파일

- `installer/cleanup.sh`
  - `--scope preinstall|install|all` 기준으로 installer 또는 배포 file artifact를 삭제하는 script를 추가했다.
  - apt, pip, npm, PostgreSQL, Node.js package uninstall은 수행하지 않도록 했다.
  - `--dry-run`, `--purge-data`, `--purge-logs` 옵션을 추가했다.
- `installer/preinstall.sh`
  - preinstall 시 `/opt/docker-infra/installer/cleanup.sh`로 cleanup script를 함께 복사하도록 했다.
- `installer/README.md`, `docs/docker-infra-deployment.md`, `README.md`
  - cleanup script 사용법과 scope별 제거 대상을 문서화했다.
- `tests/api/test_installer_contract.py`
  - cleanup script 존재/실행권한, preinstall 복사, scope별 file artifact 제거 계약, package uninstall 금지 계약을 추가했다.
- `devlog.md`
  - 이번 작업 기록을 추가했다.

## 확인 결과

- `bash -n installer/cleanup.sh`: 통과
- `bash -n installer/preinstall.sh`: 통과
- `bash -n installer/install.sh`: 통과
- `installer/cleanup.sh --help`: 통과
- `installer/cleanup.sh --dry-run --scope all`: 통과
- `/opt/conda/envs/docker-infra/bin/python -m py_compile installer/installer_api.py tests/api/test_installer_contract.py`: 통과
- `/opt/conda/envs/docker-infra/bin/python -m unittest tests.api.test_installer_contract`: 통과
- `/opt/conda/envs/docker-infra/bin/python -m unittest tests.api.test_installer_contract tests.api.test_auth_setup tests.api.test_playwright_setup`: 통과
- `wiz_project_build(projectName="main", clean=false)`: 통과

## 남은 리스크

- 실제 운영 host에서 preinstall/install 후 cleanup script를 실행하는 end-to-end 검증은 하지 않았다.
- 기본 cleanup은 runtime data/log를 보존한다. 실패 설치에서 data/log까지 삭제해야 할 경우 `--purge-data`, `--purge-logs`를 명시해야 한다.
