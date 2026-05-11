# 129. 자원 수집 web 의존 제거와 collector timer 복구

## 요청 원문

보니까 웹이 열려있을 때만 모니터링 데이터가 최합되는 것 같은 느낌이야. 실제로 데이터가 지금 보여지는게 pm 3:50을 마지막으로 없어. 4:00, 4:10도 보여야 하는데 저 때는 웹을 들어가보지 않아서 그런가 뭔가 계속 모니터링 기능이 불완전해

리뷰 ID: `eobigzwbpdvsocrfgsseznavxvdpwhiu`

## 변경 파일

- `src/model/struct/nodes_runtime.py`
- `src/model/struct/nodes_monitoring.py`
- `src/model/struct/local_command_catalog.py`
- `src/app/page.dashboard/api.py`
- `tests/api/test_node_reporter.py`
- `devlog.md`
- `devlog/2026-05-11/129-monitoring-web-independent-collector-repair.md`

## 확인 결과

- 로컬과 원격 worker 노드에 `docker-infra-node-metrics.timer/service`가 설치되어 있지 않았거나 잘못된 reporter URL로 실패하고 있었다.
- DB metadata에는 collector가 ok로 남아 있었지만 실제 systemd 상태와 불일치했다.
- 서버 관리 화면의 컨테이너 새로고침이 `containers_refresh` source의 새 `node_metrics` row를 만들고 있어, 웹 화면을 열 때만 자원 기록이 생기는 것처럼 보이는 원인이 있었다.
- 기존 timer는 설치 시각 기준 `OnUnitActiveSec=600s`라 정각 10분 단위가 아니라 설치 시각에서 10분마다 실행될 수 있었다.

## 작업 내용

- 컨테이너 새로고침은 더 이상 자원 metric row를 생성하지 않고, 최신 metric row의 `containers`만 갱신하도록 변경했다.
- 대시보드 로드 시 실제 systemd collector 상태를 백그라운드 점검하고, timer/service가 없거나 실패하면 reporter token을 재발급해 재설치하도록 self-repair 경로를 추가했다.
- timer가 active여도 마지막 collector service 실행이 failed면 상태 점검을 실패로 처리해 reporter URL 오류 등을 자동 복구 대상으로 잡도록 했다.
- collector timer를 `OnCalendar=*:0/10`로 변경해 `16:00, 16:10, 16:20...` 형태의 벽시계 기준 10분 단위 실행으로 맞췄다.
- 현재 환경의 local-master, mini2, mini3에 collector timer/service를 설치하고 즉시 1회 수집을 실행했다.

## 검증

- 성공: `/opt/conda/envs/docker-infra/bin/python -m py_compile src/model/struct/nodes_runtime.py src/model/struct/nodes_monitoring.py src/model/struct/local_command_catalog.py src/app/page.dashboard/api.py`
- 성공: `/opt/conda/envs/docker-infra/bin/python -m unittest tests.api.test_node_reporter.NodeReporterStaticContractTest`
- 성공: `wiz_project_build(projectName="main", clean=false)`
- 성공: local-master, mini2, mini3에서 `docker-infra-node-metrics.timer`가 enabled/active 상태이며, 즉시 실행 결과가 `systemd_collector` source로 DB에 저장됨을 확인했다.
- 성공: 2026-05-11 16:30 KST 정각 슬롯에서 세 노드 모두 `systemd_collector` source로 신규 metric이 저장되고 다음 실행이 16:40 KST로 예약됨을 확인했다.
- 성공: `wiz.docker-infra.service`를 재시작해 변경된 코드가 실행 프로세스에 반영됨을 확인했다.

## 비고

- 기존에 쌓인 `containers_refresh` 기반 row는 삭제하지 않았고, 신규 컨테이너 새로고침부터 자원 시계열을 만들지 않도록 막았다.
