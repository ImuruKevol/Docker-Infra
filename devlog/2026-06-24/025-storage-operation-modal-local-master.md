# 025. Storage 실행 결과 모달과 local-master SSH 우회 보정

- 날짜: 2026-06-24
- 리뷰 ID: ejosmmvibdlmlnlspihmlavbexhuwhoi

## 사용자 원본 요청

"서버 SSH 계정 정보가 없습니다. 서버를 다시 등록해주세요." 라고 뜨는데 뭔 개소리야? 마스터 노드는 ssh가 아니라 그냥 실행하면 되는데.
그리고 실행에 대한 결과가 Operation log 탭으로 가서 보이는데, 내가 이 탭의 기능을 잘못 이해했어. 탭으로 분리가 되면 안되고, 실행에 대한 결과는 모달 형태로 띄워야해.

실제 화면을 접속해서 마스터 노드 구성이 정상적으로 동작하도록 해줘.
PW: 제공됨

## 변경 파일

- `src/model/struct/nodes_shared.py`: `is_local_master_node` 공통 판별 함수 추가.
- `src/model/struct/storage_ceph_preflight.py`: local-master 판별 시 SSH 대신 local executor를 사용하도록 변경.
- `src/model/struct/storage_ceph_runtime.py`: Ceph runtime 준비 경로에서 local-master SSH 우회 적용.
- `src/model/struct/storage_ceph_osd_plan.py`, `src/model/struct/storage_ceph_osd.py`, `src/model/struct/storage_ceph_mount.py`: Ceph 관련 node 실행 분기에 같은 local-master 판별 적용.
- `src/app/page.storage/view.ts`: Operation log 탭 전환 제거, 실행 결과 모달 상태/열기/닫기 추가.
- `src/app/page.storage/view.pug`: Operation log 탭 섹션 제거, `storage-operation-modal` 실행 결과 모달 추가.
- `tests/api/test_storage_models.py`: local-master SSH 우회와 실행 결과 모달 UI 계약 반영.

## 확인 결과

- `/opt/conda/envs/docker-infra/bin/python -m py_compile ...` 통과.
- `/opt/conda/envs/docker-infra/bin/python -m unittest tests.api.test_migration_schema tests.api.test_storage_models` 통과.
- `wiz_project_build(clean=false)` 통과.
- Playwright로 `/access` 로그인 후 `/storage` 실제 화면 접속 확인.
- 화면에서 `Operation log` 탭 count 0 확인.
- `마스터 노드 설치 및 구성` 클릭 후 `storage-operation-modal` 표시 확인.
- 결과 모달에서 `storage.cluster.bootstrap · succeeded`, SSH 계정 오류 없음, `quay.io/ceph/ceph:latest` 없음 확인.
- `docker service ls --filter label=docker-infra.storage=ceph`에서 MON/MGR/MDS service 모두 `quay.io/ceph/ceph:v19.2.4`, `1/1` 확인.
- `docker ps`에서 MON/MGR/MDS container running 확인.
- MON container 내부 `ceph -s`에서 MON quorum과 active MGR 확인.
- 화면 캡처: `/tmp/storage-master-config-modal.png`.

## 남은 리스크

- OSD가 아직 0개라 `ceph -s` health는 `HEALTH_WARN`이며, MDS service는 container로 실행 중이지만 CephFS filesystem/pool 생성 전이라 `ceph -s` services 목록에는 아직 MDS가 표시되지 않는다.
