# 125. 대시보드 서버 자원 추이 기간 필터와 DB fallback 보강

## 요청 원문

작업 지시서와 스크린샷을 참고해서 에러를 수정해줘

리뷰 ID: `eobigzwbpdvsocrfgsseznavxvdpwhiu`

## 변경 파일

- `src/app/page.dashboard/api.py`
- `src/app/page.dashboard/view.ts`
- `src/app/page.dashboard/view.pug`
- `src/model/struct/infra_catalog_registry.py`
- `src/model/struct/nodes_metric_history.py`
- `tests/api/test_node_reporter.py`
- `devlog.md`
- `devlog/2026-05-11/125-dashboard-resource-range-db-fallback.md`

## 원인

- 대시보드 자원 추이 API가 기간 파라미터를 받지 않아 사용자가 날짜 범위를 바꿔 조회할 수 없었다.
- 대시보드 차트는 CSV 자원 기록만 사용해서, `node_metrics` DB에는 최신 자원 데이터가 있어도 CSV 파일이 없거나 비어 있으면 차트가 비어 보일 수 있었다.

## 작업 내용

- 대시보드 서버 자원 추이에 시작일/종료일 필터와 조회 버튼을 추가했다.
- `page.dashboard` overview API가 `start_date`, `end_date`, `start_at`, `end_at`을 받아 차트 조회에 전달하도록 수정했다.
- CSV 차트 결과가 비어 있을 때 `node_metrics` DB row를 같은 버킷 차트 payload로 변환하는 fallback을 추가했다.
- 자원 차트 payload 생성 로직을 재사용 가능하게 정리하고, DB 기반 차트 생성 메서드를 추가했다.
- 정적 계약 테스트에 대시보드 기간 필터와 DB fallback 토큰을 추가했다.

## 검증

- 성공: `/opt/conda/envs/docker-infra/bin/python -m py_compile src/model/struct/nodes_metric_history.py src/model/struct/infra_catalog_registry.py src/app/page.dashboard/api.py`
- 성공: `/opt/conda/envs/docker-infra/bin/python -m unittest tests.api.test_node_reporter.NodeReporterStaticContractTest`
- 성공: 임시 config 기반 `nodes_metric_history.dashboard_chart_from_metrics` 동작 확인
- 성공: `wiz_project_build(projectName="main", clean=false)`
- 성공: `git diff --check -- src/model/struct/nodes_metric_history.py src/model/struct/infra_catalog_registry.py src/app/page.dashboard/api.py src/app/page.dashboard/view.ts src/app/page.dashboard/view.pug tests/api/test_node_reporter.py`
