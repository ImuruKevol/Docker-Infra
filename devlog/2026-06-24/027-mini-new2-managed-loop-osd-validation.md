# mini-new2 managed loop OSD 3개 생성 오류 보정

## 사용자 요청

mini-new2 서버를 대상으로 OSD 슬롯 3개 생성을 브라우저에서 검증하고, `ceph_osd_slots_backing_type_check` 제약 오류와 이후 생성 실패를 수정해 달라는 요청.

## 변경 파일

- `src/model/db/migrations/025_ceph_osd_managed_loop_check.sql`
- `src/model/db/migrations/025_ceph_osd_managed_loop_check.down.sql`
- `src/model/struct/local_command_catalog.py`
- `src/model/struct/storage_ceph_osd.py`
- `src/model/struct/storage_ceph_osd_plan.py`
- `src/model/struct/storage_ceph_volume.py`
- `tests/api/test_migration_schema.py`
- `tests/api/test_storage_models.py`

## 작업 내용

- 실제 DB의 `ceph_osd_slots_backing_type_check`에 `managed_loop`가 누락된 상태를 보정하는 migration을 추가하고 적용했다.
- managed loop OSD 생성 시 raw 파일을 직접 `ceph-volume`에 넘기지 않고, loop 위에 PV/VG/LV를 만든 뒤 LVM LV를 `ceph-volume lvm prepare` 대상으로 사용하도록 변경했다.
- `ceph-volume lvm activate --no-systemd --no-tmpfs --all`을 슬롯 생성 단계에서 실행해 host OSD 디렉터리와 keyring을 materialize하도록 했다.
- Swarm service는 privileged block device 접근이 불가능해 OSD daemon만 대상 노드에서 `docker run -d --privileged --restart unless-stopped` 컨테이너로 실행하도록 변경했다.
- prepare 결과의 LVM artifact와 OSD FSID를 파싱해 `ceph_osd_slots`에 저장하도록 `storage_ceph_volume.py`를 추가했다.

## 확인 결과

- `/opt/conda/envs/docker-infra/bin/python -m py_compile ...` 통과.
- `/opt/conda/envs/docker-infra/bin/python -m unittest tests.api.test_migration_schema tests.api.test_storage_models` 통과.
- WIZ build 성공.
- 브라우저에서 `mini-new2` 대상 슬롯 개수 3개로 생성 실행: API `code=200`, operation `succeeded`, `OSD 슬롯 3개 구성을 완료했습니다.`
- `mini-new2`에서 `docker ps` 기준 `docker-infra-ceph-osd-0/1/2-mini-new2` 컨테이너 3개 Up 확인.
- Ceph 상태에서 `3 osds: 3 up, 3 in` 확인.

## 남은 리스크

- Ceph health는 `mon insecure global_id reclaim`, `msgr2 미활성`, pool application 미설정 경고가 남아 있다.
- 현재 3개 OSD가 모두 `mini-new2` 단일 host에 있어 host failure domain 관점의 운영 분산은 아직 충족하지 않는다.
