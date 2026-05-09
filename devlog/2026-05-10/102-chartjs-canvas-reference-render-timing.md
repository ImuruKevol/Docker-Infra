# 102. Chart.js canvas 참조와 렌더 타이밍 수정

## 요청 원문

화면에 chartjs가 제대로 보이질 않아. 확인해줘

## 변경 파일

- `src/app/page.servers/view.pug`
- `src/app/page.servers/view.ts`
- `src/app/page.dashboard/view.pug`
- `src/app/page.dashboard/view.ts`
- `tests/api/test_node_reporter.py`
- `devlog.md`
- `devlog/2026-05-10/102-chartjs-canvas-reference-render-timing.md`

## 원인

- Pug의 `canvas(#resourceChartCanvas)` / `canvas(#dashboardResourceChartCanvas)` 문법이 빌드 결과에서 Angular template reference가 아니라 `#resourceChartCanvas="#resourceChartCanvas"` 형태로 변환되어 canvas 참조가 불안정했다.
- 데이터 변경 직후 `service.render()` 다음 줄에서 바로 Chart.js 인스턴스를 생성해, `*ngIf`로 생성되는 canvas가 아직 DOM과 layout에 반영되기 전 렌더링을 시도할 수 있었다.

## 작업 내용

- canvas 참조를 Pug에서 Angular와 호환되는 `ref-resourceChartCanvas`, `ref-dashboardResourceChartCanvas` 방식으로 변경했다.
- canvas에 `block h-full w-full`을 지정해 부모 높이를 안정적으로 사용하도록 했다.
- `data-resource-chart-canvas` fallback selector를 추가해 `ViewChild` 갱신이 늦어져도 canvas를 찾을 수 있도록 했다.
- Chart.js 생성은 `setTimeout` + `requestAnimationFrame`으로 다음 프레임에 예약해 DOM 반영 이후 실행되도록 했다.
- 모달 닫기와 component destroy 시 예약된 렌더 작업도 취소하도록 했다.
- 정적 계약 테스트를 새 canvas 참조 방식과 예약 렌더 함수 기준으로 갱신했다.

## 검증

- `python -m unittest tests.api.test_node_reporter.NodeReporterStaticContractTest`
- `python -m py_compile src/app/page.servers/api.py src/model/struct/nodes_metric_history.py`
- `wiz_project_build(projectName="main", clean=false)`
- 빌드 산출물에서 `#resourceChartCanvas=` / `#dashboardResourceChartCanvas=` 형태가 남아 있지 않음을 확인
- `git diff --check`
