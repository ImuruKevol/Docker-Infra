# 067. docker commit 기반 컨테이너 스냅샷 백업과 정책 옵션 추가

## 사용자 요청

그냥 이미지 태그만 저장하는건 의미가 없어. 물론 이것도 하기는 하면 좋은데, 여기에 docker commit을 이용해서 통채로 스냅샷 채로 백업하는 것도 필요하긴 해. 이 점을 반영하고 남은 작업들을 이어서 진행해줘.

## 변경 사항

- 서비스 이미지 백업을 `이미지 tag 백업`과 `컨테이너 스냅샷 백업`으로 분리했다.
- `docker commit --pause=<옵션>`으로 실제 서비스 컨테이너를 스냅샷 이미지로 만든 뒤 내부 Harbor에 push하는 runner를 추가했다.
- 서비스 상세의 이미지 이력에서 개별 Compose service별로 수동 스냅샷 백업을 실행할 수 있게 했다.
- 시스템 설정의 자동 백업 정책에 `컨테이너 스냅샷 포함`, `스냅샷 중 일시 정지` 옵션을 추가했다.
- 예약 실행 모델이 정책에 따라 tag 백업과 스냅샷 백업을 같은 처리량 제한 안에서 실행하도록 수정했다.
- 원격 서버 스냅샷 push가 오래 걸릴 수 있어 SSH 명령 timeout 상한을 백업 작업 기준으로 늘렸다.
- TODO 문서에 docker commit 스냅샷 백업 정책을 반영했다.

## 변경 파일

- `devlog.md`
- `docs/docker-infra-development-todo.md`
- `docs/docker-infra-remaining-todo.md`
- `src/app/page.services/api.py`
- `src/app/page.services/view.pug`
- `src/app/page.services/view.ts`
- `src/app/page.system/view.pug`
- `src/app/page.system/view.ts`
- `src/model/struct/backup_system.py`
- `src/model/struct/backup_system_policy.py`
- `src/model/struct/backup_system_policy_defaults.py`
- `src/model/struct/service_image_backup_actions.py`
- `src/model/struct/service_image_backup_scheduler.py`
- `src/model/struct/service_image_backups.py`
- `src/model/struct/service_image_snapshot_runner.py`
- `src/model/struct/services_runtime.py`
- `src/model/struct/ssh_executor.py`

## 검증

- `python -m py_compile src/model/struct/backup_system.py src/model/struct/backup_system_policy.py src/model/struct/backup_system_policy_defaults.py src/model/struct/service_image_backups.py src/model/struct/service_image_backup_actions.py src/model/struct/service_image_backup_scheduler.py src/model/struct/service_image_snapshot_runner.py src/model/struct/ssh_executor.py src/model/struct/services_runtime.py src/app/page.services/api.py src/app/page.system/api.py`
- `PYTHONPATH=. /opt/conda/envs/docker-infra/bin/python -m unittest tests.api.test_images_templates_catalog.ImagesTemplatesStaticContractTest tests.api.test_migration_schema.MigrationSchemaStaticContractTest tests.api.test_wiz_structure_contract`
- `wiz_project_build(clean=false, projectName="main")`
- `git diff --check`
