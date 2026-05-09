# 065. 백업 시스템 비활성화/초기화와 서비스 이미지 이력·백업·복원 흐름 추가

## 사용자 요청

마이그레이션은 개발 단계라 신경쓰지 말고, 남은 작업들을 순서대로 이어서 진행.

## 변경 요약

- 최초 구성에서 백업 시스템 설치가 실패하면 대시보드로 건너뛰거나 백업 시스템을 사용 안 함으로 저장할 수 있게 했다.
- 시스템 설정의 서비스 백업 시스템에 `비활성화`와 `초기화` 흐름을 추가했다.
- 백업 시스템 초기화는 별도 위험 모달에서 `초기화` 확인 문구를 요구하고, 저장 데이터 삭제 여부를 선택할 수 있게 했다.
- 서비스 생성/Compose 갱신 시 Compose의 image ref를 `service_image_backups` 런타임 스키마에 기록하도록 했다.
- 서비스 상세 화면에 이미지 이력 카드를 추가하고, 이미지 이력 갱신·내장 Harbor 백업 실행·Compose 이미지 복원 버튼을 제공했다.
- 이미지 백업 실행은 내장 Harbor가 실행 중일 때 Docker pull/tag/login/push를 수행하며, password는 `--password-stdin`으로 전달하고 operation output에서 masking한다.
- digest가 같은 이미지 백업이 이미 성공한 경우 기존 backup ref를 재사용하도록 중복 백업 방지 로직을 추가했다.
- TODO 문서에서 P2/P3 완료 항목과 P4 진행 항목을 반영했다.

## 변경 파일

- `docs/docker-infra-development-todo.md`
- `docs/docker-infra-remaining-todo.md`
- `src/app/page.access/api.py`
- `src/app/page.access/view.ts`
- `src/app/page.services/api.py`
- `src/app/page.services/view.pug`
- `src/app/page.services/view.ts`
- `src/app/page.system/api.py`
- `src/app/page.system/view.pug`
- `src/app/page.system/view.ts`
- `src/model/struct.py`
- `src/model/struct/backup_system_runtime.py`
- `src/model/struct/service_image_backup_actions.py`
- `src/model/struct/service_image_backup_runner.py`
- `src/model/struct/service_image_backups.py`
- `src/model/struct/services.py`
- `src/model/struct/services_runtime.py`

## 검증

- `python -m py_compile src/app/page.access/api.py src/app/page.system/api.py src/model/struct/backup_system_runtime.py`
- `python -m py_compile src/model/struct/service_image_backups.py src/model/struct/service_image_backup_actions.py src/model/struct/service_image_backup_runner.py src/model/struct/services.py src/model/struct/services_runtime.py src/app/page.services/api.py`
- `wiz_project_build(clean=false)` 성공.
- `PYTHONPATH=. python -m unittest tests.api.test_images_templates_catalog.ImagesTemplatesStaticContractTest tests.api.test_migration_schema.MigrationSchemaStaticContractTest tests.api.test_wiz_structure_contract` 성공.
- `git diff --check` 성공.

## 비고

- 새 migration은 만들지 않았다. 개발 단계 기준으로 서비스 이미지 이력 테이블은 런타임에서 필요한 시점에 생성한다.
- 실제 이미지 백업은 내장 Harbor가 실행 중이어야 성공한다.
