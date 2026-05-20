# 264. 서버 관리 중심 서버 IP 표시와 상단 버튼 정리

- 날짜: 2026-05-19
- 리뷰 ID: ixymkupedqbkzutjjyomoghzsfwpqpct

## 사용자 요청

서버 관리 화면 상세의 중심 서버 헤더에서 `사설` 뒤에 공인 IP가 표시되는 문제를 수정하고, 서버 관리 화면 상단의 `서버 추가`, `중심 서버 확인`, `새로고침` 버튼을 제거하되 `서버 추가` 버튼은 서버 목록 카드 헤더로 이동한다.

## 변경 파일

- `src/app/page.servers/view.pug`
- `src/app/page.servers/view.ts`
- `tests/api/test_nodes_swarm.py`

## 상세

- 서버 관리 화면 최상단 헤더의 서버 추가, 중심 서버 확인, 새로고침 버튼 영역을 제거했다.
- 서버 추가 버튼을 서버 목록 카드 헤더의 서버 개수 옆으로 이동했다.
- 중심 서버 IP 표시에서 사설 주소로 판단할 수 있을 때만 `사설 ... · 공인 ...` 형식을 사용하도록 보정했다.
- 중심 서버에 공인 IP만 있는 경우에는 `공인 ...`으로 표시해 공인 IP를 사설 IP로 오인하지 않도록 했다.
- 정적 계약 테스트에 서버 관리 버튼 배치와 중심 서버 IP 라벨 회귀 검사를 추가했다.

## 확인

- `/opt/conda/envs/docker-infra/bin/python -m unittest tests.api.test_nodes_swarm.NodesSwarmStaticContractTest` 통과
- `/opt/conda/envs/docker-infra/bin/python -m unittest tests.api.test_nodes_swarm.NodesSwarmStaticContractTest tests.api.test_node_reporter.NodeReporterStaticContractTest tests.api.test_services_preflight.ServicesPreflightStaticContractTest tests.api.test_backup_registry_nodes tests.api.test_domain_management_ui` 통과
- `/opt/conda/envs/docker-infra/bin/wiz project build --project main`에 해당하는 WIZ MCP build 통과
- `season-wiz-project=main`, `season-wiz-devmode=true` 쿠키로 `http://127.0.0.1:3001/dashboard`, `/api/system/health` HTTP 200 확인

## 남은 리스크

- 실제 운영 데이터에서 사설 IP 설정이 누락된 경우 UI는 공인 IP만 표시한다. 사설/공인 동시 표시는 런타임의 사설 주소 설정이 별도로 들어와야 한다.
