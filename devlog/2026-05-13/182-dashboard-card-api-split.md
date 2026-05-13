# 대시보드 카드 단위 API 분리와 부분 로딩 적용

- **ID**: 182
- **날짜**: 2026-05-13
- **유형**: 리팩토링

## 작업 요약
대시보드 초기 로딩이 단일 overview API에 묶이지 않도록 상태, 자원 차트, 서버, 도메인, 최근 작업 API를 분리했다.
프론트엔드는 분리된 API를 병렬 호출하고 카드별 로딩/오류 상태를 표시해 먼저 도착한 카드부터 렌더링하도록 변경했다.

## 원문 요청사항
```text
작업을 진행해줘.

현재 대시보드에서 정보를 불러올 때 하나의 API로 모든 정보를 가져오고 있어.
그런데 이 탓에 처음 화면이 뜨는게 너무 늦어.
각 카드 단위로 API를 분리해서 사용자가 로딩이 빨리되었다고 느낄 수 있도록 해줘.
```

## 변경 파일 목록
- `src/app/page.dashboard/api.py`: 기존 `overview`는 유지하고 `summary`, `resources`, `servers`, `domains`, `operations` API를 추가했다.
- `src/model/struct/infra_catalog_registry.py`: 대시보드 카드별 데이터를 반환하는 `dashboard_status`, `dashboard_resources`, `dashboard_nodes`, `dashboard_domains`, `dashboard_operations` 메서드를 추가했다.
- `src/app/page.dashboard/view.ts`: 단일 `overview` 호출을 카드별 병렬 호출로 바꾸고, 카드별 로딩/오류 상태와 자원 차트 재조회 흐름을 분리했다.
- `src/app/page.dashboard/view.pug`: 전체 화면 로딩 블록 대신 카드별 로딩/오류/빈 상태를 표시하도록 수정했다.
- `devlog.md`, `devlog/2026-05-13/182-dashboard-card-api-split.md`: 작업 이력을 기록했다.

## 확인 결과
- 성공: `/opt/conda/envs/docker-infra/bin/python -m py_compile src/model/struct/infra_catalog_registry.py src/app/page.dashboard/api.py`
- 성공: `/opt/conda/envs/docker-infra/bin/python -m unittest tests.api.test_node_reporter.NodeReporterStaticContractTest`
- 성공: `PYTHONPATH=tests/api /opt/conda/envs/docker-infra/bin/python -m unittest tests.api.test_openapi_contract.OpenApiContractTest.test_static_response_examples_match_declared_schemas`
- 성공: `wiz_project_build(clean=True, projectName="main")`

## 남은 리스크
- 인증 세션이 필요한 운영 URL의 실제 네트워크 waterfall은 이 환경에서 직접 확인하지 못했다.
