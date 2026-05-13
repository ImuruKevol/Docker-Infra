# 167. 자원 차트 시간대 정규화와 ApexCharts hover 시간 표시 보강

- 날짜: 2026-05-13
- 리뷰 ID: nbrvcwxngnanwumbnczuyfsvnolkzvzn
- 요청: ApexCharts에서 표시하는 시간 정보의 timezone 설정을 자원 수집 쪽과 차트 쪽 모두 확인하고, hover 시 날짜뿐 아니라 시간도 표시되도록 수정한다.

## 변경 파일

- `src/model/struct/nodes_shared.py`
- `src/model/struct/nodes_metric_history.py`
- `src/app/page.dashboard/view.ts`
- `src/app/page.servers/view.ts`
- `tests/api/test_node_reporter.py`

## 변경 내용

- reporter ingest의 `reported_at` 파서를 UTC aware datetime으로 정규화하도록 보강했다.
- metric history CSV/차트 payload의 ISO timestamp도 UTC `Z` suffix로 정규화하도록 보강했다.
- 대시보드와 서버 상세 ApexCharts x축에 `datetimeUTC: false`를 설정하고, timestamp parsing helper에서 timezone 없는 ISO 문자열은 UTC로 해석하도록 했다.
- ApexCharts hover tooltip의 x 값을 `YYYY. MM. DD. HH:mm:ss TZ` 형식으로 표시하고, y formatter가 range 값도 정상 표시하도록 보강했다.

## 확인

- `/opt/conda/envs/docker-infra/bin/python -m py_compile src/model/struct/nodes_shared.py src/model/struct/nodes_metric_history.py src/model/struct/local_command_scripts.py`
- `/opt/conda/envs/docker-infra/bin/python -m unittest tests.api.test_node_reporter.NodeReporterStaticContractTest`
- `wiz_project_build(projectName="main", clean=false)`
