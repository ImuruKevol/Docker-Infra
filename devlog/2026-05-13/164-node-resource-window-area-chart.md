# 서버 자원 10분 통계 집계와 min/max area 차트 적용

- 날짜: 2026-05-13
- 작업 ID: 164
- 리뷰 ID: nbrvcwxngnanwumbnczuyfsvnolkzvzn

## 사용자 원 요청

각 서버 자원 수집이 10분마다 1개 값만 남는 방식이라 의미가 부족하므로, 10분 동안의 min/max, 마지막값, 평균값을 모두 가져오도록 수정하고 대시보드와 서버 상세의 차트를 min/max area와 조합해 보기 쉽게 바꿔달라는 요청.

## 변경 파일

- `config/docker_infra.py`
- `src/model/struct/local_command_catalog.py`
- `src/model/struct/local_command_scripts.py`
- `src/model/struct/nodes_monitoring.py`
- `src/model/struct/nodes_metric_history.py`
- `src/model/struct/nodes_reporter.py`
- `src/model/struct/nodes_local_master.py`
- `src/app/page.dashboard/view.ts`
- `src/app/page.servers/api.py`
- `src/app/page.servers/view.ts`
- `src/app/page.servers/view.pug`
- `tests/api/test_node_reporter.py`
- `devlog.md`
- `devlog/2026-05-13/164-node-resource-window-area-chart.md`

## 작업 내용

- 서버 자원 수집 기본 주기를 60초로 낮추고, systemd collector env에 interval/version 정보를 저장하도록 변경했다.
- collector 상태 점검 시 interval/version drift를 감지해 기존 10분 collector가 재구성될 수 있게 했다.
- metric history CSV와 DB fallback 정규화에 CPU/Memory/Storage별 `min`, `max`, `last`, `avg`, `sample_count` 필드를 추가했다.
- 차트 조회 응답을 10분 버킷으로 집계해 각 버킷의 min/max/last/avg를 반환하도록 변경했다.
- 대시보드 전체 차트, 대시보드 서버별 차트, 서버 상세 차트를 min/max area band와 avg line 조합으로 렌더링하고 tooltip에 네 통계를 표시하도록 변경했다.
- 서버 상세 상단 자원 카드에 최근 10분 버킷의 마지막값, 평균, 범위를 표시하도록 보강했다.

## 검증 결과

- `/opt/conda/envs/docker-infra/bin/python -m py_compile ...` 성공.
- `/opt/conda/envs/docker-infra/bin/python -m unittest tests.api.test_node_reporter.NodeReporterStaticContractTest` 성공.
- `wiz_project_build(projectName="main", clean=false)` 성공.
- 임시 import harness로 10분 버킷 집계의 min/max/last/avg 산출을 확인했다.
