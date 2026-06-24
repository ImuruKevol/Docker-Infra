# Dockerized Ceph 기반 Bind Mount Storage 설계

## 1. 한 줄 결론

Harbor는 image 관리 때문에 계속 필수로 둔다. 하지만 서비스 데이터는 Harbor에 저장하지 않는다. 서비스 데이터는 Docker-managed volume이 아니라 CephFS bind mount path로 관리한다.

따라서 장기 방향은 기존 volume artifact 백업을 더 개선하는 것이 아니라, 서비스 저장소 자체를 bind mount 기반으로 바꾸는 것이다. bind mount의 실제 저장소는 Dockerized Ceph이 제공하는 CephFS에 둔다. Ceph은 Docker container로 실행하되, 각 노드마다 64GB 또는 128GB 같은 고정 크기 OSD 슬롯을 Docker Infra가 만들고 관리한다.

초등학생에게 설명하듯 말하면 다음과 같다.

- Harbor는 컨테이너 이미지 보관함이다.
- 서비스 데이터는 이미지 보관함에 넣지 않는다.
- Ceph은 여러 미니PC의 작은 저장 공간을 하나의 튼튼한 공용 책장처럼 묶는 역할이다.
- Docker Infra는 각 미니PC에 "64GB짜리 책장 칸"을 만들고 Ceph에게 맡긴다.
- 서비스 컨테이너는 Docker-managed volume 대신 그 공용 책장의 정해진 칸을 bind mount로 쓴다.

## 2. 배경

이전 검증에서 확인한 내용은 명확하다.

1. Harbor는 image backup과 image rollback을 위해 필요하다.
2. 서비스 데이터를 이미지 보관함에 넣는 방식은 Docker image layer처럼 효율적인 변경분 저장이 되지 않는다.
3. 파일 일부만 바뀌어도 전체 데이터 묶음이 다시 만들어지는 구조가 된다.
4. 그래서 서비스 데이터는 이미지와 분리된 shared filesystem에서 관리해야 한다.

이 문제를 풀기 위해 여러 object storage나 backup engine을 추가할 수는 있다. 하지만 Docker Infra에 너무 많은 오픈소스가 붙으면 설치와 운영이 복잡해진다. 배보다 배꼽이 더 커질 수 있다.

그래서 이번 설계는 선택지를 줄인다.

- image는 Harbor가 맡는다.
- volume/path storage는 Ceph이 맡는다.
- Docker Infra는 Ceph 설치와 용량 슬롯, mount path, snapshot 정책을 쉽게 관리한다.

## 3. 핵심 방향

### 3.1 Docker-managed volume을 신규 경로에서 제거한다

기존 방식:

```yaml
services:
  db:
    volumes:
      - db-data:/var/lib/postgresql/data
volumes:
  db-data:
```

장기 목표 방식:

```yaml
services:
  db:
    volumes:
      - /srv/docker-infra/storage/cephfs/services/shop/mounts/db-data/current:/var/lib/postgresql/data
```

서비스 입장에서는 똑같이 `/var/lib/postgresql/data`에 쓴다. 하지만 실제 저장 위치는 Docker Infra가 관리하는 CephFS path다.

CephFS 적용 이후 Docker Infra가 새로 생성하거나 관리하는 서비스에서는 top-level `volumes:`를 만들지 않는다. Compose 초안에 Docker-managed volume이 들어오면 서비스 생성 단계에서 CephFS bind mount 또는 독립 서버 local bind mount로 변환한다.

이미 배포된 기존 서비스는 자동 변환하지 않는다. 운영자가 직접 백업 후 재배포하거나 별도 Codex agent 작업으로 수동 이전을 수행할 수 있다. Docker Infra의 기본 제품 기능은 기존 Docker-managed volume을 계속 복원하거나 보관하는 방향으로 확장하지 않는다.

### 3.2 Ceph은 Docker로 실행한다

Ceph을 host에 직접 패키지로 설치하는 것이 아니라, 공식 Ceph container image를 사용한다.

중요한 점은 이것이다.

```text
Docker Swarm이 Ceph 데이터를 복제하는 것이 아니다.
Ceph이 데이터를 복제한다.
Docker Swarm은 Ceph daemon container를 지정한 node에서 실행하고 재시작하는 역할만 한다.
```

즉 Swarm은 "실행 관리자"이고, Ceph은 "스토리지 관리자"다.

### 3.3 OSD 용량은 슬롯으로 제한한다

Ceph OSD는 저장 공간을 담당하는 일꾼이다.

Docker Infra는 각 node에 다음처럼 OSD 슬롯을 만든다.

```text
node-a
  osd-slot-0: 64GB
  osd-slot-1: 64GB

node-b
  osd-slot-0: 64GB

node-c
  osd-slot-0: 128GB
```

이렇게 하면 전체 빈 디스크를 통째로 요구하지 않고, 미니PC의 기존 디스크 일부를 Ceph에 나눠줄 수 있다.

### 3.4 독립 서버는 삭제하지 않는다

이 설계가 "Docker Infra의 모든 서버는 반드시 Ceph을 써야 한다"는 뜻은 아니다.

Docker Infra에는 두 가지 서버 운영 모드가 함께 남는다.

| 모드 | 조건 | 저장소 기본값 | 쉬운 설명 |
|---|---|---|---|
| 독립 서버 | Swarm cluster에 아직 등록하지 않은 서버 | local bind mount | 혼자 쓰는 책상이다. 책상이 단순하고 빠르지만, 다른 집으로 자동 복사되지는 않는다. |
| 클러스터 서버 | Swarm cluster에 등록된 서버 | CephFS bind mount | 여러 집이 함께 쓰는 공용 책장이다. Ceph이 데이터를 여러 서버에 나누어 보관한다. |

독립 서버는 Ceph 없이도 계속 서비스를 실행할 수 있어야 한다. 작은 단일 서버, 개발용 서버, 임시 서비스에는 이 방식이 더 단순하다.

대신 독립 서버의 데이터에는 다음 한계가 있다.

- 데이터가 해당 서버의 local path에 머문다.
- 서버 장애 시 Ceph replica 보호를 받지 못한다.
- 다른 서버로 서비스를 옮길 때 데이터가 자동으로 따라가지 않는다.
- CephFS snapshot 기반 rollback 대상이 아니다.

따라서 장기 기본값은 "클러스터 서비스는 CephFS bind mount"이지만, "독립 서버는 Ceph 없이 local bind mount로 운영 가능"이라는 예외를 제품 정책으로 남긴다.

## 4. 공식 문서 기준 전제

설계는 다음 공식 문서 전제를 따른다.

- Ceph container image는 공식적으로 제공된다. `quay.io/ceph/ceph` 계열 image가 Ceph daemon과 dependency를 포함한다.
- cephadm은 Ceph daemon을 container로 배포하는 공식 경로다. 다만 이 설계에서는 Docker Infra와 Swarm 통합을 위해 cephadm 개념을 참고하되, 최종 실행 방식은 Docker Infra가 통제한다.
- BlueStore는 Ceph OSD용 storage backend이고 raw block device, partition, logical volume 같은 block device를 직접 쓰는 방향이다.
- ceph-volume lvm은 이름은 `lvm`이지만 BlueStore OSD 준비 과정에서 physical block device, partition, logical volume을 인자로 받을 수 있다. 다만 raw physical device를 넘기면 내부적으로 logical volume을 만들 수 있고, partition을 쓸 때는 `PARTUUID`로 식별 가능해야 한다. 따라서 Docker Infra의 설계 단위는 "운영자가 직접 관리하는 LVM LV"가 아니라 "안정적으로 다시 찾을 수 있는 block device slot"이다.
- Ceph CRUSH rule은 failure domain을 `host`로 둘 수 있다. 이 경우 같은 data replica가 같은 host의 여러 OSD에 몰리지 않고, 서로 다른 host에 배치된다.
- CephFS는 subvolume과 snapshot을 제공한다. 이 기능을 서비스 mount version 관리에 사용한다.

참고:

- Ceph Container Images: https://docs.ceph.com/en/latest/install/containers/
- cephadm install: https://docs.ceph.com/en/latest/cephadm/install/
- Ceph BlueStore storage devices: https://docs.ceph.com/en/latest/rados/configuration/storage-devices/
- Ceph BlueStore config reference: https://docs.ceph.com/en/latest/rados/configuration/bluestore-config-ref/
- ceph-volume lvm prepare: https://docs.ceph.com/en/reef/ceph-volume/lvm/prepare/
- Ceph CRUSH map: https://docs.ceph.com/en/latest/rados/operations/crush-map/
- CephFS volumes and subvolumes: https://docs.ceph.com/en/latest/cephfs/fs-volumes

## 5. 전체 아키텍처

```text
Docker Infra UI/API
  ↓
Docker Infra Ceph Controller
  ↓
Docker Swarm services
  ├─ ceph-mon containers
  ├─ ceph-mgr containers
  ├─ ceph-mds containers
  └─ ceph-osd containers
        ↓
      64GB/128GB OSD slots
        ↓
      Ceph cluster
        ↓
      CephFS
        ↓
/srv/docker-infra/storage/cephfs
        ↓ bind mount
서비스 컨테이너
```

각 부분의 역할은 다음과 같다.

| 구성 요소 | 쉬운 설명 | 역할 |
|---|---|---|
| Harbor | 이미지 보관함 | container image backup/rollback |
| Ceph MON | 반장 | cluster 지도와 quorum 관리 |
| Ceph MGR | 관리자 | 상태, dashboard, module 관리 |
| Ceph OSD | 창고 일꾼 | 실제 데이터 저장 |
| Ceph MDS | 파일 목록 관리자 | CephFS directory/file metadata 관리 |
| CephFS | 공용 파일 책장 | bind mount 대상 filesystem |
| Docker Swarm | 실행 관리자 | Ceph daemon container 배치/재시작 |
| Docker Infra Ceph Controller | 조율자 | slot 생성, service 배포, health 확인, UI 연결 |

## 6. Swarm과 Ceph의 책임 분리

이 설계에서 가장 중요한 오해 방지는 다음이다.

```text
Swarm service replica를 3개로 늘린다고 Ceph OSD 3개가 안전해지는 것이 아니다.
Ceph OSD는 각자 고유한 data slot과 OSD id를 가진다.
```

따라서 Ceph daemon은 일반 stateless service처럼 아무 node에서나 뜨면 안 된다.

또 하나 중요한 규칙이 있다.

```text
서버를 등록했다고 바로 Ceph OSD slot을 만들 수 있는 것은 아니다.
OSD slot은 Swarm cluster에 등록된 서버에서만 만든다.
```

독립 서버는 Compose 실행 대상이다. 이 서버에는 Ceph daemon을 배치하지 않고, OSD slot 구성 마법사도 바로 보여주지 않는다. 화면에서는 "Ceph 없이 local bind mount로 실행할 수 있음"을 보여주고, 공용 스토리지가 필요하면 먼저 Swarm cluster에 등록하도록 안내한다.

Swarm 등록이 끝나면 Docker Infra는 해당 서버의 `swarm_node_id`를 알 수 있다. 그때부터 다음 작업이 가능해진다.

- Swarm node label 부여
- Ceph daemon placement 고정
- OSD slot 생성 마법사 실행
- CRUSH host bucket 검증
- CephFS mount 상태 확인

쉬운 말로 하면, 독립 서버는 아직 "공용 책장 팀"에 들어오지 않은 집이다. 팀에 들어온 뒤에야 그 집의 빈 공간을 공용 책장 칸으로 빌려줄 수 있다.

### 6.1 node-pinned service

OSD container는 반드시 특정 node와 특정 slot에 고정한다.

예시:

```yaml
services:
  ceph-osd-node-a-slot-0:
    image: quay.io/ceph/ceph:v19
    deploy:
      placement:
        constraints:
          - node.labels.docker-infra.ceph.node == node-a
          - node.labels.docker-infra.ceph.osd.slot.0 == true
```

쉬운 말로 하면 다음과 같다.

- OSD는 자기 책상과 자기 서랍이 정해져 있다.
- 다른 자리에서 같은 이름으로 일하면 안 된다.
- Swarm은 그 자리에 그 일꾼을 다시 앉히는 역할만 한다.

### 6.2 Swarm overlay network는 기본 storage network로 쓰지 않는다

Ceph은 storage traffic이 많다. overlay network는 편하지만 storage 경로로 쓰기에는 지연과 MTU 문제가 생길 수 있다.

권장:

- Ceph daemon은 host network를 사용한다.
- node의 고정 IP를 Ceph public network로 등록한다.
- 가능하면 별도 storage network를 두지만, 미니PC 기본형에서는 public/cluster network를 하나로 시작한다.

## 7. OSD 슬롯 설계

### 7.1 슬롯이 필요한 이유

전통적인 Ceph은 빈 디스크 전체를 OSD로 쓰는 경우가 많다. 하지만 Docker Infra의 대상은 미니PC다.

미니PC는 보통 이런 모습이다.

```text
1TB SSD 하나
  - OS
  - Docker image
  - 서비스 데이터
  - 여유 공간 일부
```

여기서 디스크 전체를 Ceph에게 줄 수 없다. 그래서 Docker Infra는 남는 공간 일부만 잘라서 OSD 슬롯으로 만든다.

```text
1TB SSD
  ├─ OS/Docker: 250GB
  ├─ 일반 데이터: 500GB
  └─ Ceph OSD slot: 128GB
```

### 7.2 권장 슬롯 크기

초기 UI는 단순하게 둔다.

| 슬롯 크기 | 용도 |
|---:|---|
| 64GB | 테스트, 작은 서비스, 미니PC 기본값 |
| 128GB | 일반 운영 기본값 |
| 256GB | 여유 디스크가 있는 node |

처음부터 자유 입력을 허용하지 않는다. 운영자가 실수로 디스크를 꽉 채우지 않도록 정해진 크기만 선택하게 한다.

### 7.3 실제 구현 방식

loopback file 방식은 비대상이다. 지원 후보, PoC 후보, 운영 fallback 후보에 넣지 않는다.

OSD 슬롯은 반드시 LVM LV일 필요가 없다. 여기서 두 가지를 나눠서 봐야 한다.

```text
용량을 자르는 방식
  - GPT partition
  - LVM LV

Ceph OSD를 준비하는 도구
  - ceph-volume lvm
```

쉽게 말하면, "128GB짜리 방을 어떻게 만들 것인가"와 "그 방을 Ceph 방으로 등록하는 도구가 무엇인가"는 다른 문제다.

Docker Infra의 기본 결론은 다음과 같다.

- 용량을 자르는 기본 방식은 GPT partition이다.
- LVM LV는 선택 방식이다.
- ceph-volume lvm은 공식 OSD 준비 도구로 검증한다.
- ceph-volume lvm을 쓰더라도, 운영자가 직접 VG/LV를 관리해야 하는 구조를 기본값으로 만들지는 않는다.

#### 방식 A: GPT partition slot

기본 권장 방식이다.

```text
host disk free space
  ↓
128GB GPT partition
  ↓
/dev/disk/by-partuuid/<slot-partuuid>
  ↓
ceph-volume lvm prepare
  ↓
ceph-osd container
```

이 방식은 "LVM을 전혀 모른 채로도 슬롯 크기와 위치를 이해할 수 있다"는 장점이 있다. Docker Infra는 partition을 만들고, `PARTUUID`를 저장하고, Ceph 준비 과정이 만든 실제 OSD 정보를 DB에 기록한다.

중요한 주의점:

- ceph-volume lvm은 partition을 인자로 받을 수 있다.
- Ceph 버전과 prepare 옵션에 따라 내부적으로 LVM metadata나 LV가 생길 수 있다.
- 그래도 운영자가 직접 LVM VG를 설계하고 관리하는 방식은 아니다.
- PoC에서 `lsblk`, `pvs`, `vgs`, `lvs`, `ceph-volume lvm list` 결과를 저장해 실제 생성물을 확인해야 한다.

장점:

- 구조가 단순하다.
- LVM 계층을 운영자가 직접 신뢰하지 않아도 된다.
- slot 크기가 partition 크기로 명확하다.
- `/dev/disk/by-partuuid`로 안정적인 device path를 잡을 수 있다.

단점:

- slot 크기 변경과 재배치가 LVM보다 불편하다.
- 디스크 중간에 빈 공간이 잘려 있으면 partition 배치가 까다롭다.
- partition 작업은 실수하면 위험하므로 Docker Infra preflight와 confirmation이 강해야 한다.

#### 방식 B: LVM LV slot

선택 방식이다. LVM을 이미 쓰고 있거나 VG 여유 공간을 관리하기 쉬운 환경에서는 유용하다.

```text
host disk free space
  ↓
docker-infra-ceph VG
  ↓
128GB LV
  ↓
/dev/docker-infra-ceph/osd-node-a-slot-0
  ↓
ceph-volume lvm prepare
  ↓
ceph-osd container
```

장점:

- 여러 slot 생성과 제거가 편하다.
- 여유 공간 관리가 쉽다.
- ceph-volume lvm 흐름과 잘 맞는다.

단점:

- LVM 계층이 추가된다.
- 운영자가 LVM에 불안감을 느낄 수 있다.
- VG/PV 손상 시 복구 절차를 알아야 한다.

LVM 자체가 일반적으로 불안정한 기술이라서 피해야 한다고 보기는 어렵다. Linux 서버에서 오래 쓰인 성숙한 기술이다. 다만 Docker Infra가 목표로 하는 "미니PC 여러 대를 빠르게 묶는 쉬운 운영"에서는 LVM이 다음 문제를 만든다.

- 사용자가 VG/PV/LV 개념을 알아야 한다.
- 잘못 지우면 OS 디스크나 다른 데이터에 영향을 줄 수 있다.
- 장애 복구 때 Ceph 문제인지 LVM 문제인지 한 단계 더 판단해야 한다.

그래서 기본값은 GPT partition으로 둔다. LVM LV는 "이미 LVM을 이해하고 있고, 노드별 여유 공간을 LV로 관리하고 싶다"는 운영자에게만 열어둔다.

정책:

- loopback file은 지원하지 않는다.
- 기본 UI 추천은 GPT partition slot이다.
- LVM은 "LVM 사용에 동의"한 node에서만 선택 가능하게 한다.
- 어떤 방식을 쓰더라도 OSD slot은 block device로만 준비한다.
- OSD 생성 후에는 Docker Infra DB에 slot 원본, PARTUUID 또는 LV UUID, 생성된 OSD ID, 실제 Ceph device 정보를 모두 저장한다.

### 7.4 슬롯 개수 예시

사용자가 원하는 예시는 다음과 같다.

```text
A server: 512GB
B server: 512GB
C server: 256GB
D server: 256GB
```

OSD 단위를 128GB로 잡으면 보수적으로 다음처럼 구성할 수 있다.

```text
A server: 128GB slot 3개 = 384GB
B server: 128GB slot 3개 = 384GB
C server: 128GB slot 1개 = 128GB
D server: 128GB slot 1개 = 128GB
```

남은 공간은 OS, Docker image, 로그, recovery 여유 공간으로 둔다. A/B가 512GB라고 해서 4개를 꽉 채우지 않는 이유는 디스크 full과 Ceph recovery 공간 부족을 피하기 위해서다.

## 8. Ceph daemon 배치

### 8.1 최소 구성

운영 기본은 3 node 이상이다.

```text
node-a: mon, mgr, mds, osd.0
node-b: mon, mgr standby, mds standby, osd.1
node-c: mon, osd.2
```

개발용 1 node나 2 node 구성은 허용할 수 있다. 하지만 UI에서 "운영 안전 모드가 아님"을 표시한다.

### 8.2 MON

MON은 cluster의 지도를 관리한다. quorum이 중요하므로 운영 기본은 3개다.

```text
mon.a
mon.b
mon.c
```

주의:

- 2개 MON은 하나가 죽으면 quorum 문제가 생길 수 있다.
- 3개가 가장 단순한 운영 기본값이다.

### 8.3 MGR

MGR은 상태와 module을 관리한다.

```text
mgr.a active
mgr.b standby
```

최소 1개로 시작할 수 있지만, 운영 기본은 active + standby다.

### 8.4 MDS

CephFS를 쓰려면 MDS가 필요하다.

```text
mds.a active
mds.b standby
```

Docker service bind mount의 기본 저장소를 CephFS로 잡기 때문에, MDS는 필수 구성 요소다.

### 8.5 OSD

OSD는 실제 데이터를 저장한다.

각 OSD는 다음을 가진다.

- OSD id
- node id
- slot id
- block device 또는 LV
- Ceph keyring
- container service id

OSD는 절대 stateless replica로 취급하지 않는다.

## 9. Pool과 replica 정책

### 9.1 기본 replica

운영 기본값은 replica size 3이다.

```text
같은 데이터 조각을 서로 다른 host 3곳에 둔다.
```

쉬운 설명:

- 공책을 3권 복사해 서로 다른 집에 둔다.
- 한 방이 불편해져도 다른 방의 공책으로 읽을 수 있다.
- 집이 3개는 있어야 이 규칙이 의미가 있다.

여기서 중요한 것은 `size=3`만이 아니다. 반드시 CRUSH rule의 failure domain을 `host`로 둔다.

```text
replica size = 3
failure domain = host
```

이렇게 하면 A 서버에 OSD 슬롯이 3개 있어도 같은 object의 3카피가 A 서버 안의 osd.0, osd.1, osd.2에 모두 들어가지 않는다. Ceph은 한 object의 replica를 서로 다른 host에 둔다.

예시:

```text
A server: osd.0, osd.1, osd.2
B server: osd.3, osd.4, osd.5
C server: osd.6
D server: osd.7
```

128GB 슬롯 기준 raw 용량은 다음과 같다.

```text
A: 384GB
B: 384GB
C: 128GB
D: 128GB
합계: 1024GB
```

replica size 3이면 같은 데이터를 3벌 저장하므로 단순 계산상 사용 가능 용량은 약 341GB다.

```text
1024GB / 3 = 약 341GB
```

여기에서 실제 운영 가능 용량은 recovery 여유 공간을 빼야 하므로 더 작게 잡아야 한다. 예를 들어 70% 선을 경고 기준으로 두면 운영자가 안전하게 쓸 수 있는 용량은 약 238GB 정도로 보는 편이 낫다.

```text
341GB * 70% = 약 238GB
```

가능한 배치:

```text
object X copy 1 → A server의 osd.1
object X copy 2 → B server의 osd.4
object X copy 3 → C server의 osd.6
```

다른 object는 다음처럼 갈 수도 있다.

```text
object Y copy 1 → A server의 osd.0
object Y copy 2 → B server의 osd.5
object Y copy 3 → D server의 osd.7
```

불가능하게 막아야 하는 배치:

```text
object X copy 1 → A server의 osd.0
object X copy 2 → A server의 osd.1
object X copy 3 → A server의 osd.2
```

즉 "A에 슬롯이 많으니 A에 다 넣는다"가 아니다. A/B 서버는 슬롯이 많으므로 전체 데이터 중 더 많은 PG에서 replica host로 선택될 수는 있다. 하지만 같은 object의 여러 copy가 같은 host에 들어가면 안 된다.

초등학생도 이해할 수 있게 말하면 다음과 같다.

```text
같은 숙제장을 3장 복사한다.
한 집에 방이 3개 있어도 3장을 모두 그 집에 두면 안 된다.
불이 나거나 전기가 나가면 3장을 한 번에 잃기 때문이다.
그래서 한 장은 A 집, 한 장은 B 집, 한 장은 C 집에 둔다.
```

운영 규칙:

- 같은 object의 copy는 서로 다른 host에 둔다.
- host가 3대 미만이면 size 3 운영 모드를 막는다.
- 4대 이상이면 한 object는 그중 3대에 놓인다.
- 슬롯이 많은 A/B는 전체 cluster에서 더 많은 데이터를 맡을 수 있다.
- 그래도 같은 object의 3개 copy가 A 내부 OSD 3개에 동시에 들어가면 설계 실패다.

Docker Infra는 Ceph pool 생성 시 host failure domain rule을 만든다.

```bash
ceph osd crush rule create-replicated dockerinfra_host_replicated default host
ceph osd pool set cephfs_data crush_rule dockerinfra_host_replicated
ceph osd pool set cephfs_metadata crush_rule dockerinfra_host_replicated
```

그리고 다음을 검증한다.

```bash
ceph osd tree
ceph osd crush rule dump dockerinfra_host_replicated
```

검증 기준:

- 모든 OSD는 올바른 host bucket 아래에 있어야 한다.
- CephFS data/metadata pool은 `dockerinfra_host_replicated` rule을 써야 한다.
- 운영 모드에서는 OSD가 있는 host가 최소 3개 이상이어야 한다.

### 9.2 개발 모드

개발/PoC에서는 size 1 또는 size 2를 허용할 수 있다.

하지만 반드시 다음 표시를 붙인다.

```text
개발 모드: 디스크 또는 node 장애 시 데이터 손실 가능성이 큽니다.
```

### 9.3 Pool 구성

초기에는 단순하게 간다.

```text
cephfs_metadata: replicated size 3, failure domain host
cephfs_data:     replicated size 3, failure domain host
```

Erasure coding은 초기 범위에서 제외한다. 저장 효율은 좋지만 운영과 복구가 복잡해진다.

## 10. CephFS 기반 bind mount 구조

### 10.1 host mount point

모든 Docker node는 CephFS를 같은 위치에 mount한다.

```text
/srv/docker-infra/storage/cephfs
```

mount 방식:

- 우선순위 1: kernel cephfs client
- 우선순위 2: ceph-fuse

kernel client가 가능하면 우선 사용한다. ceph-fuse는 설치와 격리는 편할 수 있지만 FUSE overhead가 있다.

### 10.2 서비스 path 규칙

서비스별 path는 다음처럼 만든다.

```text
/srv/docker-infra/storage/cephfs/
  services/
    <service_namespace>/
      mounts/
        <mount_name>/
          current/
          snapshots/
          restore-staging/
          .docker-infra/
```

예시:

```text
/srv/docker-infra/storage/cephfs/services/wiki/mounts/data/current
```

Compose에는 이 path를 bind mount한다.

```yaml
services:
  wiki:
    image: wiki:1.0
    volumes:
      - /srv/docker-infra/storage/cephfs/services/wiki/mounts/data/current:/app/data
```

### 10.3 Docker-managed volume 입력 처리

신규 서비스는 기본적으로 bind mount를 사용한다.

Compose 초안에 Docker-managed volume이 들어오면 Docker Infra가 저장 전에 bind mount로 변환한다.

```text
1. Compose 초안에서 top-level volumes와 service volume source를 찾는다.
2. 실행 대상이 Swarm/Ceph 서버이면 CephFS path를 만든다.
3. 실행 대상이 독립 서버이면 local bind mount path를 만든다.
4. service volumes를 host path bind mount로 바꾼다.
5. top-level volumes 항목을 제거한다.
6. 원래 source 이름은 metadata에만 남긴다.
```

이미 배포된 기존 서비스는 자동 이전 기능을 제공하지 않는다. 기존 데이터는 운영자가 직접 백업 후 재배포하거나, 별도 Codex agent 작업으로 수동 이전한다.

## 11. 버전 관리와 snapshot

### 11.1 CephFS snapshot을 기본 버전으로 사용한다

Ceph 방식에서는 CephFS snapshot이 버전이다.

```text
current/
  state.txt
  uploads/a.png

snapshot: snap_20260623_100000
```

snapshot은 특정 시점의 파일 상태를 잡아둔다.

### 11.2 Docker image layer와의 관계

CephFS snapshot은 Docker image layer와 같은 포맷은 아니다.

하지만 사용자가 원하는 핵심 목표는 같다.

```text
안 바뀐 데이터는 다시 복사하지 않는다.
바뀐 데이터만 추가 비용이 든다.
원하는 시점으로 되돌릴 수 있다.
```

Ceph은 내부적으로 RADOS object와 copy-on-write 성격의 snapshot을 사용해 이 목표에 가깝게 동작한다. Docker Infra는 이 기능을 서비스 버전 이력과 연결한다.

### 11.3 snapshot 이름 규칙

```text
snap_<YYYYMMDD>_<HHMMSS>_<compose_version>
```

예시:

```text
snap_20260623_100000_v17
```

### 11.4 rollback 흐름

안전한 rollback은 기존 current를 바로 지우지 않는다.

```text
1. 서비스 중지
2. current를 rollback-before-<time>으로 보관
3. 선택한 snapshot을 restore-staging으로 clone/copy
4. restore-staging 검증
5. restore-staging을 current로 교체
6. 서비스 시작
```

CephFS subvolume clone이 가능한 경우 clone을 사용한다. clone이 느리거나 제약이 있으면 snapshot 내용을 rsync/cp로 materialize한다.

## 12. 백업과 고가용성의 차이

Ceph replica와 snapshot은 매우 유용하지만, 이것만으로 완전한 백업은 아니다.

예를 들어 다음 사고는 Ceph만으로 어렵다.

- 운영자가 실수로 snapshot까지 삭제
- Ceph cluster 전체 설정 손상
- 모든 node가 있는 장소의 전원/화재/침수
- 악성 코드가 모든 mounted path를 암호화

따라서 단계는 나눈다.

### 12.1 1차 목표: 안정적인 shared storage

- Docker-managed volume 대신 CephFS bind mount
- Ceph replica로 node/disk 장애 대응
- CephFS snapshot으로 빠른 rollback

### 12.2 2차 목표: 외부 백업

초기에는 범위 밖으로 둔다. 나중에 다음 중 하나를 검토한다.

- 다른 Docker Infra cluster의 Ceph로 snapshot export
- 외부 S3로 CephFS snapshot export
- 중요한 DB는 DB-native logical backup 병행

Harbor는 계속 image 전용으로 유지한다. 서비스 데이터 백업을 Harbor로 밀어 넣지 않는다.

## 13. Docker Infra UI 설계

### 13.1 Ceph cluster 화면

화면에서 보여줄 항목:

```text
Ceph 상태
  health: HEALTH_OK
  mon quorum: 3/3
  mgr: active + standby
  mds: active + standby
  osd: 6 up / 6 in
  used: 210GB
  available: 174GB
```

### 13.2 Node별 OSD 슬롯 화면

OSD 슬롯 화면은 서버 상태에 따라 다르게 보인다.

독립 서버:

```text
node-dev-1
  상태: 독립 서버
  저장소: local bind mount 사용 가능

  이 서버는 아직 Swarm cluster에 등록되지 않았습니다.
  Ceph OSD slot은 Swarm 등록 후 만들 수 있습니다.

  [Swarm 클러스터에 등록]
```

클러스터 서버:

```text
node-a
  상태: Swarm 서버
  사용 가능 공간: 412GB
  [OSD 슬롯 구성 마법사]

  osd.0 128GB active
  osd.3 64GB active
```

OSD 슬롯 구성 마법사는 다음 순서로 진행한다.

```text
1. 대상 서버 확인
2. 디스크와 여유 공간 검사
3. 슬롯 크기 선택: 64GB / 128GB / 256GB
4. backing 방식 선택: GPT partition 기본, LVM LV 고급 옵션
5. 삭제/변경될 범위와 예약 공간 확인
6. partition 또는 LV 생성
7. ceph-volume prepare/activate
8. CRUSH host bucket과 host failure domain 검증
9. CephFS mount 가능 여부 확인
10. 작업 로그와 결과 저장
```

슬롯 추가 전 preflight:

- free space 확인
- reserve percent 확인
- Swarm 등록 여부와 `swarm_node_id` 확인
- GPT partition 생성 가능 여부 확인
- LVM LV 선택 시에만 VG 여유 공간과 LVM 상태 확인
- loopback file 옵션은 제공하지 않음
- node label 확인
- Ceph network reachability 확인
- CRUSH host bucket에 node가 올바르게 등록되는지 확인

### 13.3 서비스 생성 화면

```text
저장소
  방식: CephFS bind mount
  mount 이름: data
  컨테이너 경로: /app/data
  초기 quota: 20GB
  snapshot 정책: 최근 24개 + 일별 14개
```

### 13.4 서비스 상세 화면

```text
data
  backend: CephFS
  path: /srv/docker-infra/storage/cephfs/services/wiki/mounts/data/current
  quota: 20GB
  used: 3.2GB
  snapshots: 18개
  latest snapshot: snap_20260623_100000_v17
```

## 14. Agent 설계

Agent는 stateful service를 만들 때 다음을 기본으로 제안한다.

```yaml
x-docker-infra:
  storage:
    backend: cephfs
    mounts:
      - name: data
        target: /app/data
        quota: 20GiB
        snapshot_policy: default
```

규칙:

1. DB, Redis, wiki, upload service처럼 상태가 있는 서비스는 CephFS bind mount를 기본 제안한다.
2. Docker-managed volume은 생성하지 않는다. 필요한 저장소는 CephFS 또는 local bind mount로 표현한다.
3. Harbor image backup과 CephFS snapshot을 같은 서비스 버전 이력에 연결한다.
4. DB workload는 snapshot만으로 충분하다고 말하지 않는다. DB-native backup 또는 hook을 같이 제안한다.

Agent가 관여하는 모든 경로에도 같은 규칙을 적용한다.

```text
자동 템플릿 생성
  → 상태 저장 경로를 x-docker-infra.storage.mounts로 표현
  → docker-compose.yaml에는 Docker Infra가 치환할 storage placeholder만 사용
  → top-level volumes는 만들지 않음

서비스 생성/수정/import
  → Agent output을 바로 저장하지 않음
  → Docker Infra storage normalizer가 CephFS/local bind mount로 변환
  → 최종 Compose에 Docker-managed volume이 남으면 저장 실패

서비스 검사/수정/재배포
  → Agent는 CephFS mount 상태, 쓰기 가능 여부, snapshot 정책을 점검
  → Agent는 volume artifact 백업/복원 경로를 호출하지 않음
  → 기존 배포 서비스의 데이터 이동은 자동 처리하지 않음
```

초등학생에게 설명하면, Agent도 같은 규칙을 지키는 도우미다. Agent가 새 공책 양식을 만들거나, 서비스를 고치거나, 배포 후 확인을 하더라도 "데이터는 공용 책장 칸에 둔다"는 약속을 바꾸면 안 된다.

Agent가 기존 배포 서비스의 데이터를 옮겨야 하는 경우는 별도 작업으로만 다룬다. 일반 서비스 생성, 수정, 검증, 롤백 흐름에 몰래 포함하지 않는다.

## 15. 데이터 모델 초안

### 15.1 `ceph_clusters`

| 컬럼 | 설명 |
|---|---|
| id | cluster ID |
| fsid | Ceph fsid |
| status | pending, bootstrapping, running, degraded, failed |
| ceph_image | `quay.io/ceph/ceph:vXX` |
| public_network | Ceph public network |
| cluster_network | 선택 storage network |
| metadata | bootstrap 설정 |

### 15.2 `ceph_nodes`

| 컬럼 | 설명 |
|---|---|
| id | row ID |
| node_id | Docker Infra node ID |
| hostname | Ceph host name |
| ip_address | Ceph daemon IP |
| roles | mon, mgr, mds, osd 가능 여부 |
| status | ready, warning, failed |

### 15.3 `ceph_osd_slots`

| 컬럼 | 설명 |
|---|---|
| id | slot ID |
| cluster_id | Ceph cluster |
| node_id | node |
| slot_name | node-a-slot-0 |
| size_gb | 64, 128, 256 |
| backing_type | gpt_partition, lvm_lv |
| backing_path | `/dev/disk/by-partuuid/...` 또는 LV path |
| device_stable_id | PARTUUID, LV UUID 등 stable id |
| ceph_device_path | ceph-volume 준비 후 Ceph이 인식한 실제 block path |
| ceph_lvm_artifact | ceph-volume이 내부 LV를 만든 경우 해당 VG/LV 정보 |
| osd_id | Ceph OSD id |
| status | allocated, prepared, running, failed, removed |

### 15.4 `storage_mounts`

| 컬럼 | 설명 |
|---|---|
| id | mount ID |
| service_id | 서비스 ID |
| mount_name | data |
| backend | cephfs |
| host_path | bind mount path |
| container_path | container target |
| quota_bytes | 선택 quota |
| snapshot_policy_id | snapshot 정책 |

### 15.5 `storage_snapshots`

| 컬럼 | 설명 |
|---|---|
| id | snapshot ID |
| mount_id | mount |
| compose_version_id | 연결된 Compose version |
| snapshot_name | CephFS snapshot name |
| status | creating, ready, failed, deleted |
| created_at | 생성 시간 |
| metadata | hook 결과, service version |

## 16. 구현 단계

### Phase 0: 문서와 PoC 결정

- 기존 volume artifact 백업 경로는 제품 기능에서 제거한다.
- Harbor는 image 전용으로 유지한다.
- 클러스터 서비스의 장기 storage 기본값을 CephFS bind mount로 확정한다.
- 독립 서버는 Ceph 없이 local bind mount로 계속 동작하는 예외 모드로 남긴다.

### Phase 1: Ceph preflight

- 서버를 독립 서버와 Swarm 서버로 구분한다.
- node별 Docker, kernel module, network, free space 확인
- host network 사용 가능 여부 확인
- GPT partition slot 생성 가능 여부 확인
- LVM LV slot은 선택 모드에서만 가능 여부 확인
- loopback file 옵션 없음
- `ceph-volume lvm prepare`가 partition 입력에서 어떤 실제 device artifact를 만드는지 확인
- OSD host가 3개 미만이면 운영 모드 차단
- 3 node 미만이면 개발 모드 경고

### Phase 2: OSD slot allocator

- UI에서 Swarm 등록이 끝난 서버에만 64GB/128GB 슬롯 생성 버튼 노출
- 서버 상세 화면에 OSD 슬롯 구성 마법사 추가
- 기본값으로 GPT partition slot 생성
- 선택 옵션으로 LVM LV 생성
- stable device path 기록
- ceph-volume 준비 후 실제 Ceph block path와 내부 LVM artifact 기록
- reserve percent 강제
- slot 삭제/비활성화 정책 추가

### Phase 3: Dockerized Ceph bootstrap

- mon 3개 생성
- mgr active/standby 생성
- osd slot prepare/activate
- mds active/standby 생성
- CephFS 생성
- `dockerinfra_host_replicated` CRUSH rule 생성
- CephFS data/metadata pool에 host failure domain rule 적용

### Phase 4: CephFS host mount

- 각 node에 `/srv/docker-infra/storage/cephfs` mount
- cephx key 배포
- mount health check
- boot/restart 후 remount 보장

### Phase 5: 서비스 bind mount 전환

- Swarm/Ceph 대상 신규 서비스는 CephFS bind mount 기본값
- 독립 서버 대상 신규 서비스는 local bind mount 기본값
- Docker-managed volume 입력은 저장 전에 bind mount로 변환
- 기존 배포 서비스의 자동 이전 기능은 제공하지 않음
- Compose 저장 시 `x-docker-infra.storage.backend=cephfs` 기록

### Phase 6: snapshot과 rollback

- release 또는 backup checkpoint 시 CephFS snapshot 생성
- 서비스 버전 이력에 snapshot 연결
- rollback 시 snapshot restore-staging 생성
- 검증 후 current 교체

### Phase 7: 운영 안정화

- health alert
- OSD nearfull/full 처리
- node drain 절차
- OSD 교체 절차
- snapshot retention과 cleanup

### Phase 8: 외부 백업

- CephFS snapshot 외부 export 전략 검토
- DB-native backup 병행
- 다른 Docker Infra cluster로 복제 가능성 검토

## 17. 위험 요소와 대응

### 17.1 OSD slot backing 선택 위험

loopback file은 지원하지 않는다. 남는 공간 일부만 Ceph에 주려면 GPT partition 또는 LVM LV로 block device slot을 만들어야 한다.

대응:

- 기본값은 GPT partition slot으로 둔다.
- LVM LV는 선택 옵션으로 둔다.
- ceph-volume lvm을 쓰더라도 Docker Infra의 기본 UX는 "직접 LVM 관리"가 아니라 "partition slot 관리"로 둔다.
- partition/LV 생성 전 대상 디스크, 남은 공간, reserve, wipe 범위를 UI에서 명확히 보여준다.
- slot 생성 후에는 stable device id로 추적한다.
- PoC에서 `lsblk`, `blkid`, `pvs`, `vgs`, `lvs`, `ceph-volume lvm list` 결과를 저장해 실제 device 구성을 검증한다.

### 17.2 Swarm scheduling 위험

OSD가 잘못된 node로 이동하면 안 된다.

대응:

- OSD service는 node label과 slot label로 강하게 고정
- placement 변경 전 Ceph `osd safe-to-destroy` 또는 out 절차 확인
- 임의 scale 금지

### 17.3 CRUSH failure domain 설정 위험

`size=3`이어도 CRUSH rule이 `host` failure domain을 쓰지 않으면 같은 host의 여러 OSD에 같은 object copy가 들어갈 수 있다.

대응:

- Docker Infra가 pool 생성 시 `dockerinfra_host_replicated` rule을 강제로 만든다.
- pool rule이 바뀌면 health warning을 띄운다.
- `ceph osd tree` 기준으로 OSD가 host bucket 아래에 없으면 운영 모드를 차단한다.
- A/B 서버처럼 OSD 슬롯이 많은 node는 전체 저장 비중은 커질 수 있지만, 같은 object의 다중 copy는 같은 host에 배치하지 않는다.

### 17.4 디스크 full 위험

Ceph은 full 상태가 되면 쓰기가 막힐 수 있다.

대응:

- slot 생성 시 host reserve 유지
- Ceph nearfull/backfillfull/full ratio 모니터링
- UI에 "새 서비스 생성 금지" 상태 표시

### 17.5 DB 일관성 위험

CephFS snapshot은 파일시스템 시점 보존이다. DB 내부 일관성까지 자동 보장하지 않는다.

대응:

- PostgreSQL/MySQL 등은 pre-freeze hook 또는 DB-native backup 병행
- snapshot 전 checkpoint/flush
- 복원 테스트 자동화

### 17.6 Ceph 운영 복잡도

Ceph은 단순한 도구가 아니다.

대응:

- Docker Infra UI가 "해야 할 작업"만 노출한다.
- ceph CLI를 직접 몰라도 되게 한다.
- 위험한 기능은 고급 모드로 숨긴다.
- 3 node 미만 운영은 계속 경고한다.

### 17.7 독립 서버 데이터 고립 위험

독립 서버를 Ceph 없이 유지하면 단순성은 좋아진다. 하지만 데이터가 한 서버에만 남는다는 위험도 그대로 남는다.

대응:

- 독립 서버 화면에는 "공유 저장소 보호 없음"을 명확히 표시한다.
- 독립 서버에서 만든 local bind mount 서비스는 다른 서버로 자동 이동하지 않는다.
- Swarm 등록 후 CephFS로 옮기려면 운영자가 직접 백업/재배포하거나 별도 Codex agent 작업으로 처리한다.
- 독립 서버는 Ceph 운영 상태에 영향을 주지 않게 하고, Ceph OSD slot 대상 목록에서도 기본 제외한다.

## 18. 검증 계획

### 18.1 4 node / 128GB partition slot 배치 PoC

- A/B/C/D node 구성
- A/B는 128GB partition slot 2-3개
- C/D는 128GB partition slot 1개
- `lsblk`, `blkid`로 PARTUUID와 slot 크기 확인
- `pvs`, `vgs`, `lvs`로 ceph-volume 준비 후 내부 LVM artifact 생성 여부 확인
- `ceph-volume lvm list`로 OSD ID와 실제 block path 확인
- mon 3, mgr 2, mds 2
- CephFS mount
- 간단한 nginx/upload service bind mount
- `ceph osd tree`에서 모든 OSD가 host bucket 아래에 있는지 확인
- CRUSH rule failure domain이 host인지 확인
- sample object/PG replica가 같은 host에 중복 배치되지 않는지 확인
- node 1대 중지 후 read/write 확인

### 18.2 3 node / 128GB LVM 선택 PoC

- 각 node 128GB LV OSD 1개
- PostgreSQL service bind mount
- checkpoint hook snapshot
- rollback 검증
- OSD 하나 down 후 recovery 확인

### 18.3 Docker-managed volume 차단/변환 검증

- 신규 서비스 생성 초안에 Docker-managed volume을 넣는다.
- Swarm/Ceph 대상에서는 CephFS bind mount로 변환되는지 확인한다.
- 독립 서버 대상에서는 local bind mount로 변환되는지 확인한다.
- 저장된 Compose에 top-level `volumes:`가 남지 않는지 확인한다.
- 기존 배포 서비스가 자동 이전 대상에 들어가지 않는지 확인한다.

### 18.4 snapshot 효율 검증

- 큰 파일 생성
- snapshot 1 생성
- 일부만 수정
- snapshot 2 생성
- Ceph 사용량 증가량 확인

목표는 Docker image layer와 완전히 같은 숫자를 만드는 것이 아니다. 목표는 "서비스 데이터 전체를 매번 다시 묶는 방식"보다 훨씬 덜 증가하는지 확인하는 것이다.

### 18.5 독립 서버와 Swarm 전환 검증

- 서버를 등록한 직후 독립 서버로 표시되는지 확인
- 독립 서버에서 local bind mount 서비스 생성 가능 여부 확인
- 독립 서버 화면에 OSD 슬롯 구성 버튼이 숨겨지는지 확인
- Swarm cluster 등록 후 `swarm_node_id`가 기록되는지 확인
- Swarm 등록 완료 후 OSD 슬롯 구성 마법사가 표시되는지 확인
- 마법사에서 GPT partition slot 생성 전 plan이 표시되는지 확인
- slot activate 후 CRUSH host rule이 host failure domain을 쓰는지 확인

## 19. 결론

이제 장기 방향은 다음으로 정리한다.

1. Harbor는 image 전용으로 유지한다.
2. 기존 volume artifact 백업 경로는 제품 기능에서 제거한다.
3. Docker Infra가 생성/관리하는 서비스는 Docker-managed volume을 만들지 않는다.
4. Ceph은 Docker container로 실행한다.
5. Docker Infra는 64GB/128GB OSD 슬롯을 만들어 Ceph 용량을 제한한다.
6. Swarm은 Ceph daemon container lifecycle을 관리한다.
7. 실제 데이터 복제, snapshot, 장애 대응은 Ceph이 담당한다.
8. 독립 서버는 Ceph 없이 local bind mount로 계속 운영할 수 있게 남긴다.
9. OSD 슬롯은 Swarm cluster 등록이 끝난 서버에서만 구성한다.

핵심은 "Ceph을 크게 운영하는 제품"을 만드는 것이 아니다. Docker Infra가 Ceph의 복잡한 부분을 감추고, 미니PC 여러 대에서도 쓸 수 있는 작은 Ceph storage appliance처럼 제공하는 것이다.
