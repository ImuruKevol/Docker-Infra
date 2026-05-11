# 128. 대시보드 서버별 자원 차트와 1분 중복 샘플 방어

## 요청 원문

대시보드에서 서버별 보기 버튼을 누르면 서버 관리 화면으로 가는게 아니라 서버별로 차트가 각각 뜨도록 해야해.
그리고 데이터를 보니 같은 시간(+-1분)에 데이터가 중복으로 찍히는 등 문제가 있어. 자원 모니터링 부분에 대해 확실하게 문제가 없는지, 중복은 없는지 등등 로직을 꼼꼼하게 점검하고 수정해줘.

리뷰 ID: `eobigzwbpdvsocrfgsseznavxvdpwhiu`

## 변경 파일

- `src/app/page.dashboard/view.pug`
- `src/app/page.dashboard/view.ts`
- `src/model/struct/infra_catalog_registry.py`
- `src/model/struct/nodes_metric_history.py`
- `src/model/struct/nodes_reporter.py`
- `src/model/struct/nodes_local_master.py`
- `tests/api/test_node_reporter.py`
- `devlog.md`
- `devlog/2026-05-11/128-dashboard-node-resource-charts-dedupe.md`

## 확인 결과

- 대시보드의 `서버별 보기` 버튼이 `/servers`로 이동하고 있어, 대시보드 안에서 서버별 차트를 확인할 수 없었다.
- reporter 수집, 로컬 master 수집, 수동 metric snapshot 저장 경로가 모두 `node_metrics`와 CSV 히스토리에 바로 append하고 있어 같은 노드의 1분 내 샘플이 중복 저장될 수 있었다.
- systemd timer는 10분 주기지만 설치 직후 service 즉시 실행, timer 실행, 수동 새로고침이 겹치면 같은 시각대 샘플이 만들어질 수 있었다.

## 작업 내용

- 대시보드 `서버별 보기` 버튼을 서버 관리 화면 링크에서 서버별 차트 오버레이로 변경했다.
- dashboard API 응답에 전체 서버 기준 `node_resource_charts`를 추가하고, CSV가 비어 있는 서버는 DB metric fallback으로 차트를 채우도록 했다.
- `nodes_metric_history`에 60초 중복 샘플 치환 로직을 추가해 CSV append 시 같은 노드의 근접 샘플을 새 값으로 대체하도록 했다.
- CSV/DB 기반 조회와 차트 집계에서도 60초 내 중복 샘플을 제거해 기존에 쌓인 중복 데이터가 화면 집계에 영향을 주지 않도록 했다.
- reporter ingest와 local master metric 저장을 DB insert-only에서 advisory lock 기반 upsert로 변경해 같은 노드의 60초 내 metric row를 update하도록 했다.

## 검증

- 성공: `/opt/conda/envs/docker-infra/bin/python -m py_compile src/model/struct/nodes_metric_history.py src/model/struct/nodes_reporter.py src/model/struct/nodes_local_master.py src/model/struct/infra_catalog_registry.py`
- 성공: `/opt/conda/envs/docker-infra/bin/python -m unittest tests.api.test_node_reporter.NodeReporterStaticContractTest`
- 성공: 임시 data dir에서 `nodes_metric_history.append/query` 60초 중복 치환 스크립트 검증
- 성공: `wiz_project_build(projectName="main", clean=false)`

## 비고

- 기존 DB의 물리 중복 row를 삭제하지는 않고, 신규 저장 방어와 조회/차트 집계 단계의 dedupe로 화면 영향만 제거했다.
