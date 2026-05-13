# 대시보드 배치·도메인 조회·ApexCharts hover와 자원 min/max 보정

- **ID**: 170
- **날짜**: 2026-05-13
- **유형**: UX 개선 / 버그 수정

## 작업 요약
대시보드에서 서버 목록 카드를 사용 중인 도메인 카드 왼쪽으로 옮기고 최근 작업 카드를 하단 단독 영역으로 내렸습니다.
도메인 사용 현황은 `service_domains` 기준으로 우선 조회하도록 바꾸고, ApexCharts가 생성하는 `title` 속성과 SVG `title` 노드를 렌더 후 제거하도록 보강했습니다.
자원 추이는 DB의 `resource_window` 통계를 우선 사용하고, metadata 안의 `sample_count`를 올바르게 반영하도록 수정했습니다.

## 원문 요청사항
```text
서버 목록 카드를 사용 중인 도메인 왼쪽으로 옮기고, 최근 작업 카드를 아래쪽으로 내려줘.
그리고 도메인 정보가 불러와지지 않고 있어.

그리고 apexcharts들에 마우스를 hover하면 title 속성때문에 짜증나. title 속성에 들어가있는걸 지워줘.

그리고 자원 추이에서 min/max값들이 min값과 max값이 같은 값(ex: min 3.4%, max 3.4%)으로 표시가 되고 있어. 확인해줘.
```

## 변경 파일 목록
- `src/app/page.dashboard/view.pug`: 서버/도메인/최근 작업 카드 배치 재정렬.
- `src/app/page.dashboard/view.ts`: 대시보드 ApexCharts 렌더 후 `title` 속성 및 SVG `title` 제거 로직 추가.
- `src/app/page.servers/view.ts`: 서버 상세 자원 ApexCharts에도 동일한 `title` 제거 로직 적용.
- `src/model/struct/infra_catalog_registry.py`: 도메인 사용 현황을 서비스 도메인 기준으로 조회하고, 대시보드 자원 차트는 DB metric window 통계를 우선 사용하도록 변경.
- `src/model/struct/nodes_metric_history.py`: metadata/resource_window 내부 `sample_count` fallback 반영.
- `devlog.md`, `devlog/2026-05-13/170-dashboard-domain-chart-fixes.md`: 작업 이력 기록.

## 확인 결과
- `/opt/conda/envs/docker-infra/bin/python -m py_compile project/main/src/model/struct/infra_catalog_registry.py project/main/src/model/struct/nodes_metric_history.py project/main/src/app/page.dashboard/api.py project/main/src/app/page.servers/api.py` 성공.
- `wiz_project_build(projectName="main", clean=false)` 성공.
- `/opt/conda/envs/docker-infra/bin/python -m unittest tests.api.test_node_reporter.NodeReporterStaticContractTest` 성공.
- 로컬 DB에서 도메인 사용 현황 SQL 실행 성공(`service_domains=1`, 결과 1건).
- 로컬 DB 최근 48시간 `node_metrics` 확인 결과 `resource_window` 12건, CPU/Memory min/max 범위 보유 12건 확인.
- 합성 metric payload로 `dashboard_chart_from_metrics()`가 CPU min/max와 sample_count를 유지하는지 확인.
- `git diff --check` 성공.

## 남은 리스크
- 실제 브라우저 hover 동작과 최종 대시보드 렌더링은 ReviewOps/브라우저 캡처 환경에서 직접 확인하지 못했습니다.
- Storage는 수집기가 10분 동안 단일 디스크 샘플만 기록하므로 CPU/Memory와 달리 min/max 범위가 생기지 않는 것이 현재 의도된 동작입니다.
