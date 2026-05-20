# 265. 중심 서버 기본 사설 IP 적용과 표시 보정

- 날짜: 2026-05-19
- 리뷰 ID: ixymkupedqbkzutjjyomoghzsfwpqpct

## 사용자 요청

기본적으로 사설 IP로 표시해야 한다. 사설 IP는 `172.16.0.224`이므로 환경변수에 적용한 다음 확인한다.

## 변경 파일

- `/root/docker-infra/config.env`
- `src/app/page.servers/view.ts`
- `tests/api/test_nodes_swarm.py`

## 상세

- 런타임 환경에 중심 서버 사설 IP `172.16.0.224`를 적용했다.
  - `DOCKER_INFRA_MASTER_PRIVATE_IP`
  - `DOCKER_INFRA_ADVERTISE_ADDRESS`
- 기존 로컬 중심 서버 DB 레코드의 `host`, `metadata.private_host`, `metadata.node_access_host`를 `172.16.0.224`로 동기화했다.
- 서버 관리 UI의 중심 서버 라벨에서 사설 IP만 있는 경우에도 `사설 172.16.0.224`처럼 사설 라벨이 기본으로 표시되도록 보정했다.
- 정적 계약 테스트에 사설 IP 단독 표시 회귀 검사를 추가했다.

## 확인

- 환경 설정 로드 결과 `advertise_address=172.16.0.224`, `reporter_internal_base_url=http://172.16.0.224:3001` 확인
- DB 로컬 중심 서버 레코드의 `host`, `private_host`, `node_access_host`가 `172.16.0.224`인 것을 확인
- `/opt/conda/envs/docker-infra/bin/python -m unittest tests.api.test_nodes_swarm.NodesSwarmStaticContractTest tests.api.test_node_reporter.NodeReporterStaticContractTest tests.api.test_services_preflight.ServicesPreflightStaticContractTest tests.api.test_backup_registry_nodes tests.api.test_domain_management_ui` 통과
- `/opt/conda/envs/docker-infra/bin/wiz project build --project main`에 해당하는 WIZ MCP build 통과
- `season-wiz-project=main`, `season-wiz-devmode=true` 쿠키로 `http://127.0.0.1:3001/dashboard`, `/api/system/health` HTTP 200 확인

## 남은 리스크

- 인증 세션이 없어 UI API의 `ensure_local_master` 호출은 직접 검증하지 못했고, DB 레코드는 동일한 대상 필드를 직접 동기화했다.
