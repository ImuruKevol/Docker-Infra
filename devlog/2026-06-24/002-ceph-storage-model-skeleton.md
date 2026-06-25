# Ceph Storage DB migration과 Struct skeleton 추가

- **ID**: 002
- **날짜**: 2026-06-24
- **유형**: 기능 추가

## 작업 요약
Ceph storage 관리를 위한 `023_ceph_storage` migration을 추가해 cluster, node, OSD slot, mount, snapshot, snapshot policy 테이블을 정의했다.
Storage domain Struct를 `storage_ceph_*`, `storage_mounts`, `storage_snapshots`, `storage_snapshot_policies`로 분리하고 `/storage` page API overview가 DB-backed read-only 요약을 반환하도록 연결했다.

## 원문 요청사항
```text
# ReviewOps Codex 작업 요청

아래 요청을 현재 프로젝트 루트에서 처리하세요. 필요한 파일을 직접 수정하고, 마지막 응답은 한국어로 간결하게 작성하세요.
스트리밍 응답은 사용하지 않습니다. 작업이 끝난 뒤 변경 요약, 확인한 내용, 남은 리스크만 정리하세요.
이 작업의 세션 단위는 아래 리뷰 ID입니다. 리뷰 ID가 같으면 같은 Codex 히스토리 맥락으로 이어서 처리하세요.

## 사용자 요청

작업 시작

## 리뷰 요약

- 리뷰 ID: dyihxwmluteihnynfoksovbhcobjznqu
- 제목: Ceph Storage 데이터 모델과 기본 Struct 추가
- 요청 링크: https://infra-dev.nanoha.kr/access
- Codex 요청자: 권태욱
- 프로젝트 루트: /root/docker-infra
- Codex 세션 ID: 신규
- 스크린샷 컨텍스트: 없음
- 에이전트 작업 지시서 컨텍스트: 포함됨
- HTML 문서 생성 규칙 컨텍스트: 없음
- HTML 문서 설정 컨텍스트: 없음
- HTML 프로젝트 인스트럭션 파일: 없음
- 첨부파일 컨텍스트: 0개

## 에이전트 작업 지시서

# 에이전트 작업 지시서

## 리뷰 정보

- 리뷰 ID: dyihxwmluteihnynfoksovbhcobjznqu
- 제목: Ceph Storage 데이터 모델과 기본 Struct 추가
- 상태: in_progress
- 우선순위: high
- 분류: design
- 프로젝트: Docker Infra DEV
- 프로젝트 종류: web_service
- 요청 링크: https://infra-dev.nanoha.kr/access
- 화면: 1440x900
- 캡처 방식: reviewops-sdk-dom-snapshot
- 스크린샷 첨부: no
- 리뷰 첨부 파일: 0개

## 리뷰어 요청 내용

Ceph storage 관리를 위한 DB migration과 model skeleton을 추가한다. 대상은 `ceph_clusters`, `ceph_nodes`, `ceph_osd_slots`, `storage_mounts`, `storage_snapshots`, `storage_snapshot_policies`이다. Struct는 `storage.py`, `storage_health.py`, `storage_ceph_cluster.py` 등으로 분리하고, UI/API에서 읽기 전용 overview를 조회할 수 있게 한다. 기존 `backup_system`에는 넣지 않는다.

참고:
- `docs/ceph-storage-application-plan.md` §12, §13, §14, §23 Phase 1
- `docs/backup-volume-layered-storage-design.md` §15, §16

## 첨부 파일

-

## 콘솔 로그 요약

-

## 네트워크 로그 요약

- GET https://infra-dev.nanoha.kr/assets/font/SUIT/SUIT-Medium.woff2 200
- GET https://infra-dev.nanoha.kr/assets/font/SUIT/SUIT-ExtraLight.woff2 200
- GET https://infra-dev.nanoha.kr/assets/font/SUIT/SUIT-Light.woff2 200
- GET https://infra-dev.nanoha.kr/media/fa-solid-900.woff2 200
- GET https://infra-dev.nanoha.kr/assets/font/SUIT/SUIT-SemiBold.woff2 200
- GET https://infra-dev.nanoha.kr/assets/font/SUIT/SUIT-Regular.woff2 200
- GET https://infra-dev.nanoha.kr/assets/font/SUIT/SUIT-Medium.woff2 200
- GET https://infra-dev.nanoha.kr/assets/font/SUIT/SUIT-Bold.woff2 200
- GET https://infra-dev.nanoha.kr/assets/font/SUIT/SUIT-ExtraBold.woff2 200
- GET https://infra-dev.nanoha.kr/assets/font/SUIT/SUIT-Heavy.woff2 200
- GET https://infra-dev.nanoha.kr/api/system/assets/logo 200
- GET https://infra-dev.nanoha.kr/assets/font/SUIT/SUIT-SemiBold.woff2 200
- GET https://infra-dev.nanoha.kr/assets/font/SUIT/SUIT-Bold.woff2 200
- GET https://infra-dev.nanoha.kr/assets/font/SUIT/SUIT-ExtraBold.woff2 200
- GET https://infra-dev.nanoha.kr/media/fa-solid-900.ttf 200
- GET https://infra-dev.nanoha.kr/assets/font/SUIT/SUIT-Heavy.woff2 200
- GET https://infra-dev.nanoha.kr/api/system/assets/logo 200
- GET https://infra-dev.nanoha.kr/api/system/assets/logo 200
- GET https://infra-dev.nanoha.kr/assets/bg-login.optimized.webp 200
- GET https://infra-dev.nanoha.kr/assets/bg-login.optimized.webp 200

## 환경 로그 요약

- reviewops-sdk: SDK 0.1.10 / https://infra-dev.nanoha.kr
- reviewops-sdk: SDK 0.1.10
- iframe-fingerprint: restricted / https://infra-dev.nanoha.kr
- reviewops-sdk: SDK 0.1.10
- reviewops-sdk: SDK 0.1.10 / https://infra-dev.nanoha.kr
- browser-fingerprint: MacIntel / ko-KR / 2560x1440
- iframe-fingerprint: restricted / https://infra-dev.nanoha.kr
- reviewops-sdk: SDK 0.1.10 / https://infra-dev.nanoha.kr
- reviewops-sdk: SDK 0.1.10 / https://infra-dev.nanoha.kr
- reviewops-sdk: SDK 0.1.10 / https://infra-dev.nanoha.kr
```

## 변경 파일 목록

### DB migration
- `src/model/db/migrations/023_ceph_storage.sql`: Ceph cluster/node/OSD slot과 storage mount/snapshot/policy 테이블, 인덱스, updated_at trigger 추가.
- `src/model/db/migrations/023_ceph_storage.down.sql`: 추가 테이블 rollback 정의.

### Model / Struct
- `src/model/struct/storage.py`: Storage overview 진입점에 DB-backed Ceph, mount, snapshot, policy 요약 연결.
- `src/model/struct/storage_health.py`: schema pending, Ceph health, OSD, mount failure warning 계산 추가.
- `src/model/struct/storage_ceph.py`: Storage DB 공통 query/row 변환/schema readiness helper 추가.
- `src/model/struct/storage_ceph_cluster.py`: cluster, node, daemon, capacity overview skeleton 추가.
- `src/model/struct/storage_ceph_osd.py`: OSD slot list/summary skeleton 추가.
- `src/model/struct/storage_ceph_mount.py`: CephFS node mount list/summary skeleton 추가.
- `src/model/struct/storage_mounts.py`: 서비스 storage mount list/summary skeleton 추가.
- `src/model/struct/storage_snapshots.py`: snapshot list/summary skeleton 추가.
- `src/model/struct/storage_snapshot_policies.py`: snapshot policy list/default/summary skeleton 추가.
- `src/model/struct.py`: `storage` aggregate property 추가.

### UI / API
- `src/app/page.storage/view.ts`: overview의 storage summary 표시 helper 추가.
- `src/app/page.storage/view.pug`: OSD slot, service mount, snapshot, policy read-only summary 카드 추가.
- `src/app/page.storage/api.py`: 기존 `load` API가 확장된 overview payload를 반환하도록 model 연결 유지.

### Tests
- `tests/api/test_migration_schema.py`: `023_ceph_storage` migration과 신규 테이블 계약 반영.
- `tests/api/test_storage_models.py`: Storage Struct 분리, backup_system 비연결, migration 관계 계약 테스트 추가.

## 확인 결과
- `/opt/conda/envs/docker-infra/bin/python -m py_compile src/model/struct/storage.py src/model/struct/storage_health.py src/model/struct/storage_ceph.py src/model/struct/storage_ceph_cluster.py src/model/struct/storage_ceph_osd.py src/model/struct/storage_ceph_mount.py src/model/struct/storage_mounts.py src/model/struct/storage_snapshots.py src/model/struct/storage_snapshot_policies.py src/app/page.storage/api.py` 통과.
- `/opt/conda/envs/docker-infra/bin/python -m unittest tests.api.test_storage_models tests.api.test_migration_schema.MigrationSchemaStaticContractTest` 통과.
- `wiz_project_build(clean=False)` 성공.
- `scripts/docker_infra_migrate.py status`에서 `023_ceph_storage`가 pending migration으로 인식됨을 확인했다.
- dev 쿠키 `season-wiz-project=main; season-wiz-devmode=true`를 포함해 `https://infra-dev.nanoha.kr/storage` 요청 시 200 HTML 응답 확인.
- 동일 dev 쿠키로 `https://infra-dev.nanoha.kr/wiz/api/page.storage/load` POST 요청 시 인증 컨트롤러의 401 JSON 응답 확인.
- `tests.api.test_wiz_structure_contract.WizStructureContractTest.test_model_files_declare_model_and_stay_small`는 기존 300줄 초과 Struct 파일 44개 때문에 실패했다. 새로 추가한 Storage Struct 파일들은 `wc -l`과 `test_storage_models`에서 300줄 이하임을 확인했다.

## 남은 리스크
- 현재 DB에는 `023_ceph_storage` migration이 아직 적용되지 않았다.
- migration status에서 기존 `021_ai_agent_history` checksum mismatch가 확인되어, 그대로는 `migrate_up`으로 `023` 적용이 막힐 수 있다. 이번 작업 범위 밖이라 수정하지 않았다.
- 인증 세션이 없어 로그인 후 실제 Storage overview JSON과 화면 렌더링까지는 검증하지 못했다.
