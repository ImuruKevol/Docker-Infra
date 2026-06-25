# CephFS host mount와 service storage mount 모델 구현

- **ID**: 009
- **날짜**: 2026-06-24
- **유형**: 기능 추가

## 작업 요약
모든 Swarm/Ceph node의 `/srv/docker-infra/storage/cephfs` host mount 상태를 DB와 operation log에서 관리할 수 있게 했다.
CephFS mount ensure 명령은 cephx keyring 배포, mount health check, systemd 재시작 후 remount 보장을 포함한다.
서비스 생성 경로에서는 Docker-managed volume 입력을 실행 대상에 따라 CephFS 또는 local bind mount host path로 변환하고 `storage_mounts`에 기록하도록 연결했다.

## 원문 요청사항
```text
# ReviewOps Codex 작업 요청

아래 요청을 현재 프로젝트 루트에서 처리하세요. 필요한 파일을 직접 수정하고, 마지막 응답은 한국어로 간결하게 작성하세요.
스트리밍 응답은 사용하지 않습니다. 작업이 끝난 뒤 변경 요약, 확인한 내용, 남은 리스크만 정리하세요.
이 작업의 세션 단위는 아래 리뷰 ID입니다. 리뷰 ID가 같으면 같은 Codex 히스토리 맥락으로 이어서 처리하세요.

## 사용자 요청

작업 시작

## 리뷰 요약

- 리뷰 ID: egsxglkrxmskxbxfgibfjxuccdjwpodf
- 제목: CephFS host mount와 service mount 모델 구현
- 요청 링크: https://infra-dev.nanoha.kr/access
- Codex 요청자: 권태욱
- 프로젝트 루트: /root/docker-infra

## 리뷰어 요청 내용

모든 Swarm/Ceph node에 `/srv/docker-infra/storage/cephfs` mount 상태를 관리한다. mount health check, cephx key 배포, 재시작 후 remount 보장, 누락 node warning을 구현한다. 서비스별 mount는 `storage_mounts`에 기록하고 host path는 `/srv/docker-infra/storage/cephfs/services/<service>/mounts/<name>/current` 규칙을 따른다. 독립 서버 서비스는 local bind mount를 유지한다.
```

## 변경 파일 목록

### Storage / CephFS
- `src/model/struct/storage_ceph_mount.py`: Swarm node별 CephFS mount ensure, cephx keyring 배포, missing node 합성 row, mount_status 갱신, operation log 기록 추가.
- `src/model/struct/local_command_catalog.py`: `storage.ceph.mount.ensure` 명령과 `STORAGE_CEPH_MOUNT_ENSURE_SCRIPT` 추가. kernel CephFS mount, ceph-fuse fallback, systemd boot remount unit, health check를 수행한다.
- `src/model/struct/storage_health.py`: CephFS mount 누락 node warning 추가.
- `src/model/struct/storage.py`, `src/app/page.storage/api.py`: `ensure_node_mount` API 연결.

### Service Storage Mount
- `src/model/struct/storage_mounts.py`: Compose volume normalizer, CephFS/local host path 규칙, top-level Docker volume 제거, `x-docker-infra.storage` metadata, `storage_mounts` upsert 추가.
- `src/model/struct/services.py`: 서비스 저장 전 storage normalizer 실행, 서비스 metadata에 storage 계약 기록, 생성 후 `storage_mounts` row 저장.
- `src/model/struct/services_wizard.py`: wizard create payload에 node/placement/storage 선택 전달.
- `src/model/struct/services_preflight.py`: Docker-managed volume 입력을 storage mount로 변환하는 preflight 항목 추가.
- `src/model/struct/services_deploy.py`: 배포 전 CephFS host mount 보장과 service bind mount directory 생성 추가.

### Tests / Devlog
- `tests/api/test_storage_models.py`: CephFS host mount, service mount normalizer, deploy/preflight 연결 static contract 추가.
- `devlog.md`, `devlog/2026-06-24/009-cephfs-host-service-mount-model.md`: 작업 이력 추가.

## 확인 결과
- `/opt/conda/envs/docker-infra/bin/python -m py_compile src/model/struct/storage_ceph_mount.py src/model/struct/storage_mounts.py src/model/struct/services.py src/model/struct/services_wizard.py src/model/struct/services_preflight.py src/model/struct/services_deploy.py src/model/struct/local_command_catalog.py src/model/struct/storage.py src/model/struct/storage_health.py src/app/page.storage/api.py` 통과.
- `/opt/conda/envs/docker-infra/bin/python -m unittest tests.api.test_storage_models tests.api.test_migration_schema` 통과.
- `wiz_project_build(clean=False)` 성공.
- `season-wiz-project=main`, `season-wiz-devmode=true` 쿠키로 `http://127.0.0.1:3001/storage` HTTP 200 확인.
- 같은 쿠키로 `/wiz/api/page.storage/load` 호출 시 wrapper `code: 401`, `AUTHENTICATION_REQUIRED` 확인. 인증 세션이 없어 실제 storage 데이터 API는 로그인 후 검증이 필요하다.
- `/opt/conda/envs/docker-infra/bin/python -m unittest discover tests/api`는 기존 인증/구조 계약 실패가 남아 실패했다. 대표적으로 live API 401, 기존 대형 struct 파일 300줄 초과, 기존 service create template 문구 계약 불일치가 확인됐다.

## 남은 리스크
- 실제 CephFS mount는 운영 node의 kernel Ceph client, ceph-fuse, systemd, 권한 상태에 따라 live 검증이 필요하다.
- 현재 mount keyring은 로컬 Ceph runtime 디렉터리의 admin keyring 또는 cluster metadata의 mount keyring을 전제로 배포한다. 별도 최소 권한 client 발급 자동화는 후속 보강 대상이다.
- 기존 배포 서비스의 Docker-managed volume은 자동 이전하지 않는다. 신규 생성/저장 경로의 변환만 적용된다.
