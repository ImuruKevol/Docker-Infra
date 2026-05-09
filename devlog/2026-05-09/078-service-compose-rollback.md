# 078. Compose 버전 되돌리기와 영향 범위 확인 모달 추가

## 사용자 요청

- "이어서 진행해줘"
- 직전 서비스 관리 TODO 중 남은 작업을 순서대로 이어서 진행.

## 변경 요약

- 서비스 상세 고급 정보의 Compose 버전 이력에서 버전별 되돌리기 버튼을 추가했다.
- 되돌리기 실행 전 이미지 변경, 포트 변경, 구성 추가/제거, 도메인 연결 영향 범위를 확인하는 전용 모달을 추가했다.
- 선택한 Compose 버전 파일을 현재 Compose로 복원하고, 새 Compose 버전 이력과 이미지 이력, operation log를 남기는 `services_rollback` struct를 추가했다.
- 되돌린 뒤 바로 배포할 수 있도록 "되돌리고 적용" 흐름을 연결했다.
- TODO 문서에서 Compose rollback과 영향 범위 확인 모달 항목을 완료로 표시했다.

## 변경 파일

- `src/model/struct/services_rollback.py`
- `src/model/struct/services.py`
- `src/app/page.services/api.py`
- `src/app/page.services/view.ts`
- `src/app/page.services/view.pug`
- `tests/api/test_services_preflight.py`
- `docs/docker-infra-remaining-todo.md`
- `docs/docker-infra-development-todo.md`
- `devlog.md`

## 검증

- `python -m py_compile src/model/struct/services_rollback.py src/model/struct/services.py src/app/page.services/api.py`
- `PYTHONPATH=. python -m unittest tests.api.test_services_preflight.ServicesPreflightStaticContractTest`
- `PYTHONPATH=. python -m unittest tests.api.test_services_preflight.ServicesPreflightStaticContractTest tests.api.test_wiz_structure_contract.WizStructureContractTest tests.api.test_images_templates_catalog.ImagesTemplatesStaticContractTest tests.api.test_migration_schema.MigrationSchemaStaticContractTest`
- `wiz_project_build(clean=false, projectName="main")`
- `git diff --check`
