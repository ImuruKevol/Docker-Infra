# 064. 외부 Harbor 설정 제거와 내장 로컬 Harbor 백업 시스템 실행 경로 연결

## 사용자 요청

이어서 진행. 기존에 설정했던 Harbor 환경변수는 무시하고 사용하던 부분은 삭제한 뒤, 로컬 Harbor를 새로 띄우는 방향으로 진행. 로컬 Harbor를 띄울 때 초기 admin password 등은 자동으로 가져와 저장하도록 처리.

## 변경 요약

- 외부 Harbor integration 모델과 registry 모델을 제거하고, 기존 `integration.harbor.*` 설정과 `integration_harbor` 테이블을 제거하는 migration을 추가했다.
- 백업 시스템 설정을 기준으로 로컬 Harbor URL, 자동 생성 admin 계정 secret, 저장 경로, 설치 상태, 용량 정보를 관리하도록 `backup_system` 모델을 확장했다.
- Harbor installer 다운로드, `harbor.yml` 생성, install/up/down/restart/ps 실행을 담당하는 `backup_system_resources`, `backup_system_runtime` 모델을 추가했다.
- destructive local command allowlist에 백업 시스템 설치/시작/정지/재시작 command를 추가하고 timeout 상한을 Harbor 설치에 맞게 확장했다.
- 최초 구성에서 백업 시스템을 활성화하면 설정 저장 후 로컬 Harbor 설치/실행을 시도하고, 실패 시 관리자 설정은 유지한 채 시스템 설정에서 재시도할 수 있도록 오류를 반환한다.
- 시스템 설정 화면에서 Harbor URL/token/password 입력 UI를 제거하고, 내장 서비스 백업 시스템 상태와 시작/정지/재시작/상태 갱신 UI로 교체했다.
- 이미지 관리의 Harbor API는 외부 환경변수나 integration table 대신 내장 백업 시스템의 자동 저장 credential만 사용하도록 전환했다.
- GitLab/외부 Harbor 호환 처리 잔여 코드를 dashboard와 템플릿 seed에서 제거하고, 기존 GitLab CE/Harbor Registry seed 템플릿 삭제 migration을 추가했다.
- TODO/README를 로컬 Harbor 백업 시스템 기준으로 갱신했다.

## 변경 파일

- `README.md`
- `config/docker_infra.py`
- `docs/docker-infra-development-todo.md`
- `docs/docker-infra-remaining-todo.md`
- `src/app/page.access/api.py`
- `src/app/page.access/view.ts`
- `src/app/page.dashboard/api.py`
- `src/app/page.dashboard/view.ts`
- `src/app/page.images/view.pug`
- `src/app/page.system/api.py`
- `src/app/page.system/view.pug`
- `src/app/page.system/view.ts`
- `src/model/db/migrations/010_remove_harbor_integration.sql`
- `src/model/db/migrations/010_remove_harbor_integration.down.sql`
- `src/model/db/migrations/011_remove_deprecated_templates.sql`
- `src/model/db/migrations/011_remove_deprecated_templates.down.sql`
- `src/model/struct.py`
- `src/model/struct/backup_system.py`
- `src/model/struct/backup_system_resources.py`
- `src/model/struct/backup_system_runtime.py`
- `src/model/struct/images_harbor.py`
- `src/model/struct/infra_catalog.py`
- `src/model/struct/infra_catalog_registry.py`
- `src/model/struct/integrations.py` 삭제
- `src/model/struct/integrations_registry.py` 삭제
- `src/model/struct/local_command_catalog.py`
- `src/model/struct/setup.py`
- `src/model/struct/templates.py`
- `src/model/struct/templates_seed.py`
- `src/model/struct/templates_seed_harbor.py` 삭제
- `tests/api/test_images_templates_catalog.py`

## DB 적용

- `010_remove_harbor_integration` migration을 실제 DB에 적용했다.
- `011_remove_deprecated_templates` migration을 실제 DB에 적용했다.
- 적용 후 `integration_harbor` table이 제거되고, `backup_system_settings` table이 유지되며, deprecated template row가 0개임을 확인했다.

## 검증

- `python -m py_compile`로 변경 Python 파일 문법 확인.
- `wiz_project_build(clean=false)` 성공.
- `PYTHONPATH=. python -m unittest tests.api.test_images_templates_catalog.ImagesTemplatesStaticContractTest tests.api.test_migration_schema.MigrationSchemaStaticContractTest tests.api.test_wiz_structure_contract` 성공.
- `git diff --check` 성공.
- `src/app`, `src/model/struct`, `config`, `tests` 범위에서 과거 Harbor env key, integration registry 참조가 남지 않았음을 확인.

## 비고

- 민감 정보는 devlog에 기록하지 않았다.
- 실제 Harbor 설치/이미지 pull은 인증된 시스템 설정 API의 `시작` 동작에서 수행된다.
