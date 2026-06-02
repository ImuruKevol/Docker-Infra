# Claude Code 설치 스크립트 문구 롤백과 기존 설치 정리

- 날짜: 2026-05-29
- 리뷰 ID: cxaqmytxjrdnjjdcuazqouethjqeipfv
- 요청: 현재 npm으로 설치한 claude code agent를 삭제하고 내가 직접 화면에서 네이티브 방식으로 설치할 수 있도록 해줘. 그리고 사용자는 네이티브던 npm이던 관심 없어. 단어는 이전 그대로 설치 스크립트로 롤백해줘.

## 변경 요약

- 현재 서버에 npm global로 설치되어 있던 `@anthropic-ai/claude-code@2.1.156`을 제거했다.
- Claude Code 설치 스크립트 실행 시 기존 npm global 설치본이 있으면 먼저 조용히 정리한 뒤 Claude Code 설치 스크립트를 실행하도록 보강했다.
- 시스템 설정 화면의 Claude Code 문구에서 네이티브/npm 노출을 제거하고 `설치 스크립트 실행`, `설치됨`, `설치 필요` 중심으로 되돌렸다.
- installer 화면, README, installer README, 배포 문서를 설치 스크립트 표현으로 정리했다.
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
- `src/model/struct/codex_runtime.py`
- `tests/api/test_installer_contract.py`
- `tests/api/test_system_settings_dynamic_menu.py`
- `devlog.md`
- `devlog/2026-05-29/006-claude-code-install-script-wording.md`

## 확인

- `npm uninstall -g @anthropic-ai/claude-code`: 성공
- `npm list -g --depth=0 @anthropic-ai/claude-code`: global 목록에서 제거 확인
- `command -v claude`: 제거 후 경로 없음 확인
- `/opt/conda/envs/docker-infra/bin/python -m py_compile src/model/struct/codex_runtime.py src/model/struct/ai_settings.py src/app/page.system/api.py`: 성공
- `bash -n installer/install.sh installer/preinstall.sh installer/cleanup.sh /root/docker-infra/update-wiz-bundle.sh /root/docker-infra/update-wiz-service.sh`: 성공
- `/opt/conda/envs/docker-infra/bin/python -m unittest tests.api.test_installer_contract.InstallerContractTest tests.api.test_system_settings_dynamic_menu.SystemSettingsStaticContractTest`: 성공
- `/opt/conda/envs/docker-infra/bin/python -m unittest tests.api.test_system_settings_dynamic_menu.SystemSettingsStaticContractTest tests.api.test_services_preflight.ServicesPreflightStaticContractTest tests.api.test_installer_contract.InstallerContractTest tests.api.test_backup_registry_nodes.BackupRegistryNodeStaticContractTest`: 성공
- `git diff --check` 대상 변경 파일: 성공
- `wiz_project_build(projectName="main", clean=false)`: 성공
- `/opt/conda/envs/docker-infra/bin/wiz bundle --project=main`: 성공
- `/root/docker-infra/update-wiz-bundle.sh`: 성공, payload checksum 검증 포함
- `installer/payload/wiz-bundle.tar.zst` 내부에 Claude Code 설치 스크립트 URL과 기존 npm 설치 정리 명령이 포함된 것 확인

## 남은 리스크

- 시스템 설정 화면에서 Claude Code 설치 스크립트를 실제 클릭해 설치하는 live 검증은 하지 않았다.
- 운영 환경이 Claude Code 설치 스크립트 URL에 접근할 수 있어야 설치가 성공한다.
