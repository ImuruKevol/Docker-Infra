# 볼륨 백업 장기 레이어형 스토리지 설계 문서화

## 사용자 요청

이대로라면 oras를 사용하는건 어려울 것 같아. 일단 놔두고 앞으로 어떻게 볼륨 백업까지 할 수 있을지 방향성을 설계해줘.
나중에는 각 서버마다 minio같은걸 설치하도록 해서 모든 서버가 논리적으로 스토리지를 전부 공유할 수 있도록 할거야. 그렇게 되면 named volume을 따로 두지 않고 그냥 path mount식으로 하고, 해당 path는 minio 에서 마운트한 경로 아래에 체계적으로 저장하는 식으로.
이렇게 했을 때 볼륨 자체의 버전까지 최적화하여 관리할 수 있었으면 좋겠어. docker image가 layer 단위로 쌓여서 효율적으로 저장이 되는 것처럼.

설계 문서는 최대한 상세하게 잘 정리해서 한글로 작성해줘. 그리고 설계 문서의 각 내용은 초등학생도 알아먹을 수 있을 정도로 쉽게 설명이 되어야 해.

## 변경 파일

- `docs/backup-volume-layered-storage-design.md`
- `docs/backup-named-volume-snapshot-design.md`
- `devlog.md`
- `devlog/2026-06-22/031-volume-layered-storage-design.md`

## 작업 내용

- ORAS 기반 volume tar.gz artifact 방식은 장기 최적화 방향에서 보류한다는 전제를 새 설계 문서에 정리했다.
- named volume 대신 Docker Infra 관리 host path와 bind mount를 사용하는 장기 저장소 모델을 설계했다.
- MinIO는 POSIX filesystem이 아니라 object storage이므로, version 최적화는 backup engine의 chunk/index/manifest 계층에서 담당해야 한다는 방향을 명시했다.
- Docker image layer와 비슷한 목표를 volume에 적용하기 위해 Content Defined Chunking, pack, index, manifest, retention, GC, restore staging, multi-node repository 설계를 상세히 정리했다.
- 기존 ORAS 설계 문서 상단에 새 장기 설계 문서를 우선 문서로 보라는 상태 안내를 추가했다.

## 검증 결과

- 문서 전용 변경이라 애플리케이션 빌드나 unit test는 실행하지 않았다.
- `wc -l docs/backup-volume-layered-storage-design.md docs/backup-named-volume-snapshot-design.md`로 새 설계 문서 1034줄, 기존 문서 136줄을 확인했다.
- `rg`로 ORAS 보류, MinIO versioning 한계, MinIO-mounted path, Content Defined Chunking, Kopia/restic 참고, 단계별 구현 계획 문구가 포함된 것을 확인했다.

## 남은 리스크

- 실제 구현 전에는 Kopia/restic을 감싸는 방식과 Docker Infra native repository 구현 방식 중 어느 쪽이 운영 요구에 더 맞는지 PoC가 필요하다.
- MinIO-mounted path를 실제 서비스 write path로 쓰려면 FUSE/shared filesystem gateway의 POSIX 동작, DB 일관성, 장애 시 동작을 별도로 검증해야 한다.
