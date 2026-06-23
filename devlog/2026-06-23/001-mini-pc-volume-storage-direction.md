# 미니PC 지향 볼륨 스토리지 후보와 Ceph 제외 기준 보강

## 사용자 요청

내가 MinIO를 예시로 들었던건 ceph을 쓰기엔 Docker Infra의 의도와 맞지 않기 때문이야.
ceph은 완전히 비어있는 하나의 하드를 통채로 3카피로 해야하기에 최소 3개 이상의 하드가 필요해. 하지만 docker infra의 의도는 그런 본격적인 서버랙같은 형태가 아니라 미니pc같은것들을 여러 개 묶어서 빠르고 간편하게 인프라를 구성할 수 있도록 하는거야.
그런 의미에서 ceph은 맞지 않다고 판단했어. 물론 docker 컨테이너를 띄울 때 bind mount를 하려면 ceph만큼 좋은걸 찾기 힘들긴 해. 그런 의미에서 이 내용들을 반영했을 때 설계 문서를 수정 및 보강해줘.
MinIO말고 다른 좋은 SW가 있다면 추천해도 좋아.

## 변경 파일

- `docs/backup-volume-layered-storage-design.md`
- `devlog.md`
- `devlog/2026-06-23/001-mini-pc-volume-storage-direction.md`

## 작업 내용

- 장기 볼륨 백업 설계 문서에서 MinIO 단일 전제를 S3 호환 object storage 후보군으로 확장했다.
- Docker Infra의 기본 목표를 미니PC 여러 대, 기존 디스크/디렉터리 활용, 빠른 설치, 쉬운 복구로 명확히 적었다.
- Ceph은 POSIX/shared storage로 강력하지만 기본값이 아니라 고급 외부 storage driver로만 다룬다는 기준을 추가했다.
- 백업 repository 1차 후보를 Garage로 제안하고, MinIO와 SeaweedFS S3를 2차 후보로 정리했다.
- Docker bind mount에 가까운 shared filesystem이 필요한 경우 JuiceFS over Garage/MinIO를 선택형 POSIX storage driver로 PoC하는 방향을 추가했다.
- 구현 단계에 Garage cluster 우선 PoC, 대안 backend 검증, 선택형 POSIX driver Phase를 반영했다.

## 검증 결과

- 문서 전용 변경이라 애플리케이션 빌드나 unit test는 실행하지 않았다.
- `rg`로 Ceph 제외 기준, Garage cluster, JuiceFS, SeaweedFS, 미니PC, Phase 8 문구가 포함된 것을 확인했다.
- `rg '^##|^###'`로 설계 문서 장/절 번호가 1-31 흐름으로 정리된 것을 확인했다.

## 남은 리스크

- Garage, MinIO, SeaweedFS, JuiceFS는 실제 Docker Infra target 환경에서 설치/장애/성능 PoC가 필요하다.
- JuiceFS 같은 FUSE 기반 path mount를 DB workload에 쓰려면 fsync, lock, rename, latency, metadata DB 장애를 장기 검증해야 한다.
