# 023. Ceph 마스터 bootstrap preflight 완화와 MGR/MDS 자동 배치

- 날짜: 2026-06-24
- 리뷰 ID: ejosmmvibdlmlnlspihmlavbexhuwhoi

## 사용자 원본 요청

마스터 노드 설치 및 구성을 눌렀더니 아래 에러 로그가 저장되었어. 아래 에러를 포함해서 mgr, mds까지 자동으로 구성될 수 있도록 해줘. mgr, mds는 컨테이너의 로그나 직접 docker exec 명령어 등을 통해서 지연 실행 형태나 백그라운드 실행 형태로 해서 하면 될 것 같은데 왜 안되니?

```text
system

Ceph preflight 대상 Swarm 서버 1대입니다.

system

Swarm host count: error - Ceph 마스터로 구성할 eligible Swarm host가 없습니다.

system

local-master: failed 실패 항목: Ceph container image, Ceph container runtime, ceph-volume in container
```

## 변경 파일

- `config/docker_infra.py`: MGR/MDS metadata keyring 생성 명령을 local executor allowlist에 추가.
- `src/model/struct/local_command_catalog.py`: 기본 Ceph 이미지를 `quay.io/ceph/ceph:v19.2.4`로 고정하고, MON 응답 대기 후 MGR/MDS keyring을 생성하는 `storage.ceph.master.metadata.ensure` 명령 추가.
- `src/model/struct/storage_ceph_preflight.py`: master-only bootstrap에서는 OSD 전용 조건과 Ceph image/container/ceph-volume 확인을 warning으로 낮춰 eligible host 판단을 막지 않도록 변경.
- `src/model/struct/storage_ceph_bootstrap.py`: master-only 계획에도 MON/MGR/MDS를 포함하고, MON 배치 후 MGR/MDS keyring 생성 단계를 거쳐 service를 생성하도록 변경.
- `src/model/struct/storage_ceph_runtime.py`: MON 응답 대기 및 MGR/MDS keyring 생성 실행/로그 기록 메서드 추가.
- `src/model/struct/storage_ceph_mount.py`, `src/model/struct/storage_ceph_osd_plan.py`: 기본 Ceph 이미지 tag를 `v19.2.4`로 통일.
- `src/model/db/migrations/024_ceph_default_image.sql`, `src/model/db/migrations/024_ceph_default_image.down.sql`: 이미 적용된 DB schema의 `ceph_clusters.ceph_image` default tag 갱신 migration 추가.
- `tests/api/test_storage_models.py`, `tests/api/test_migration_schema.py`: 신규 명령과 migration 계약 반영.

## 확인 결과

- `/opt/conda/envs/docker-infra/bin/python -m py_compile ...` 통과.
- `/opt/conda/envs/docker-infra/bin/python -m unittest tests.api.test_migration_schema tests.api.test_storage_models` 통과.
- `wiz_project_build(clean=false)` 통과.
- `docker manifest inspect quay.io/ceph/ceph:v19.2.4` 통과.
- `http://127.0.0.1:3001/storage`는 WIZ dev cookies 포함 HTTP 200 확인.
- `/wiz/api/page.storage/load`, `/wiz/api/page.storage/master_status`는 HTTP wrapper 200이나 인증 미충족으로 payload code 401 확인.

## 남은 리스크

- 실제 bootstrap API는 Ceph 컨테이너/service를 생성하는 파괴적 동작이라 검증 중 호출하지 않았다.
- OSD가 없는 상태에서 MDS service는 생성되지만 CephFS filesystem/pool 활성화는 OSD 추가 이후 별도 단계가 필요하다.
