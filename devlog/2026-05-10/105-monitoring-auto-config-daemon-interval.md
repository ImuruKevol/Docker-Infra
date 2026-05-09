# 105. 모니터링 자동 구성과 10분 주기 백그라운드 수집 분리

## 원본 요청

정보 수집 중 인디케이터는 선택 중인 서버만 뜨는게 아니라 모니터링이 구성된 모든 서버에서 표시가 되어야 해. 당연하게도 백그라운드에서 계속 리소스 정보는 수집을 해야해.
근데 초 단위로 계속 수집하면 데이터 양이 너무 많을테니 백그라운드에서 서비스 데몬으로 수집되는 리소스 정보는 10분마다 한 번씩만 자동으로 기록하도록 하고, 웹에서 보는것만 선택한 초마다 따로 정보를 호출하도록 하면 될 것 같아.

그리고 지금은 모니터링 설정을 서버 생성 후 수동으로 하게 되어있는데, 서버 생성 시 자동으로 구성되도록 해야해. 물론 이 부분도 사용자가 따로 뭘 할 필요는 없고, 그냥 자동으로 구성하고 나서 "모니터링 구성됨" 뱃지만 인디케이터로 바꿔서 보여주면 돼.

## 변경 파일

- `config/docker_infra.py`
- `src/model/struct/nodes_monitoring.py`
- `src/model/struct/nodes_runtime.py`
- `src/model/struct/nodes_local_master.py`
- `src/app/page.servers/api.py`
- `src/app/page.servers/view.ts`
- `src/app/page.servers/view.pug`
- `src/route/api-nodes/controller.py`
- `src/route/api-system-local-master-ensure/controller.py`
- `tests/api/test_node_reporter.py`
- `devlog.md`
- `devlog/2026-05-10/105-monitoring-auto-config-daemon-interval.md`

## 작업 내용

- 모니터링 백그라운드 수집 기본 주기를 10분으로 변경하고, 환경값이 더 낮게 들어와도 최소 600초로 제한했다.
- 화면에서 선택한 서버의 CPU/Memory/Storage 자동 갱신은 DB/CSV 기록을 남기지 않는 `live_metric` 경로로 분리했다.
- 서버 등록 API와 nodes API에서 신규 서버 저장 후 `node_exporter` systemd 서비스 구성을 자동 실행하고, 성공 시 서버 metadata의 `monitoring_agent.configured` 상태를 반영하도록 했다.
- 중심 서버 확인 API와 local-master route도 모니터링 에이전트 자동 구성을 수행하도록 연결했다.
- 서버 목록과 상세 상단의 `모니터링 구성됨` 텍스트 뱃지를 제거하고, 구성된 서버 전체에 깜빡이는 파란 정보 수집 인디케이터가 보이도록 했다.
- 이후 106번 작업에서 웹 요청이 데몬을 시작하지 않도록 `ensure_daemon`/자동 구성 예약 흐름은 제거했다.

## 검증 결과

- `python -m py_compile config/docker_infra.py src/model/struct/nodes_monitoring.py src/model/struct/nodes_runtime.py src/model/struct/nodes_local_master.py src/app/page.servers/api.py src/app/page.dashboard/api.py src/app/page.services/api.py src/app/page.services.create/api.py src/route/api-nodes/controller.py src/route/api-system-local-master-ensure/controller.py` 통과
- `python -m unittest tests.api.test_node_reporter.NodeReporterStaticContractTest tests.api.test_images_templates_catalog.ImagesTemplatesStaticContractTest` 통과
- `wiz_project_build(projectName="main", clean=false)` 성공
- `git diff --check` 통과
