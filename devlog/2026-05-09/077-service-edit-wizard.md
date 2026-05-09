# 077. 서비스 수정 wizard와 Compose 버전 갱신 흐름 추가

## 사용자 요청

서비스 관리 화면의 남은 작업을 이어서 진행한다.

## 변경 사항

- 서비스 상세 화면에 `수정` 버튼과 서비스 수정 모달을 추가했다.
- 수정 모달에서 서비스 이름, 설명, 이미지 이름/tag, 내부 포트, 등록 도메인, 연결 포트를 일반 관리자용 폼으로 수정할 수 있게 했다.
- 환경변수와 데이터 보관 볼륨은 고급 설정 토글 안에서 수정하도록 했다.
- 서비스 수정 저장 시 기존 Compose를 wizard 입력값으로 다시 렌더링하고 내부 검증, 이미지/포트/볼륨/도메인 preflight를 다시 실행하도록 했다.
- 수정 저장 시 새 Compose 파일을 쓰고, `.history`에 이전/현재 Compose를 보관하며, `compose_versions`에 새 버전을 추가하도록 했다.
- 수정 후 서비스 상태를 `draft`로 돌려서 사용자가 `서비스 적용`을 통해 서버에 반영하도록 했다.
- 수정한 도메인과 연결 port로 `service_domains`를 갱신하고, 도메인 제거 시 기존 연결 row를 삭제하도록 했다.
- 수정 후 이미지 이력 기록을 갱신하도록 했다.
- 서비스 상세 API가 현재 Compose에서 추출한 component 목록을 함께 내려주도록 했다.
- TODO 문서에서 서비스 수정 wizard와 service domain 갱신 항목을 완료로 갱신했다.
- 정적 테스트에 서비스 수정 API, UI, update mixin 계약을 추가했다.

## 변경 파일

- `devlog.md`
- `devlog/2026-05-09/077-service-edit-wizard.md`
- `docs/docker-infra-development-todo.md`
- `docs/docker-infra-remaining-todo.md`
- `src/app/page.services/api.py`
- `src/app/page.services/view.pug`
- `src/app/page.services/view.ts`
- `src/model/struct/services.py`
- `src/model/struct/services_preflight.py`
- `src/model/struct/services_update.py`
- `src/model/struct/services_wizard.py`
- `tests/api/test_services_preflight.py`

## 검증

- `python -m py_compile src/model/struct/services_update.py src/model/struct/services.py src/model/struct/services_wizard.py src/model/struct/services_preflight.py src/app/page.services/api.py`
- `PYTHONPATH=. python -m unittest tests.api.test_services_preflight.ServicesPreflightStaticContractTest tests.api.test_wiz_structure_contract.WizStructureContractTest tests.api.test_images_templates_catalog.ImagesTemplatesStaticContractTest tests.api.test_migration_schema.MigrationSchemaStaticContractTest`
- `wiz_project_build(clean=false, projectName="main")`
- `git diff --check`

## 비고

- 실제 서비스 수정/배포 실행은 운영 Compose와 nginx 설정을 변경하는 작업이라 이번 검증에서는 직접 실행하지 않았다.
