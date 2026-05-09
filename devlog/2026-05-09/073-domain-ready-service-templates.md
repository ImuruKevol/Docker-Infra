# 073. 기본 서비스 템플릿을 도메인 연결 가능한 다중 서비스 스택으로 교체

## 사용자 요청

현재 저장되어있는 템플릿들을 실제 도메인과 연결이 가능한 템플릿들로 바꾼다. 워드프레스처럼 웹 서비스와 DB 등 여러 서비스가 함께 동작하는 템플릿을 3~4개 정도 구성한다.

## 변경 사항

- 기본 seed 템플릿을 WordPress, Nextcloud, Odoo, Wiki.js 4종으로 교체했다.
- 각 템플릿을 외부 도메인 연결 대상이 되는 web/WAS 구성과 내부 DB 또는 cache 구성이 함께 동작하는 Compose stack으로 구성했다.
- DB, Redis 같은 내부 구성요소는 외부 공개 port 없이 Compose 내부 네트워크로만 연결되도록 정리했다.
- 템플릿 seed 모델을 web stack, business stack, shared helper로 분리해 WIZ 구조의 모델 크기 기준을 지키도록 했다.
- 기존 단일 컨테이너 템플릿과 GitLab/Harbor 계열 legacy seed는 기본 템플릿에서 제거하고, seed 동기화 시 삭제되도록 했다.
- 서비스 생성 wizard에서 내부 구성요소처럼 port가 없는 component도 정상적으로 다음 단계로 진행할 수 있게 검증을 조정했다.
- 템플릿 관련 TODO 문서에 완료 범위와 남은 고급 편집/릴리즈 작업을 반영했다.
- 런타임 템플릿 저장소를 동기화해 현재 저장된 템플릿 디렉토리가 새 4개 템플릿만 남도록 정리했다.

## 변경 파일

- `devlog.md`
- `devlog/2026-05-09/073-domain-ready-service-templates.md`
- `docs/docker-infra-development-todo.md`
- `docs/docker-infra-remaining-todo.md`
- `src/app/page.services.create/view.pug`
- `src/app/page.services.create/view.ts`
- `src/model/struct/templates.py`
- `src/model/struct/templates_seed.py`
- `src/model/struct/templates_seed_business_stacks.py`
- `src/model/struct/templates_seed_shared.py`
- `src/model/struct/templates_seed_web_stacks.py`
- `tests/api/test_images_templates_catalog.py`

## 검증

- `python -m py_compile src/model/struct/templates_seed.py src/model/struct/templates_seed_shared.py src/model/struct/templates_seed_web_stacks.py src/model/struct/templates_seed_business_stacks.py src/model/struct/templates.py`
- `PYTHONPATH=. python -m unittest tests.api.test_images_templates_catalog.ImagesTemplatesStaticContractTest`
- `wiz_project_build(clean=false, projectName="main")`
- `PYTHONPATH=. python -m unittest tests.api.test_images_templates_catalog.ImagesTemplatesStaticContractTest tests.api.test_migration_schema.MigrationSchemaStaticContractTest tests.api.test_wiz_structure_contract`
- `PYTHONPATH=. python -m unittest tests.api.test_images_templates_catalog.ImagesTemplatesLiveFlowTest.test_templates_seed_and_preview_flow`
