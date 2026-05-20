# 263. 마스터 공인 IP와 노드 접근용 사설 IP 분리

- 날짜: 2026-05-19
- 리뷰 ID: ixymkupedqbkzutjjyomoghzsfwpqpct

## 사용자 요청

현재 마스터 노드에 IP 설정이 공인 IP로만 되어있는 듯 함. 서비스 생성 시 DDNS나 Cloudflare API로 보낼 공인 IP 설정과 다른 노드들과 통신할 때(Harbor IP, 자원 수집 등) 사용하는 사설 IP 설정이 분리되어야 함.

## 변경 파일

- `config/docker_infra.py`
- `docs/api/openapi.json`
- `src/app/page.servers/view.pug`
- `src/app/page.servers/view.ts`
- `src/model/struct/domains.py`
- `src/model/struct/service_nginx.py`
- `src/model/struct/nodes_shared.py`
- `src/model/struct/nodes_view.py`
- `src/model/struct/setup.py`
- `src/model/struct/nodes_local_master.py`
- `src/model/struct/nodes_join.py`
- `src/model/struct/nodes_backup_registry.py`
- `src/model/struct/nodes_monitoring.py`
- `tests/api/test_backup_registry_nodes.py`
- `tests/api/test_domain_management_ui.py`

## 상세

- 런타임 설정에 공인 DNS IP와 내부 노드 접근 주소를 분리했다.
  - 공인 DNS IP: `DOCKER_INFRA_PUBLIC_IPV4`, `DOCKER_INFRA_PUBLIC_IP`, `DOCKER_INFRA_PUBLIC_IPV6`, 기존 DDNS 공인 IP 설정 fallback.
  - 내부 접근 주소: `DOCKER_INFRA_MASTER_PRIVATE_IP`, `DOCKER_INFRA_PRIVATE_IP`, `DOCKER_INFRA_INTERNAL_ADDRESS`, 기존 `DOCKER_INFRA_ADVERTISE_ADDRESS` fallback.
- Cloudflare 서비스 DNS 레코드는 더 이상 Swarm advertise/private 주소를 사용하지 않고 공인 DNS IP를 사용하도록 변경했다.
- 로컬 마스터 등록 정보에는 `private_host`, `public_ip`를 노출하고 서버 화면에서는 중심 서버의 사설/공인 IP를 구분해 표시한다.
- 일반 노드의 Harbor 백업 레지스트리 주소와 자원 수집 reporter URL은 내부 접근 주소를 우선 사용하도록 변경했다.
- Swarm join/로컬 마스터 ensure API에 `private_address`, `node_access_host` alias를 추가했다.

## 확인

- `/opt/conda/envs/docker-infra/bin/python -m py_compile ...` 통과
- `/opt/conda/envs/docker-infra/bin/python -m unittest tests.api.test_domain_management_ui tests.api.test_backup_registry_nodes tests.api.test_nodes_swarm.NodesSwarmStaticContractTest tests.api.test_node_reporter.NodeReporterStaticContractTest tests.api.test_services_preflight.ServicesPreflightStaticContractTest tests.api.test_backup_system_runtime.BackupSystemResourceTest` 통과
- `/opt/conda/envs/docker-infra/bin/wiz project build --project main`에 해당하는 WIZ MCP build 통과
- `season-wiz-project=main`, `season-wiz-devmode=true` 쿠키로 `http://127.0.0.1:3001/dashboard`, `/api/system/health` HTTP 200 확인

## 남은 리스크

- 실제 Cloudflare/DDNS API 호출은 외부 계정과 운영 공인 IP 설정이 필요해 로컬 검증 범위에서는 실행하지 않았다.
- `python -m unittest tests.api.test_openapi_contract...`는 환경에 `openapi_validator` 모듈이 없어 실행하지 못했다.
