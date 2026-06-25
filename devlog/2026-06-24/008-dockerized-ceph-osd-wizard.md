# Dockerized Ceph runtime과 OSD 슬롯 구성 마법사 연결

- **ID**: 008
- **날짜**: 2026-06-24
- **유형**: 기능 추가

## 작업 요약
Ceph이 host에 설치되어 있지 않은 서버를 전제로, Storage 마법사가 Ceph container image를 pull/run해서 런타임과 설정을 준비하도록 보강했다.
cluster bootstrap은 각 Swarm 서버에 `/srv/docker-infra/ceph/<fsid>` 설정/런타임 디렉터리를 만들고 MON/MGR/MDS Swarm service를 실제 Ceph daemon command로 생성한다.
OSD 슬롯 구성 마법사는 plan 확인 후 선택한 block device에 Ceph container 기반 `ceph-volume`을 실행하고 OSD daemon service 및 DB slot 상태를 갱신하도록 연결했다.

## 원문 요청사항
```text
# ReviewOps Codex 작업 요청

아래 요청을 현재 프로젝트 루트에서 처리하세요. 필요한 파일을 직접 수정하고, 마지막 응답은 한국어로 간결하게 작성하세요.
스트리밍 응답은 사용하지 않습니다. 작업이 끝난 뒤 변경 요약, 확인한 내용, 남은 리스크만 정리하세요.
이 작업의 세션 단위는 아래 리뷰 ID입니다. 리뷰 ID가 같으면 같은 Codex 히스토리 맥락으로 이어서 처리하세요.

## 사용자 요청

작업 시작. 마법사에서 해당 서버에 ceph을 docker container로 띄워서 구성을 하는 것까지 처리가 되어야 해.
현재는 각 서버들에 ceph 자체가 구성되어있지 않아.

## 리뷰 요약

- 리뷰 ID: ejosmmvibdlmlnlspihmlavbexhuwhoi
- 제목: Swarm 서버 OSD 슬롯 구성 마법사 구현
- 요청 링크: https://infra-dev.nanoha.kr/access
- Codex 요청자: 권태욱
- 프로젝트 루트: /root/docker-infra
- Codex 세션 ID: 신규
- 스크린샷 컨텍스트: 없음
- 에이전트 작업 지시서 컨텍스트: 없음
- HTML 문서 생성 규칙 컨텍스트: 없음
- HTML 문서 설정 컨텍스트: 없음
- HTML 프로젝트 인스트럭션 파일: 없음
- 첨부파일 컨텍스트: 0개
```

## 변경 파일 목록

### Source App
- `src/app/page.storage/api.py`: `osd_nodes`, `osd_slot_plan`, `osd_slot_create` API 추가.
- `src/app/page.storage/view.ts`: OSD 슬롯 마법사 상태, plan 생성, slot 생성/활성화 호출 로직 추가.
- `src/app/page.storage/view.pug`: Storage 서버 목록의 OSD 버튼과 OSD 슬롯 구성 마법사 모달 추가. cluster bootstrap 문구를 Dockerized Ceph 기준으로 변경.

### Model / Command
- `src/model/struct/local_command_catalog.py`: Ceph image 기반 preflight, Ceph node runtime/config ensure, OSD slot create script, OSD daemon service create 명령 추가/보강.
- `src/model/struct/storage_ceph_runtime.py`: Ceph keyring 생성과 노드별 runtime/config 배포 로직 분리.
- `src/model/struct/storage_ceph_bootstrap.py`: PoC sleep container 대신 Dockerized Ceph runtime ensure 후 MON/MGR/MDS daemon service를 생성하도록 변경.
- `src/model/struct/storage_ceph_preflight.py`: host `ceph-volume` 설치 대신 Ceph container 내부 `ceph-volume` 실행 가능 여부를 점검하도록 변경.
- `src/model/struct/storage_ceph_osd.py`: OSD slot plan/create, Ceph container 기반 `ceph-volume`, OSD service 생성, DB 상태 갱신 로직 추가.
- `src/model/struct/storage_ceph_cluster.py`, `src/model/struct/storage.py`: OSD slot API delegation 추가.
- `config/docker_infra.py`: Ceph runtime/daemon/OSD destructive command allowlist 추가.
- `src/model/db/migrations/023_ceph_storage.sql`: 기본 Ceph image를 `:latest` 대신 고정 tag `quay.io/ceph/ceph:v19`로 변경.

### Tests / Devlog
- `tests/api/test_storage_models.py`: Dockerized Ceph runtime과 OSD slot wizard static contract 추가.
- `devlog.md`, `devlog/2026-06-24/008-dockerized-ceph-osd-wizard.md`: 작업 이력 추가.

## 확인 결과
- `python -m py_compile src/model/struct/storage_ceph_cluster.py src/model/struct/storage_ceph_preflight.py src/model/struct/storage_ceph_bootstrap.py src/model/struct/storage_ceph_runtime.py src/model/struct/storage_ceph_osd.py src/model/struct/local_command_catalog.py src/app/page.storage/api.py src/model/struct/storage.py` 통과.
- `python -m unittest tests.api.test_migration_schema tests.api.test_storage_models` 통과.
- `wiz_project_build(clean=True)` 성공. 새 API 함수가 추가되어 clean build로 확인했다.
- `season-wiz-project=main`, `season-wiz-devmode=true` 쿠키로 `http://127.0.0.1:3001/storage` 접근 시 HTTP 200 확인.
- 같은 쿠키로 `/wiz/api/page.storage/load` 호출 시 HTTP 200 wrapper 내부 `code: 401` 확인. 인증 세션이 없어 실제 데이터 API 검증은 로그인 이후 필요하다.

## 남은 리스크
- 실제 OSD 생성은 선택한 block device에 partition/LVM 및 `ceph-volume` 작업을 수행하는 파괴적 작업이다. 운영 서버에서는 plan의 device 경로를 수동 확인해야 한다.
- Docker Swarm service로 OSD daemon을 운영하는 경로는 host device bind와 권한 요구사항이 있어 실제 서버 조합에서 추가 live 검증이 필요하다.
- Ceph MON/MGR/MDS/OSD container 명령은 공식 container image의 Ceph daemon/`ceph-volume` 제공을 전제로 한다.
