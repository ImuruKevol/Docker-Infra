# 206. 초기 설정 마법사를 installer로 통합하고 access 화면 단순화

- 날짜: 2026-05-15
- 리뷰 ID: ismjwijqevuqjalzluaiuezfxbdfprcf

## 원 요청

관리자 패스워드가 설정되지 않았을 때 뜨던 설정 마법사 화면을 installer 쪽으로 통합하고, `preinstall`은 최소 환경과 installer HTML만 준비하며, `install`에서는 HTML을 보면서 Docker Infra 서비스 설치, DB 설치, DB 초기값, 관리자 패스워드, 초기 시스템 설정까지 구성하도록 수정해 달라고 요청했다. 설정 마법사 화면은 제거하는 방향을 요청했다.

## 변경 파일

- `installer/install.sh`
  - `setup` 단계를 추가해 WIZ service 기동 후 installer payload를 `/api/system/setup`에 적용하도록 했다.
  - `all` 실행 순서를 service 등록 후 initial setup, nginx, verify 순서로 조정했다.
  - `verify`가 DB와 service뿐 아니라 초기 설정 완료 상태까지 확인하도록 바꿨다.
- `installer/installer_api.py`
  - installer HTML에서 받은 초기 설정 payload를 `/etc/docker-infra/initial-setup.json`에 `0600` 권한으로 임시 저장하도록 했다.
  - `setup` step을 installer API 허용 목록에 추가했다.
- `installer/installer.html`
  - 관리자 비밀번호, 대표 IP, service root, 백업 저장소 사용 여부를 입력하는 초기 시스템 설정 UI를 추가했다.
  - `all`/`setup` 실행 시 password 확인 검증과 setup payload 전달을 추가했다.
- `installer/preinstall.sh`
  - installer API와 install script가 공유할 initial setup payload 경로를 환경 파일에 기록하도록 했다.
- `src/app/page.access/view.ts`, `src/app/page.access/view.pug`, `src/app/page.access/api.py`
  - 제품 내부 초기 설정 form과 완료 action을 제거했다.
  - 초기 설정이 끝나지 않은 경우 installer URL 안내와 `설치 관리자 열기`만 표시하도록 바꿨다.
  - access page API는 setup status와 login/logout/session만 남겼다.
- `tests/api/test_installer_contract.py`, `tests/api/test_auth_setup.py`, `tests/api/test_playwright_setup.py`, `tests/e2e/helpers/auth.ts`, `tests/e2e/specs/access.spec.ts`
  - installer-owned setup과 access 화면 단순화 계약에 맞춰 테스트를 갱신했다.
- `README.md`, `docs/docker-infra-deployment.md`, `docs/docker-infra-runtime.md`, `docs/docker-infra-design.md`, `docs/api/openapi.json`
  - 초기 설정 소유권을 제품 access 화면에서 installer로 옮긴 기준을 문서화했다.
- `devlog.md`
  - 이번 작업 기록을 추가했다.

## 확인 결과

- `bash -n installer/install.sh`: 통과
- `bash -n installer/preinstall.sh`: 통과
- `/opt/conda/envs/docker-infra/bin/python -m py_compile installer/installer_api.py tests/api/test_installer_contract.py tests/api/test_auth_setup.py tests/api/test_playwright_setup.py`: 통과
- `/opt/conda/envs/docker-infra/bin/python -m unittest tests.api.test_installer_contract tests.api.test_auth_setup tests.api.test_playwright_setup`: 18개 통과
- `wiz_project_build(projectName="main", clean=false)`: 통과

## 남은 리스크

- 실제 운영 host에서 installer HTML로 admin password 입력부터 `/api/system/setup` 적용까지 end-to-end 실행하지는 않았다.
- initial setup payload는 성공 시 삭제되지만, 실패 시 재시도를 위해 남을 수 있으므로 운영자는 설치 실패 후 `/etc/docker-infra/initial-setup.json` 존재 여부를 확인해야 한다.
- installer API는 설치 완료 후 계속 노출할 서비스가 아니므로 중지하거나 네트워크 접근을 제한해야 한다.
