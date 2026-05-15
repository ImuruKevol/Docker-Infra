# 209. installer에 Node.js LTS와 공식 Codex npm 설치 단계 추가

- 날짜: 2026-05-15
- 리뷰 ID: ismjwijqevuqjalzluaiuezfxbdfprcf

## 원 요청

custom Codex CLI뿐 아니라 정식 Codex CLI인 npm package `@openai/codex`도 설치해야 하며, 설치 과정에서 Node.js LTS와 npm을 설치하고 `@openai/codex` 설치 과정을 추가해 달라고 요청했다.

## 변경 파일

- `installer/install.sh`
  - `NODE_SOURCE_SETUP_URL=https://deb.nodesource.com/setup_lts.x`와 `OFFICIAL_CODEX_PACKAGE=@openai/codex` 설정을 추가했다.
  - `node` step을 추가해 Node.js LTS/npm 설치 후 `npm install -g @openai/codex`를 실행하도록 했다.
  - `all` 실행 순서에 `node` step을 `python` 다음, custom Codex binary 설치 전으로 추가했다.
- `installer/installer_api.py`
  - installer HTML/API에서 `node` step을 실행할 수 있도록 허용 목록에 추가했다.
- `installer/installer.html`
  - 단계 목록에 `Official Codex CLI`를 추가했다.
- `installer/README.md`, `docs/docker-infra-deployment.md`, `README.md`
  - Node.js LTS/npm과 공식 `@openai/codex` global 설치 기준을 문서화했다.
- `tests/api/test_installer_contract.py`
  - NodeSource LTS setup, `nodejs`, `npm install -g @openai/codex`, API/HTML `node` step 계약을 정적 테스트에 추가했다.
- `devlog.md`
  - 이번 작업 기록을 추가했다.

## 확인 결과

- `bash -n installer/install.sh`: 통과
- `bash -n installer/preinstall.sh`: 통과
- `/opt/conda/envs/docker-infra/bin/python -m py_compile installer/installer_api.py tests/api/test_installer_contract.py`: 통과
- `/opt/conda/envs/docker-infra/bin/python -m unittest tests.api.test_installer_contract`: 7개 통과
- `/opt/conda/envs/docker-infra/bin/python -m unittest tests.api.test_installer_contract tests.api.test_auth_setup tests.api.test_playwright_setup`: 19개 통과
- `wiz_project_build(projectName="main", clean=false)`: 통과

## 남은 리스크

- 실제 운영 host에서 NodeSource LTS repository setup과 `npm install -g @openai/codex`를 end-to-end 실행하지는 않았다.
- 공식 npm Codex CLI는 설치 시점의 npm registry 최신 배포판을 설치하므로, 특정 버전 고정이 필요하면 `OFFICIAL_CODEX_PACKAGE=@openai/codex@<version>` 형태로 고정해야 한다.
