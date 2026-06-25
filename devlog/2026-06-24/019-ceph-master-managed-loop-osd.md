# Ceph 마스터 bootstrap과 managed loop OSD 슬롯 선택 추가

- **ID**: 019
- **날짜**: 2026-06-24
- **유형**: 기능 보강

## 작업 요약
Ceph cluster가 아직 없을 때 Storage 화면에서 Docker Infra master 노드에 MON/MGR/MDS Ceph container runtime을 먼저 설치/구성할 수 있는 버튼과 API를 추가했다.
OSD 슬롯 마법사는 64GB, 128GB, 256GB 슬롯 크기 선택을 지원하고, 비어 있는 block device가 없으면 `/srv/docker-infra/ceph/<fsid>/osd-slots/<slot>.raw` 파일을 만들고 `losetup`으로 loop block device를 attach해 Ceph container `ceph-volume`에 넘기도록 보강했다.

## 원문 요청사항
```text
# ReviewOps Codex 작업 요청

아래 요청을 현재 프로젝트 루트에서 처리하세요. 필요한 파일을 직접 수정하고, 마지막 응답은 한국어로 간결하게 작성하세요.
스트리밍 응답은 사용하지 않습니다. 작업이 끝난 뒤 변경 요약, 확인한 내용, 남은 리스크만 정리하세요.
이 작업의 세션 단위는 아래 리뷰 ID입니다. 리뷰 ID가 같으면 같은 Codex 히스토리 맥락으로 이어서 처리하세요.

## 사용자 요청

mini-new2 서버를 새롭게 추가했어. 이 서버는 완전히 깡통 서버라 설치 및 삭제 등이 매우 자유로워.
근데 이 서버를 대상으로 "OSD 슬롯 만들기"를 클릭하면 모달에서 아래와 같이 나오고 있어. 이 모달에서 일단 슬롯 크기를 64/128/256 중에 선택하여 설정할 수 있어야 하고, block device는 찾지 못하는게 당연해. 마법사에서 만들어서 ceph container를 띄울 때 사용해야하기 때문이야.
---
자동으로 사용할 수 있는 비어 있는 block device를 찾지 못했습니다.
자동 대상: 탐지 실패

---
그리고 맨 처음에 ceph 마스터 설정도 되어있지 않을 때는 스토리지 화면을 열면 Docker Infra의 마스터 노드에 ceph 마스터 노드 설치 및 구성 등부터 할 수 있도록 해야해.

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
- `src/app/page.storage/api.py`: `cluster_master_bootstrap` API 추가.
- `src/app/page.storage/view.ts`: 마스터 bootstrap 호출, OSD 슬롯 크기 선택 상태, selected size payload 전달, managed target 표시 추가.
- `src/app/page.storage/view.pug`: Ceph 마스터 노드 구성 카드와 OSD 슬롯 64/128/256 선택 컨트롤 추가.
- `src/model/struct/storage.py`, `src/model/struct/storage_ceph_cluster.py`: 마스터 bootstrap delegation 추가.
- `src/model/struct/storage_ceph_bootstrap.py`: Docker Infra master를 Swarm manager로 보장하고 단일 노드 master-only Ceph daemon bootstrap을 실행하는 경로 추가.
- `src/model/struct/storage_ceph_preflight.py`: master-only preflight에서는 단일 eligible host를 warning 통과로 처리하고 GPT partition 도구 부재를 warning으로 완화.
- `src/model/struct/storage_ceph_osd_plan.py`: 64/128/256 slot size 반영, block device가 없을 때 managed loop backing plan 생성.
- `src/model/struct/storage_ceph_osd.py`: managed loop path를 OSD slot create command에 전달.
- `src/model/struct/local_command_catalog.py`: `managed_loop` backing type 검증과 loop file 생성/`losetup` attach 후 container `ceph-volume` 실행 지원.
- `src/model/db/migrations/023_ceph_storage.sql`: `ceph_osd_slots.backing_type`에 `managed_loop` 허용.
- `tests/api/test_storage_models.py`: 마스터 bootstrap, managed loop OSD, slot size 선택 정적 계약 추가.

## 확인 결과
- `/opt/conda/envs/docker-infra/bin/python -m py_compile src/model/struct/storage.py src/model/struct/storage_ceph_bootstrap.py src/model/struct/storage_ceph_cluster.py src/model/struct/storage_ceph_osd.py src/model/struct/storage_ceph_osd_plan.py src/model/struct/storage_ceph_preflight.py src/model/struct/local_command_catalog.py src/app/page.storage/api.py` 통과.
- `/opt/conda/envs/docker-infra/bin/python -m unittest tests.api.test_migration_schema tests.api.test_storage_models` 통과.
- `wiz_project_build(clean=True)` 성공.
- `season-wiz-project=main`, `season-wiz-devmode=true` 쿠키로 `http://127.0.0.1:3001/storage` HTTP 200 확인.
- 같은 쿠키로 `/wiz/api/page.storage/load` 호출 시 HTTP wrapper 200, 내부 `code: 401` 확인. 인증 세션이 없어 데이터 API 본문 검증은 로그인 후 필요하다.

## 남은 리스크
- `managed_loop`는 loop device attach 상태와 host `/srv/docker-infra/ceph/<fsid>/osd-slots` 파일에 의존한다. 재부팅/장애 복구 시 loop device 재attach와 OSD service 재기동 경로는 실제 서버에서 추가 검증이 필요하다.
- OSD 생성은 `fallocate`/`truncate`, `losetup`, privileged Docker container, `ceph-volume lvm create`를 수행하는 파괴적 작업이다. 실제 mini-new2에서 버튼 실행 전 plan 경로와 용량을 확인해야 한다.
- 로그인 세션이 없어 destructive API는 호출하지 않았고, 브라우저 상호작용 검증은 인증 후 추가 확인이 필요하다.
