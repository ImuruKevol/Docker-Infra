# GlusterFS 대안 검토와 CephFS 기본값 유지 근거 보강

## 사용자 요청

혹시 ceph도 ceph인데 글러스터를 쓰는 쪽은 어때?

## 변경 파일

- `docs/backup-volume-layered-storage-design.md`
- `docs/ceph-storage-application-plan.md`
- `devlog.md`
- `devlog/2026-06-23/014-glusterfs-alternative-review.md`

## 변경 내용

- GlusterFS를 Docker Infra의 shared storage 후보로 검토한 결과를 설계 문서에 추가했다.
- GlusterFS의 장점인 단순한 brick 기반 공유 폴더 구조, replicated/distributed-replicated volume 가능성을 정리했다.
- 기본 backend로 채택하지 않는 이유로 Red Hat Gluster Storage EOL, FUSE 계층, LVM thin snapshot 의존성, replica set brick 순서 관리, 장기 roadmap 리스크를 문서화했다.
- 실제 적용 계획에서는 GlusterFS를 UI 기본 선택지로 노출하지 않고, 추후 `glusterfs_experimental` 같은 실험 backend로만 확장 가능하게 남기는 방향으로 정리했다.

## 확인 결과

- 공식 문서와 저장소 정보를 확인했다.
  - GlusterFS volume types: https://docs.gluster.org/en/main/Administrator-Guide/Setting-Up-Volumes/
  - GlusterFS snapshot prerequisites: https://docs.gluster.org/en/main/Administrator-Guide/Managing-Snapshots/
  - GlusterFS FUSE architecture: https://docs.gluster.org/en/main/Quick-Start-Guide/Architecture/
  - Red Hat Gluster Storage life cycle: https://access.redhat.com/support/policy/updates/rhs
  - GlusterFS releases: https://github.com/gluster/glusterfs/releases
- `rg`로 `GlusterFS`, `brick slot`, `thin-provisioned LVM`, `실험 후보` 문구 반영 여부를 확인했다.
- 문서 변경만 수행했으므로 빌드와 자동 테스트는 실행하지 않았다.

## 남은 리스크

- GlusterFS 자체 PoC는 수행하지 않았다.
- GlusterFS를 실제 backend로 추가하려면 brick slot 생성, self-heal, split-brain, LVM thin snapshot, package lifecycle을 별도로 검증해야 한다.
- GlusterFS를 지원 backend로 노출하면 CephFS와 별도 운영 UX가 생기므로 제품 복잡도가 증가한다.
