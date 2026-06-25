# Ceph 마스터 구성 카드 표시 조건 보정

- **ID**: 021
- **날짜**: 2026-06-24
- **유형**: 버그 수정

## 작업 요약
Storage 화면의 Ceph 마스터 구성 카드 표시 조건을 `cluster.configured`가 아니라 Docker Infra local master의 Ceph runtime 준비 상태로 분리했다.
이제 DB에 `ceph_clusters` row가 이미 있어도 local master가 Ceph MON/MGR/MDS 역할로 등록되어 있고 `/srv/docker-infra/ceph/<fsid>/etc/ceph.conf`가 존재하지 않으면 마스터 구성 카드가 계속 표시된다.
마스터 구성 버튼 실행 시에도 기존 active cluster row가 있으면 새 row를 만들지 않고 해당 FSID/image를 재사용해 master bootstrap을 이어가도록 보정했다.

## 원문 요청사항
```text
# ReviewOps Codex 작업 요청

아래 요청을 현재 프로젝트 루트에서 처리하세요. 필요한 파일을 직접 수정하고, 마지막 응답은 한국어로 간결하게 작성하세요.
스트리밍 응답은 사용하지 않습니다. 작업이 끝난 뒤 변경 요약, 확인한 내용, 남은 리스크만 정리하세요.
이 작업의 세션 단위는 아래 리뷰 ID입니다. 리뷰 ID가 같으면 같은 Codex 히스토리 맥락으로 이어서 처리하세요.

## 사용자 요청

마스터 노드에 ceph이 설치되지 않은 것 같은데 마스터 노드 구성 관련 UI가 표시가 되지 않네?

## 리뷰 요약

- 리뷰 ID: ejosmmvibdlmlnlspihmlavbexhuwhoi
- 제목: Swarm 서버 OSD 슬롯 구성 마법사 구현
- 요청 링크: https://infra-dev.nanoha.kr/access
- Codex 요청자: 권태욱
- 프로젝트 루트: /root/docker-infra
- Codex 세션 ID: 019ef783-f68e-7d60-98bd-b8bbe05c36ad
- 스크린샷 컨텍스트: 없음
- 에이전트 작업 지시서 컨텍스트: 없음
- HTML 문서 생성 규칙 컨텍스트: 없음
- HTML 문서 설정 컨텍스트: 없음
- HTML 프로젝트 인스트럭션 파일: 없음
- 첨부파일 컨텍스트: 0개
```

## 변경 파일 목록
- `src/model/struct/storage_ceph_cluster.py`: Ceph node 목록에 `node_is_local_master`를 포함하고 local master의 Ceph 역할/런타임 파일 기준 `master_status`를 추가.
- `src/model/struct/storage_ceph_bootstrap.py`: 기존 active cluster row가 있는 masterless 상태에서도 `existing_cluster_id`로 해당 row를 재사용해 master bootstrap을 진행하도록 변경.
- `src/model/struct/storage.py`: overview payload에 `master`와 `cluster.master_configured`를 포함.
- `src/app/page.storage/view.ts`: `master()`와 `showMasterBootstrap()` 조건 추가.
- `src/app/page.storage/view.pug`: 마스터 구성 카드 표시 조건을 `showMasterBootstrap()`으로 변경.
- `tests/api/test_storage_models.py`: master 상태 payload와 UI 표시 조건 계약 추가.

## 확인 결과
- `/opt/conda/envs/docker-infra/bin/python -m py_compile src/model/struct/storage.py src/model/struct/storage_ceph_cluster.py src/app/page.storage/api.py` 통과.
- `/opt/conda/envs/docker-infra/bin/python -m unittest tests.api.test_migration_schema tests.api.test_storage_models` 통과.
- `wiz_project_build(clean=False)` 성공.
- `season-wiz-project=main`, `season-wiz-devmode=true` 쿠키로 `http://127.0.0.1:3001/storage` HTTP 200 확인.
- 같은 쿠키로 `/wiz/api/page.storage/load` 호출 시 HTTP wrapper 200, 내부 `code: 401` 확인. 인증 세션이 없어 실제 overview payload는 로그인 후 확인이 필요하다.

## 남은 리스크
- master runtime 판단은 local filesystem의 `/srv/docker-infra/ceph/<fsid>/etc/ceph.conf` 존재 여부와 DB의 local master Ceph roles를 함께 본다. 실제 Docker service 상태까지의 live health 검증은 별도 보강이 필요하다.
- 로그인 세션이 없어 실제 운영 데이터로 카드 표시 여부를 브라우저에서 검증하지 못했다.
