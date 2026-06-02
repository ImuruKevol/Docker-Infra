# Claude Code Agent 네이티브 설치 전환

- 날짜: 2026-05-29
- 리뷰 ID: cxaqmytxjrdnjjdcuazqouethjqeipfv
- 요청: 클루드 코드 agent 설치가 현재는 npm 설치로 되어있는데, 네이티브 설치가 훨씬 성능이 좋다고 해. 설치 방법을 수정하고, 화면에도 반영해줘.

## 변경 요약

- Claude Code Agent 기본 설치 방식을 npm global 설치에서 Anthropic 공식 native installer 실행으로 전환했다.
- Claude Code 설치 스크립트는 `https://claude.ai/install.sh`와 `latest` channel을 기본값으로 사용하고, `DOCKER_INFRA_CLAUDE_CODE_NATIVE_INSTALL_URL`, `DOCKER_INFRA_CLAUDE_CODE_INSTALL_CHANNEL`로 override할 수 있게 했다.
- 시스템 설정 AI Agent 화면에서 Claude Code의 설치 방식, 상태 문구, 버튼 문구가 네이티브 설치 기준으로 보이도록 변경했다.
- installer env 생성, env 예시, installer HTML, README/배포 문서를 새 설치 방식에 맞춰 갱신했다.
- installer payload WIZ bundle archive와 checksum을 최신 변경 기준으로 재생성했다.

## 변경 파일

- `README.md`
- `docs/docker-infra-deployment.md`
- `installer/README.md`
- `installer/docker-infra.env.example`
- `installer/install.sh`
- `installer/installer.html`
- `installer/payload/checksums.sha256`
- `installer/payload/wiz-bundle.tar.zst`
- `src/app/page.system/view.pug`
- `src/app/page.system/view.ts`
- `src/model/struct/ai_settings.py`
- `src/model/struct/codex_runtime.py`
- `tests/api/test_installer_contract.py`
- `tests/api/test_system_settings_dynamic_menu.py`
- `devlog.md`
- `devlog/2026-05-29/005-claude-code-native-install.md`

## 확인

- Anthropic Claude Code 공식 setup 문서에서 native install recommended, `curl -fsSL https://claude.ai/install.sh | bash`, native auto-update, `claude --version` 검증 방식을 확인했다.
- `/opt/conda/envs/docker-infra/bin/python -m py_compile src/model/struct/codex_runtime.py src/model/struct/ai_settings.py src/app/page.system/api.py`: 성공
- `bash -n installer/install.sh installer/preinstall.sh installer/cleanup.sh /root/docker-infra/update-wiz-bundle.sh /root/docker-infra/update-wiz-service.sh`: 성공
- `/opt/conda/envs/docker-infra/bin/python -m unittest tests.api.test_installer_contract.InstallerContractTest tests.api.test_system_settings_dynamic_menu.SystemSettingsStaticContractTest`: 성공
- `/opt/conda/envs/docker-infra/bin/python -m unittest tests.api.test_system_settings_dynamic_menu.SystemSettingsStaticContractTest tests.api.test_services_preflight.ServicesPreflightStaticContractTest tests.api.test_installer_contract.InstallerContractTest tests.api.test_backup_registry_nodes.BackupRegistryNodeStaticContractTest`: 성공
- `git diff --check` 대상 변경 파일: 성공
- `wiz_project_build(projectName="main", clean=false)`: 성공
- `/opt/conda/envs/docker-infra/bin/wiz bundle --project=main`: 성공
- `/root/docker-infra/update-wiz-bundle.sh`: 성공, payload checksum 검증 포함
- `installer/payload/wiz-bundle.tar.zst` 내부에 Claude Code native installer 상수와 channel 설정이 포함된 것 확인

## 남은 리스크

- 실제 시스템 설정 화면에서 Claude Code native installer를 실행하는 live 검증은 하지 않았다.
- 운영 환경이 인터넷에서 `https://claude.ai/install.sh`에 접근할 수 있어야 기본 설치가 성공한다.
