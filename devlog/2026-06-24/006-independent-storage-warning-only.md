# 독립 서버 Storage 탭을 단일 경고 메시지로 단순화

- **ID**: 006
- **날짜**: 2026-06-24
- **유형**: UI 단순화

## 작업 요약
독립 서버의 `/servers` 상세 `스토리지` 탭에서 모드 카드, 저장소 기본값 카드, Swarm 등록 CTA 등 복잡한 정보를 제거했다.
`swarm_node_id`가 없는 서버에서는 "아직 Swarm 클러스터로 연결되어 있지 않아 스토리지를 적용할 수 없습니다." 단일 경고 메시지만 표시한다.
Swarm 서버에서는 기존처럼 OSD 슬롯 구성 진입 정보가 보이도록 분기를 유지했다.

## 원문 요청사항
```text
독립 서버의 상세 화면에서 스토리지 탭에는 복잡하게 뭐 이것저것 보여주지 말고 그냥 아직 Swarm 클러스터로 연결되어있지 않아서 스토리지 적용이 불가능하다 이런 식의 경고 메세지 하나만 딱 보여주면 돼.
다른 복잡한 카드, 정보 이런건 전부 필요 없어.
```

## 변경 파일 목록

### Source App
- `src/app/page.servers/view.pug`: 독립 서버 storage 탭을 `servers-storage-independent-warning` 단일 경고 영역으로 변경하고, 상세 카드/CTA/OSD 버튼은 Swarm 서버 branch로 이동.
- `src/app/page.servers/view.ts`: 더 이상 쓰지 않는 독립 서버 storage CTA helper 제거.

### Tests / Devlog
- `tests/api/test_storage_models.py`: 독립 서버 storage 탭 단일 경고 메시지와 Swarm 등록 CTA 제거 계약 반영.
- `devlog.md`: 작업 요약 행 추가.
- `devlog/2026-06-24/006-independent-storage-warning-only.md`: 상세 devlog 추가.

## 확인 결과
- `/opt/conda/envs/docker-infra/bin/python -m py_compile src/model/struct/nodes_shared.py src/model/struct/nodes_view.py src/model/struct/storage.py src/app/page.servers/api.py src/app/page.storage/api.py` 통과.
- `/opt/conda/envs/docker-infra/bin/python -m unittest tests.api.test_storage_models tests.api.test_nodes_swarm.NodesSwarmStaticContractTest` 통과.
- `wiz_project_build(clean=False)` 성공.
- dev 쿠키 `season-wiz-project=main; season-wiz-devmode=true`를 포함해 `https://infra-dev.nanoha.kr/servers` 요청 시 200 HTML 응답 확인.
- 동일 dev 쿠키로 `https://infra-dev.nanoha.kr/wiz/api/page.servers/load` POST 요청 시 HTTP 200 JSON 응답 경로 확인. 인증 세션이 없어 payload code는 401이었다.

## 남은 리스크
- 인증 세션이 없어 실제 독립 서버 선택 후 브라우저 화면에서 경고 메시지 1개만 보이는지는 직접 클릭 검증하지 못했다.
- Swarm 서버 branch의 OSD 슬롯 구성은 아직 실제 wizard가 아니라 `/storage` 진입 버튼 수준이다.
