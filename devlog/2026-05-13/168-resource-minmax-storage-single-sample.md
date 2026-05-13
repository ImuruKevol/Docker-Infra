# 168. CPU/Memory min-max 차트와 Storage 단일 측정 수집 로직 정리

- 날짜: 2026-05-13
- 리뷰 ID: nbrvcwxngnanwumbnczuyfsvnolkzvzn
- 요청: CPU, Memory의 min/max 로직을 정상화하고 Memory 차트는 Used/Cache/Free 구분 없이 사용량의 평균/min/max만 표시한다. CPU, Memory는 1초마다 측정해 10분 평균/min/max를 계산하고 Storage는 10분에 한 번만 측정한다.

## 변경 파일

- `src/model/struct/local_command_scripts.py`
- `src/model/struct/local_command_catalog.py`
- `src/app/page.dashboard/view.ts`
- `src/app/page.servers/view.ts`
- `src/app/page.servers/view.pug`
- `tests/api/test_node_reporter.py`

## 변경 내용

- 노드 collector의 1초 샘플에서 Storage 측정을 제거하고, 10분 윈도우 종료 후 `df -Pk /`를 1회만 호출하도록 변경했다.
- collector agent version을 갱신해 기존 노드의 구버전 collector가 drift 검사로 재설치되도록 했다.
- Storage의 `resource_window.storage_used_percent`는 1회 측정값으로 min/max/last/avg가 동일하게 기록되도록 했다.
- Memory 차트를 Used/Cache/Free stacked area에서 사용량 min/max range area + 평균 line으로 변경했다.
- CPU와 Memory 차트가 각각 `*_min`, `*_max`, `*_avg` 필드를 직접 사용하도록 테스트 계약을 보강했다.
- 서버 상세 차트 안내 문구에서 Used/Cache/Free 표현을 제거했다.

## 확인

- `/opt/conda/envs/docker-infra/bin/python -m py_compile src/model/struct/local_command_scripts.py src/model/struct/nodes_metric_history.py src/model/struct/nodes_shared.py`
- `/opt/conda/envs/docker-infra/bin/python -m unittest tests.api.test_node_reporter`
- `wiz_project_build(projectName="main", clean=false)`
- metric history helper로 CPU/Memory min/avg/max와 Storage 단일 측정 min/avg/max 반영을 확인했다.
