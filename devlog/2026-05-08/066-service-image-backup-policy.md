# 066. 서비스 이미지 자동 백업 정책과 수동 실행 흐름 추가

## 사용자 요청

서비스 이미지 자동 백업의 경우엔 정책을 잘 설정해야해. docker commit같은 명령어로 백업 시 해당 서비스가 잠깐 멈추기 때문에 사용자가 자동 백업 주기나 시간 등을 설정을 하거나 수동으로 백업할 수도 있어야 해. 이 점을 고려해서 이어서 진행해줘.

## 변경 사항

- `backup_system_settings.metadata`에 자동 백업 정책을 저장하도록 `backup_policy` 기본값, 정규화, 저장/실행 결과 갱신 흐름을 추가했다.
- 서비스 이미지 자동 백업은 기본 비활성화로 두고, 실행 주기, 허용 시간대, 한 번에 처리할 이미지 개수를 설정할 수 있게 했다.
- 자동 백업 실행 모델을 추가해 예약 조건을 만족하거나 수동 실행할 때 아직 내부 Harbor에 저장되지 않은 서비스 이미지 이력만 처리하도록 했다.
- 실행 중 컨테이너 스냅샷 방식은 서비스 중단 가능성이 있으므로 자동 백업 대상에서 제외하고, 현재는 서비스가 사용하는 이미지 tag를 내부 Harbor에 저장하는 방식으로 고정했다.
- 시스템 설정 화면에 자동 백업 정책 저장과 `지금 백업 실행` 버튼, 마지막 실행/최근 결과 표시를 추가했다.
- TODO 문서에 자동 백업 정책 반영 사항과 남은 예약 실행 트리거 연결 작업을 정리했다.

## 변경 파일

- `devlog.md`
- `docs/docker-infra-development-todo.md`
- `docs/docker-infra-remaining-todo.md`
- `src/app/page.system/api.py`
- `src/app/page.system/view.pug`
- `src/app/page.system/view.ts`
- `src/model/struct.py`
- `src/model/struct/backup_system.py`
- `src/model/struct/backup_system_policy.py`
- `src/model/struct/service_image_backup_scheduler.py`

## 검증

- `python -m py_compile src/model/struct/backup_system.py src/model/struct/backup_system_policy.py src/model/struct/service_image_backup_scheduler.py src/model/struct/service_image_backups.py src/model/struct/service_image_backup_actions.py src/model/struct/service_image_backup_runner.py src/app/page.system/api.py`
- `PYTHONPATH=. /opt/conda/envs/docker-infra/bin/python -m unittest tests.api.test_images_templates_catalog.ImagesTemplatesStaticContractTest tests.api.test_migration_schema.MigrationSchemaStaticContractTest tests.api.test_wiz_structure_contract`
- `wiz_project_build(clean=false, projectName="main")`
- `git diff --check`
