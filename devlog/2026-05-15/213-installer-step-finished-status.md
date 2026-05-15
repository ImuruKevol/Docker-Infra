# 213. installer 단계 종료 성공/실패 인지 보강

- 날짜: 2026-05-15
- 리뷰 ID: ismjwijqevuqjalzluaiuezfxbdfprcf

## 원 요청

installer 단계별 실행이 종료되었을 때 성공/실패와 관계없이 종료 사실을 확실하게 인지할 수 있게 해 달라고 요청했다.

## 변경 파일

- `installer/installer_api.py`
  - 단계 프로세스 종료 감지 시 `단계 종료` footer를 installer log에 추가하도록 했다.
  - footer에는 step, success/failed result, exit code를 기록한다.
- `installer/installer.html`
  - 실행 상태 metric에 종료 시각을 추가했다.
  - 상태 badge가 단계명 기준으로 `실행 중`, `완료`, `실패(exit code)`를 명확히 표시하도록 했다.
  - API 로그에 footer가 없는 경우에도 UI에서 종료 footer를 보강해 표시하도록 했다.
- `tests/api/test_installer_contract.py`
  - 단계 종료 footer와 종료 시각 UI 계약을 추가했다.
- `devlog.md`
  - 이번 작업 기록을 추가했다.

## 확인 결과

- `bash -n installer/install.sh && bash -n installer/preinstall.sh && bash -n installer/cleanup.sh`: 통과
- `/opt/conda/envs/docker-infra/bin/python -m py_compile installer/installer_api.py tests/api/test_installer_contract.py`: 통과
- `/opt/conda/envs/docker-infra/bin/python -m unittest tests.api.test_installer_contract`: 통과
- `/opt/conda/envs/docker-infra/bin/python -m unittest tests.api.test_installer_contract tests.api.test_system_settings_dynamic_menu tests.api.test_auth_setup tests.api.test_playwright_setup`: 통과, 23개 중 2개 skip
- `rg`로 `finishedAt`, `단계 종료`, 단계별 완료/실패 status 표시 계약 확인: 통과

## 남은 리스크

- 브라우저에서 실제 장시간 설치 단계를 실행하며 종료 표시가 보이는지 E2E로 확인하지는 않았다.
