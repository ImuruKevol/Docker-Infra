# 212. installer 관리자 비밀번호 단계 보강과 시스템 General 비밀번호 변경 추가

- 날짜: 2026-05-15
- 리뷰 ID: ismjwijqevuqjalzluaiuezfxbdfprcf

## 원 요청

installer에서 관리자 패스워드를 설정하는 부분을 보강하고, 다른 단계 실행 시 실행 상태 터미널 로그가 clear되도록 수정하며, Docker Infra 시스템 설정의 General에 관리자 패스워드 변경 기능을 추가한 뒤 새 bundle을 만들어 installer에 복사해 달라고 요청했다.

## 변경 파일

- `installer/installer.html`
  - `setup` 단계를 `관리자 비밀번호 / 초기 시스템 설정`으로 명확히 표시했다.
  - 관리자 비밀번호 입력 test id를 추가하고, 단계 실행 시작 시 로그 화면을 초기화하도록 했다.
- `installer/installer_api.py`
  - 단계 실행마다 installer log 파일을 새로 열어 이전 단계 로그가 터미널에 다시 표시되지 않도록 했다.
- `src/model/struct/auth.py`
  - 현재 비밀번호 검증 후 새 관리자 비밀번호를 저장하는 `change_password`를 추가했다.
- `src/app/page.system/api.py`
  - General 탭에서 호출할 `change_admin_password` API를 추가했다.
- `src/app/page.system/view.pug`, `src/app/page.system/view.ts`
  - General 탭에 현재/새/확인 비밀번호 입력과 변경 버튼을 추가했다.
- `tests/api/test_installer_contract.py`, `tests/api/test_system_settings_dynamic_menu.py`
  - installer 관리자 비밀번호 UI, 로그 초기화, 시스템 General 비밀번호 변경 계약을 추가했다.
- `docs/docker-infra-design.md`, `docs/docker-infra-runtime.md`, `docs/docker-infra-deployment.md`
  - 설치 이후 관리자 비밀번호 변경 위치를 문서화했다.
- `installer/payload/wiz-bundle.tar.zst`, `installer/payload/checksums.sha256`
  - 변경된 WIZ bundle을 재생성해 installer payload에 반영했다.
- `devlog.md`
  - 이번 작업 기록을 추가했다.

## 확인 결과

- `bash -n installer/install.sh && bash -n installer/preinstall.sh && bash -n installer/cleanup.sh`: 통과
- `/opt/conda/envs/docker-infra/bin/python -m py_compile installer/installer_api.py src/app/page.system/api.py src/model/struct/auth.py tests/api/test_installer_contract.py tests/api/test_system_settings_dynamic_menu.py`: 통과
- `/opt/conda/envs/docker-infra/bin/python -m unittest tests.api.test_installer_contract tests.api.test_system_settings_dynamic_menu tests.api.test_auth_setup tests.api.test_playwright_setup`: 통과, 23개 중 2개 skip
- `wiz_project_build(projectName="main", clean=false)`: 통과
- `/opt/conda/envs/docker-infra/bin/wiz bundle --project=main`: 통과
- `tar --zstd -cf installer/payload/wiz-bundle.tar.zst bundle`: 통과
- `sha256sum -c installer/payload/checksums.sha256`: 통과
- 새 bundle archive에서 `change_admin_password`, `change_password`, `system-admin-password-save` 포함 여부 확인: 통과

## 남은 리스크

- 관리자 비밀번호 변경 live flow는 실제 DB가 연결된 환경에서 현재 비밀번호를 입력해야 검증할 수 있다.
- installer HTML의 단계형 UI는 정적 계약 테스트로 확인하며 브라우저 클릭 E2E는 별도로 수행하지 않았다.
