# 024. Ceph legacy image tag 정규화

- 날짜: 2026-06-24
- 리뷰 ID: ejosmmvibdlmlnlspihmlavbexhuwhoi

## 사용자 원본 요청

에러가 뜨잖아

```text
Unable to find image 'quay.io/ceph/ceph:latest' locally
docker: Error response from daemon: failed to resolve reference "quay.io/ceph/ceph:latest": quay.io/ceph/ceph:latest: not found

Run 'docker run --help' for more information
```

## 변경 파일

- `src/model/struct/local_command_catalog.py`: local executor의 모든 Ceph image parameter에서 `quay.io/ceph/ceph:latest`, `quay.io/ceph/ceph:v19`를 `quay.io/ceph/ceph:v19.2.4`로 정규화.
- `src/model/struct/storage_ceph_bootstrap.py`: payload/active cluster가 legacy tag를 들고 있어도 bootstrap에서 `v19.2.4`를 사용하고, 기존 cluster 재사용 시 DB `ceph_image`도 갱신하도록 수정.
- `src/model/struct/storage_ceph_preflight.py`: preflight payload/image 값의 legacy tag를 `v19.2.4`로 정규화.
- `src/model/struct/storage_ceph_osd_plan.py`: OSD slot 계획에서 cluster legacy tag를 `v19.2.4`로 정규화.
- `src/model/struct/storage_ceph_mount.py`: CephFS mount command parameter에서 cluster legacy tag를 `v19.2.4`로 정규화.
- `src/model/db/migrations/024_ceph_default_image.sql`: 기존 `ceph_clusters` row의 `latest`/`v19` 값을 `v19.2.4`로 보정.

## 확인 결과

- `/opt/conda/envs/docker-infra/bin/python -m py_compile ...` 통과.
- `/opt/conda/envs/docker-infra/bin/python -m unittest tests.api.test_migration_schema tests.api.test_storage_models` 통과.
- local command factory mock 확인: `storage.ceph.auth.key.generate`에 `latest`를 넣어도 argv가 `quay.io/ceph/ceph:v19.2.4`로 생성됨.
- `wiz_project_build(clean=false)` 통과.
- `http://127.0.0.1:3001/storage`는 WIZ dev cookies 포함 HTTP 200 확인.
- `/wiz/api/page.storage/load`는 HTTP wrapper 200이나 인증 미충족으로 payload code 401 확인.

## 남은 리스크

- 실제 bootstrap API는 Ceph container/service 생성 동작이라 검증 중 호출하지 않았다.
- DB migration이 아직 적용되지 않은 운영 환경에서도 코드 경로는 정규화하지만, DB row 자체 정리는 migration 적용 이후 반영된다.
