# Ceph OSD slot backing과 CRUSH host 분산 정책 보강

## 사용자 요청

loopback file 형태는 아예 고려하지 말도록 해줘.
그리고 OSD 슬롯은 반드시 LVM으로 해야하나? LVM도 좀 불안정한 부분이 있는 것 같은데 어때?
---
OSD는 단위가 128GB다 하면 내가 바라는 구조는 아래와 같아.

A server: 512GB
B server: 512GB
C server: 256GB
D server: 256GB

이렇게 되어있을 때 A 서버에는 OSD 슬롯이 2~3개, B 서버도 2~3개, C는 1개, D는 1개 이렇게 구성이 되겠지.
이 때 ceph은 3카피가 기본이니, 컨테이너를 하나 띄우고 마운트를 한다 하면 A에 OSD 슬롯이 2~3개 있다고 해서 A의 OSD에 전부 때려박는게 아니라 반드시 A, B, C 서버에 분할이 되어야 해.

## 변경 파일

- `docs/backup-volume-layered-storage-design.md`
- `devlog.md`
- `devlog/2026-06-23/008-ceph-osd-slot-crush-host-policy.md`

## 작업 내용

- loopback file을 지원 후보, PoC 후보, 운영 fallback 후보에서 제외한다고 명확히 정리했다.
- OSD slot은 반드시 LVM LV일 필요가 없고, 기본 backing은 GPT partition slot로 두며 LVM LV는 선택 옵션으로만 둔다고 보강했다.
- ceph-volume lvm은 공식 OSD 준비 도구로 검증하되, 운영자가 직접 LVM VG/LV를 관리하는 UX를 기본값으로 두지 않도록 경계를 분리했다.
- partition slot 사용 시 `PARTUUID`, 실제 Ceph block path, ceph-volume이 만든 내부 LVM artifact를 DB에 기록하도록 데이터 모델을 보강했다.
- A/B/C/D 서버별 128GB slot 예시를 추가하고, replica size 3의 단순 사용 가능 용량과 운영 여유 공간 기준을 설명했다.
- CRUSH rule의 failure domain을 `host`로 강제해 같은 object의 3개 copy가 같은 서버의 여러 OSD에 들어가지 않도록 설계했다.
- `dockerinfra_host_replicated` CRUSH rule 생성, pool 적용, `ceph osd tree`와 `ceph osd crush rule dump` 검증 기준을 추가했다.
- 4 node / 128GB partition slot PoC에 `lsblk`, `blkid`, `pvs`, `vgs`, `lvs`, `ceph-volume lvm list` 검증 항목을 추가했다.

## 검증 결과

- 문서 전용 변경이라 애플리케이션 빌드나 unit test는 실행하지 않았다.
- Ceph 공식 문서에서 ceph-volume lvm이 physical block device, partition, logical volume을 인자로 받을 수 있고 partition에는 `PARTUUID` 식별이 필요하다는 내용을 확인했다.
- Ceph CRUSH 공식 문서에서 `host` failure domain을 쓰면 replica가 unique host에 배치된다는 내용을 확인했다.
- `rg`로 loopback이 지원 후보가 아니라 비대상/미제공 옵션으로만 남아 있는지 확인했다.
- `rg`로 GPT partition, LVM LV 선택 옵션, CRUSH host failure domain, A/B/C/D OSD slot 예시, `dockerinfra_host_replicated` rule이 포함된 것을 확인했다.

## 남은 리스크

- ceph-volume lvm이 partition 입력에서 실제로 어떤 내부 LV/artifact를 만드는지는 Ceph image 버전별 PoC로 확인해야 한다.
- Docker Swarm으로 Ceph daemon을 직접 운영하는 방식은 cephadm 표준 운영 경로와 다르므로 OSD 재시작, device mapping, host network 안정성 검증이 필요하다.
- CRUSH rule이 잘못 바뀌면 size 3이어도 같은 host에 copy가 몰릴 수 있으므로 운영 health check에서 pool rule drift를 계속 감시해야 한다.
