# 서버 관리 일반 서버 등록 해제와 원격 정리 흐름 추가

## 사용자 요청

- Review ID: `mzvfizwicuxkeaopjrpcouqvllxauyqx`
- 요청: 서버 관리 화면의 일반 서버에 삭제 버튼을 추가하고, GitLab 방식처럼 서버 이름을 정확히 입력해야 삭제되게 한다. 삭제 시 마스터 노드의 SSH key/서버 정보와 대상 서버의 자원 수집용 node-exporter, 마스터 SSH key 교환 정보를 정리한다.

## 변경 파일

- `config/docker_infra.py`
- `src/model/struct/local_command_catalog.py`
- `src/model/struct/ssh_executor.py`
- `src/model/struct/nodes.py`
- `src/model/struct/nodes_delete.py`
- `src/app/page.servers/api.py`
- `src/app/page.servers/view.ts`
- `src/app/page.servers/view.pug`
- `src/route/api-nodes-path/controller.py`
- `docs/api/openapi.json`
- `tests/api/test_nodes_swarm.py`
- `devlog.md`
- `devlog/2026-05-19/259-server-unregister-cleanup-flow.md`

## 작업 내용

- 일반 서버 상세 헤더에 `등록 해제` 버튼을 추가하고, 서버 이름을 정확히 입력해야 실행 가능한 확인 모달을 추가했다.
- `page.servers` WIZ API와 `/api/nodes/{node_id}` DELETE 경로에서 같은 등록 해제 모델을 호출하도록 연결했다.
- `NodeDeleteMixin`을 추가해 대상 서버에서 metrics collector, node-exporter, Swarm leave, 관리용 SSH 공개키 제거를 수행하고, 마스터에서는 Swarm node 제거, known_hosts 정리, DB node/credential/metric/scoped macro cascade 삭제, 미사용 managed SSH key 파일 삭제를 수행하게 했다.
- 로컬 command catalog에 `swarm.node.remove`, `monitoring.node_exporter.remove`, `monitoring.metrics_collector.remove`를 추가하고 기본 allowlist에 반영했다.

## 검증 결과

- `py_compile`로 변경 Python 파일 문법 확인 완료.
- `/opt/conda/envs/docker-infra/bin/python -m unittest tests.api.test_nodes_swarm.NodesSwarmStaticContractTest` 통과.
- `PYTHONPATH=tests/api /opt/conda/envs/docker-infra/bin/python -m unittest`로 OpenAPI 정적 계약 5개 테스트 통과.
- `wiz_project_build(clean=false)` 통과.
- `season-wiz-project=main`, `season-wiz-devmode=true` 쿠키를 포함해 `http://127.0.0.1:3001/servers` HEAD 요청 200 확인.
- 전체 OpenAPI live 계약 테스트는 로그인 세션이 없는 상태에서 dashboard API가 401을 반환해 제외했다.
