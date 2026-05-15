# 211. installer token 제거와 단계형 wizard UI 적용

- 날짜: 2026-05-15
- 리뷰 ID: ismjwijqevuqjalzluaiuezfxbdfprcf

## 원 요청

`installer.token` 같은 token 인증은 필요 없으니 제거하고, installer HTML의 왼쪽 단계 목록 나열 방식을 이전/다음으로 단계별 설정 및 실행할 수 있는 화면으로 수정해 달라고 요청했다.

## 변경 파일

- `installer/installer_api.py`
  - installer token file, token read, `X-Installer-Token` 인증 검사를 제거했다.
  - `/status`, `/run`을 token 없이 처리하도록 했다.
- `installer/preinstall.sh`
  - `installer.token` 생성과 env 기록을 제거했다.
  - 완료 로그를 token 안내 대신 installer 준비 완료 안내로 변경했다.
- `installer/installer.html`
  - token 입력/저장 UI와 단계 목록 나열 UI를 제거했다.
  - `이전`, `현재 단계 실행`, `다음` 버튼 기반의 단일 단계 wizard UI로 변경했다.
  - 초기 시스템 설정 입력 영역은 `setup` 단계에서만 표시되도록 했다.
- `installer/install.sh`, `installer/cleanup.sh`
  - self-cleanup/cleanup 문구와 token 삭제 대상을 현재 tokenless 구조에 맞춰 정리했다.
- `installer/README.md`, `docs/docker-infra-deployment.md`
  - installer token 안내를 제거하고 tokenless local installer API 기준으로 문서를 갱신했다.
- `tests/api/test_installer_contract.py`
  - token 관련 문자열이 preinstall/API/HTML에 남지 않는지 확인하고, wizard 이전/다음/현재 단계 실행 UI 계약을 추가했다.
- `devlog.md`
  - 이번 작업 기록을 추가했다.

## 확인 결과

- `bash -n installer/install.sh`: 통과
- `bash -n installer/preinstall.sh`: 통과
- `bash -n installer/cleanup.sh`: 통과
- `/opt/conda/envs/docker-infra/bin/python -m py_compile installer/installer_api.py tests/api/test_installer_contract.py`: 통과
- `/opt/conda/envs/docker-infra/bin/python -m unittest tests.api.test_installer_contract`: 통과
- `/opt/conda/envs/docker-infra/bin/python -m unittest tests.api.test_installer_contract tests.api.test_auth_setup tests.api.test_playwright_setup`: 통과
- `wiz_project_build(projectName="main", clean=false)`: 통과

## 남은 리스크

- tokenless installer API는 설치 중에만 노출되어야 한다. 설치 port `8088`은 운영망에서 접근 제한하거나, 설치 완료 후 `cleanup` 단계로 installer API/nginx site를 제거해야 한다.
- 실제 브라우저에서 wizard 이전/다음 단계 UI를 클릭하는 E2E 검증은 하지 않았다.
