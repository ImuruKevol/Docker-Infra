# 103. Chart.js template reference NG0301 제거

## 요청 원문

Uncaught (in promise) RuntimeError: NG0301
    at PageDashboardComponent_div_20_div_16_Template (view.html:1:3154)
_debug_node-chunk.mjs:7837 Uncaught (in promise) RuntimeError: NG0301
    at PageServersComponent_div_26_div_51_Template (view.html:1:36239)

## 변경 파일

- `src/app/page.servers/view.pug`
- `src/app/page.servers/view.ts`
- `src/app/page.dashboard/view.pug`
- `src/app/page.dashboard/view.ts`
- `tests/api/test_node_reporter.py`
- `devlog.md`
- `devlog/2026-05-10/103-chartjs-ng0301-reference-removal.md`

## 원인

- Chart canvas에 넣은 `ref-resourceChartCanvas`, `ref-dashboardResourceChartCanvas`가 빌드 결과에서 Angular template reference의 export 이름으로 해석되었다.
- 해당 export 이름을 가진 directive가 없어서 Angular가 `NG0301`을 발생시켰다.

## 작업 내용

- Chart.js는 canvas DOM만 필요하므로 Angular template reference와 `@ViewChild`를 완전히 제거했다.
- canvas는 `data-resource-chart-canvas` 속성만 남기고, TypeScript에서는 `document.querySelector`로 조회하도록 단순화했다.
- 정적 계약 테스트도 template reference가 아니라 `data-resource-chart-canvas` selector 기반 렌더링을 확인하도록 갱신했다.

## 검증

- `python -m unittest tests.api.test_node_reporter.NodeReporterStaticContractTest`
- `wiz_project_build(projectName="main", clean=false)`
- 빌드 산출물에서 `ref-resourceChartCanvas`, `ref-dashboardResourceChartCanvas`, `#resourceChartCanvas=`, `#dashboardResourceChartCanvas=` 및 chart용 `viewQuery`가 남아 있지 않음을 확인
- `git diff --check`
