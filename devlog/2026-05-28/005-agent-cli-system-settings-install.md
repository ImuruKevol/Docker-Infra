# AI Agent CLI 설치를 시스템 설정 실행 방식으로 전환

- 날짜: 2026-05-28
- 리뷰 ID: cxaqmytxjrdnjjdcuazqouethjqeipfv
- 요청: installer에 이 내용들을 반영하고, codex, 클루드 코드, 헤르메스에 대한건 기본 설치가 아니라 관리자가 시스템 설정에서 설치 스크립트를 실행해서 설치하는 방식으로 변경해줘.

## 변경 요약

- installer 기본 설치에서 공식 Codex CLI global 설치를 제거하고, `node` 단계는 Node.js/npm runtime 준비만 수행하도록 변경했다.
- `/etc/docker-infra/docker-infra.env`와 env 예시에 Agent별 설치 스크립트 override 값을 추가했다.
- 시스템 설정 AI Agent 화면에서 Codex, Claude Code, 헤르메스 설치/업데이트 스크립트를 백그라운드 operation으로 실행하고 로그를 확인할 수 있게 했다.
- Codex 설치/업데이트는 Node.js/npm이 없으면 설치한 뒤 `@openai/codex@latest`를 설치하는 스크립트로 전환했고, Claude Code와 헤르메스도 같은 Agent 설치 실행 경로를 사용한다.
- README, 배포 문서, installer 문서와 정적 계약 테스트를 새 설치 방식에 맞췄다.

## 변경 파일

- README.md
- docs/docker-infra-deployment.md
- installer/README.md
- installer/docker-infra.env.example
- installer/install.sh
- installer/installer.html
- installer/payload/checksums.sha256
- installer/payload/wiz-bundle.tar.zst
- src/app/page.system/api.py
- src/app/page.system/view.pug
- src/app/page.system/view.ts
- src/model/struct/codex_runtime.py
- tests/api/test_installer_contract.py
- tests/api/test_system_settings_dynamic_menu.py

## 확인

- `/opt/conda/envs/docker-infra/bin/python -m py_compile src/model/struct/codex_runtime.py src/app/page.system/api.py src/model/struct/ai_settings.py`
- `bash -n installer/install.sh installer/preinstall.sh installer/cleanup.sh`
- `/opt/conda/envs/docker-infra/bin/python -m unittest tests.api.test_installer_contract.InstallerContractTest tests.api.test_system_settings_dynamic_menu.SystemSettingsStaticContractTest`
- `/opt/conda/envs/docker-infra/bin/python -m unittest tests.api.test_system_settings_dynamic_menu.SystemSettingsStaticContractTest tests.api.test_services_preflight.ServicesPreflightStaticContractTest tests.api.test_installer_contract.InstallerContractTest tests.api.test_backup_registry_nodes.BackupRegistryNodeStaticContractTest`
- WIZ build `main` 성공
- `/opt/conda/envs/docker-infra/bin/wiz bundle --project=main`
- `/root/docker-infra/update-wiz-bundle.sh`
- `cd installer/payload && sha256sum -c checksums.sha256`
- installer payload archive에서 `install_agent_async`, `agent_install_script`, `ai_agent_install`, `ai_agent_install_status` 포함 확인
- installer의 기존 Codex 기본 설치 문구/명령 잔존 검색 완료

## 남은 리스크

- 실제 시스템 설정에서 Agent 설치 스크립트를 실행하는 live 검증은 하지 않았다.
- 헤르메스 Agent의 기본 npm package 이름은 `hermes-agent`로 두었으며, 운영 환경에서 다른 배포 경로를 쓰면 `DOCKER_INFRA_HERMES_AGENT_INSTALL_SCRIPT` 또는 package override 설정이 필요하다.
