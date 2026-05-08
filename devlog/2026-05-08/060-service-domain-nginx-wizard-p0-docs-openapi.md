# 060. 서비스-도메인 nginx 연결 wizard TODO 반영과 P0 문서/OpenAPI 정리

## 사용자 요청

nginx 설정은 서비스에서 도메인을 연결해야 하므로 직접 수정은 고급 모드로 격리하되, 폼이나 마법사 형태로 서비스와 도메인을 연결할 수 있어야 한다는 점을 TODO에 반영한다. 이후 남은 작업을 순서대로 진행한다.

## 변경 파일

- `docs/docker-infra-development-todo.md`: 서비스 생성/수정 wizard에서 도메인 선택, 신규 도메인 연결, 내부 port와 SSL 방식 기반 nginx 자동 생성, helper 문구 표시 TODO를 추가했다. P0 문서 정리와 OpenAPI 정리 완료 상태를 반영했다.
- `docs/docker-infra-remaining-todo.md`: P5/P7에 서비스-도메인-nginx 연결 wizard TODO를 추가하고, P0 문서/OpenAPI 항목을 완료로 표시했다.
- `docs/docker-infra-design.md`: 기존 다단계 작업 큐와 외부 registry 중심 설계를 제거하고, 단일 운영 장비, 고정 nginx, 서비스 wizard, 내장 백업 시스템, operation/audit log 중심 설계로 재작성했다.
- `docs/docker-infra-runtime.md`: runtime API와 운영 기준에서 기존 작업 큐 API를 제거하고, operation log, 서비스-도메인-nginx 연결, 내장 백업 시스템 기준을 정리했다.
- `README.md`: 제품 패키징 전제, nginx 고정, 내장 백업 시스템 선택 흐름, 서비스 wizard 중심 운영 흐름을 반영했다.
- `docs/api/openapi.json`: `/api/jobs*` path, Job tag, Job schema를 제거하고 `OperationSummary`와 operation 기반 node join 응답으로 정리했다.
- `tests/api/test_openapi_contract.py`: OpenAPI 계약 테스트가 Job schema 제거와 `OperationSummary`를 기대하도록 수정했다.
- `tests/api/test_wiz_structure_contract.py`: 제거 예정인 Job route를 protected route 필수 목록에서 제외했다.
- `devlog.md`: 060 작업 요약 row를 추가했다.
- `devlog/2026-05-08/060-service-domain-nginx-wizard-p0-docs-openapi.md`: 상세 devlog를 추가했다.

## 검증

- `git diff --check`: 통과.
- `rg -n "Job|jobs|job_|job\\b|harbor_token|GitLab|gitlab|external Harbor|외부 Harbor" docs/api/openapi.json`: 제거 확인.
- `rg -n "Job Queue|Job Worker|/api/jobs|job_steps|job_logs|integration_gitlab|integration_harbor|GitLab|Apache2|apache2|httpd|외부 Harbor 연동" README.md docs/docker-infra-design.md docs/docker-infra-runtime.md`: 제거 확인.
- `PYTHONPATH=tests/api python -m unittest tests.api.test_openapi_contract.OpenApiContractTest.test_static_openapi_contains_initial_contract tests.api.test_openapi_contract.OpenApiContractTest.test_static_openapi_contains_p1_common_components tests.api.test_openapi_contract.OpenApiContractTest.test_static_response_examples_match_declared_schemas`: 통과.
- `PYTHONPATH=tests/api python -m unittest tests.api.test_openapi_contract`: 정적 OpenAPI 검사는 통과했으나 live dashboard 계약 테스트는 현재 인증 세션이 없어 `401`로 실패했다.
- `python -m unittest tests.api.test_wiz_structure_contract`: 기존 model 파일 길이 제한과 `page.system/api.py`의 try/except 내부 `wiz.response` 위치 이슈로 실패했다. 이번 변경과 직접 관련된 protected route 목록은 새 방향으로 갱신했다.
