# Storage cluster/preflight 버튼 제거와 CephFS 서비스 배포 검증

## 사용자 요청

Ceph Cluster 만들기 버튼과 사전 점검 버튼은 삭제하고, 구성된 OSD 슬롯을 이용해 실제 서비스 생성 시 CephFS 연결과 동작, 에러 여부를 검증한다.

## 변경 파일

- `src/app/page.storage/view.pug`
  - Storage 개요의 Ceph cluster 만들기/사전 점검 버튼 제거를 유지하고 OSD 슬롯 생성은 아이콘 버튼으로만 노출되도록 확인했다.
- `config/docker_infra.py`
  - CephFS host mount 보장에 필요한 `storage.ceph.mount.ensure` local executor command를 기본 allowlist에 추가했다.
- `src/model/struct/services_deploy.py`
  - CephFS mount 보장 중 예외가 발생하면 HTTP 500과 running operation으로 남지 않고 `SERVICE_DEPLOY_FAILED` JSON 오류와 failed operation으로 정리되도록 처리했다.
- `tests/api/test_storage_models.py`
  - 제거된 Storage 버튼과 CephFS mount allowlist/failure contract를 검증하는 assertion을 보강했다.

## 확인 결과

- `/opt/conda/envs/docker-infra/bin/python -m unittest tests.api.test_storage_models tests.api.test_migration_schema` 통과.
- WIZ build(`main`, clean=false) 통과.
- 브라우저에서 `https://infra-dev.nanoha.kr/storage` 접속 후 `season-wiz-project=main`, `season-wiz-devmode=true` 쿠키 기준으로 확인:
  - `Ceph cluster 만들기` 버튼 0개.
  - `사전 점검` 버튼 0개.
  - OSD 슬롯 만들기 아이콘 버튼 5개 표시.
- 검증용 서비스 `codex_cephfs_verify_1782357204731_417f79` 생성/배포 확인:
  - storage preview backend: `cephfs`.
  - storage mount path: `/srv/docker-infra/storage/cephfs/services/.../mounts/verify_data/current`.
  - Swarm service: `1/1`, `nginx:alpine`.
  - container 내부 `/usr/share/nginx/html/index.html` 값과 host CephFS path의 `index.html` 값 모두 `cephfs-ok`.
  - 검증 완료 후 서비스 삭제 API로 삭제했고 Docker service/container 잔존 없음.
- Ceph 상태 확인:
  - OSD `10 up / 10 in`.
  - MGR available.
  - health는 `HEALTH_WARN`이며 기존 `AUTH_INSECURE_GLOBAL_ID_RECLAIM_ALLOWED`, `MON_MSGR2_NOT_ENABLED` 경고가 남아 있음.

## 남은 리스크

- 검증 과정에서 allowlist 수정 전 발생한 실패 재현 operation 1건이 `running`으로 남았고, DB 컨테이너 role이 달라 직접 상태 정리는 하지 않았다.
- Ceph 자체 health warning 2건은 이번 요청 범위 밖이라 유지했다.
