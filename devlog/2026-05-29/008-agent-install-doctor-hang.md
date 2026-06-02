# Agent 설치 스크립트 완료 상태 갱신 지연 수정

- 날짜: 2026-05-29
- 리뷰 ID: cxaqmytxjrdnjjdcuazqouethjqeipfv
- 요청: Claude Code 설치 완료 메시지와 버전 출력까지 떴지만 진행 중 상태가 업데이트되지 않는 문제를 수정해 달라는 요청.

## 변경 요약

- Claude Code 설치 후 `/root/.local/bin/claude doctor`가 종료되지 않아 설치 operation이 `running`에 남는 원인을 확인했다.
- 현재 걸려 있던 `claude doctor` 프로세스를 종료해 부모 설치 스크립트가 끝날 수 있게 했다.
- Agent 설치 스크립트와 상태 확인 command에서 `doctor` 호출을 제거하고, 비대화형 `--version` 검증만 수행하도록 변경했다.
- `doctor` 호출이 runtime 코드에 다시 들어오지 않도록 시스템 설정 정적 계약 테스트를 보강했다.
- installer payload WIZ bundle archive와 checksum을 최신 변경 기준으로 재생성했다.

## 변경 파일

- `src/model/struct/codex_runtime.py`
- `tests/api/test_system_settings_dynamic_menu.py`
- `installer/payload/checksums.sha256`
- `installer/payload/wiz-bundle.tar.zst`
- `devlog.md`
- `devlog/2026-05-29/008-agent-install-doctor-hang.md`

## 확인

- `ps`로 `/root/.local/bin/claude doctor`가 설치 스크립트 하위에서 실행 중임을 확인했다.
- `kill <claude doctor pid>` 실행 후 해당 설치 스크립트/doctor 프로세스가 사라진 것 확인.
- `timeout 3s claude doctor`가 timeout 124로 끝나는 것을 재현했다.
- `claude --version`: `2.1.156 (Claude Code)` 확인.
- `/opt/conda/envs/docker-infra/bin/python -m py_compile src/model/struct/codex_runtime.py src/model/struct/ai_settings.py src/app/page.system/api.py`: 성공
- `bash -n installer/install.sh installer/preinstall.sh installer/cleanup.sh /root/docker-infra/update-wiz-bundle.sh /root/docker-infra/update-wiz-service.sh`: 성공
- `/opt/conda/envs/docker-infra/bin/python -m unittest tests.api.test_installer_contract.InstallerContractTest tests.api.test_system_settings_dynamic_menu.SystemSettingsStaticContractTest`: 성공
- `/opt/conda/envs/docker-infra/bin/python -m unittest tests.api.test_system_settings_dynamic_menu.SystemSettingsStaticContractTest tests.api.test_services_preflight.ServicesPreflightStaticContractTest tests.api.test_installer_contract.InstallerContractTest tests.api.test_backup_registry_nodes.BackupRegistryNodeStaticContractTest`: 성공
- `git diff --check` 대상 변경 파일: 성공
- `wiz_project_build(projectName="main", clean=false)`: 성공
- `/opt/conda/envs/docker-infra/bin/wiz bundle --project=main`: 성공
- `/root/docker-infra/update-wiz-bundle.sh`: 성공, payload checksum 검증 포함
- `installer/payload/wiz-bundle.tar.zst` 내부 `codex_runtime.py`에 `doctor` 호출이 없고 `--version` 검증만 남은 것 확인

## 남은 리스크

- 화면에서 같은 설치 operation이 완료 상태로 보이는지 브라우저 live 검증은 하지 않았다.
- 기존 stuck operation이 이미 클라이언트 캐시에 남아 있으면 화면 새로고침이 필요할 수 있다.
