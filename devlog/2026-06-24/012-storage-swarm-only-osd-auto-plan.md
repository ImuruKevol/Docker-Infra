# Storage 화면 Swarm 전용화와 OSD 자동 슬롯 계획 UX 개선

- **ID**: 012
- **날짜**: 2026-06-24
- **유형**: UX 개선 / 기능 보강

## 작업 요약
Storage 화면에서 독립 서버 표시와 제외 서버 안내를 제거하고, Swarm 서버만 스토리지 대상 목록과 preflight 후보로 다루도록 정리했다.
사전점검 결과는 모달에만 표시되도록 본문 결과 영역을 제거하고, Operation log는 별도 탭으로 분리했다.
OSD 슬롯 마법사는 backing 방식과 block device 입력을 없애고, 서버 용량과 자동 탐지된 OSD 후보 기준으로 생성 가능한 슬롯 수를 계산해 표시하도록 변경했다.

## 원문 요청사항
```text
# ReviewOps Codex 작업 요청

아래 요청을 현재 프로젝트 루트에서 처리하세요. 필요한 파일을 직접 수정하고, 마지막 응답은 한국어로 간결하게 작성하세요.
스트리밍 응답은 사용하지 않습니다. 작업이 끝난 뒤 변경 요약, 확인한 내용, 남은 리스크만 정리하세요.
이 작업의 세션 단위는 아래 리뷰 ID입니다. 리뷰 ID가 같으면 같은 Codex 히스토리 맥락으로 이어서 처리하세요.

## 사용자 요청

작업 시작

## 리뷰 요약

- 리뷰 ID: zyqsvvysbltycxwkhsghunmhrnxytqqu
- 제목: 스토리지 화면 개선
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

- 리뷰 ID: zyqsvvysbltycxwkhsghunmhrnxytqqu
- 제목: 스토리지 화면 개선
- 상태: in_progress
- 우선순위: normal
- 분류: ux
- 프로젝트: Docker Infra DEV
- 프로젝트 종류: web_service
- 요청 링크: https://infra-dev.nanoha.kr/access
- 화면: 1440x900
- 캡처 방식: reviewops-sdk-dom-snapshot
- 스크린샷 첨부: no
- 리뷰 첨부 파일: 0개

## 리뷰어 요청 내용

- 일단 스토리지 화면 전체에서 독립 서버는 아예 대상에서 제외하고 표시도 안되게 해줘. 이 화면에서는 오로지 swarm으로 클러스터링 되어있는 서버들만 표시하고 그 서버들만을 대상으로 스토리지를 구성할 수 있어야 하는 화면이야. 제외 독립 서버 등 표시들 등 모두 제거해줘.
- 사전점검 기능을 실행하면 모달에만 결과가 표시되어야 하는데 모달 밖에도 여전히 표시가 되고 있어.
- Operation log는 별도의 탭으로 분리가 되어야 해.
- 서버 구분 카드에서 해당 서버에 OSD 슬롯을 만들 수 있는데 찾기가 너무 어렵게 되어있어.
- OSD 슬롯 구성 마법사에서 backing 방식, block device는 사용자가 직접 선택하거나 입력을 하게하면 안돼. 자동으로 구성이 되어야 해. 그리고 해당 서버의 총 용량과 남은 용량을 표시하면서 OSD 슬롯이 몇 개가 구성된다는 식으로 구성이 되어야 해.
```

## 변경 파일 목록

### Source App
- `src/app/page.storage/view.ts`: 탭 활성 상태, Operation log 탭, OSD 자동 plan helper, 용량/슬롯 수 표시 helper를 추가하고 수동 OSD 입력 상태를 제거.
- `src/app/page.storage/view.pug`: 본문 preflight 결과/독립 서버 제외 영역 제거, Operation log 탭 분리, Swarm 서버 카드의 OSD 생성 버튼 강조, OSD 마법사 자동 용량/슬롯 plan UI로 변경.

### Model / Command
- `src/model/struct/storage.py`: Storage overview의 node 요약과 row를 Swarm 서버만 대상으로 필터링.
- `src/model/struct/storage_ceph_preflight.py`: preflight 후보를 Swarm 서버만 처리하고 독립 서버 excluded payload/progress 제거, OSD 후보 디스크 용량 정보를 check detail에 반영.
- `src/model/struct/storage_ceph_cluster.py`: preflight operation log에서 독립 서버 제외 메시지 제거.
- `src/model/struct/storage_ceph_bootstrap.py`: bootstrap preflight log에서 독립 서버 제외 메시지 제거.
- `src/model/struct/storage_ceph_osd.py`: OSD plan 실행 결과의 슬롯 목록을 순회해 여러 슬롯을 생성하도록 변경.
- `src/model/struct/storage_ceph_osd_plan.py`: OSD 자동 plan 전용 struct 추가. Swarm node 검증, 비어 있는 block device 후보 탐지 결과, 128GB 기준 슬롯 수/용량 산정 담당.
- `src/model/struct/local_command_catalog.py`: Ceph preflight 스크립트가 storage 총/사용/남은 용량과 비어 있는 OSD 후보 device 정보를 emit하도록 보강.

### Tests / Devlog
- `tests/api/test_storage_models.py`: Swarm 전용 Storage 화면, Operation log 탭, OSD 자동 plan 계약에 맞게 정적 테스트 갱신.
- `devlog.md`: 작업 요약 행 추가.
- `devlog/2026-06-24/012-storage-swarm-only-osd-auto-plan.md`: 상세 devlog 추가.

## 확인 결과

- `/opt/conda/envs/docker-infra/bin/python -m py_compile src/model/struct/storage.py src/model/struct/storage_ceph_cluster.py src/model/struct/storage_ceph_bootstrap.py src/model/struct/storage_ceph_preflight.py src/model/struct/storage_ceph_osd.py src/model/struct/storage_ceph_osd_plan.py src/model/struct/local_command_catalog.py src/app/page.storage/api.py` 통과.
- `/opt/conda/envs/docker-infra/bin/python -m unittest tests.api.test_storage_models` 통과.
- `/opt/conda/envs/docker-infra/bin/python -m unittest tests.api.test_migration_schema tests.api.test_storage_models` 통과.
- `wiz_project_build(projectName=main, clean=false)` 성공.
- dev 쿠키 `season-wiz-project=main; season-wiz-devmode=true`를 포함해 `https://infra-dev.nanoha.kr/storage` 요청 시 HTTP 200 HTML 응답 확인.
- 같은 dev 쿠키로 `https://infra-dev.nanoha.kr/wiz/api/page.storage/load` POST 요청 시 HTTP 200, wrapper 내부 `code: 401` 응답 확인. 인증 세션이 없어 실제 데이터 payload 검증은 로그인 이후 필요하다.

## 남은 리스크

- 인증 세션이 없어 실제 로그인 상태의 Storage 화면 렌더링과 OSD 마법사 상호작용은 브라우저에서 직접 확인하지 못했다.
- OSD 자동 plan은 비어 있고 mount/fstype이 없는 disk/partition만 후보로 삼는다. 서버에 별도 빈 디스크가 없으면 슬롯 수는 0개로 표시된다.
- 실제 OSD 생성은 자동 탐지된 block device에 partition/ceph-volume 작업을 수행하는 파괴적 작업이므로 운영 서버 live 검증 전에는 실행하지 않았다.
