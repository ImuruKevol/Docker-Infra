# 079. 서비스 처리 로그 모달과 operation polling 조회 추가

## 사용자 요청

- "이어서 진행해줘"
- 서비스 관리 TODO 중 남은 배포/처리 로그 확인 흐름을 이어서 진행.

## 변경 요약

- 서비스 페이지에 `operation_detail` API를 추가해 operation output을 상세 조회할 수 있게 했다.
- 최근 처리 내역에서 각 operation의 로그를 모달로 열 수 있도록 했다.
- 실행 중인 operation은 모달이 열려 있는 동안 2초 주기로 polling해 output과 상태를 갱신하도록 했다.
- stdout/stderr/system 로그를 구분해서 운영자가 처리 흐름을 확인할 수 있게 정리했다.
- TODO 문서에서 배포 output streaming/polling 항목을 완료로 표시했다.

## 변경 파일

- `src/app/page.services/api.py`
- `src/app/page.services/view.ts`
- `src/app/page.services/view.pug`
- `tests/api/test_services_preflight.py`
- `docs/docker-infra-remaining-todo.md`
- `docs/docker-infra-development-todo.md`
- `devlog.md`

## 검증

- `python -m py_compile src/app/page.services/api.py src/model/struct/services_rollback.py src/model/struct/services.py`
- `PYTHONPATH=. python -m unittest tests.api.test_services_preflight.ServicesPreflightStaticContractTest tests.api.test_wiz_structure_contract.WizStructureContractTest tests.api.test_images_templates_catalog.ImagesTemplatesStaticContractTest tests.api.test_migration_schema.MigrationSchemaStaticContractTest`
- `wiz_project_build(clean=false, projectName="main")`
- `git diff --check`
