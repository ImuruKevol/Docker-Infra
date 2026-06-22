# 자동 백업 실행 대상 등록 서비스 스냅샷으로 전환

- 날짜: 2026-06-22
- 작업 ID: 005
- 리뷰 ID: vgosoiiihlsnzkukbdizwwevcjgpgjcg

## 사용자 요청

> 지금 백업 실행을 누르니까 스냅샷 대상 0개라고 뜨네? 등록되어있는 서비스들을 기준으로 해당 서비스들이 떠있는 서버에 백업 명령을 날리고 백업 시스템(harbor)에 push하는 것까지 되어야 해.

## 변경 파일

- `src/model/struct/service_image_backup_scheduler.py`
  - 수동/자동 백업 실행 대상을 기존 이미지 이력 기준이 아니라 등록 서비스의 실행 중인 컨테이너 스냅샷 대상으로 변경.
  - 이미지 단독 백업 처리 루프를 제거하고 스냅샷 생성 및 Harbor push 흐름만 실행하도록 정리.
- `src/model/struct/service_image_backups.py`
  - 등록 서비스와 서버 컨테이너 목록을 기준으로 런타임 스냅샷 대상 레코드를 생성하는 `record_runtime_snapshot_targets` 추가.
  - 대상 노드/컨테이너 정보를 metadata에 저장해 실제 컨테이너가 떠있는 서버에서 스냅샷이 실행되도록 연결.
- `src/model/struct/service_image_snapshot_runner.py`
  - 스냅샷 대상 metadata의 node/container를 우선 사용해 해당 서버에서 `docker commit`/`docker push`가 실행되도록 보정.
  - 복수 컨테이너 스냅샷의 태그 충돌을 줄이기 위해 노드/컨테이너 식별자를 백업 태그에 포함.
- `tests/api/test_backup_system_schedule.py`
  - 등록 서비스의 실행 중인 컨테이너에서 스냅샷 대상이 생성되는 단위 검증 추가.
  - 수동 실행이 이미지 백업이 아니라 스냅샷 대상으로 동작하는 기대값으로 갱신.
- `tests/api/test_backup_system_ui.py`
  - 백업 실행이 등록 서비스 런타임 스냅샷 대상을 사용한다는 정적 계약 검증 추가.

## 확인 결과

- `/opt/conda/envs/docker-infra/bin/python -m py_compile src/model/struct/service_image_backups.py src/model/struct/service_image_backup_scheduler.py src/model/struct/service_image_snapshot_runner.py tests/api/test_backup_system_schedule.py`
- `/opt/conda/envs/docker-infra/bin/python -m unittest tests.api.test_backup_system_schedule tests.api.test_backup_system_ui tests.api.test_backup_registry_nodes tests.api.test_service_migration`
- `git diff --check`
- WIZ build: `wiz_project_build(projectName="main", clean=false)`

## 남은 리스크

- 실제 Harbor push가 발생하는 수동 백업 실행은 운영 데이터에 영향을 줄 수 있어 직접 실행하지 않았다.
- 등록 서버의 Docker 접근 또는 SSH 접근이 실패하면 해당 서버의 스냅샷 대상 생성/실행이 실패한다.
