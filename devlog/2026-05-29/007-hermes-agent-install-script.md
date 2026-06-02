# Hermes Agent 설치 스크립트 방식 전환

- 날짜: 2026-05-29
- 리뷰 ID: cxaqmytxjrdnjjdcuazqouethjqeipfv
- 요청: 헤르메스 Agent도 네이티브 설치 방식으로 수정해줘.

## 변경 요약

- Hermes Agent 기본 설치를 npm package 설치 경로에서 설치 스크립트 실행 경로로 전환했다.
- 기본 Hermes Agent 설치 URL을 `https://raw.githubusercontent.com/NousResearch/hermes-agent/main/scripts/install.sh`로 설정하고, `DOCKER_INFRA_HERMES_AGENT_INSTALL_URL`, `DOCKER_INFRA_HERMES_AGENT_INSTALL_CHANNEL`로 override할 수 있게 했다.
- Hermes 설치 스크립트 실행 전에 기존 `hermes-agent` npm global 설치본이 있으면 먼저 정리하도록 보강했다.
- Hermes 기본 실행 파일 탐색을 설치 스크립트 결과인 `hermes` 명령 중심으로 조정했다.
- installer env 생성, env 예시, 배포 문서, 정적 계약 테스트를 새 설치 방식에 맞춰 갱신했다.
- installer payload WIZ bundle archive와 checksum을 최신 변경 기준으로 재생성했다.

## 변경 파일

- `docs/docker-infra-deployment.md`
- `installer/docker-infra.env.example`
- `installer/install.sh`
- `installer/payload/checksums.sha256`
- `installer/payload/wiz-bundle.tar.zst`
- `src/app/page.system/view.ts`
- `src/model/struct/codex_runtime.py`
- `tests/api/test_installer_contract.py`
- `tests/api/test_system_settings_dynamic_menu.py`
- `devlog.md`
- `devlog/2026-05-29/007-hermes-agent-install-script.md`

## 확인

- Hermes Agent 설치 문서에서 one-line installer와 `hermes --version`, `hermes doctor` 검증 명령을 확인했다.
- 현재 서버에는 `hermes-agent` npm global package와 `hermes`/`hermes-agent` 명령이 없음을 확인했다.
- `/opt/conda/envs/docker-infra/bin/python -m py_compile src/model/struct/codex_runtime.py src/model/struct/ai_settings.py src/app/page.system/api.py`: 성공
- `bash -n installer/install.sh installer/preinstall.sh installer/cleanup.sh /root/docker-infra/update-wiz-bundle.sh /root/docker-infra/update-wiz-service.sh`: 성공
- `/opt/conda/envs/docker-infra/bin/python -m unittest tests.api.test_installer_contract.InstallerContractTest tests.api.test_system_settings_dynamic_menu.SystemSettingsStaticContractTest`: 성공
- `/opt/conda/envs/docker-infra/bin/python -m unittest tests.api.test_system_settings_dynamic_menu.SystemSettingsStaticContractTest tests.api.test_services_preflight.ServicesPreflightStaticContractTest tests.api.test_installer_contract.InstallerContractTest tests.api.test_backup_registry_nodes.BackupRegistryNodeStaticContractTest`: 성공
- `git diff --check` 대상 변경 파일: 성공
- `wiz_project_build(projectName="main", clean=false)`: 성공
- `/opt/conda/envs/docker-infra/bin/wiz bundle --project=main`: 성공
- `/root/docker-infra/update-wiz-bundle.sh`: 성공, payload checksum 검증 포함
- `installer/payload/wiz-bundle.tar.zst` 내부에 Hermes Agent 설치 URL, `hermes` 실행 파일 설정, 기존 npm 설치 정리 설정이 포함된 것 확인

## 남은 리스크

- 시스템 설정 화면에서 Hermes Agent 설치 스크립트를 실제 클릭해 설치하는 live 검증은 하지 않았다.
- 운영 환경이 GitHub raw 설치 스크립트 URL에 접근할 수 있어야 설치가 성공한다.
