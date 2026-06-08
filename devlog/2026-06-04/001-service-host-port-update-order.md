# 서비스 host-mode 포트 변경 배포 실패 수정

- 날짜: 2026-06-04
- 리뷰 ID: tpuvsgrpgzkejzmhuhyaztqjynkcdwfp
- 요청: 현재 "bus"라는 이름으로 만든 서비스에서 밖으로 빠지는 포트 하나를 변경하고 적용했는데 에러가 계속 뜨면서 적용되지 않음. 로직 상 문제가 있다면 반드시 수정해야 함.

## 변경 파일

- `src/model/struct/compose_validator.py`
- `src/model/struct/services_deploy.py`
- `devlog.md`
- `devlog/2026-06-04/001-service-host-port-update-order.md`

## 작업 내용

- Docker Swarm host-mode published port가 있는 서비스의 Compose 정규화 시 `deploy.update_config.order`를 `stop-first`로 보정했다.
- 이미 저장된 Compose에 `start-first`가 남아 있는 경우에도 배포 직전에 `stop-first`로 자동 보정하고 operation log에 남기도록 했다.
- 원인 확인: `bus_f7b72d_app`의 실패 작업이 `host-mode port already in use`로 Pending 상태였고, 기존 작업이 같은 노드에서 3000번 host-mode 포트를 잡고 있어 `start-first` 업데이트가 새 작업을 먼저 띄우지 못했다.

## 확인 결과

- `python -m py_compile project/main/src/model/struct/compose_validator.py project/main/src/model/struct/services_deploy.py` 통과.
- `wiz_project_build(projectName="main", clean=false)` 성공.
- `docker service ps bus_f7b72d_app`에서 기존 실패 작업의 에러가 `host-mode port already in use`임을 확인했다.
