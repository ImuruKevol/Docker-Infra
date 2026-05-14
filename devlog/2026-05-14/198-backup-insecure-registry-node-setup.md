# 198. 백업 레지스트리 insecure registry 노드 자동 적용

- 날짜: 2026-05-14
- 리뷰 ID: `nweydhaljsjvjvdsjkvyxmxwjmjlgihs`
- 요청자: 권태욱

## 원 요청

Harbor에는 HTTPS를 적용하지 않고 내부 백업 시스템으로만 사용할 예정이므로, 등록 노드의 Docker daemon에 insecure registry 설정을 추가해 모든 노드에서 백업이 동작하는지 확인해달라는 요청.

추가 요구:

- insecure registry 설정으로 원격 백업이 해결되면 서버 추가 시 Swarm 합류 후 자동 적용.
- 현재 등록된 서버들에도 일괄 적용.

## 변경 파일

- `config/docker_infra.py`
  - Docker daemon insecure registry 설정 명령을 local executor allowlist에 추가.
- `src/model/struct/local_command_catalog.py`
  - `/etc/docker/daemon.json`의 `insecure-registries`를 보존 병합하고 Docker daemon을 재시작하는 명령 추가.
  - 원격 노드에서도 같은 스크립트를 SSH로 재사용할 수 있도록 command factory 노출.
- `src/model/struct/nodes_backup_registry.py`
  - 백업 레지스트리 주소 계산, 노드별 적용 대상 registry 산정, 로컬/SSH 실행, 전체 노드 일괄 적용 로직 추가.
  - 로컬 마스터는 loopback Harbor 경로가 Docker 기본 허용 범위라 불필요한 Docker 재시작을 건너뛰도록 처리.
- `src/model/struct/nodes.py`
  - 백업 레지스트리 설정 mixin 연결.
- `src/model/struct/nodes_join.py`
  - Swarm join 검증 성공 후 백업 레지스트리 노드 설정을 자동 적용.
- `src/model/struct/service_image_snapshot_runner.py`
  - 원격 스냅샷 push 레지스트리 주소를 노드 백업 레지스트리 계산 로직과 공유.
- `src/app/page.system/api.py`
  - 등록 노드 백업 레지스트리 설정 일괄 적용 API 추가.
- `src/app/page.system/view.pug`
  - 백업 시스템 화면에 `노드 설정 적용` 버튼 추가.
- `src/app/page.system/view.ts`
  - 노드 설정 적용 호출, 진행 상태, 결과 요약 알림 추가.
- `tests/api/test_backup_registry_nodes.py`
  - insecure registry 명령, allowlist, join 후 자동 적용, UI/API 연결 정적 계약 테스트 추가.

## 검증 결과

- 정적/단위 테스트:
  - `/opt/conda/envs/docker-infra/bin/python -m unittest tests.api.test_nodes_swarm tests.api.test_backup_registry_nodes tests.api.test_backup_system_ui tests.api.test_backup_system_runtime tests.api.test_backup_system_schedule tests.api.test_backup_system_cleanup`
  - 결과: `Ran 14 tests`, `OK`, `skipped=2`
- WIZ 빌드:
  - `wiz_project_build(clean=false, projectName="main")`
  - 결과: 성공

## 실제 적용 및 기능 확인

- 등록 노드 일괄 적용:
  - 원격 등록 노드 3대에 내부 백업 레지스트리 insecure registry 설정 적용 성공.
  - 로컬 마스터는 loopback registry 사용이라 설정 변경 없이 건너뜀.
- 실제 이미지 push 확인:
  - `busybox:1.36` 기반 테스트 이미지를 로컬 마스터와 등록 원격 노드 3대에서 내부 Harbor로 push 성공.
- 컨테이너 스냅샷 확인:
  - 로컬 마스터 컨테이너 스냅샷 백업 성공.
  - 원격 등록 노드 1대 컨테이너 스냅샷 백업 성공.
- 정리:
  - 테스트 Swarm 서비스 제거.
  - 테스트 Harbor 프로젝트 제거.

## 남은 리스크

- 원격 노드 Docker daemon 설정 변경 시 Docker 재시작이 필요하므로, 노드 설정 적용 버튼과 서버 추가 후 자동 적용 시 해당 노드의 컨테이너가 일시 영향을 받을 수 있다.
- Swarm 상태가 Down인 등록 서버도 SSH와 Docker daemon이 살아 있으면 레지스트리 push는 가능하지만, Swarm 서비스 스냅샷 대상이 되려면 Swarm 노드 상태가 Ready여야 한다.
