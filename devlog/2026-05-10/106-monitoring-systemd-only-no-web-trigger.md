# 106. 웹 요청 기반 모니터링 데몬 시작 제거와 systemd 상태 확인 정리

## 원본 요청

데몬은 어차피 systemctl 서비스 형식으로 등록해놓고 서버 부팅 시 자동으로 시작되도록 하게 할거니까 웹에서 따로 뭘 시작 트리거를 주거나 할 필요는 없어. 오히려 웹에서 따로 트리거를 따로 주면 안돼. 그냥 서버 추가 시 자동으로 systemctl enable, systemctl start만 추가하고, 상태만 Running인지 확인하면 돼.

## 변경 파일

- `config/docker_infra.py`
- `src/model/struct/nodes_monitoring.py`
- `src/model/struct/local_command_catalog.py`
- `src/app/page.servers/api.py`
- `src/app/page.dashboard/api.py`
- `src/app/page.services/api.py`
- `src/app/page.services.create/api.py`
- `src/route/api-nodes/controller.py`
- `src/route/api-system-local-master-ensure/controller.py`
- `tests/api/test_node_reporter.py`
- `devlog.md`
- `devlog/2026-05-10/105-monitoring-auto-config-daemon-interval.md`
- `devlog/2026-05-10/106-monitoring-systemd-only-no-web-trigger.md`

## 작업 내용

- 웹 화면 진입 API에서 `ensure_daemon`, 자동 누락 구성 예약, `monitoring.tick()` 같은 웹 요청 기반 데몬 시작/예약 호출을 제거했다.
- 서버 등록과 중심 서버 확인 흐름에만 `node_exporter` systemd 서비스 자동 구성을 남겼다.
- systemd 구성 스크립트는 `systemctl enable`, `systemctl start`, `systemctl is-active --quiet` 순서로 실행하고 `Running` 상태를 확인하도록 바꿨다.
- `systemctl restart`와 `systemctl enable --now` 사용을 제거했다.
- 별도 수동 트리거 API 성격의 `ensure_monitoring_agent`는 서비스를 시작하지 않고 현재 systemd 상태만 확인하도록 바꿨다.
- 로컬 executor에 `monitoring.node_exporter.status` 명령을 추가해 Running 상태 확인만 수행할 수 있게 했다.

## 검증 결과

- `python -m py_compile src/model/struct/nodes_monitoring.py src/model/struct/local_command_catalog.py src/app/page.servers/api.py src/app/page.dashboard/api.py src/app/page.services/api.py src/app/page.services.create/api.py src/route/api-nodes/controller.py src/route/api-system-local-master-ensure/controller.py config/docker_infra.py` 통과
- `python -m unittest tests.api.test_node_reporter.NodeReporterStaticContractTest` 통과
