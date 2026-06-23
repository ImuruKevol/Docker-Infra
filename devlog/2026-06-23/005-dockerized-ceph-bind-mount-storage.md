# Dockerized Ceph 기반 bind mount 스토리지 설계 재작성

## 사용자 요청

너무 많은 오픈소스가 추가되면 배보다 배꼽이 더 큰 사태가 될 것 같아.
일단 harbor는 이미지 관리때문에 필수로 있어야 해. 근데 harbor에 named volume을 저장하려면 oras를 써야하는데, 이게 비효율적인 방식이라 좋지 못해서 다른 대안을 찾고있는거야. 그래서 이 참에 가능하면 named volume 방식 자체를 bind mount 방식으로 바꾸면서 스토리지 안정성까지 챙기려는거야.

내가 따로 이것저것 찾아본 결과, 그래도 ceph을 써야한다는 결론이 나왔어.
근데 ceph을 그냥 쓰진 않고, ceph을 docker로 띄우는 방식을 사용할거야. docker로 띄울 때 용량을 지정을 해버리는거지. 64GB나 128GB 단위로 ceph을 각각 띄워버리고 docker swarm을 이용한 클러스터로 묶어버리면 될 것 같아.
이걸 상세하게 심화해서 설계 문서를 갈아엎어줘

## 변경 파일

- `docs/backup-volume-layered-storage-design.md`
- `docs/backup-named-volume-snapshot-design.md`
- `devlog.md`
- `devlog/2026-06-23/005-dockerized-ceph-bind-mount-storage.md`

## 작업 내용

- 기존 object storage 후보 비교 중심 문서를 Dockerized Ceph 기반 bind mount storage 설계로 전면 재작성했다.
- 기존 ORAS named volume 설계 문서의 우선 문서 링크를 새 Ceph 설계 제목으로 갱신했다.
- Harbor는 image 전용으로 유지하고, ORAS volume artifact는 장기 방향에서 제외한다는 전제를 명확히 했다.
- named volume 기본값을 CephFS bind mount로 전환하는 방향을 설계했다.
- Docker Swarm은 Ceph 데이터를 복제하는 계층이 아니라 Ceph daemon container lifecycle을 관리하는 계층으로 분리해 설명했다.
- 64GB/128GB OSD 슬롯 모델을 추가하고, 운영 권장 구현은 LVM LV, PoC fallback은 loopback file로 정리했다.
- MON/MGR/MDS/OSD 배치, replica size, CephFS mount path, snapshot/rollback, named volume migration, UI/API 데이터 모델, 구현 단계, 검증 계획을 포함했다.

## 검증 결과

- 문서 전용 변경이라 애플리케이션 빌드나 unit test는 실행하지 않았다.
- `wc -l docs/backup-volume-layered-storage-design.md`로 문서가 868줄로 재작성된 것을 확인했다.
- `rg`로 Harbor, ORAS 제외, Dockerized Ceph, CephFS, 64GB/128GB, LVM, loopback, Swarm, BlueStore, ceph-volume, Phase 항목이 포함된 것을 확인했다.
- `rg '^##|^###'`로 장/절 번호가 1-19 흐름으로 정리된 것을 확인했다.

## 남은 리스크

- Docker Swarm으로 Ceph daemon을 운영하는 방식은 Ceph 공식 cephadm 경로와 다르므로 PoC에서 container lifecycle, host networking, device mapping, OSD 재시작 안정성을 검증해야 한다.
- loopback OSD는 편의용 fallback으로만 보고, 운영 기본은 LVM LV 기반 slot으로 검증해야 한다.
