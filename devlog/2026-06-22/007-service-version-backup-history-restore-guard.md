# 서비스 버전 이력 백업 내역 연동과 만료 복원 차단

- 날짜: 2026-06-22
- 작업 ID: 007
- 리뷰 ID: vgosoiiihlsnzkukbdizwwevcjgpgjcg

## 사용자 요청

> 백업 시 각 서비스 관리 상세에서 버전 이력 탭에서 백업한 이력이 보여야 해. "자동 백업 - ~~~~" 식으로 해서 보이게 하고, 갯수를 넘어간 이전 릴리즈에 대해서는 복원이 안되니까 못하도록 막는 등등. 중요한건 서비스 관리 상세 화면의 버전 이력 탭과 유기적으로 연동이 되어야 한다는거야.

## 변경 파일

- `src/model/struct/services_runtime.py`
  - 서비스 상세 버전 목록에 백업 이력 항목과 삭제/만료 집계를 함께 첨부.
  - 스냅샷 실행을 위한 임시 대상 레코드는 버전 이력에서 제외.
- `src/model/struct/service_image_backups.py`
  - 자동 백업 스냅샷 결과가 `backup_policy_snapshot` 출처를 유지하도록 metadata를 보강.
- `src/model/struct/services_rollback.py`
  - 보존 정책으로 삭제된 백업만 남은 버전은 rollback plan 단계에서 `SERVICE_ROLLBACK_BACKUP_EXPIRED`로 차단.
- `src/app/page.services/view.ts`
  - 버전 이력용 백업 라벨, 상태, 보존 만료 표시, 복원 차단 판정을 추가.
- `src/app/page.services/view.pug`
  - 버전 이력 탭에 `자동 백업 - app` 형태의 백업 이력 chip과 `복원 불가` 표시를 추가.
  - 복원 불가 버전의 `되돌리기` 버튼을 비활성화.
- `tests/api/test_services_preflight.py`
  - 버전 이력 백업 표시와 만료 복원 차단 계약 검증을 추가.

## 확인 결과

- `/opt/conda/envs/docker-infra/bin/python -m py_compile src/model/struct/services_runtime.py src/model/struct/services_rollback.py src/model/struct/service_image_backups.py tests/api/test_services_preflight.py`
- `/opt/conda/envs/docker-infra/bin/python -m unittest tests.api.test_services_preflight.ServicesPreflightStaticContractTest.test_service_release_contract_is_wired tests.api.test_services_preflight.ServicesPreflightStaticContractTest.test_service_rollback_contract_is_wired`
- `/opt/conda/envs/docker-infra/bin/python -m unittest tests.api.test_backup_system_schedule tests.api.test_backup_system_cleanup tests.api.test_backup_system_ui tests.api.test_backup_registry_nodes tests.api.test_service_migration`
- `git diff --check`
- WIZ build: `wiz_project_build(projectName="main", clean=false)`

## 남은 리스크

- 실제 서비스/Harbor 데이터를 대상으로 한 복원 차단과 만료 표시 검증은 운영 데이터 영향 때문에 수행하지 않았다.
- 과거에 생성된 스냅샷 중 `snapshot_request_source` metadata가 없는 항목은 `자동 백업` 대신 일반 `스냅샷 백업`으로 표시된다.
