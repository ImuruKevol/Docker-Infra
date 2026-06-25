# Ceph preflight와 cluster bootstrap PoC 구현

- **ID**: 004
- **날짜**: 2026-06-24
- **유형**: Storage/Ceph PoC

## 작업 요약
Swarm 등록 서버만 Ceph cluster 후보로 삼는 preflight를 추가했다.
Docker, Swarm 상태, kernel Ceph module, Docker host network, free space, GPT partition 도구, LVM 선택 가능 여부, ceph-volume 상태, 3개 host 이상 조건을 점검하고 operation log에 남긴다.
bootstrap은 preflight 통과 후 MON 3개, MGR 2개, MDS 2개 배치 계획을 만들고 Swarm `docker service create --network host` 명령으로 PoC container 배치를 시도하며, `ceph_clusters`/`ceph_nodes`와 operation log를 함께 기록한다.
이미 pending/bootstrapping/running/degraded cluster가 있으면 중복 bootstrap을 중단한다.

## 원문 요청사항
```text
작업 시작

리뷰 ID: ybptdjndmjlcgkhwmdxfulwtxfuviqrz
제목: Ceph preflight와 cluster bootstrap PoC 구현

Swarm 등록 서버만 Ceph 대상 node 후보로 삼아 preflight를 구현한다.
Docker, kernel module, host network, free space, GPT partition 가능 여부, LVM 선택 가능 여부, 3개 host 이상 여부를 검사한다.
bootstrap은 mon/mgr/mds container 배치와 operation log 기록까지 PoC로 연결한다.
독립 서버는 preflight 대상에서 제외하고 Swarm 등록 안내만 표시한다.

참고:
- `docs/ceph-storage-application-plan.md` §5.2, §11, §14, §22, §23 Phase 2
- `docs/backup-volume-layered-storage-design.md` §4, §6, §8, §16 Phase 1
```

## 변경 파일 목록

### Source App
- `src/app/page.storage/api.py`: `cluster_preflight`, `cluster_bootstrap`, `operation_status` API 추가.
- `src/app/page.storage/view.ts`: preflight/bootstrap 실행 상태, operation 조회, 결과 helper 추가.
- `src/app/page.storage/view.pug`: 사전 점검/cluster 만들기 버튼, Swarm 후보 결과, 독립 서버 제외 및 Swarm 등록 안내, operation log 패널 추가.

### Model
- `src/model/struct/local_command_catalog.py`: Ceph node preflight shell script와 `storage.ceph.node.preflight`, `storage.ceph.daemon.service.create` 명령 추가.
- `src/model/struct/storage.py`: storage service 진입점에 cluster preflight/bootstrap/status 메서드 추가.
- `src/model/struct/storage_ceph_cluster.py`: preflight operation 기록과 bootstrap helper 연결 추가.
- `src/model/struct/storage_ceph_preflight.py`: Swarm 등록 서버 필터링과 node별 preflight 검사 구현.
- `src/model/struct/storage_ceph_bootstrap.py`: MON/MGR/MDS placement plan, cluster/node DB 기록, Swarm service 생성 PoC, operation log 기록 구현.

### Tests / Devlog
- `tests/api/test_storage_models.py`: Phase 2 preflight/bootstrap 계약 static test 추가.
- `devlog.md`: 작업 요약 행 추가.
- `devlog/2026-06-24/004-ceph-preflight-bootstrap-poc.md`: 상세 devlog 추가.

## 확인 결과
- `/opt/conda/envs/docker-infra/bin/python -m py_compile src/model/struct/storage_ceph_cluster.py src/model/struct/storage_ceph_preflight.py src/model/struct/storage_ceph_bootstrap.py src/model/struct/local_command_catalog.py src/app/page.storage/api.py src/model/struct/storage.py` 통과.
- `/opt/conda/envs/docker-infra/bin/python -m unittest tests.api.test_storage_models` 통과.
- `/opt/conda/envs/docker-infra/bin/python -m unittest tests.api.test_migration_schema tests.api.test_storage_models` 통과.
- `wiz_project_build(clean=False)` 성공.
- dev 서버를 `127.0.0.1:3017`에서 띄우고 Playwright로 `season-wiz-project=main`, `season-wiz-devmode=true` 쿠키를 설정한 뒤 `/storage` 진입을 시도했다. 인증 세션이 없어 `/access`로 리다이렉트되는 것을 확인했다.

## 남은 리스크
- bootstrap PoC의 `docker service create`는 destructive local command allowlist와 실제 Swarm manager 권한이 있어야 실행된다.
- MON/MGR/MDS container는 PoC placement용이며, 실제 Ceph quorum/fs 생성과 OSD prepare/activate는 후속 Phase 범위다.
- 인증 세션이 없어 로그인 후 실제 `/storage` 화면 상호작용과 preflight API 실행은 브라우저에서 검증하지 못했다.
