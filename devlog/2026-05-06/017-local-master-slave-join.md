# 017. Local Master ensure와 Slave join 구현

- 날짜: 2026-05-06
- 원 요청: 사용자가 "P5-02, P5-03 작업을 진행해줘. 테스트에 사용할 서버는 ssh config 파일에 mini2, mini3 이름으로 등록해놨고, 일단 ssh-copy-id로 패스워드 없이 접속할 수 있게 설정해놨어."라고 요청했다.
- 범위: TODO P5-02 Local Master 자동 등록과 Swarm init, TODO P5-03 슬레이브 노드 등록과 join

## 변경 파일

- `src/model/docker_infra/local_executor.py`
- `src/model/docker_infra/ssh_executor.py`
- `src/model/docker_infra/nodes.py`
- `src/route/api-system-local-master-ensure/app.json`
- `src/route/api-system-local-master-ensure/controller.py`
- `src/route/api-nodes/app.json`
- `src/route/api-nodes/controller.py`
- `src/route/api-nodes-path/app.json`
- `src/route/api-nodes-path/controller.py`
- `src/app/page.dashboard/api.py`
- `docs/api/openapi.json`
- `docs/docker-infra-runtime.md`
- `README.md`
- `tests/api/test_nodes_swarm.py`
- `tests/api/test_openapi_contract.py`
- `devlog.md`
- `devlog/2026-05-06/017-local-master-slave-join.md`

## 작업 내용

- Local Executor에 Swarm join token, overlay network inspect/create, parameterized swarm init adapter를 추가했다.
- SSH config alias를 사용하는 `SSHExecutor`를 추가하고 stdout/stderr/exit code/timeout result 구조를 정의했다.
- `NodeService`를 추가해 local master ensure, node 목록/상세, slave 등록, SSH/Docker check, Swarm join job을 구현했다.
- local master ensure는 이미 manager이면 init을 skip하고, overlay network가 없을 때만 생성한다.
- slave credential은 `node_credentials`에 암호화 저장하고 API 응답에는 secret 원문 대신 보유 여부와 fingerprint만 노출한다.
- slave join은 Job/Step/Log를 생성하고, 이미 Swarm에 속한 remote node는 join token fetch와 join command를 skip한다.
- join token은 runtime secret으로 Job log masking에 전달해 로그 평문 저장을 방지했다.
- `/api/system/local-master/ensure`, `/api/nodes`, `/api/nodes/{node_id}`, `/api/nodes/{node_id}/check`, `/api/nodes/{node_id}/join` route와 OpenAPI 계약을 추가했다.
- 대시보드 진행표와 README, 런타임 문서에 P5-02/P5-03 완료 내용을 반영했다.

## 검증

- `/opt/conda/envs/docker-infra/bin/python -m json.tool docs/api/openapi.json`
- `/opt/conda/envs/docker-infra/bin/python -m py_compile src/model/docker_infra/local_executor.py src/model/docker_infra/ssh_executor.py src/model/docker_infra/nodes.py src/route/api-system-local-master-ensure/controller.py src/route/api-nodes/controller.py src/route/api-nodes-path/controller.py tests/api/test_nodes_swarm.py tests/api/test_openapi_contract.py`
- `/opt/conda/envs/docker-infra/bin/python -m unittest discover tests/api`
  - 결과: 56개 통과, 10개 skip(DB 미설정)
- 테스트 DB migration 적용 후 `tests.api.test_nodes_swarm`
  - 결과: 6개 통과
- 테스트 DB migration 적용 후 `/opt/conda/envs/docker-infra/bin/python -m unittest discover tests/api`
  - 결과: 69개 통과, 4개 skip
- 운영 통합 확인
  - local master: Swarm manager 확인, `docker_infra_overlay` overlay network 생성/확인
  - `mini3`: SSH/Docker check 성공, 이미 active worker라 join job idempotent 성공
  - `mini2`: SSH 성공, remote Docker CLI 없음 실패 job과 stderr log 경로 확인
- `npx playwright test --list`
  - 결과: 5개 테스트 목록 확인
- WIZ build
  - 결과: 성공

## Cleanup

- 테스트 DB row는 `test_run_id` 기준으로 삭제했다.
- `mini3`는 이미 Swarm worker였으므로 join command를 재실행하지 않았다.
- `mini2`는 Docker daemon이 없어 join command를 실행하지 않았다.
- `docker_infra_overlay`는 Docker Infra 기본 overlay network라 유지했다.
- 테스트 PostgreSQL 컨테이너와 volume, Python cache, 임시 OpenAPI 검증 파일을 제거했다.
