# CephFS Storage 작업 지시서 구현 가능성 검토

## 1. 결론

작업 지시서대로 구현하면 Docker Infra의 storage 방향을 CephFS bind mount 중심으로 정리하는 것은 가능하다. 현재 코드에도 이미 활용할 수 있는 기반이 있다.

- 서버는 `swarm_node_id` 유무로 독립 서버와 Swarm 서버를 구분할 수 있다.
- 서비스 생성, 배포, 릴리즈, 롤백, 삭제가 Struct mixin으로 나뉘어 있어 storage 로직을 끼워 넣을 위치가 있다.
- `operation_logs` 기반 작업 로그가 있어 Ceph bootstrap, OSD slot 생성, snapshot, restore 같은 긴 작업을 기록할 수 있다.
- 기존 Docker-managed volume backup/이전 코드가 있어 제거 대상과 충돌 지점을 식별할 수 있다.

하지만 "작업 지시서 12개만 그대로 구현하면 운영 안정성까지 모두 보완된다"고 보기는 어렵다.

정확한 판정은 다음이다.

```text
구현 가능성: 가능
제품 구조 정리 가능성: 가능
운영 안정성 보장: 추가 기반 작업 없이는 부족
권장 방식: 현재 작업 지시서 + 선행 보강 작업을 함께 진행
```

쉬운 말로 하면, 설계는 방향이 맞다. 다만 집을 짓기 전에 수도관, 전기 차단기, 안전 잠금장치를 먼저 잡아야 한다. CephFS 기능만 화면에 붙이면 처음에는 동작할 수 있지만, 장애나 삭제/복원 상황에서 위험해질 수 있다.

## 2. 현재 코드와 잘 맞는 부분

### 2.1 독립 서버와 Swarm 서버 분기

`src/model/struct/services.py`, `src/model/struct/services_status.py`, `src/app/page.servers/view.ts`는 이미 `swarm_node_id`를 기준으로 Compose/Swarm 또는 독립 서버/클러스터 서버를 구분한다.

따라서 작업 지시서의 "독립 서버는 local bind mount, Swarm 서버는 CephFS 후보"라는 방향은 현재 구조와 잘 맞는다.

보완할 점:

- 이 기준을 storage domain에서 공식 계약으로 선언해야 한다.
- UI 문구만 바꾸는 것이 아니라 API 응답에도 `server_mode`, `storage_capability` 같은 명시 필드를 추가하는 것이 좋다.

### 2.2 Operation log 구조

`src/model/struct/operations.py`는 긴 작업의 상태, 출력, metadata를 저장한다. Ceph preflight, OSD prepare, mount ensure, snapshot restore 같은 작업은 이 구조를 재사용할 수 있다.

보완할 점:

- destructive 작업에는 `plan_id`, `confirmed_at`, `confirmed_by`, `lock_key`가 필요하다.
- 같은 node에 OSD slot 생성 작업이 동시에 2개 실행되지 않도록 operation lock이 필요하다.

### 2.3 서비스 lifecycle 분리

현재 서비스는 생성, 배포, 릴리즈, 롤백, 삭제가 파일별로 나뉘어 있다.

- `services.py`: 생성과 DB 저장
- `services_deploy.py`: 배포
- `services_release.py`: Compose version 릴리즈
- `services_rollback.py`: Compose/image/volume rollback
- `services_delete.py`: 서비스 삭제

이 구조는 CephFS mount, snapshot, rollback을 단계별로 넣기 좋다.

보완할 점:

- storage 처리를 각 파일에 직접 흩뿌리면 나중에 유지보수가 어려워진다.
- `storage_mounts`, `storage_snapshots` Struct를 중심에 두고 서비스 lifecycle은 그 API만 호출하는 형태가 좋다.

## 3. 현재 작업 지시서만으로 부족한 부분

### 3.1 Storage 상태 기계가 필요하다

문서에는 `ceph_clusters`, `ceph_osd_slots`, `storage_mounts`, `storage_snapshots` 테이블이 있다. 하지만 운영 안정성을 위해서는 각 row의 상태 전이가 더 구체적이어야 한다.

필요한 예:

```text
ceph_osd_slots
  planned → allocated → prepared → activating → running
  running → out_requested → out → removing → removed
  failed → repair_required

storage_snapshots
  requested → creating → ready
  ready → restore_planned → restore_staging → restored
  failed → cleanup_required
```

이 상태 전이가 없으면 UI는 단순히 성공/실패만 보게 된다. 실제 운영에서는 "중간에 실패했는데 어디까지 진행됐는지"가 가장 중요하다.

### 3.2 Ceph 명령 실행 계층이 아직 없다

현재 `local_command_catalog.py`에는 Docker/Swarm/service 명령은 있지만 Ceph 전용 명령 catalog는 없다.

추가가 필요한 명령 범위:

- Ceph image pull/version 확인
- mon/mgr/mds/osd container 실행
- `ceph-volume prepare/activate`
- `ceph osd tree`
- `ceph osd crush rule dump`
- CephFS mount 확인
- snapshot create/list/restore

이 계층은 단순 command 추가가 아니다. secret redaction, timeout, retry, idempotency, stdout/stderr 저장 정책까지 같이 정해야 한다.

### 3.3 디스크 작업은 별도 안전장치가 필요하다

OSD slot 생성은 partition 또는 LV를 만드는 작업이다. 이 작업은 실패하면 되돌리기 어렵다.

작업 지시서에는 plan 후 실행이 들어가 있지만, 운영 안전성을 위해 다음이 더 필요하다.

- node별 storage operation lock
- 대상 disk allowlist 또는 explicit 선택
- wipe 범위 표시
- 최소 reserve 공간 강제
- `lsblk`, `blkid`, `parted`, `ceph-volume list` 결과 저장
- 실패 시 `repair_required` 상태 기록
- 동일 disk에 중복 slot 생성 방지

### 3.4 서비스 삭제 흐름이 위험해질 수 있다

`services_delete.py`는 Compose 독립 서버 삭제 시 `docker compose down --volumes`를 사용하고, Swarm 서비스 삭제 시 stack volume remove도 수행한다.

CephFS bind mount로 전환하면 bind mount path는 Docker volume이 아니므로 직접 삭제되지는 않는다. 하지만 다음 정책을 명확히 해야 한다.

- 서비스 삭제와 CephFS 데이터 삭제는 분리한다.
- 기본 삭제는 서비스 실행물만 제거하고 storage path는 보존한다.
- storage path 삭제는 별도 destructive plan으로만 실행한다.
- 기존 Docker-managed volume 삭제/복원 정책은 제품 기능에서 제거하고, CephFS mount에는 적용하지 않는다.

이 부분을 먼저 정리하지 않으면 사용자가 서비스를 지웠을 때 데이터가 남는지 없어지는지 예측하기 어렵다.

### 3.5 릴리즈와 snapshot 연결은 현재 구현보다 더 커진다

`services_release.py`의 `include_snapshots`는 현재 metadata와 operation message 수준이다. CephFS snapshot을 실제로 만들려면 release가 단순 DB insert로 끝나면 안 된다.

권장 구조:

```text
release 요청
  → compose version 저장
  → storage snapshot operation 생성
  → snapshot 생성 성공/실패 기록
  → compose version metadata에 snapshot 목록 연결
```

snapshot 실패 시에도 Compose release 자체를 실패로 볼지, release는 성공하고 storage snapshot만 warning으로 둘지 정책을 정해야 한다.

### 3.6 Rollback은 두 단계 복원으로 바뀌어야 한다

현재 `services_rollback.py`는 Compose를 먼저 쓰고, 기존 volume artifact 복원을 시도할 수 있다. CephFS snapshot restore에서는 이 순서가 위험하므로 기존 volume artifact 복원 경로를 제거해야 한다.

권장 구조:

```text
rollback plan
  → 서비스 중지 필요 여부 계산
  → restore-staging 생성
  → 검증
  → current 교체
  → Compose 적용
  → 배포
```

즉 rollback은 "파일 하나 되돌리기"가 아니라 "서비스 실행 상태와 데이터 current를 함께 바꾸는 transaction 비슷한 작업"으로 봐야 한다.

### 3.7 자동 백업 scheduler는 바로 교체하면 안 된다

`service_image_backup_scheduler.py`는 image snapshot과 기존 volume backup을 함께 실행한다. CephFS snapshot으로 바꿀 때는 다음을 분리해야 한다.

- Harbor image backup은 계속 Harbor 기준으로 유지
- 기존 volume artifact backup은 제품 기능에서 제거
- CephFS snapshot은 Harbor 실행 여부와 무관하게 실행 가능해야 함
- 정책 UI는 `/system/backup`과 `/storage/policy`로 분리

이 분리를 하지 않으면 "이미지 백업 시스템이 꺼져 있어 storage snapshot도 안 됨" 같은 이상한 의존성이 생길 수 있다.

### 3.8 권한과 UID/GID 정책이 빠져 있다

CephFS bind mount path를 서비스 container에 넣으면 파일 권한 문제가 반드시 생긴다.

필요한 정책:

- mount 생성 시 owner UID/GID 기본값
- container user가 root가 아닐 때 writable 여부 검사
- DB data directory 권한 사전 점검
- snapshot/restore 후 권한 유지
- 파일 브라우저에서 DB path 수정 제한

이 정책이 없으면 storage 자체는 정상이어도 서비스가 `permission denied`로 뜰 수 있다.

## 4. 작업 지시서 보완 권고

현재 12개 작업 지시서는 큰 흐름을 잘 나눈다. 다만 운영 안정성을 위해 아래 작업을 선행 또는 병행 작업으로 추가하는 것이 좋다.

### 4.1 Storage feature flag와 compatibility mode

CephFS 기능을 한 번에 기본값으로 켜지 않는다.

필요 기능:

- `storage.cephfs.enabled`
- `storage.cephfs.default_for_swarm`
- `storage.docker_managed_volume.enabled=false`
- 기존 서비스는 자동 변환하지 않음
- 신규 서비스만 정책에 따라 CephFS 선택

### 4.2 Storage operation lock과 상태 전이

OSD slot 생성, Ceph bootstrap, mount ensure, snapshot restore, Compose volume rewrite는 동시에 실행되면 안 되는 조합이 있다.

필요 기능:

- node 단위 lock
- cluster 단위 lock
- service mount 단위 lock
- operation 취소/실패 후 재시도 정책
- 상태 전이 검증

### 4.3 Ceph command catalog와 secret redaction

Ceph 명령은 local executor와 SSH executor 양쪽에서 실행될 수 있다. command catalog에 넣고, 위험 명령은 destructive로 표시한다.

필요 기능:

- command id 표준화
- timeout 표준화
- secret redaction
- dry-run/plan 가능 명령 분리
- stdout/stderr 최대 길이 제한

### 4.4 Service delete와 storage retention 정책

서비스 삭제와 데이터 삭제를 분리한다.

필요 기능:

- 서비스 삭제 시 storage mount 기본 보존
- storage 삭제는 별도 plan 필요
- snapshot retention과 current 삭제 정책 분리
- 기존 Docker-managed volume 삭제 경로와 CephFS path 삭제 로직 분리

### 4.5 CephFS permission profile

서비스별 mount 생성 시 권한 profile을 둔다.

예:

```text
default: uid=0,gid=0,mode=0755
postgres: uid=999,gid=999,mode=0700
app-data: uid=1000,gid=1000,mode=0755
```

이 profile이 없으면 많은 서비스가 storage path는 있어도 쓰기 실패를 낼 수 있다.

### 4.6 AI/Agent storage 계약

서비스 생성은 UI wizard만으로 끝나지 않는다. AI 초안, 자동 템플릿 생성, 서버 Compose import 보정, `service.ai.verify`, runtime repair도 같은 저장소 정책을 따라야 한다.

필요 기능:

- Agent request context에 `storage_context` 포함
- AI output contract에 `x-docker-infra.storage.mounts` 또는 같은 의미의 `storage.mounts` 포함
- 자동 템플릿 생성 시 `${DOCKER_INFRA_STORAGE_*}` placeholder 사용
- 최종 저장 전 Docker-managed volume을 CephFS/local bind mount로 변환
- Agent prompt에서 volume artifact 백업/복원 제안 금지
- `service.ai.verify`에서 CephFS/local mount health와 쓰기 가능 여부 검사
- AI 초안, 템플릿 초안, runtime repair에 대한 테스트 fixture 추가

이 보강이 없으면 사용자가 화면 wizard에서는 CephFS를 쓰더라도, Agent가 만든 초안이나 수정 Compose가 다시 Docker-managed volume 형태로 되돌아갈 수 있다.

## 5. 최종 판단

작업 지시서대로 구현하면 Docker Infra의 storage 기능을 CephFS 중심으로 크게 정리할 수 있다. 특히 독립 서버를 유지하면서 Swarm 서버에만 Ceph OSD slot을 붙이는 방향은 현재 코드의 `swarm_node_id` 기반 구조와 잘 맞는다.

하지만 운영 안정성까지 보완하려면 다음 순서가 안전하다.

```text
1. feature flag와 storage 상태 모델을 먼저 만든다.
2. 읽기 전용 /storage와 server mode 표시를 붙인다.
3. Ceph command catalog와 operation lock을 만든다.
4. OSD slot wizard를 PoC로 제한해 검증한다.
5. CephFS mount와 service storage metadata를 붙인다.
6. 신규 서비스에만 CephFS bind mount를 연다.
7. release/snapshot/rollback을 storage state machine 위로 옮긴다.
8. 기존 volume artifact 백업/복원 경로를 제거하고 신규/수정/import 경로에서 Docker-managed volume을 차단한다.
9. AI/Agent 초안 생성, 템플릿 생성, runtime repair, service.ai.verify에 같은 storage 계약을 적용한다.
```

따라서 현재 작업 지시서는 방향성 문서로는 충분하다. 다만 실제 개발 착수 전에는 "운영 안정성 보강 작업"을 1차 milestone에 포함해야 한다.

이 보강 없이 곧바로 서비스 생성/롤백/삭제까지 바꾸면, 기능은 붙을 수 있지만 장애 상황에서 복구하기 어려운 상태가 될 가능성이 높다.
