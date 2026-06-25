# 서버 상세의 독립/Swarm Storage 분기 표시 정리

- **ID**: 003
- **날짜**: 2026-06-24
- **유형**: UI/모델 정리

## 작업 요약
`swarm_node_id` 유무를 기준으로 서버 모드를 `독립 서버`와 `Swarm 서버`로 명확히 구분했다.
`/servers` 상세에 스토리지 탭을 추가해 독립 서버에는 local bind mount 안내와 Swarm 등록 CTA만 표시하고, Swarm 서버에는 `swarm_node_id`와 OSD 슬롯 구성 진입 버튼을 표시하도록 했다.
Storage overview의 서버 목록도 같은 mode payload를 사용해 OSD slot 후보 여부와 기본 저장소 backend를 일관되게 노출한다.

## 원문 요청사항
```text
작업 시작

리뷰 ID: wxquoxlmdpdwsqddqnfelilbqjuxboit
제목: 독립 서버와 Swarm 서버 상태 분기 정리

`/servers` 화면과 관련 model에서 서버 모드를 명확히 구분한다.
`swarm_node_id`가 없으면 독립 서버로 표시하고, Ceph 없이 local bind mount로 서비스 실행 가능하다는 안내를 보여준다.
`swarm_node_id`가 있으면 Swarm 서버로 표시하고 Ceph OSD slot 후보가 될 수 있게 한다.
독립 서버에는 OSD slot 버튼을 노출하지 않고 Swarm 등록 CTA를 제공한다.

참고:
- `docs/ceph-storage-application-plan.md` §2, §3, §6, §23 Phase 1
- `docs/backup-volume-layered-storage-design.md` §3.4, §6, §13.2, §18.5
```

## 변경 파일 목록

### Source App
- `src/app/page.servers/view.ts`: `swarm_node_id` 기준 서버 모드 판정, storage 탭 route key, local/CephFS 저장소 문구, OSD slot/Swarm CTA 표시 helper 추가.
- `src/app/page.servers/view.pug`: 서버 상세 탭에 `스토리지` 추가, 독립 서버 local bind mount 안내, Swarm 등록 CTA, Swarm 서버 OSD 슬롯 구성 버튼 추가.
- `src/app/page.storage/view.ts`: Storage overview 서버 목록의 mode badge를 model payload 기준으로 표시.
- `src/app/page.storage/view.pug`: Storage overview 서버 목록에 storage backend 안내 문구 표시.

### Model
- `src/model/struct/nodes_shared.py`: `swarm_node_id` 기반 `server_mode`, `storage_backend`, `osd_slot_candidate` 공통 payload 추가.
- `src/model/struct/nodes_view.py`: 서버 상세/cached detail 응답에 mode payload 포함.
- `src/model/struct/storage.py`: Storage overview node summary가 공통 mode payload와 `ready_for_osd`를 사용하도록 정리.

### Tests / Devlog
- `tests/api/test_storage_models.py`: 서버 storage mode 분기 계약 static test 추가.
- `devlog.md`: 작업 요약 행 추가.
- `devlog/2026-06-24/003-independent-swarm-server-storage-branch.md`: 상세 devlog 추가.

## 확인 결과
- `/opt/conda/envs/docker-infra/bin/python -m py_compile src/model/struct/nodes_shared.py src/model/struct/nodes_view.py src/model/struct/storage.py src/app/page.servers/api.py src/app/page.storage/api.py` 통과.
- `/opt/conda/envs/docker-infra/bin/python -m unittest tests.api.test_storage_models tests.api.test_nodes_swarm.NodesSwarmStaticContractTest` 통과.
- `wiz_project_build(clean=False)` 성공.
- dev 쿠키 `season-wiz-project=main; season-wiz-devmode=true`를 포함해 `https://infra-dev.nanoha.kr/servers` 요청 시 200 HTML 응답 확인.
- 동일 dev 쿠키로 `https://infra-dev.nanoha.kr/wiz/api/page.servers/load` POST 요청 시 HTTP 200 JSON 응답 경로 확인. 인증 세션이 없어 payload code는 401이었다.
- 빌드 산출물에서 `/servers` storage 탭과 OSD 슬롯 구성 문구가 포함된 것을 확인했다.

## 남은 리스크
- OSD 슬롯 구성 마법사는 아직 실제 wizard 구현이 아니라 `/storage` 진입 버튼 수준이다.
- 인증 세션이 없어 로그인 후 실제 서버 목록 데이터가 포함된 API payload와 브라우저 상호작용은 검증하지 못했다.
- 현재 DB에는 `023_ceph_storage` migration이 아직 pending일 수 있으며, 실제 Ceph node/slot 데이터 연동은 후속 단계 범위다.
