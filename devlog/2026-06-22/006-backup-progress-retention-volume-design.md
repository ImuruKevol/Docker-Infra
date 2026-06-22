# 백업 진행 서비스명 표시와 보존 정책 자동 정리

- 날짜: 2026-06-22
- 작업 ID: 006
- 리뷰 ID: vgosoiiihlsnzkukbdizwwevcjgpgjcg

## 사용자 요청

> - 백업 시 그냥 "app 스냅샷 백업을 시작합니다." 라고만 뜨는데, 어떤 서비스의 스냅샷인지 표시가 되어야 해.
> - 백업 시 서비스별 보존 개수에 지정한 숫자에 맞도록 초과하는 이전 이미지는 harbor에서 삭제가 되는지 확인해줘.
> - named volume의 경우엔 docker commit으로 백업이 되지 않는데, 이건 어떻게 스냅샷 백업을 하면 좋을지 설계안을 작성해줘. DB의 경우엔 스냅샷은 따로 push하지 않고 named volume만 백업하면 되는 경우가 대부분이라 이 부분도 고려가 되어야 해.

## 변경 파일

- `src/model/struct/service_image_backups.py`
  - 스냅샷 대상 metadata에 서비스명과 namespace를 저장하도록 보강.
- `src/model/struct/service_image_backup_scheduler.py`
  - 진행 로그에 `서비스명 / compose 서비스명` 형태의 스냅샷 대상을 표시.
  - 백업 성공 후 `service_image_backup_cleanup`을 호출해 서비스별 보존 개수 초과 Harbor 태그를 정리하도록 연결.
- `src/model/struct/backup_system_policy.py`
  - 마지막 백업 결과에 보존 정책 정리 결과를 함께 저장하도록 보강.
- `docs/backup-named-volume-snapshot-design.md`
  - named volume 스냅샷 백업 설계안 추가.
  - DB 서비스의 `volume_only` 백업, Harbor OCI artifact 저장, 복구 흐름, 보존 정책 연동을 정리.
- `tests/api/test_backup_system_schedule.py`
  - 진행 로그 서비스명 표시와 보존 정책 정리 호출 검증 추가.
- `tests/api/test_backup_system_cleanup.py`
  - scheduler의 보존 정책 정리 연동과 named volume 설계 문서 존재 검증 추가.

## 확인 결과

- `/opt/conda/envs/docker-infra/bin/python -m py_compile src/model/struct/service_image_backup_scheduler.py src/model/struct/service_image_backups.py tests/api/test_backup_system_schedule.py tests/api/test_backup_system_cleanup.py`
- `/opt/conda/envs/docker-infra/bin/python -m unittest tests.api.test_backup_system_schedule tests.api.test_backup_system_ui tests.api.test_backup_registry_nodes tests.api.test_service_migration tests.api.test_backup_system_cleanup`
- `git diff --check`
- WIZ build: `wiz_project_build(projectName="main", clean=false)`

## 남은 리스크

- 실제 Harbor 삭제가 발생하는 보존 정책 정리는 운영 백업 태그에 영향을 줄 수 있어 실환경 실행으로 검증하지 않았다.
- named volume 스냅샷은 설계 문서만 추가했으며, 실제 volume archive/OCI artifact push 구현은 후속 작업이다.
