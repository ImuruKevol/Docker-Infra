# Docker Infra CephFS Storage 실제 적용 설계

## 1. 문서 목적

이 문서는 `Dockerized Ceph 기반 Bind Mount Storage 설계`를 실제 Docker Infra 제품에 어떻게 붙일지 정리한다.

앞 문서는 "어떤 저장소 구조를 선택할 것인가"를 설명했다. 이 문서는 "사용자가 어떤 화면에서 무엇을 누르고, Docker Infra 내부 코드는 어디가 바뀌어야 하는가"를 설명한다.

쉽게 말하면 다음과 같다.

```text
앞 문서: 튼튼한 공용 책장을 Ceph으로 만들자.
이 문서: 그 책장을 Docker Infra 화면 어디에 두고, 사용자가 어떻게 칸을 만들고, 서비스가 어떻게 쓰게 할지 정한다.
```

## 2. 최종 사용자 경험 한 줄 결론

사용자는 Ceph CLI를 직접 몰라도 된다.

사용자는 Docker Infra 화면에서 다음 흐름만 따라가면 된다.

```text
1. 서버를 등록한다.
2. 단순하게 쓸 서버는 독립 서버로 둔다.
3. 공유 저장소가 필요한 서버는 Swarm cluster에 등록한다.
4. Swarm 등록이 끝난 서버에서 OSD 슬롯 구성 마법사를 실행한다.
5. 스토리지 화면에서 Ceph cluster 상태를 확인한다.
6. 새 서비스를 만들 때 실행 대상에 맞는 저장소를 선택한다.
7. 서비스 버전을 릴리즈하면 이미지 이력은 Harbor에, 데이터 이력은 CephFS snapshot에 남는다.
8. 문제가 생기면 서비스 상세에서 원하는 시점으로 복원한다.
```

여기서 중요한 분기는 다음이다.

| 서버 상태 | 사용자가 할 수 있는 일 | 저장소 기본값 |
|---|---|---|
| 독립 서버 | Ceph 없이 단일 서버 서비스를 실행한다. | local bind mount |
| Swarm 서버 | Ceph OSD slot을 만들고 공용 저장소에 참여한다. | CephFS bind mount |

독립 서버는 삭제하지 않는다. Docker Infra의 장점 중 하나는 작은 미니PC 한 대도 빠르게 서비스 실행 대상으로 쓸 수 있다는 점이다. 다만 독립 서버는 공용 저장소 보호를 받지 못한다는 점을 화면에서 분명히 보여준다.

초등학생도 이해할 수 있게 말하면 다음과 같다.

- 서버는 집이다.
- OSD slot은 집마다 내어주는 책장 칸이다.
- Ceph은 여러 집의 책장 칸을 모아 큰 공용 책장을 만든다.
- 독립 서버는 혼자 쓰는 책상이다. 간단하지만 책상 위 물건이 다른 집으로 자동 복사되지는 않는다.
- 서비스는 자기 물건을 그 공용 책장에 넣는다.
- snapshot은 책장의 현재 모습을 사진으로 찍어두는 것이다.
- rollback은 예전 사진을 보고 책장을 그때 모습으로 되돌리는 것이다.

## 3. 현재 Docker Infra 구조 요약

현재 프로젝트 기준 주요 화면은 다음과 같다.

| 화면 | 현재 역할 | Ceph 적용 후 역할 |
|---|---|---|
| `/dashboard` | 서버/서비스/도메인/작업 로그 요약 | Ceph health, storage 사용량, 위험 경고 요약 추가 |
| `/services` | 서비스 목록, 상세, 배포, 버전, 롤백 | 서비스별 CephFS mount, snapshot, restore 관리 추가 |
| `/services/create` | 새 서비스 생성 wizard | 대상이 독립 서버면 local bind mount, Swarm/Ceph 대상이면 CephFS bind mount 선택 |
| `/servers` | 서버 등록, 자원, 파일, 터미널, 매크로, Swarm 등록 | 독립 서버/Swarm 서버 상태 표시, Swarm 등록 후 OSD 슬롯 구성 마법사 제공 |
| `/system/backup` | Harbor 기반 백업 시스템 관리 | 이름과 범위를 이미지 백업 중심으로 정리하고, volume 저장은 Storage로 이동 |
| `/operations` | 작업 로그 | Ceph bootstrap, OSD prepare, snapshot, restore 작업 로그 표시 |
| 사이드바 | 주요 메뉴 | `스토리지` 메뉴 추가 |

현재 코드 기준 주요 백엔드 구조는 다음과 같다.

| 파일 | 현재 역할 | 영향 |
|---|---|---|
| `src/model/struct/service_volume_backups.py` | Docker-managed volume artifact 백업 | CephFS 적용 시 제품 기능에서 제거 |
| `src/model/struct/service_image_backups.py` | Compose image 이력 기록 | 유지 |
| `src/model/struct/service_image_backup_scheduler.py` | 컨테이너 스냅샷과 volume 백업 자동 실행 | volume artifact 백업 제거, image backup과 CephFS snapshot 정책 분리 |
| `src/model/struct/services_wizard.py` | 서비스 생성 Compose 렌더링 | storage mount metadata를 받아 bind mount path로 변환 |
| `src/model/struct/services_preflight.py` | 서비스 생성 전 검사 | CephFS mount 가능 여부, quota, snapshot policy 검사 추가 |
| `src/model/struct/services.py` | 서비스 생성과 DB 저장 | storage mount row 생성, Compose metadata 연결 추가 |
| `src/model/struct/services_release.py` | Compose 버전 릴리즈 | CephFS snapshot 생성 연결 |
| `src/model/struct/services_rollback.py` | Compose/image/volume rollback | 기존 volume artifact restore 제거, CephFS snapshot restore로 전환 |
| `src/model/struct/services_deploy.py` | Docker compose/swarm 배포 | 배포 전 host bind path와 CephFS mount 상태 보장 |
| `src/model/struct/nodes*.py` | 서버 등록, SSH, runtime 확인 | OSD slot prepare, Ceph client mount, node label 검증 추가 |
| `src/model/struct/nodes_join.py` | 등록 서버를 Swarm cluster에 join | join 성공 후 OSD 슬롯 구성 마법사 진입 조건 제공 |
| `src/model/struct/compose_rules.py` | compose/swarm 배포 모드와 network 규칙 | 독립 서버 local bind mount와 Swarm CephFS 기본값 분기 |
| `src/model/struct/backup_system*.py` | 내부 Harbor 백업 시스템 | Harbor는 image 전용으로 유지, UI 문구와 정책 분리 |

현재 코드에는 이미 중요한 기준점이 있다. `swarm_node_id`가 있으면 Swarm 서버이고, 없으면 독립 서버로 볼 수 있다. 이 설계는 그 기준을 활용한다.

## 4. 메뉴 구조 변경

### 4.1 사이드바에 `스토리지` 추가

현재 사이드바 고급 메뉴에는 서버, 이미지, 템플릿, 매크로, 작업, 시스템이 있다.

여기에 `스토리지`를 추가한다.

```text
고급 관리
  서버
  스토리지
  이미지
  템플릿
  매크로
  작업
  시스템
```

권장 위치는 `서버` 바로 아래다.

이유:

- 스토리지는 서버 디스크와 직접 연결된다.
- 사용자는 먼저 서버를 등록하고, 다음으로 storage cluster를 만든다.
- 이미지 관리는 Harbor이고, 스토리지 관리는 Ceph이므로 메뉴가 분리되어야 한다.

### 4.2 새 페이지

새 페이지를 만든다.

```text
src/app/page.storage/
  app.json
  view.ts
  view.pug
  view.scss
  api.py
```

URL은 다음으로 둔다.

```text
/storage
```

초기에는 별도 route API를 만들지 않고 page app의 `api.py`에서 `wiz.call`로 시작해도 된다. 기능이 커지면 `/api/storage/<path:path>` route로 분리한다.

## 5. `/storage` 화면 설계

`/storage`는 Ceph과 서비스 저장소를 관리하는 중심 화면이다.

화면은 5개 탭으로 나눈다.

```text
스토리지
  개요
  클러스터
  OSD 슬롯
  서비스 저장소
  정책
```

### 5.1 개요 탭

사용자는 이 탭에서 지금 저장소가 건강한지만 보면 된다.

표시 항목:

```text
Storage 상태
  HEALTH_OK / WARNING / ERROR

가용 용량
  raw: 1024GB
  replica 후 예상: 341GB
  운영 권장 사용 가능: 238GB

Ceph daemon
  mon: 3/3
  mgr: 1 active + 1 standby
  mds: 1 active + 1 standby
  osd: 8 up / 8 in

위험 경고
  nearfull
  down osd
  host failure domain 미적용
  CephFS mount 누락 node
```

쉬운 설명:

- 초록이면 평소처럼 쓰면 된다.
- 노랑이면 아직 서비스는 돌아가지만 조치가 필요하다.
- 빨강이면 새 서비스 생성이나 복원을 막아야 한다.

필요 API:

```text
storage.load_overview
```

응답 예시:

```json
{
  "cluster": {
    "status": "running",
    "health": "HEALTH_OK",
    "fsid": "..."
  },
  "capacity": {
    "raw_bytes": 1099511627776,
    "usable_bytes": 366503875925,
    "recommended_bytes": 256552713147,
    "used_bytes": 128849018880
  },
  "daemons": {
    "mon": {"ready": 3, "wanted": 3},
    "mgr": {"active": 1, "standby": 1},
    "mds": {"active": 1, "standby": 1},
    "osd": {"up": 8, "in": 8, "total": 8}
  },
  "warnings": []
}
```

### 5.2 클러스터 탭

Ceph cluster를 만들고 기본 daemon을 배치하는 곳이다.

처음 화면:

```text
Ceph cluster가 아직 없습니다.

[사전 점검]
[Ceph cluster 만들기]
```

사전 점검 항목:

- 등록 서버가 3대 이상인지
- Docker Swarm이 준비되어 있는지
- host network 사용 가능 여부
- 서버 간 Ceph public network 통신 가능 여부
- 사용할 Ceph image pull 가능 여부
- kernel cephfs client 사용 가능 여부
- `ceph-volume` 실행 가능 여부

cluster 생성 wizard:

```text
1단계: 대상 서버 선택
2단계: 네트워크 확인
3단계: MON/MGR/MDS 배치 확인
4단계: 생성 전 요약
5단계: 실행 로그
```

중요한 UX 원칙:

- 사용자가 MON, MGR, MDS를 깊게 몰라도 되게 한다.
- 기본값은 자동 배치다.
- 고급 모드에서만 daemon 위치를 바꿀 수 있게 한다.

필요 API:

```text
storage.cluster_preflight
storage.cluster_bootstrap
storage.cluster_operation_status
storage.cluster_refresh
storage.cluster_destroy_plan
```

`destroy`는 초기 구현 범위에서 버튼을 숨기고, PoC 이후 고급 위험 작업으로만 둔다.

### 5.3 OSD 슬롯 탭

서버별 저장 공간을 Ceph에 빌려주는 화면이다.

이 탭은 Swarm cluster에 등록된 서버만 OSD slot 대상으로 본다.

독립 서버는 목록에 보일 수는 있지만, 슬롯 추가 버튼은 보여주지 않는다.

```text
node-dev-1
  상태: 독립 서버
  OSD 슬롯: 생성 불가

  이 서버는 Ceph 없이 local bind mount로 서비스를 실행할 수 있습니다.
  공용 저장소에 참여하려면 먼저 Swarm cluster에 등록하세요.

  [Swarm 등록으로 이동]
```

표시 예시:

```text
A server
  상태: Swarm 서버
  디스크: 512GB
  예약 공간: 128GB
  OSD 슬롯:
    osd.0 128GB GPT partition active
    osd.1 128GB GPT partition active
    osd.2 128GB GPT partition active

B server
  디스크: 512GB
  OSD 슬롯:
    osd.3 128GB active
    osd.4 128GB active
    osd.5 128GB active

C server
  디스크: 256GB
  OSD 슬롯:
    osd.6 128GB active

D server
  디스크: 256GB
  OSD 슬롯:
    osd.7 128GB active
```

슬롯 추가 버튼:

```text
[OSD 슬롯 구성 마법사]
```

기본 방식은 GPT partition이다.

LVM LV는 고급 옵션으로만 제공한다.

```text
고급 옵션
  [ ] 이 서버에서 LVM LV slot 사용을 허용합니다.
```

loopback file 옵션은 제공하지 않는다.

OSD 슬롯 구성 마법사 단계:

```text
1. 대상 서버 확인
   - Swarm 등록 여부 확인
   - swarm_node_id 확인
   - Ceph cluster 참여 가능 상태 확인

2. 디스크 스캔
   - 디스크 목록
   - filesystem 사용 중 여부
   - 남은 공간
   - Docker image/cache/log 여유 공간

3. 슬롯 크기 선택
   - 64GB
   - 128GB
   - 256GB

4. backing 방식 선택
   - GPT partition: 기본값
   - LVM LV: 고급 옵션
   - loopback file: 제공하지 않음

5. 작업 plan 확인
   - 새로 만들 partition/LV
   - 남길 예약 공간
   - wipe 또는 format 범위
   - 장애 시 되돌릴 수 없는 항목

6. slot 생성
   - partition 또는 LV 생성
   - stable device id 기록

7. Ceph OSD 준비
   - ceph-volume prepare
   - ceph-volume activate
   - osd id 기록

8. 배치 규칙 검증
   - OSD가 올바른 host bucket 아래에 있는지 확인
   - pool이 host failure domain CRUSH rule을 쓰는지 확인

9. 완료
   - CephFS mount 가능 여부 확인
   - 작업 로그 저장
```

마법사에서 사용자에게 보여줄 plan 예시:

```text
이 작업은 서버 디스크에 새 partition을 만듭니다.
선택한 디스크: /dev/nvme0n1
추가할 슬롯: 128GB
남길 예약 공간: 128GB
추가 후 Ceph raw 용량: +128GB
replica size 3 기준 사용 가능 증가량: 약 +42GB
```

왜 128GB를 추가했는데 42GB만 늘어나는지 쉽게 설명한다.

```text
같은 데이터를 3벌 저장하기 때문에, 책장 128GB를 빌려줘도 실제로 물건을 넣을 수 있는 공간은 약 1/3만 늘어난다.
```

필요 API:

```text
storage.osd_nodes
storage.osd_slot_preflight
storage.osd_slot_create
storage.osd_slot_prepare
storage.osd_slot_activate
storage.osd_slot_out
storage.osd_slot_remove_plan
storage.osd_slot_remove
```

위험 작업은 항상 plan을 먼저 보여준다.

```text
remove_plan → 사용자 확인 → remove
```

### 5.4 서비스 저장소 탭

모든 서비스가 사용하는 CephFS mount를 한 곳에서 보는 화면이다.

목록 컬럼:

| 컬럼 | 설명 |
|---|---|
| 서비스 | 서비스 이름 |
| mount | data, db-data 같은 mount 이름 |
| 컨테이너 경로 | `/app/data`, `/var/lib/postgresql/data` |
| host path | 실제 bind mount 경로 |
| quota | 사용 제한 |
| 사용량 | 현재 사용량 |
| snapshot | snapshot 개수와 최근 시각 |
| 상태 | mounted, warning, error |

행 클릭 시 오른쪽 패널:

```text
서비스: wiki
mount: data
컨테이너 경로: /app/data
host path: /srv/docker-infra/storage/cephfs/services/wiki/mounts/data/current
quota: 20GB
최근 snapshot: snap_20260623_100000_v17

[snapshot 만들기]
[snapshot 목록]
[복원 staging 만들기]
[서비스 상세로 이동]
```

이 탭은 운영자가 "어떤 서비스가 storage를 얼마나 쓰는지" 보는 곳이다.

### 5.5 정책 탭

전체 기본값을 관리한다.

정책 항목:

```text
신규 서비스 기본 저장소
  - 독립 서버: local bind mount
  - Swarm/Ceph 서버: CephFS bind mount
  - Docker-managed volume 생성 금지

기본 snapshot 정책
  - 릴리즈 시 snapshot 생성
  - 수동 snapshot 허용
  - 최근 24개 유지
  - 일별 14개 유지
  - 월별 6개 유지

quota 기본값
  - 일반 data: 20GB
  - DB data: 50GB
  - cache: snapshot 제외 가능

위험 기준
  - Ceph 사용률 70% warning
  - Ceph 사용률 85% critical
  - OSD host 3대 미만이면 운영 모드 차단
```

## 6. `/servers` 화면 변경

현재 `/servers`는 서버 보드, 자원, 서비스 목록, 파일, 터미널을 제공한다.

여기에 `스토리지` 탭을 추가한다.

```text
서버 상세 탭
  개요
  파일
  터미널
  스토리지
```

스토리지 탭의 첫 영역은 서버 모드 카드다.

독립 서버:

```text
서버 모드
  독립 서버

이 서버는 Ceph 없이 local bind mount로 서비스를 실행할 수 있습니다.
공유 저장소 복제와 CephFS snapshot은 사용할 수 없습니다.

[Swarm 클러스터에 등록]
```

Swarm 서버:

```text
서버 모드
  Swarm 서버
  swarm_node_id: xxxxx

이 서버는 Ceph OSD slot을 만들 수 있습니다.

[OSD 슬롯 구성 마법사]
```

서버별 스토리지 탭에서 보여줄 항목:

```text
Ceph 역할
  mon: yes/no
  mgr: yes/no
  mds: yes/no
  osd: 3개

OSD slot
  slot-0 128GB active osd.0
  slot-1 128GB active osd.1

CephFS mount
  /srv/docker-infra/storage/cephfs mounted
  mount type: kernel cephfs
  last checked: 2026-06-23 15:00

사전 점검
  Docker: OK
  Swarm label: OK
  network: OK
  free space: OK
  partition tool: OK
```

서버 상세에서 할 수 있는 작업:

- 이 서버를 Swarm cluster에 등록
- Swarm 등록 후 이 서버에 OSD slot 추가
- 이 서버의 OSD를 out 처리
- CephFS mount 다시 확인
- Ceph client mount 재설정
- Ceph 관련 작업 로그 보기

OSD slot 추가 버튼은 다음 조건을 모두 만족할 때만 활성화한다.

- 서버가 등록되어 있다.
- SSH/Docker 점검이 통과했다.
- 서버가 Swarm cluster에 active 상태로 join되어 있다.
- `swarm_node_id`가 저장되어 있다.
- Ceph cluster가 생성되었거나 bootstrap wizard가 진행 중이다.

독립 서버에서는 버튼 대신 다음 안내를 보여준다.

```text
OSD slot은 Swarm 서버에서만 만들 수 있습니다.
먼저 이 서버를 Swarm cluster에 등록하세요.
```

주의:

서버 등록 해제 시에는 Ceph OSD가 있으면 바로 삭제하면 안 된다.

등록 해제 버튼을 누를 때 다음을 막아야 한다.

```text
이 서버에는 active OSD가 있습니다.
먼저 Storage 화면에서 OSD를 out 처리하고 Ceph가 복구를 완료해야 서버 등록을 해제할 수 있습니다.
```

영향 파일:

- `src/app/page.servers/view.ts`
- `src/app/page.servers/view.pug`
- `src/app/page.servers/api.py`
- `src/model/struct/nodes.py`
- `src/model/struct/nodes_join.py`
- `src/model/struct/nodes_delete.py`
- `src/model/struct/nodes_runtime.py`
- `src/model/struct/nodes_runtime_files.py`
- `src/model/struct/storage_ceph_osd.py`

## 7. `/services/create` 화면 변경

현재 새 서비스 만들기는 다음 흐름이다.

```text
템플릿/AI/직접 작성
→ 서비스 이름
→ 도메인
→ preflight
→ 생성
```

여기에 `저장소` 단계를 추가한다.

권장 흐름:

```text
1. 서비스 초안 선택
2. 서비스 정보
3. 저장소
4. 도메인
5. 점검 및 생성
```

### 7.1 저장소 자동 감지

Compose 초안에 다음이 있으면 storage candidate로 감지한다.

```yaml
volumes:
  - data:/app/data
  - db-data:/var/lib/postgresql/data
```

Docker Infra는 사용자에게 이렇게 보여준다.

```text
이 서비스는 데이터를 저장하는 경로가 있습니다.

data
  컨테이너 경로: /app/data
  추천 방식: 대상 서버가 독립 서버이면 local bind mount, Swarm/Ceph 서버이면 CephFS bind mount

db-data
  컨테이너 경로: /var/lib/postgresql/data
  추천 방식: Swarm/Ceph 서버이면 CephFS bind mount + DB snapshot hook 권장
```

### 7.2 기본 선택값

신규 서비스 기본값은 실행 대상에 따라 달라진다.

```text
독립 서버 대상: local bind mount 사용
Swarm 서버 + Ceph 정상: CephFS bind mount 사용
Swarm 서버 + Ceph 미구성: local bind mount로 시작하거나 Storage 설정으로 이동
```

선택지는 다음처럼 둔다.

| 선택지 | 표시 조건 | 설명 |
|---|---|---|
| CephFS bind mount | 대상 서버가 Swarm 서버이고 Ceph cluster 정상 | 클러스터 서비스 기본값 |
| Local bind mount | 독립 서버, 개발 모드, Ceph 미구성 | 해당 서버에만 저장 |

독립 서버를 대상으로 서비스를 만들 때는 다음 안내를 보여준다.

```text
이 서비스는 독립 서버에 생성됩니다.
데이터는 이 서버의 local path에 저장됩니다.
다른 서버로 서비스를 옮길 때는 운영자가 직접 백업 후 재배포해야 합니다.

[local bind mount로 계속]
[Swarm 등록 후 공유 저장소 사용]
```

Ceph cluster가 없으면 다음 안내를 보여준다.

```text
공유 저장소가 아직 준비되지 않았습니다.
이 서비스는 local bind mount로 만들 수 있지만, 다른 서버로 옮기면 데이터가 같이 이동하지 않습니다.

[스토리지 설정으로 이동]
[local bind mount로 계속]
```

### 7.3 Compose 변환 규칙

사용자가 CephFS bind mount를 선택하면 Compose는 다음처럼 바뀐다.

입력:

```yaml
services:
  app:
    volumes:
      - data:/app/data
volumes:
  data:
```

저장 후:

```yaml
services:
  app:
    volumes:
      - /srv/docker-infra/storage/cephfs/services/<namespace>/mounts/data/current:/app/data
```

top-level `volumes:`의 `data:`는 제거한다.

Docker Infra metadata에는 원래 volume 이름을 남긴다.

```json
{
  "storage": {
    "backend": "cephfs",
    "mounts": [
      {
        "name": "data",
        "original_source": "data",
        "container_path": "/app/data",
        "host_path": "/srv/docker-infra/storage/cephfs/services/wiki/mounts/data/current",
        "quota_bytes": 21474836480,
        "snapshot_policy": "default"
      }
    ]
  }
}
```

### 7.4 Preflight 추가 항목

`services_preflight.py`에 다음 검사를 추가한다.

```text
저장소
  - Ceph cluster 상태가 HEALTH_OK 또는 허용 가능한 WARNING인지
  - 배포 대상 node에 CephFS가 mount 되어 있는지
  - mount path 생성 권한이 있는지
  - quota가 cluster 사용 가능 용량보다 크지 않은지
  - DB 경로라면 snapshot hook 안내가 필요한지
  - Docker-managed volume이 남아 있으면 bind mount 변환이 가능한지
```

점검 결과 예시:

```text
저장소: OK
wiki/data → CephFS bind mount로 생성합니다.
quota 20GB, snapshot 정책 default.
```

### 7.5 영향 파일

- `src/app/page.services.create/view.ts`
- `src/app/page.services.create/view.pug`
- `src/app/page.services.create/api.py`
- `src/model/struct/services_wizard.py`
- `src/model/struct/services_preflight.py`
- `src/model/struct/services.py`
- `src/model/struct/compose_validator.py`
- `src/model/struct/compose_rules.py`
- `src/model/struct/ai_assistant.py`
- `docs/compose-template-standard.md`

## 8. `/services` 상세 화면 변경

서비스 상세 탭에 `저장소`를 추가한다.

현재 탭:

```text
개요
로그
파일
버전
```

변경 후:

```text
개요
저장소
로그
파일
버전
```

### 8.1 저장소 탭

표시 예시:

```text
data
  backend: CephFS
  컨테이너 경로: /app/data
  host path: /srv/docker-infra/storage/cephfs/services/wiki/mounts/data/current
  quota: 20GB
  used: 3.2GB
  snapshots: 18개
  최근 snapshot: snap_20260623_100000_v17

[snapshot 만들기]
[snapshot 목록]
[복원 staging 생성]
[quota 변경]
```

snapshot 목록:

```text
snap_20260623_100000_v17
  연결 버전: Compose v17
  생성 이유: 릴리즈
  상태: ready

snap_20260623_090000_manual
  생성 이유: 수동
  상태: ready
```

### 8.2 릴리즈 modal 변경

현재 릴리즈 modal에는 `Compose만` 또는 `Compose + 스냅샷` 선택이 있다.

변경 방향:

```text
릴리즈에 포함할 항목
  [x] Compose 버전 저장
  [x] CephFS 데이터 snapshot
  [ ] 실행 컨테이너 이미지 snapshot
```

설명:

- Compose 버전은 서비스 설정의 사진이다.
- CephFS snapshot은 서비스 데이터의 사진이다.
- 컨테이너 이미지 snapshot은 컨테이너 파일시스템까지 이미지로 저장하는 고급 기능이다.

Harbor image backup은 계속 유지한다.

### 8.3 롤백 modal 변경

현재 롤백 modal은 image restore와 기존 volume restore를 함께 고려한다.

변경 후:

```text
복원 계획
  Compose: v17로 되돌림
  이미지: Harbor 백업 이미지 2개 반영 가능
  저장소: CephFS snapshot 1개 복원 가능
```

CephFS 적용 후 제품 롤백은 CephFS snapshot만 다룬다. 기존 배포 서비스의 Docker-managed volume 복원은 제품 기능에서 제공하지 않는다.

CephFS 서비스의 저장소 복원은 다음 안전 흐름을 따른다.

```text
1. 서비스 중지
2. 현재 current를 rollback-before-<time>으로 보관
3. 선택 snapshot을 restore-staging으로 준비
4. staging 검증
5. current 교체
6. 서비스 재배포
```

사용자에게는 이렇게 보여준다.

```text
저장소는 바로 덮어쓰지 않습니다.
먼저 복원 준비 영역을 만들고, 문제가 없으면 현재 데이터와 교체합니다.
```

### 8.4 서비스 파일 탭 주의

현재 서비스 파일 탭은 서비스 디렉토리 파일을 보여준다.

CephFS mount path는 서비스 디렉토리 밖에 있다.

따라서 서비스 파일 탭에서 CephFS 데이터까지 마음대로 수정하게 하면 위험하다.

정책:

- 서비스 파일 탭은 기존 Compose와 부가 파일 관리로 유지한다.
- CephFS 데이터 파일 탐색은 `저장소` 탭의 별도 `데이터 파일 보기` 버튼으로 제한한다.
- DB data path는 기본적으로 파일 브라우저 mutate를 막는다.

## 9. `/system/backup` 화면 변경

현재 `/system/backup`은 "서비스 백업 시스템"이라고 표현되어 있다.

Ceph 적용 후에는 역할을 분리해야 한다.

```text
Harbor 백업 시스템
  - 이미지 백업
  - 컨테이너 이미지 snapshot
  - image rollback용 backup_ref

Storage 시스템
  - CephFS bind mount
  - CephFS snapshot
  - 데이터 rollback
```

따라서 `/system/backup` 문구를 다음처럼 바꾼다.

```text
이미지 백업 시스템
```

설명도 바꾼다.

```text
서비스 이미지와 컨테이너 이미지 스냅샷을 내부 Harbor에 보관합니다.
서비스 데이터는 스토리지 메뉴의 CephFS snapshot으로 관리합니다.
```

자동 백업 정책도 나눈다.

| 정책 | 위치 |
|---|---|
| 이미지 backup retention | `/system/backup` |
| CephFS snapshot retention | `/storage/policy` |
| DB-native backup hook | 서비스 저장소 탭 또는 서비스 고급 설정 |

## 10. `/dashboard` 변경

Dashboard 상단에 storage 상태 badge를 추가한다.

```text
Storage HEALTH_OK
```

카드 추가:

```text
스토리지
  Ceph HEALTH_OK
  사용량 120GB / 권장 238GB
  OSD 8 up / 8 in
  snapshot 134개
```

경고 우선순위:

1. Ceph health error
2. OSD down
3. CephFS mount 누락
4. CRUSH rule drift
5. nearfull
6. snapshot cleanup 실패

Dashboard는 상세 작업을 하지 않는다. 문제를 누르면 `/storage`로 이동한다.

## 11. `/operations` 변경

Ceph 관련 operation type을 추가한다.

```text
storage.cluster.preflight
storage.cluster.bootstrap
storage.cluster.refresh
storage.osd.slot.create
storage.osd.slot.prepare
storage.osd.slot.activate
storage.osd.slot.out
storage.osd.slot.remove
storage.cephfs.mount.ensure
storage.mount.create
storage.snapshot.create
storage.snapshot.restore
storage.snapshot.cleanup
storage.compose.volume_rewrite
```

작업 로그에는 사용자가 이해할 수 있는 문구를 남긴다.

나쁜 로그:

```text
ceph osd crush rule create-replicated ...
```

좋은 로그:

```text
복사본이 같은 서버에 몰리지 않도록 host 단위 배치 규칙을 만들었습니다.
```

CLI 원문은 접힌 상세에 둔다.

## 12. 데이터 모델 설계

새 migration을 추가한다.

예상 파일:

```text
src/model/db/migrations/023_ceph_storage.sql
src/model/db/migrations/023_ceph_storage.down.sql
```

### 12.1 `ceph_clusters`

| 컬럼 | 설명 |
|---|---|
| id | cluster ID |
| fsid | Ceph fsid |
| status | pending, bootstrapping, running, degraded, failed |
| health | HEALTH_OK, HEALTH_WARN, HEALTH_ERR |
| ceph_image | Ceph container image |
| public_network | Ceph public network |
| cluster_network | 선택 storage network |
| mount_root | `/srv/docker-infra/storage/cephfs` |
| metadata | bootstrap 설정 |

### 12.2 `ceph_nodes`

| 컬럼 | 설명 |
|---|---|
| id | row ID |
| cluster_id | Ceph cluster |
| node_id | Docker Infra node |
| ceph_hostname | CRUSH host bucket 이름 |
| ip_address | Ceph daemon IP |
| roles | mon, mgr, mds, osd 가능 여부 |
| mount_status | mounted, unmounted, failed |
| status | ready, warning, failed |
| metadata | 마지막 점검 결과 |

### 12.3 `ceph_osd_slots`

| 컬럼 | 설명 |
|---|---|
| id | slot ID |
| cluster_id | Ceph cluster |
| node_id | Docker Infra node |
| slot_name | node-a-slot-0 |
| size_gb | 64, 128, 256 |
| backing_type | gpt_partition, lvm_lv |
| backing_path | `/dev/disk/by-partuuid/...` 또는 LV path |
| device_stable_id | PARTUUID 또는 LV UUID |
| ceph_device_path | Ceph이 인식한 block path |
| ceph_lvm_artifact | 내부 LV artifact 정보 |
| osd_id | Ceph OSD ID |
| osd_fsid | Ceph OSD FSID |
| status | allocated, prepared, active, out, removed, failed |
| metadata | prepare/activate 검증 결과 |

### 12.4 `storage_mounts`

| 컬럼 | 설명 |
|---|---|
| id | mount ID |
| service_id | 서비스 |
| compose_version_id | 생성 당시 Compose version |
| mount_name | data |
| backend | cephfs, local_bind |
| original_source | Compose 초안의 원래 source 이름 |
| host_path | bind mount host path |
| container_path | container target path |
| quota_bytes | quota |
| snapshot_policy_id | snapshot 정책 |
| status | active, warning, failed, deleted |
| metadata | DB hook, restore 상태 |

### 12.5 `storage_snapshots`

| 컬럼 | 설명 |
|---|---|
| id | snapshot ID |
| mount_id | storage mount |
| service_id | 서비스 |
| compose_version_id | 연결 Compose version |
| snapshot_name | CephFS snapshot name |
| snapshot_path | snapshot path |
| source | release, manual, policy, pre_rollback |
| status | creating, ready, restoring, failed, deleted |
| size_bytes | 가능하면 계산한 사용량 |
| metadata | hook 결과, operation ID |

### 12.6 `storage_snapshot_policies`

| 컬럼 | 설명 |
|---|---|
| id | policy ID |
| name | default |
| keep_recent | 최근 N개 |
| keep_daily | 일별 N개 |
| keep_monthly | 월별 N개 |
| db_hook_mode | none, postgres, mysql, custom |
| metadata | 세부 설정 |

## 13. 새 모델 구조

새 model 파일을 추가한다.

```text
src/model/struct/storage.py
src/model/struct/storage_ceph.py
src/model/struct/storage_ceph_cluster.py
src/model/struct/storage_ceph_osd.py
src/model/struct/storage_ceph_mount.py
src/model/struct/storage_mounts.py
src/model/struct/storage_snapshots.py
src/model/struct/storage_snapshot_policies.py
src/model/struct/storage_health.py
```

역할:

| 파일 | 역할 |
|---|---|
| `storage.py` | storage domain 진입점 |
| `storage_ceph.py` | Ceph CLI/container 공통 실행 |
| `storage_ceph_cluster.py` | bootstrap, daemon 배치, health |
| `storage_ceph_osd.py` | OSD slot preflight/create/prepare/activate |
| `storage_ceph_mount.py` | 각 node CephFS mount 보장 |
| `storage_mounts.py` | 서비스 mount DB와 path 생성 |
| `storage_snapshots.py` | snapshot 생성/복원/삭제 |
| `storage_snapshot_policies.py` | retention 정책 |
| `storage_health.py` | dashboard와 warning 계산 |

### 13.1 왜 기존 `backup_system`에 넣지 않는가

기존 `backup_system`은 내부 Harbor 관리다.

CephFS는 단순 백업이 아니라 서비스의 실시간 저장소다.

따라서 분리해야 한다.

```text
backup_system = 이미지 보관 창고 관리
storage = 서비스 데이터가 실제로 사는 땅 관리
```

## 14. API 설계

초기에는 page API로 시작할 수 있다.

```text
src/app/page.storage/api.py
```

기능이 커지면 route로 분리한다.

```text
src/route/api-storage/controller.py
/api/storage/<path:path>
```

초기 `wiz.call` 함수:

| 함수 | 역할 |
|---|---|
| `load` | overview, cluster, nodes, mounts, policies 기본 데이터 |
| `cluster_preflight` | cluster 생성 전 점검 |
| `cluster_bootstrap` | cluster 생성 시작 |
| `cluster_refresh` | health 갱신 |
| `osd_slot_preflight` | 특정 node slot 추가 전 점검 |
| `osd_slot_create` | partition/LV slot 생성 |
| `osd_slot_prepare` | ceph-volume prepare |
| `osd_slot_activate` | OSD container activate |
| `ensure_node_mount` | node CephFS mount 보장 |
| `snapshot_create` | mount snapshot 생성 |
| `snapshot_restore_plan` | 복원 계획 |
| `snapshot_restore` | staging 복원 후 교체 |
| `operation_status` | long-running operation 조회 |

## 15. 서비스 생성 내부 처리 변경

### 15.1 `services_wizard.py`

현재 `render()`는 component volume을 그대로 Compose volume 문자열로 만든다.

변경:

1. 사용자의 storage 선택을 payload로 받는다.
2. CephFS mount 선택이면 host path를 미리 계산한다.
3. Compose `volumes` 항목을 host bind path로 렌더링한다.
4. top-level Docker-managed volume은 제거한다.

payload 예시:

```json
{
  "storage": {
    "backend": "cephfs",
    "mounts": [
      {
        "name": "data",
        "component_key": "app",
        "target": "/app/data",
        "quota_gb": 20,
        "snapshot_policy": "default"
      }
    ]
  }
}
```

### 15.2 `services_preflight.py`

현재 `_check_volumes()`는 volume 이름과 target만 확인한다.

변경:

- Docker-managed volume을 보면 저장 전 bind mount 변환 후보로 표시한다.
- CephFS 선택이면 cluster health와 mount path 생성 가능 여부를 확인한다.
- DB 경로로 보이면 hook 안내를 warning으로 추가한다.

예시:

```text
PostgreSQL 데이터 경로입니다.
파일 snapshot 전 checkpoint hook을 켜는 것을 권장합니다.
```

### 15.3 `services.py`

서비스 생성 시 다음을 함께 저장한다.

- `services.metadata.storage`
- `storage_mounts` row
- 생성된 host path
- 선택한 snapshot policy

서비스 생성 실패 시 만든 directory를 정리해야 한다.

### 15.4 `services_deploy.py`

배포 전 다음을 확인한다.

- target node가 CephFS를 mount했는지
- host path가 존재하는지
- Swarm 배포라면 모든 후보 node에서 같은 path가 보이는지
- path 권한이 container UID/GID와 충돌하지 않는지

배포 실패 시에는 mount row status를 `warning`으로 바꾸고 operation log에 남긴다.

## 16. 서비스 릴리즈와 rollback 변경

### 16.1 `services_release.py`

현재 릴리즈는 Compose version을 만들고, 옵션에 따라 container snapshot backup을 요청한다.

변경:

```text
Compose version 생성
→ storage_mounts 조회
→ mount별 CephFS snapshot 생성
→ storage_snapshots row 연결
→ 필요 시 Harbor image backup/snapshot 요청
```

릴리즈 metadata:

```json
{
  "last_release": {
    "compose_version_id": "...",
    "storage_snapshot_count": 2,
    "image_backup_count": 2
  }
}
```

### 16.2 `services_rollback.py`

현재는 기존 volume artifact restore context를 볼 수 있다.

변경:

- CephFS 서비스는 `storage_snapshots.rollback_context()`를 본다.
- 기존 volume artifact restore context는 제거한다.
- rollback 실행 시 `storage_snapshots.restore_version()`을 호출한다.

전환 후 메시지:

```text
Compose 버전 17 기준으로 되돌림 · 이미지 2개 Harbor 백업 반영 · 저장소 snapshot 1개 복원
```

기존 배포 서비스 메시지:

```text
이 서비스는 기존 Docker-managed volume을 사용합니다.
Docker Infra의 CephFS rollback 기능으로는 복원하지 않습니다.
운영자가 직접 백업 후 재배포하거나 별도 작업으로 수동 이전하세요.
```

## 17. 기존 volume artifact 기능 제거

CephFS 적용 후 기존 volume artifact 백업/복원 코드는 제품 기능에서 제거한다.

이미 배포된 서비스는 자동 이전하지 않는다. 운영자가 직접 백업 후 재배포하거나 별도 Codex agent 작업으로 수동 이전할 수 있다.

### 17.1 제거할 기능

- `service_volume_backups.py` 기반 volume artifact 생성/조회/복원
- 자동 백업 정책의 volume backup 실행
- 서버 등록 시 volume artifact 도구 설치 안내
- rollback modal의 기존 volume restore context
- 기존 volume artifact cleanup 정책

현재:

```text
container snapshot → Harbor
volume artifact → Harbor
```

변경:

```text
container/image backup → Harbor
CephFS mount snapshot → CephFS
```

즉 `service_image_backup_scheduler.py`는 이름부터 장기적으로 맞지 않다.

권장 리팩터링:

```text
service_state_scheduler.py
  - image backup job
  - storage snapshot job
  - retention cleanup job
```

초기에는 파일명을 유지하고 내부에서 storage snapshot을 호출해도 된다. 하지만 최종적으로는 이름을 바꾸는 것이 맞다.

## 18. 기존 배포 서비스 처리 원칙

기존 배포 서비스는 자동 이전 대상이 아니다.

원칙:

```text
1. Docker Infra는 기존 Docker-managed volume 데이터를 자동 복사하지 않는다.
2. 기존 서비스의 volume artifact 복원 기능도 제공하지 않는다.
3. 운영자는 직접 백업 후 재배포할 수 있다.
4. 필요하면 별도 Codex agent 작업으로 수동 이전을 진행한다.
5. 신규 생성/수정/import 경로에서는 Docker-managed volume을 저장 전에 bind mount로 변환한다.
```

서비스 상세에는 다음 안내만 표시한다.

```text
이 서비스는 기존 Docker-managed volume을 사용합니다.
CephFS 기반 snapshot/rollback 대상이 아닙니다.
데이터 보호가 필요하면 직접 백업 후 CephFS 서비스로 재배포하세요.
```

## 19. AI Agent와 템플릿 영향

### 19.1 AI/Agent 공통 storage 계약

AI와 Agent가 만드는 모든 서비스 초안은 같은 storage 계약을 따른다.

적용 범위:

- `/services/create` AI 초안 생성
- Compose 템플릿 AI 초안 생성
- 기존 서비스 AI 검사/수정
- 배포 후 `service.ai.verify`
- runtime repair가 반환하는 수정 Compose
- 서버 Compose import 후 Agent 보정

AI가 stateful service를 만들 때는 다음 metadata를 포함해야 한다.

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

AI가 Docker-managed volume 형태의 Compose를 만들면 Docker Infra가 저장 전에 CephFS 또는 local bind mount로 바꾼다. 최종 저장되는 Compose에는 top-level `volumes:`가 남지 않아야 한다.

AI에게 줄 쉬운 규칙:

```text
업로드 파일, DB 파일, 사용자 데이터는 Docker-managed volume 대신 storage mount로 표시한다.
```

Agent runtime에는 다음 context를 항상 전달한다.

```json
{
  "storage_context": {
    "server_mode": "independent|swarm",
    "default_backend": "local_bind|cephfs",
    "cephfs_health": "unknown|ready|warning|error",
    "mount_root": "/srv/docker-infra/storage/cephfs",
    "docker_managed_volume_allowed": false,
    "volume_artifact_backup_allowed": false
  }
}
```

서비스 AI output 검증 규칙:

1. 상태 저장 경로가 있으면 `x-docker-infra.storage.mounts`가 있어야 한다.
2. Swarm/Ceph 대상이면 `backend: cephfs`를 기본으로 한다.
3. 독립 서버 대상이면 `backend: local_bind`를 기본으로 한다.
4. `services.*.volumes`의 source가 Docker-managed volume 이름이면 저장 전 host path bind mount로 변환한다.
5. Agent가 volume artifact 백업/복원을 제안하면 경고로 바꾸고 실행하지 않는다.
6. Agent가 기존 배포 서비스 데이터 이동을 제안하면 일반 자동 동작이 아니라 별도 수동 작업으로 표시한다.

영향 파일:

- `src/model/struct/ai_assistant.py`
- `src/model/struct/template_ai.py`
- `src/model/struct/ai_agent_actions.py`
- `src/model/struct/codex_runtime.py`
- `src/model/struct/services_wizard.py`
- `src/model/struct/services_preflight.py`
- `src/model/struct/compose_validator.py`
- `src/model/struct/compose_rules.py`
- `docs/service-ai-codex-agent-design.md`
- `docs/compose-template-standard.md`

### 19.2 자동 템플릿 생성

템플릿 README와 compose 표준에 storage block을 추가한다.

템플릿 예시:

```yaml
services:
  app:
    image: example/app:latest
    volumes:
      - ${DOCKER_INFRA_STORAGE_DATA}:/app/data

x-docker-infra:
  storage:
    backend: auto
    mounts:
      - name: data
        target: /app/data
        quota: 20GiB
        snapshot_policy: default
```

규칙:

- `${DOCKER_INFRA_STORAGE_DATA}`는 사용자가 입력하는 값이 아니다.
- 템플릿 렌더러가 실행 대상에 따라 CephFS 또는 local bind mount path로 치환한다.
- 템플릿 AI는 host의 실제 CephFS 절대 경로를 직접 쓰지 않는다.
- 템플릿 AI는 top-level `volumes:`를 만들지 않는다.
- 템플릿 AI는 storage mount 이름, target, quota, snapshot policy만 제안한다.

즉 템플릿은 "여기에 데이터 칸이 필요하다"고 말할 뿐이다. 실제 어느 책장 칸을 쓸지는 Docker Infra가 서비스 생성 시 결정한다.

### 19.3 Agent 서비스 동작

Agent가 서비스와 관련해 수행하는 동작도 storage 계약을 통과해야 한다.

| 동작 | 추가 규칙 |
|---|---|
| 서비스 초안 생성 | storage mount metadata 필수, 최종 Compose 저장 전 bind mount 변환 |
| 서비스 수정 | 기존 CephFS/local mount를 보존하고 임의로 Docker-managed volume으로 되돌리지 않음 |
| `service.ai.verify` | CephFS mount 상태, current path 쓰기 가능 여부, snapshot policy 연결 확인 |
| runtime repair | volume artifact 복원 제안 금지, 필요 시 storage warning으로 반환 |
| 재배포 | storage mount path가 준비되지 않았으면 배포 전 preflight 실패 |
| 롤백 보조 | Compose/image/CephFS snapshot 계획을 설명할 수 있지만 직접 우회 복원하지 않음 |

기존 배포 서비스가 Docker-managed volume을 쓰는 경우 Agent는 다음 중 하나만 할 수 있다.

1. "CephFS snapshot/rollback 대상이 아니다"라는 경고를 표시한다.
2. 운영자가 명시한 별도 작업에서 수동 이전 절차를 제안한다.
3. 일반 서비스 생성/수정/검증 흐름에서는 자동 데이터 이동을 실행하지 않는다.

## 20. 파일 트리와 보안 영향

현재 `component.file.tree`는 서버 파일과 서비스 파일을 다룬다.

CephFS path는 실서비스 데이터이므로 더 조심해야 한다.

정책:

- 기본 파일 트리에서 `/srv/docker-infra/storage/cephfs` 직접 탐색을 제한한다.
- 서비스 저장소 탭에서만 해당 서비스 mount path를 열 수 있다.
- DB mount는 읽기 전용 기본값으로 둔다.
- 삭제/이동/업로드는 고급 확인 modal이 필요하다.

영향 파일:

- `src/model/struct/file_tree.py`
- `src/app/component.file.tree/view.ts`
- `src/route/api-file-tree/controller.py`
- `src/route/api-file-tree-upload/controller.py`

## 21. 설치와 setup 영향

초기 설치 wizard에서 Ceph을 바로 설치하게 만들지는 않는다.

이유:

- Ceph은 최소 3대 서버가 있어야 운영 의미가 있다.
- 설치 첫 화면에서 Ceph까지 강제하면 제품 진입 장벽이 커진다.

초기 설치에서는 다음만 선택하게 한다.

```text
저장소 기본 정책
  - 나중에 Storage 화면에서 구성
  - local bind mount로 시작
```

서버 3대 이상 등록 후 Storage 화면에서 Ceph 구성을 안내한다.

설치 직후 서버 한 대만 쓰는 사용자는 독립 서버 모드로 계속 진행할 수 있다. 이 경우 화면은 다음처럼 설명한다.

```text
현재 구성은 독립 서버 모드입니다.
Ceph 없이 local bind mount로 서비스를 만들 수 있습니다.
나중에 서버를 Swarm cluster에 등록하면 OSD 슬롯 구성 마법사를 사용할 수 있습니다.
```

영향 파일:

- `src/model/struct/setup.py`
- `src/app/page.access/*` 또는 installer HTML
- `docs/docker-infra-deployment.md`

## 22. 운영 안전장치

### 22.1 위험 작업은 항상 plan 먼저

바로 실행하면 안 되는 작업:

- OSD slot 생성
- OSD slot 삭제
- OSD out 처리
- Ceph cluster reset
- snapshot 삭제
- snapshot restore
- Docker-managed volume 변환/차단
- 서버 등록 해제

공통 흐름:

```text
plan API
→ 영향 범위 표시
→ 사용자가 이름/문구 입력
→ run API
→ operation log
```

### 22.2 새 서비스 생성 차단 조건

다음이면 CephFS 신규 mount 생성을 막는다.

- Ceph health가 `HEALTH_ERR`
- OSD host가 3대 미만인데 운영 모드
- CephFS mount가 target node에 없음
- 사용률이 critical 이상
- CRUSH rule이 host failure domain이 아님

### 22.3 경고만 하는 조건

다음은 생성은 가능하지만 경고한다.

- Ceph health가 `HEALTH_WARN`
- 사용률 warning 이상
- MDS standby 없음
- snapshot cleanup이 최근 실패
- DB hook 미설정

## 23. 단계별 구현 계획

### Phase 1: 읽기 전용 Storage 화면

목표:

- `/storage` 페이지 추가
- 사이드바 메뉴 추가
- Ceph cluster가 없으면 준비 안내 표시
- DB schema와 model skeleton 추가

작업:

- `page.storage` 생성
- `storage.py`, `storage_health.py` 추가
- migration `023_ceph_storage.sql` 추가
- `/dashboard`에 storage badge 자리만 추가
- `/servers`에서 독립 서버와 Swarm 서버 상태 표시 기준 정리

완료 기준:

- 기존 기능 영향 없이 `/storage`가 열린다.
- cluster 미구성 상태를 정상 표시한다.
- `swarm_node_id`가 없는 서버는 독립 서버로 표시된다.

### Phase 2: Ceph preflight와 cluster bootstrap PoC

목표:

- 서버 3대 기준 cluster 생성 사전 점검
- mon/mgr/mds container bootstrap operation 기록

작업:

- `storage_ceph_cluster.py`
- local command catalog에 Ceph 명령 추가
- operation log streaming 연결
- Swarm 등록된 서버만 Ceph 대상 node 후보로 표시

완료 기준:

- 사전 점검 결과가 화면에 표시된다.
- bootstrap 작업 로그가 `/operations`에 남는다.
- 독립 서버는 Ceph preflight 대상에서 제외되며 Swarm 등록 안내를 보여준다.

### Phase 3: Swarm 서버 OSD slot 구성 마법사

목표:

- node별 128GB GPT partition slot 생성
- ceph-volume prepare/activate 검증
- CRUSH host rule 적용 확인
- `/servers` 상세에서 Swarm 등록 후 OSD slot 생성까지 이어지는 wizard 제공

작업:

- `storage_ceph_osd.py`
- `/storage/osd-slots` UI
- `/servers/{node}/storage` 탭
- `/servers` Swarm 등록 완료 후 "OSD 슬롯 구성" CTA 노출
- OSD slot create plan API 추가

완료 기준:

- A/B/C/D 예시 구조에서 A/B 2-3개, C/D 1개 slot 생성 가능
- 같은 object replica가 같은 host에 몰리지 않는지 검증 결과 표시
- 독립 서버에서는 OSD slot 버튼이 비활성화되고 Swarm 등록 안내만 표시
- Swarm 등록 서버에서는 마법사에서 plan 확인 후 slot 생성 가능

### Phase 4: CephFS mount와 service bind mount

목표:

- 모든 node에 `/srv/docker-infra/storage/cephfs` mount
- Swarm/Ceph 대상 신규 서비스 생성에서 CephFS bind mount 사용
- 독립 서버 대상 신규 서비스는 local bind mount 기본값 유지

작업:

- `storage_ceph_mount.py`
- `storage_mounts.py`
- `services_wizard.py` storage payload 반영
- `services_preflight.py` storage 검사
- `services.py` storage_mount row 생성
- `services_deploy.py` mount 보장

완료 기준:

- 신규 서비스가 Docker-managed volume 없이 CephFS host path를 bind mount로 사용한다.
- 독립 서버 대상 서비스는 Ceph 상태와 무관하게 local bind mount로 생성할 수 있다.

### Phase 5: snapshot과 rollback

목표:

- 서비스 릴리즈 시 CephFS snapshot 생성
- 서비스 rollback 시 snapshot restore 가능

작업:

- `storage_snapshots.py`
- `services_release.py` 연동
- `services_rollback.py` 연동
- `/services/{id}/storage` 탭

완료 기준:

- 파일 수정 후 snapshot 생성, rollback으로 이전 내용 복원이 가능하다.

### Phase 6: 기존 volume 경로 제거

목표:

- Docker-managed volume artifact 백업/복원 경로 제거
- 신규/수정/import Compose 저장 전 bind mount 변환 강제
- 기존 배포 서비스는 자동 이전 대상에서 제외

작업:

- `service_volume_backups.py` 제품 호출 제거
- rollback modal의 volume artifact restore context 제거
- scheduler의 volume artifact backup 실행 제거
- 서비스 상세에 기존 배포 서비스 안내 문구 추가

완료 기준:

- 신규 생성/수정/import 경로에서 Docker-managed volume이 저장되지 않는다.
- 기존 배포 서비스는 CephFS snapshot/rollback 대상이 아님을 표시한다.

### Phase 7: 자동 정책 정리

목표:

- 기존 자동 백업 정책에서 volume artifact 경로 제거
- CephFS snapshot retention 적용

작업:

- `service_image_backup_scheduler.py` 조정
- `service_image_backup_cleanup.py`에서 volume artifact cleanup 경로 제거
- `backup_system_policy_defaults.py` 문구/정책 분리
- `/system/backup` UI 문구 변경
- `/storage/policy` 구현

완료 기준:

- 자동 실행 시 image backup은 Harbor로, volume state는 CephFS snapshot으로 남는다.

## 24. 구현 영향 파일 전체 목록

### 새로 추가할 가능성이 큰 파일

```text
src/app/page.storage/app.json
src/app/page.storage/view.ts
src/app/page.storage/view.pug
src/app/page.storage/view.scss
src/app/page.storage/api.py
src/model/db/migrations/023_ceph_storage.sql
src/model/db/migrations/023_ceph_storage.down.sql
src/model/struct/storage.py
src/model/struct/storage_ceph.py
src/model/struct/storage_ceph_cluster.py
src/model/struct/storage_ceph_osd.py
src/model/struct/storage_ceph_mount.py
src/model/struct/storage_mounts.py
src/model/struct/storage_snapshots.py
src/model/struct/storage_snapshot_policies.py
src/model/struct/storage_health.py
```

### 수정이 필요한 기존 파일

```text
src/app/component.nav.sidebar/view.ts
src/app/page.dashboard/view.ts
src/app/page.dashboard/view.pug
src/app/page.servers/view.ts
src/app/page.servers/view.pug
src/app/page.servers/api.py
src/app/page.services.create/view.ts
src/app/page.services.create/view.pug
src/app/page.services.create/api.py
src/app/page.services/view.ts
src/app/page.services/view.pug
src/app/page.services/api.py
src/app/page.system/view.ts
src/app/page.system/view.pug
src/app/page.system/api.py
src/model/struct/services.py
src/model/struct/services_wizard.py
src/model/struct/services_preflight.py
src/model/struct/services_deploy.py
src/model/struct/services_release.py
src/model/struct/services_rollback.py
src/model/struct/services_delete.py
src/model/struct/services_update.py
src/model/struct/service_volume_backups.py
src/model/struct/service_image_backup_scheduler.py
src/model/struct/service_image_backup_cleanup.py
src/model/struct/backup_system_policy_defaults.py
src/model/struct/nodes.py
src/model/struct/nodes_delete.py
src/model/struct/nodes_join.py
src/model/struct/nodes_runtime.py
src/model/struct/file_tree.py
src/model/struct/compose_validator.py
src/model/struct/compose_rules.py
src/model/struct/ai_assistant.py
docs/api/openapi.json
docs/compose-template-standard.md
docs/docker-infra-deployment.md
docs/docker-infra-development-todo.md
```

### 삭제하거나 제품 호출에서 제거할 파일

```text
src/model/struct/service_volume_backups.py
src/model/struct/service_volume_migration.py
```

## 25. 검증 계획

### 25.1 UI 검증

- `/storage` 미구성 상태 표시
- Ceph preflight 결과 표시
- OSD slot 추가 plan 표시
- 서비스 생성 저장소 단계 표시
- 서비스 상세 저장소 탭 표시
- rollback modal에서 CephFS snapshot 표시

### 25.2 API 검증

- storage schema migration
- cluster preflight
- OSD slot preflight
- storage mount create
- snapshot create
- snapshot restore plan
- Docker-managed volume 차단/변환 검사

### 25.3 실제 동작 검증

4 node 예시:

```text
A: 128GB slot 3개
B: 128GB slot 3개
C: 128GB slot 1개
D: 128GB slot 1개
```

검증:

- `ceph osd tree`에서 host bucket 확인
- `dockerinfra_host_replicated` rule 확인
- sample object/PG replica가 같은 host에 중복 배치되지 않는지 확인
- CephFS mount path가 모든 node에서 같은지 확인
- 서비스 bind mount read/write 확인
- snapshot 생성 후 일부 파일 수정
- rollback 후 파일 내용 복원 확인

## 26. 최종 정리

Docker Infra에 CephFS storage를 붙이는 핵심은 새 기능을 하나 추가하는 수준이 아니다.

다음 3가지를 제품 흐름 전체에 녹여야 한다.

```text
1. 독립 서버는 Ceph 없이 local bind mount로 단순하게 실행한다.
2. Swarm 서버는 OSD slot을 제공하고 Ceph 공용 저장소에 참여한다.
3. Docker Infra가 생성/관리하는 서비스는 Docker-managed volume 대신 bind mount를 쓴다.
4. 버전 이력은 Compose + Harbor image + CephFS snapshot을 함께 본다.
```

사용자에게는 어렵게 보이면 안 된다.

사용자가 보는 말은 다음 정도면 충분하다.

```text
공유 저장소가 정상입니다.
이 서비스의 data 저장소는 20GB까지 사용할 수 있습니다.
릴리즈 시 데이터 snapshot도 함께 저장됩니다.
문제가 생기면 이 시점으로 되돌릴 수 있습니다.
```

내부적으로는 Ceph, CRUSH, OSD, CephFS, snapshot, mount, quota, operation log가 움직인다. 하지만 화면은 "안전한 공용 저장소를 만들고, 서비스 데이터가 거기에 저장되고, 필요한 시점으로 되돌린다"는 흐름으로 단순하게 유지해야 한다.
