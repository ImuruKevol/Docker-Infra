# 063. WIZ 구조 계약에 맞춘 대형 모델 분리와 api.py 응답 위치 정리

## 사용자 요청

> 이어서 진행해줘.

P2 변경 검증 중 WIZ 구조 계약 테스트에서 기존 대형 model 파일과 `wiz.response` 위치 문제가 드러나 함께 보완했다.

## 변경 파일

- `src/model/struct/images.py`
- `src/model/struct/images_local.py`
  - 로컬 이미지 조회/삭제, 캐시 갱신, Harbor tag 캐시 보조 로직을 `images_local` mixin으로 분리했다.
- `src/model/struct/nodes_runtime.py`
- `src/model/struct/nodes_runtime_files.py`
  - 서버 파일 브라우징/파일 읽기 로직을 `nodes_runtime_files` mixin으로 분리했다.
- `src/model/struct/templates_seed.py`
- `src/model/struct/templates_seed_harbor.py`
  - Harbor 기본 템플릿 seed를 별도 model로 분리했다.
- `src/model/struct/templates_store.py`
  - 반환 객체 구성을 간결하게 정리해 300줄 제한 안으로 맞췄다.
- `src/model/struct/domains_cloudflare.py`
  - helper와 operation 기록 호출부를 압축해 300줄 제한 안으로 맞췄다.
- `src/app/page.system/api.py`
  - `wiz.response.status`가 `try` 블록 안에서 호출되던 분기를 code/payload 방식으로 정리했다.
- `docs/docker-infra-remaining-todo.md`
- `docs/docker-infra-development-todo.md`
  - P1에서 완료된 `operation_logs` schema 항목을 완료로 반영했다.

## 검증

- `python -m py_compile src/app/page.system/api.py src/model/struct/images.py src/model/struct/images_local.py src/model/struct/nodes_runtime.py src/model/struct/nodes_runtime_files.py src/model/struct/templates_seed.py src/model/struct/templates_seed_harbor.py src/model/struct/templates_store.py`
- `PYTHONPATH=tests/api /opt/conda/envs/docker-infra/bin/python -m unittest tests.api.test_wiz_structure_contract tests.api.test_migration_schema.MigrationSchemaStaticContractTest tests.api.test_openapi_contract.OpenApiContractTest.test_static_openapi_contains_initial_contract tests.api.test_openapi_contract.OpenApiContractTest.test_static_openapi_contains_p1_common_components tests.api.test_openapi_contract.OpenApiContractTest.test_static_response_examples_match_declared_schemas`
- `wiz_project_build(clean=false)`
