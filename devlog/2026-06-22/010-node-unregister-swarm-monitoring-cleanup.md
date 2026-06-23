# 서버 등록 해제 시 Swarm 원격 확인과 수집 agent 정리 검증

- **ID**: 010
- **날짜**: 2026-06-22
- **유형**: 버그 수정
- **리뷰 ID**: tgiqhdvvxkrzxkvvpfnoosfazlzogejm

## 작업 요약
서버 등록 해제 흐름을 점검해 자원 수집 systemd agent, node-exporter 컨테이너, 원격 Swarm leave, 마스터 Swarm node remove가 실행되는 것을 확인했다.
DB에 저장된 `swarm_node_id`가 비어 있어도 등록 해제 직전 원격 `docker info`로 Swarm NodeID를 확인해 마스터 노드 제거에 사용하도록 보강했다.

## 원문 요청사항
```text
작업 시작

서버 등록 해제 시 swarm이 연결되어 있었으면 해제해야하고, 자원 수집용 컨테이너 띄워놨던 것도 삭제해야해.
이런것들이 정상적으로 되어있는지 확인해줘.
```

## 변경 파일 목록
- `src/model/struct/nodes_delete.py`
  - 등록 해제 전 원격 Docker Swarm 상태를 사전 조회하는 `Remote swarm inspect` 단계를 추가.
  - 저장된 `swarm_node_id`가 없을 때 원격 조회로 얻은 Swarm NodeID를 `swarm.node.remove`에 사용하도록 보강.
  - 결과 payload에 `remote_swarm` 정보를 포함해 등록 해제 후 어떤 Swarm 상태를 기준으로 정리했는지 확인 가능하게 정리.
- `tests/api/test_nodes_swarm.py`
  - 등록 해제 계약 테스트에 원격 Swarm 사전 확인, metrics collector 제거, node-exporter 제거, remote swarm leave, master swarm node remove 조건을 추가.
- `devlog.md`
  - 이번 작업 요약 행을 추가.

## 확인 결과
- `python -m py_compile src/model/struct/nodes_delete.py`
- `python -m unittest tests.api.test_nodes_swarm.NodesSwarmStaticContractTest`
- `python -m unittest tests.api.test_nodes_swarm` 통과, live 2건은 환경 변수 미설정으로 skip.
- `wiz_project_build(projectName="main", clean=false)` 성공.

## 남은 리스크
실제 원격 서버 등록 해제 E2E는 SSH 접속 가능한 테스트 서버 환경이 없어 수행하지 못했다.
다만 코드 경로와 정적 계약, WIZ 빌드 기준으로 수집 agent/exporter 제거와 Swarm 해제 흐름은 확인했다.
