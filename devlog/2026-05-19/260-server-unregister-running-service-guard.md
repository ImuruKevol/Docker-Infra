# 서버 등록 해제 전 실행 중 서비스 차단 추가

## 사용자 요청

- Review ID: `mzvfizwicuxkeaopjrpcouqvllxauyqx`
- 요청: 해당 서버에서 실행 중인 서비스가 있으면 등록 해제를 못하도록 에러 메세지를 띄워야 한다.

## 변경 파일

- `src/model/struct/nodes_delete.py`
- `src/app/page.servers/view.ts`
- `tests/api/test_nodes_swarm.py`
- `devlog.md`
- `devlog/2026-05-19/260-server-unregister-running-service-guard.md`

## 작업 내용

- `NodeDeleteMixin.unregister_slave()`에서 삭제 작업을 생성하기 전에 대상 서버의 최신 컨테이너 목록을 조회하고, 등록 서비스 그룹에 실행 중 컨테이너가 있으면 409 `NODE_RUNNING_SERVICES_BLOCK_UNREGISTER` 오류로 중단하게 했다.
- 오류 응답에 실행 중인 서비스 이름, namespace, running 개수를 포함해 화면에서 구체적인 에러 메시지를 표시할 수 있게 했다.
- 서버 관리 화면에서 현재 상세 패널에 실행 중인 등록 서비스가 보이면 확인 모달을 열기 전에 같은 안내 메시지로 즉시 차단하게 했다.
- 서버 등록 해제 정적 계약 테스트에 실행 중 서비스 차단 코드 경로를 확인하는 항목을 추가했다.

## 검증 결과

- `/opt/conda/envs/docker-infra/bin/python -m py_compile src/model/struct/nodes_delete.py src/app/page.servers/api.py src/route/api-nodes-path/controller.py` 통과.
- `/opt/conda/envs/docker-infra/bin/python -m unittest tests.api.test_nodes_swarm.NodesSwarmStaticContractTest` 통과.
- `PYTHONPATH=tests/api /opt/conda/envs/docker-infra/bin/python -m unittest`는 테스트 디스커버리 대상이 없어 0개 실행됨을 확인했다.
- `PYTHONPATH=tests/api /opt/conda/envs/docker-infra/bin/python -m unittest tests.api.test_openapi_contract tests.api.test_swagger_contract`는 live dashboard API가 로그인 세션 없이 401을 반환해 1개 실패했으며, 정적 OpenAPI/Swagger 계약 6개 테스트는 별도로 통과했다.
- `git diff --check` 통과.
- `wiz_project_build(clean=false)` 통과.
- `season-wiz-project=main`, `season-wiz-devmode=true` 쿠키를 포함해 `http://127.0.0.1:3001/servers` HEAD 요청 200 확인.
