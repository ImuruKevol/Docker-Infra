# 015. 시스템 백업 무제한 대상 처리와 기본 백그라운드 실행

## 원 요청

- 리뷰 ID: `umeijhbofjxqlffyghnwvevzoaqihiiq`
- 요청: `"기본/최소 처리 한도를 50개로 보정했습니다." 라고 하는데 한도가 있으면 안돼. 그리고 백업을 누르면 기본적으로 백그라운드에서 돌아가도록 하고 화면 UI에서는 polling같은 방식으로 확인할 수 있도록 개선해줘.`

## 변경 파일

- `src/model/struct/service_image_backup_scheduler.py`
  - 시스템 백업 수동 실행에서 `DEFAULT_SNAPSHOT_LIMIT`와 대상 수 보정 로직을 제거했다.
  - 스냅샷 후보 조회는 등록 서비스 전체를 대상으로 수행하고, 작업 payload에도 처리 한도를 기록하지 않도록 정리했다.
  - 백그라운드 실행 payload에서 legacy 한도 키(`max_items_per_run`, `limit`)를 제거한다.
- `src/model/struct/service_image_backups.py`
  - 런타임 스냅샷 후보 기록 함수의 기본 동작을 무제한 처리로 변경했다.
  - 호환용 `limit` 인자가 들어와도 `None`/빈 값/0 이하 값은 한도로 취급하지 않도록 정리했다.
- `src/model/struct/backup_system_policy_defaults.py`
  - 백업 정책 기본값/정규화 결과에서 처리 한도 필드를 제거했다.
- `src/app/page.system/api.py`
  - `run_backup_policy_now` API가 기본적으로 백그라운드 작업을 생성하고 `202`로 응답하도록 변경했다.
  - legacy 한도 키를 요청 payload에서 제거한다.
- `src/app/page.system/view.ts`
  - 수동 백업 요청에서 `background` 파라미터를 보내지 않아도 백엔드 기본 백그라운드 실행을 사용하도록 변경했다.
  - `200`/`202` 응답 모두 작업 ID를 받아 기존 polling 흐름으로 진행 상태를 확인하도록 정리했다.
- `tests/api/test_backup_system_ui.py`
- `tests/api/test_backup_system_schedule.py`

## 확인 결과

- `python -m py_compile src/model/struct/service_image_backups.py src/model/struct/service_volume_backups.py src/model/struct/service_image_backup_scheduler.py src/model/struct/backup_system_policy.py src/model/struct/backup_system_policy_defaults.py src/app/page.system/api.py` 성공.
- `python -m unittest tests.api.test_backup_system_ui.BackupSystemUiStaticContractTest.test_backup_system_ui_hides_internal_harbor_details_and_streams_backup_progress` 성공.
- `python -m unittest tests.api.test_backup_system_schedule.BackupSystemSchedulePolicyTest.test_force_manual_run_includes_snapshots_even_when_policy_option_is_off` 성공.
- `python -m unittest tests.api.test_backup_system_schedule`는 기존 환경 의존성인 `psycopg` 미설치로 `service_image_backups.py` import 단계에서 실패했다.
- WIZ build(`clean=false`) 성공.

## 남은 리스크

- 실제 백업 시스템/Harbor를 대상으로 한 E2E 실행은 수행하지 않았다.
- 작업 전부터 존재하던 다른 파일 변경과 미추적 파일은 유지했다.
