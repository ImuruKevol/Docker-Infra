# 독립 서버 등록 해제 시 Swarm skip 상태 정상화

- **ID**: 011
- **날짜**: 2026-06-22
- **유형**: 버그 수정
- **리뷰 ID**: tgiqhdvvxkrzxkvvpfnoosfazlzogejm

## 작업 요약
서버 등록 해제 시 독립 서버는 Swarm 정리가 필요한 대상이 아니므로, 원격 Docker Swarm 상태가 active가 아니면 마스터 Swarm node remove를 정상 skip으로 기록하도록 보정했다.
active 상태인데 NodeID가 없는 경우만 `remote_swarm_node_id_empty`로 구분해, 독립 서버와 비정상 Swarm 상태를 분리했다.

## 원문 요청사항
```text
서버가 독립 서버일 경우도 있으니 독립 서버는 해제 시 swarm을 굳이 신경쓰지 않아도 된다는 점을 생각해줘
```

## 변경 파일 목록
- `src/model/struct/nodes_delete.py`
  - 원격 Swarm inspect payload에 `swarm_active`, `standalone` 상태를 추가.
  - 원격 상태가 `inactive`, `pending`, 빈 값이면 마스터 Swarm node remove skip reason을 `standalone_node`로 기록.
  - 원격 상태가 `active`인데 NodeID가 없을 때만 `remote_swarm_node_id_empty`로 기록.
- `tests/api/test_nodes_swarm.py`
  - 독립 서버 skip reason과 active Swarm NodeID 누락 분기 계약을 추가.
- `devlog.md`
  - 이번 작업 요약 행을 추가.

## 확인 결과
- `python -m py_compile src/model/struct/nodes_delete.py`
- `python -m unittest tests.api.test_nodes_swarm` 통과, live 2건은 환경 변수 미설정으로 skip.
- `wiz_project_build(projectName="main", clean=false)` 성공.

## 남은 리스크
실제 독립 서버 등록 해제 E2E는 SSH 접속 가능한 테스트 서버 환경이 없어 수행하지 못했다.
정적 계약과 빌드 기준으로 독립 서버가 Swarm 오류처럼 처리되지 않는 흐름은 확인했다.
