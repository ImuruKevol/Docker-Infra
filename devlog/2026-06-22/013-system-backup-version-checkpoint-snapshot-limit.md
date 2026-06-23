# 013. 시스템 백업 전체 스냅샷 대상 처리와 버전 이력 체크포인트 연결

## 사용자 원 요청

- 리뷰 ID `umeijhbofjxqlffyghnwvevzoaqihiiq`
- 시스템 설정에서 백업을 실행했는데 `notedown-server` 서비스는 이미지는 백업되지 않고 볼륨만 백업되는지 확인 필요.
- 백업 완료 후 해당 서비스의 버전 이력에 아무것도 표시되지 않지만, 이미지 관리의 백업 저장소에는 이미지가 올라간 것을 확인함.

## 변경 요약

- 시스템 백업 스냅샷 대상 기본 처리 한도를 50개로 높이고, 숨겨진 기존 정책값이 3개로 남아 있어도 수동/예약 백업에서 최소 50개까지 스캔하도록 보정했다.
- 이미지 스냅샷 대상과 named volume 백업 대상 수집 시 현재 Compose 파일 checksum 기준의 `compose_versions` 체크포인트를 보장하도록 추가했다.
- 백업 체크포인트가 서비스 버전 이력에 `자동 백업`으로 표시되도록 문구와 source label을 보정했다.
- 백업 정책 마지막 실행 결과에 named volume 처리 건수도 저장하도록 보강했다.

## 변경 파일

- `src/model/struct/service_image_backup_scheduler.py`
- `src/model/struct/service_image_backups.py`
- `src/model/struct/service_volume_backups.py`
- `src/model/struct/backup_system_policy.py`
- `src/model/struct/backup_system_policy_defaults.py`
- `src/app/page.system/view.ts`
- `src/app/page.services/view.ts`
- `src/app/page.services/view.pug`
- `tests/api/test_backup_system_ui.py`
- `tests/api/test_backup_system_schedule.py`
- `tests/api/test_services_preflight.py`
- `devlog.md`
- `devlog/2026-06-22/013-system-backup-version-checkpoint-snapshot-limit.md`

## 확인 결과

- `python -m py_compile src/model/struct/service_image_backups.py src/model/struct/service_volume_backups.py src/model/struct/service_image_backup_scheduler.py src/model/struct/backup_system_policy.py src/model/struct/backup_system_policy_defaults.py` 통과.
- `python -m unittest tests.api.test_backup_system_ui.BackupSystemUiStaticContractTest.test_backup_system_ui_hides_internal_harbor_details_and_streams_backup_progress` 통과.
- `python -m unittest tests.api.test_backup_system_schedule.BackupSystemSchedulePolicyTest.test_force_manual_run_includes_snapshots_even_when_policy_option_is_off` 통과.
- `python -m unittest tests.api.test_services_preflight.ServicesPreflightStaticContractTest.test_service_release_contract_is_wired` 통과.
- `wiz_project_build(clean=false)` 통과.
- 전체 `python -m unittest tests.api.test_backup_system_ui tests.api.test_backup_system_schedule tests.api.test_backup_system_cleanup tests.api.test_services_preflight`는 현재 환경의 `psycopg` 미설치 및 별도 서비스 생성 템플릿 정적 계약 불일치로 실패했다.
