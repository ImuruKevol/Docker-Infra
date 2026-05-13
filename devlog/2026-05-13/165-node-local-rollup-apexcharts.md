# 165. 노드 로컬 1초 샘플링 10분 집계와 ApexCharts 분리 차트 적용

- 날짜: 2026-05-13
- 리뷰 ID: nbrvcwxngnanwumbnczuyfsvnolkzvzn
- 요청: 각 노드가 매초 자원 현황을 수집하고 메인 노드는 10분 집계 정보만 가져오도록 조정한다. CPU, Memory, Storage 차트를 분리하고 Chart.js 대신 ApexCharts를 사용한다. CPU는 평균 라인과 min/max 영역, Memory는 Used/Cache/Free 100% stacked area, Storage는 사용률 라인으로 표시한다.

## 변경 파일

- `config/docker_infra.py`
- `src/model/struct/local_command_catalog.py`
- `src/model/struct/local_command_scripts.py`
- `src/model/struct/nodes_monitoring.py`
- `src/model/struct/nodes_metric_history.py`
- `src/app/page.dashboard/view.pug`
- `src/app/page.dashboard/view.ts`
- `src/app/page.servers/view.pug`
- `src/app/page.servers/view.ts`
- `src/angular/package.json`
- `package.json`
- `tests/api/test_node_reporter.py`

## 변경 내용

- 노드 메트릭 수집기를 10분 실행 동안 1초 간격으로 `/proc/stat`, `/proc/meminfo`, `df -Pk /`를 샘플링하고, Docker 컨테이너 목록은 전송 직전에 1회만 조회하도록 변경했다.
- 수집 결과 payload에 CPU, memory used/cache/free, storage 사용률의 min/max/last/avg와 sample_count를 포함하도록 했다.
- 메인 노드 저장/조회 로직은 10분 버킷 단위로 통계를 보존하고, memory stacked chart용 cache/free 평균값도 함께 전달하도록 확장했다.
- 대시보드 및 서버 상세 자원 차트를 CPU, Memory, Storage로 분리하고 ApexCharts 기반 렌더링으로 전환했다.
- collector 상태 점검에 수집 간격, 샘플 간격, agent version drift 검사를 추가해 기존 노드의 오래된 collector가 자동 보정되도록 했다.

## 확인

- `/opt/conda/envs/docker-infra/bin/python -m py_compile config/docker_infra.py src/model/struct/local_command_catalog.py src/model/struct/local_command_scripts.py src/model/struct/nodes_metric_history.py src/model/struct/nodes_monitoring.py`
- `/opt/conda/envs/docker-infra/bin/python -m unittest tests.api.test_node_reporter.NodeReporterStaticContractTest`
- `wiz_project_build(projectName="main", clean=false)`
- 메트릭 집계 helper를 직접 호출해 CPU min/max/avg와 memory used/cache/free 평균값이 chart row에 반영되는 것을 확인했다.
