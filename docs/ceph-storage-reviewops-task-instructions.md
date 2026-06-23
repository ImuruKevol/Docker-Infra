# CephFS Storage 적용 ReviewOps 작업 지시서

아래 항목은 ReviewOps에 `title`, `body`만 바로 복사해서 등록할 수 있도록 정리했다. 각 body는 1000자 이하로 작성했다.

---

## 1

Title:
Storage 메뉴와 읽기 전용 개요 페이지 추가

Body:
Docker Infra 사이드바에 `스토리지` 메뉴를 추가하고 `/storage` 페이지 골격을 만든다. 초기 범위는 읽기 전용이다. cluster 미구성 상태, health placeholder, raw/usable/recommended 용량, daemon 개수, warning 목록을 표시한다. 새 app은 `src/app/page.storage/*`로 만들고 API는 우선 page `api.py`에서 시작한다. 기존 기능에는 영향이 없어야 한다.

참고:
- `docs/ceph-storage-application-plan.md` §4, §5.1, §14, §23 Phase 1
- `docs/backup-volume-layered-storage-design.md` §5, §13.1, §16

---

## 2

Title:
Ceph Storage 데이터 모델과 기본 Struct 추가

Body:
Ceph storage 관리를 위한 DB migration과 model skeleton을 추가한다. 대상은 `ceph_clusters`, `ceph_nodes`, `ceph_osd_slots`, `storage_mounts`, `storage_snapshots`, `storage_snapshot_policies`이다. Struct는 `storage.py`, `storage_health.py`, `storage_ceph_cluster.py` 등으로 분리하고, UI/API에서 읽기 전용 overview를 조회할 수 있게 한다. 기존 `backup_system`에는 넣지 않는다.

참고:
- `docs/ceph-storage-application-plan.md` §12, §13, §14, §23 Phase 1
- `docs/backup-volume-layered-storage-design.md` §15, §16

---

## 3

Title:
독립 서버와 Swarm 서버 상태 분기 정리

Body:
`/servers` 화면과 관련 model에서 서버 모드를 명확히 구분한다. `swarm_node_id`가 없으면 독립 서버로 표시하고, Ceph 없이 local bind mount로 서비스 실행 가능하다는 안내를 보여준다. `swarm_node_id`가 있으면 Swarm 서버로 표시하고 Ceph OSD slot 후보가 될 수 있게 한다. 독립 서버에는 OSD slot 버튼을 노출하지 않고 Swarm 등록 CTA를 제공한다.

참고:
- `docs/ceph-storage-application-plan.md` §2, §3, §6, §23 Phase 1
- `docs/backup-volume-layered-storage-design.md` §3.4, §6, §13.2, §18.5

---

## 4

Title:
Ceph preflight와 cluster bootstrap PoC 구현

Body:
Swarm 등록 서버만 Ceph 대상 node 후보로 삼아 preflight를 구현한다. Docker, kernel module, host network, free space, GPT partition 가능 여부, LVM 선택 가능 여부, 3개 host 이상 여부를 검사한다. bootstrap은 mon/mgr/mds container 배치와 operation log 기록까지 PoC로 연결한다. 독립 서버는 preflight 대상에서 제외하고 Swarm 등록 안내만 표시한다.

참고:
- `docs/ceph-storage-application-plan.md` §5.2, §11, §14, §22, §23 Phase 2
- `docs/backup-volume-layered-storage-design.md` §4, §6, §8, §16 Phase 1

---

## 5

Title:
Swarm 서버 OSD 슬롯 구성 마법사 구현

Body:
`/storage` OSD 슬롯 탭과 `/servers/{node}/storage` 탭에서 OSD 슬롯 구성 마법사를 구현한다. 조건은 Swarm active, `swarm_node_id` 저장, Docker/SSH 점검 통과이다. 단계는 서버 확인, 디스크 스캔, 64/128/256GB 선택, GPT partition 기본 선택, plan 확인, slot 생성, ceph-volume prepare/activate, CRUSH host 검증, 결과 저장이다. 위험 작업은 반드시 plan 후 실행한다.

참고:
- `docs/ceph-storage-application-plan.md` §5.3, §6, §14, §22.1, §23 Phase 3
- `docs/backup-volume-layered-storage-design.md` §7, §9.1, §13.2, §17.1

---

## 6

Title:
CephFS host mount와 service mount 모델 구현

Body:
모든 Swarm/Ceph node에 `/srv/docker-infra/storage/cephfs` mount 상태를 관리한다. mount health check, cephx key 배포, 재시작 후 remount 보장, 누락 node warning을 구현한다. 서비스별 mount는 `storage_mounts`에 기록하고 host path는 `/srv/docker-infra/storage/cephfs/services/<service>/mounts/<name>/current` 규칙을 따른다. 독립 서버 서비스는 local bind mount를 유지한다.

참고:
- `docs/ceph-storage-application-plan.md` §5.4, §12.4, §14, §23 Phase 4
- `docs/backup-volume-layered-storage-design.md` §10, §15.4, §16 Phase 4

---

## 7

Title:
서비스 생성 Wizard에 저장소 단계 추가

Body:
`/services/create`에 저장소 단계를 추가한다. Compose의 named volume 후보를 감지하고 실행 대상에 따라 기본값을 다르게 둔다. 독립 서버는 local bind mount, Swarm/Ceph 서버는 CephFS bind mount를 기본으로 한다. Ceph 미구성 시 local bind mount로 계속하거나 Storage 설정으로 이동하게 한다. CephFS 선택 시 top-level `volumes:`를 제거하고 host bind path로 변환한다.

참고:
- `docs/ceph-storage-application-plan.md` §7, §15.1, §15.2, §15.3, §23 Phase 4
- `docs/backup-volume-layered-storage-design.md` §10.2, §10.3, §13.3, §14

---

## 8

Title:
서비스 릴리즈와 롤백을 CephFS snapshot과 연결

Body:
서비스 릴리즈 시 Compose version, Harbor image backup, CephFS snapshot을 같은 이력으로 연결한다. 롤백 modal은 Compose, image, 저장소 복원 계획을 함께 보여준다. CephFS restore는 서비스 중지, 현재 current 보관, snapshot restore-staging 생성, 검증, current 교체, 재배포 순서로 수행한다. DB workload는 snapshot만으로 충분하다고 안내하지 말고 hook/DB-native backup 여지를 남긴다.

참고:
- `docs/ceph-storage-application-plan.md` §8.2, §8.3, §12.5, §16, §23 Phase 5
- `docs/backup-volume-layered-storage-design.md` §11, §17.5, §18.4

---

## 9

Title:
기존 ORAS named volume 기능을 legacy 경로로 축소

Body:
신규 기본 경로에서는 ORAS named volume backup을 제거하고 CephFS snapshot을 사용한다. 기존 named volume 서비스와 과거 artifact 복원은 legacy 경로로 유지한다. scheduler의 volume backup 부분은 CephFS snapshot 생성으로 교체하고, Harbor는 image backup 전용으로 문구와 정책을 정리한다. `/system/backup`은 이미지 백업 중심으로, storage 정책은 `/storage/policy`로 분리한다.

참고:
- `docs/ceph-storage-application-plan.md` §9, §17, §22, §23 Phase 7
- `docs/backup-volume-layered-storage-design.md` §2, §3.1, §12, §16 Phase 0

---

## 10

Title:
Named volume에서 CephFS로 이전하는 Migration Wizard 구현

Body:
기존 named volume 서비스를 CephFS bind mount로 이전하는 wizard를 구현한다. 흐름은 대상 volume 감지, 서비스 중지 계획, CephFS path 생성, 데이터 복사, Compose rewrite, 재배포, 검증이다. 기존 named volume은 자동 삭제하지 않고 rollback 가능성을 남긴다. migration은 plan API로 영향 범위를 먼저 보여주고 사용자 확인 후 실행한다.

참고:
- `docs/ceph-storage-application-plan.md` §18, §22.1, §23 Phase 6
- `docs/backup-volume-layered-storage-design.md` §10.3, §17.7, §18.3

---

## 11

Title:
Dashboard와 Operations에 Storage 상태와 작업 로그 추가

Body:
`/dashboard`에 Storage health badge와 요약 카드를 추가한다. Ceph health error, OSD down, CephFS mount 누락, CRUSH rule drift, nearfull, snapshot cleanup 실패를 우선순위대로 표시한다. `/operations`에는 cluster preflight/bootstrap, OSD slot create/prepare/activate/out/remove, CephFS mount ensure, snapshot create/restore/cleanup, migration 작업 타입을 추가한다. CLI 원문은 접힌 상세로 둔다.

참고:
- `docs/ceph-storage-application-plan.md` §10, §11, §14, §23 Phase 7
- `docs/backup-volume-layered-storage-design.md` §13.1, §17.4, §17.6

---

## 12

Title:
CephFS Storage 검증 시나리오와 테스트 보강

Body:
UI/API/실동작 검증을 추가한다. UI는 `/storage` 미구성, preflight 결과, OSD slot plan, 서비스 생성 저장소 단계, 서비스 상세 저장소 탭, rollback modal을 확인한다. API는 migration, cluster preflight, OSD slot preflight, mount create, snapshot create/restore plan을 검증한다. 실제 동작은 A/B 3개 slot, C/D 1개 slot 예시에서 host bucket, CRUSH rule, mount read/write, snapshot rollback을 확인한다.

참고:
- `docs/ceph-storage-application-plan.md` §22, §25
- `docs/backup-volume-layered-storage-design.md` §18, §9.1, §13.2
