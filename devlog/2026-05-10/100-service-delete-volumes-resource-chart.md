# 100. 서비스 삭제 시 stack 볼륨 제거와 서버 자원 추이 차트/기록 삭제 UI 추가

## 요청 원문

서비스 삭제 시 볼륨도 기본적으로 같이 삭제되는지 확인해줘. 볼륨도 같이 삭제가 되어야 해.

서버별 리소스 모니터링은 서버 상세에서 자동 갱신 부분 왼쪽에 크게 보기 버튼같은걸 추가해서 x축을 시간, y축을 값으로 한 차트를 출력하도록 해줘. 여기에는 날짜를 지정해서 조회할 수 있는 기능도 있어야 하고, 날짜 구간을 선택해서 로그를 삭제하는 기능도 필요해.
리소스 차트는 대시보드에도 추가해줘.

## 변경 파일

- `config/docker_infra.py`
- `src/model/struct/local_command_catalog.py`
- `src/model/struct/services_delete.py`
- `src/model/struct/nodes_metric_history.py`
- `src/model/struct/infra_catalog_registry.py`
- `src/app/page.servers/api.py`
- `src/app/page.servers/view.ts`
- `src/app/page.servers/view.pug`
- `src/app/page.dashboard/view.ts`
- `src/app/page.dashboard/view.pug`
- `src/app/page.services/view.ts`
- `tests/api/test_node_reporter.py`
- `tests/api/test_services_preflight.py`

## 원인

- 기존 서비스 삭제 흐름은 `docker stack rm` 이후 nginx 설정, 서비스 파일, DB row를 삭제했지만 Docker stack이 만든 named volume은 별도로 제거하지 않았다.
- 서버별 CSV 자원 기록은 append와 dashboard summary만 있었고, 기간 조회/삭제 API와 차트용 데이터 가공 로직이 없었다.

## 작업 내용

- `service.stack.volumes.remove` local executor 명령을 추가하고 기본 allowlist에 포함했다.
- stack namespace label 또는 `stack_` 접두어로 연결된 Docker volume을 찾아 삭제하고, stack 제거 직후 아직 사용 중인 볼륨은 최대 30회 재시도하도록 했다.
- 서비스 삭제 작업 결과에 `volumes` 삭제 결과를 포함하고, 삭제 확인 문구에도 Docker 볼륨 삭제를 명시했다.
- `nodes_metric_history`에 기간 조회, dashboard용 5분 버킷 평균 차트 데이터, 기간 삭제 기능을 추가했다.
- 서버 상세 자동 갱신 컨트롤 왼쪽에 `크게 보기` 버튼을 추가하고, CPU/Memory/Storage 시간축 SVG 차트 모달과 날짜 조회/기간 삭제 UI를 붙였다.
- 대시보드에 오늘 수집된 서버 평균 자원 추이 차트를 추가했다.
- 관련 정적 계약 테스트에 볼륨 삭제 명령과 리소스 차트/API 토큰을 추가했다.

## 검증

- `/opt/conda/bin/python -m py_compile config/docker_infra.py src/model/struct/local_command_catalog.py src/model/struct/services_delete.py src/model/struct/nodes_metric_history.py src/model/struct/infra_catalog_registry.py src/app/page.servers/api.py src/app/page.dashboard/api.py`
- 임시 데이터 디렉토리 기반 `nodes_metric_history` append/query/dashboard_chart/delete_range 동작 확인
- `/opt/conda/bin/python -m unittest tests.api.test_node_reporter.NodeReporterStaticContractTest tests.api.test_services_preflight.ServicesPreflightStaticContractTest`
- `git diff --check`
- `wiz_project_build(projectName="main", clean=false)`

## 비고

- 확인 결과, 기존 서비스 삭제는 볼륨을 기본 삭제하지 않았다. 이번 변경 이후 서비스 삭제 시 stack 관련 Docker 볼륨까지 삭제 대상에 포함된다.
