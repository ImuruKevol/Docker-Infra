# 실제 DB schema 대조 후 Ceph Storage migration 적용

- **ID**: 005
- **날짜**: 2026-06-24
- **유형**: 설정 변경

## 작업 요약
실제 PostgreSQL schema와 migration SQL을 비교해 `021_ai_agent_history` checksum mismatch가 schema 누락이 아니라 적용 후 SQL 파일 보강으로 생긴 불일치임을 확인했다.
021 실제 schema가 현재 SQL 요구 컬럼, 인덱스, trigger, check constraint를 모두 만족해 `schema_migrations` checksum을 현재 파일 기준으로 정렬한 뒤 `023_ceph_storage` migration을 실제 DB에 적용했다.

## 원문 요청사항
```text
# ReviewOps Codex 작업 요청

아래 요청을 현재 프로젝트 루트에서 처리하세요. 필요한 파일을 직접 수정하고, 마지막 응답은 한국어로 간결하게 작성하세요.
스트리밍 응답은 사용하지 않습니다. 작업이 끝난 뒤 변경 요약, 확인한 내용, 남은 리스크만 정리하세요.
이 작업의 세션 단위는 아래 리뷰 ID입니다. 리뷰 ID가 같으면 같은 Codex 히스토리 맥락으로 이어서 처리하세요.

## 사용자 요청

현재 실제 DB 스키마와 sql을 잘 비교해서 실제 DB에 적용해줘.
문제가 생기면 왜 생겼는지 분석하고 해결하고.

## 리뷰 요약

- 리뷰 ID: dyihxwmluteihnynfoksovbhcobjznqu
- 제목: Ceph Storage 데이터 모델과 기본 Struct 추가
- 요청 링크: https://infra-dev.nanoha.kr/access
- Codex 요청자: 권태욱
- 프로젝트 루트: /root/docker-infra
- Codex 세션 ID: 019ef740-93a9-7763-b7ab-cd7a8b7e1246
- 스크린샷 컨텍스트: 없음
- 에이전트 작업 지시서 컨텍스트: 없음
- HTML 문서 생성 규칙 컨텍스트: 없음
- HTML 문서 설정 컨텍스트: 없음
- HTML 프로젝트 인스트럭션 파일: 없음
- 첨부파일 컨텍스트: 0개

## 세션 처리

저장된 Codex 세션을 resume해 이전 대화 맥락을 우선 사용하세요. 이전 Codex 히스토리는 이 요청에 포함되지 않습니다.
```

## 변경 파일 목록

### Devlog
- `devlog.md`: 실제 DB 적용 작업 요약 행 추가.
- `devlog/2026-06-24/003-ceph-storage-db-apply.md`: DB 대조와 적용 상세 기록 추가.

## DB 변경 내용
- `schema_migrations`의 `021` checksum을 현재 `021_ai_agent_history.sql` 파일 checksum으로 정렬.
- `023_ceph_storage.sql` 적용.
- 신규 생성 테이블:
  - `ceph_clusters`
  - `ceph_nodes`
  - `ceph_osd_slots`
  - `storage_mounts`
  - `storage_snapshots`
  - `storage_snapshot_policies`

## 문제 분석
- `migrate_up` 적용 전 `021_ai_agent_history`는 실제 DB에 적용되어 있었지만 `schema_migrations.checksum`이 현재 SQL 파일 checksum과 달랐다.
- 실제 `ai_agent_histories` table을 확인한 결과 현재 SQL 기준 필수 컬럼 누락 없음, 필수 인덱스 누락 없음, `ai_agent_histories_set_updated_at` trigger 존재, `ai_agent_histories_status_check` constraint 존재를 확인했다.
- 따라서 원인은 DB schema 미적용이 아니라, 021 적용 이후 SQL 파일이 idempotent 보강 형태로 변경되어 발생한 checksum drift로 판단했다.

## 확인 결과
- checksum 정렬 전 021 실제 checksum: `cebf911d386269714ccf31655ff0a9ba906be432b7f19679e269c3332386f283`.
- 현재 021 SQL checksum: `c6c65b9bd786c9c71d95316da3f9e8e911faef1942a256e2f3577c0bc9669453`.
- `migration.migrate_up()` 실행 결과 `023` 적용 완료.
- `scripts/docker_infra_migrate.py status`에서 `019`~`023` 모두 `applied=true`, `checksum_matches=true` 확인.
- 실제 DB에서 6개 Ceph Storage 테이블의 컬럼, 외래키, `updated_at` trigger 생성 확인.
- `/opt/conda/envs/docker-infra/bin/python -m unittest tests.api.test_storage_models tests.api.test_migration_schema.MigrationSchemaStaticContractTest` 통과.
- `/opt/conda/envs/docker-infra/bin/python -m py_compile src/model/struct/storage.py src/model/struct/storage_health.py src/model/struct/storage_ceph.py src/model/struct/storage_ceph_cluster.py src/model/struct/storage_ceph_osd.py src/model/struct/storage_ceph_mount.py src/model/struct/storage_mounts.py src/model/struct/storage_snapshots.py src/model/struct/storage_snapshot_policies.py src/app/page.storage/api.py` 통과.

## 남은 리스크
- 실제 DB에는 schema만 적용했고 Ceph cluster, node, mount, snapshot seed 데이터는 아직 없다.
- 인증 세션이 없어 로그인된 상태의 `/storage` overview API 응답은 직접 확인하지 못했다.
