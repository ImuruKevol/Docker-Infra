# local-master OSD daemon allowlist와 prepared 슬롯 재시도 보정

## 원 요청

local-master에 OSD 슬롯을 만들려고 하니 `destructive local command가 allowlist에 없습니다.` 라는 에러가 떴고, 만들다가 중간에 실패한 것 같으니 확인하고 고쳐달라는 요청.

## 변경 파일

- `config/docker_infra.py`
- `src/model/struct/storage_ceph_osd.py`
- `src/model/struct/storage_ceph_osd_retry.py`
- `tests/api/test_storage_models.py`
- `devlog.md`
- `devlog/2026-06-25/001-local-master-osd-allowlist-retry.md`

## 작업 내용

- local-master OSD 생성의 두 번째 단계인 `storage.ceph.osd.daemon.container.run`을 기본 destructive local command allowlist에 추가했다.
- OSD 슬롯 생성이 `prepared` 이후 daemon container 생성 단계에서 실패한 경우, 다음 실행 때 ceph-volume prepare를 반복하지 않고 기존 prepared 슬롯을 daemon container run 단계부터 재시도하도록 보강했다.
- prepared 슬롯 재시도 조회/plan 생성을 `storage_ceph_osd_retry.py`로 분리했다.
- storage 정적 계약 테스트에 새 helper 파일, allowlist 항목, prepared 재시도 경로 검증을 추가했다.

## 확인 결과

- `/opt/conda/envs/docker-infra/bin/python -m unittest tests.api.test_storage_models tests.api.test_migration_schema` 통과.
- WIZ build `main` 성공.
- 브라우저 세션에서 storage API로 local-master `slot_count=1` 재시도 실행 완료.
- 실행 전 local-master `osd-9`는 `prepared` 1개였고, 실행 후 같은 슬롯이 `active` 1개로 전환됐다.
- `docker ps`에서 `docker-infra-ceph-osd-9-local-master` 컨테이너가 실행 중임을 확인했다.
- Ceph CLI에서 `10 osds: 10 up, 10 in` 및 `osd.9 up`을 확인했다.
- Storage 화면에서 local-master가 `1/1 active`, `osd-9 active`로 표시되는 것을 확인했다.

## 남은 리스크

- Ceph health는 여전히 `HEALTH_WARN`이다. 현재 남은 warning은 `insecure global_id reclaim` 및 `msgr2` 관련으로 OSD allowlist 문제와는 별도다.
- Ceph CRUSH tree의 host 표시는 런타임 hostname 기준으로 보일 수 있어, 화면의 Docker Infra 서버명과 완전히 같지 않을 수 있다.
