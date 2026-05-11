# 126. 노드 자원 수집 systemd timer 자동 구성

## 요청 원문

각 노드의 자원 수집이 자동으로 되고있지 않았던 것으로 확인했는데, 처음 기능을 추가할 때 요청했던 내용은 systemctl의 형태로 노드 자원 수집이 서버 부팅 시 자동으로 시작되고, 10분 단위로 자원을 기록해야해. 그리고 그것들을 메인 노드나 웹 서비스에서 요청하면 가져와서 시각화를 해야하고. 이러한 플로우들이 정상적으로 동작하고 있는지 확인해줘.

리뷰 ID: `eobigzwbpdvsocrfgsseznavxvdpwhiu`

## 변경 파일

- `config/docker_infra.py`
- `src/model/struct/local_command_scripts.py`
- `src/model/struct/local_command_catalog.py`
- `src/model/struct/nodes_monitoring.py`
- `src/app/page.servers/api.py`
- `src/app/page.access/api.py`
- `src/route/api-nodes/controller.py`
- `src/route/api-system-local-master-ensure/controller.py`
- `src/route/api-system-setup/controller.py`
- `tests/api/test_node_reporter.py`
- `devlog.md`
- `devlog/2026-05-11/126-node-metrics-systemd-collector.md`

## 확인 결과

- 기존 구현은 `node_exporter` systemd service만 구성했고, 실제 `node_metrics` DB/CSV 기록은 웹 프로세스의 수동/임시 tick 또는 화면 요청 경로에 의존했다.
- 서버 부팅 후 10분마다 reporter API로 자원을 push하는 systemd timer 구성은 없어서, 화면 요청이 없으면 대시보드 차트 원천 데이터가 계속 쌓이지 않을 수 있었다.

## 작업 내용

- 각 노드에 설치되는 `docker-infra-node-metrics.service`와 `docker-infra-node-metrics.timer` 구성 흐름을 추가했다.
- timer는 `OnBootSec=1min`, `OnUnitActiveSec=600s`, `Persistent=true`로 부팅 후 자동 시작 및 10분 단위 수집을 수행한다.
- collector agent는 CPU/Memory/Storage/Container 상태를 수집해 `/api/reporter/metrics`로 POST하고, 기존 reporter token ingest 경로가 DB와 CSV 기록을 남기도록 연결했다.
- 로컬/원격 노드 등록, 로컬 master 확인, 최초 setup 완료 시 reporter base URL을 추론해 collector timer를 자동 구성하도록 연결했다.
- `DOCKER_INFRA_REPORTER_BASE_URL` 설정 fallback을 추가해 프록시/도메인 환경에서도 명시 URL을 사용할 수 있게 했다.

## 검증

- 성공: `/opt/conda/envs/docker-infra/bin/python -m py_compile config/docker_infra.py src/model/struct/local_command_scripts.py src/model/struct/local_command_catalog.py src/model/struct/nodes_monitoring.py src/app/page.servers/api.py src/app/page.access/api.py src/route/api-nodes/controller.py src/route/api-system-local-master-ensure/controller.py src/route/api-system-setup/controller.py`
- 성공: `/opt/conda/envs/docker-infra/bin/python -m unittest tests.api.test_node_reporter.NodeReporterStaticContractTest`
- 성공: collector install/status shell script `sh -n` 검증
- 성공: embedded node metrics agent Python script compile 검증
- 성공: `wiz_project_build(projectName="main", clean=false)`
- 성공: `git diff --check -- config/docker_infra.py src/model/struct/local_command_scripts.py src/model/struct/local_command_catalog.py src/model/struct/nodes_monitoring.py src/app/page.servers/api.py src/app/page.access/api.py src/route/api-nodes/controller.py src/route/api-system-local-master-ensure/controller.py src/route/api-system-setup/controller.py tests/api/test_node_reporter.py`

## 비고

- 실제 원격 노드의 `systemctl status docker-infra-node-metrics.timer`와 reporter POST 성공 여부는 운영 환경에서 노드별 재구성 실행 후 확인이 필요하다.
