# Storage 개요를 Ceph 대시보드형 OSD 배치 화면으로 재구성

## 원 요청

스토리지 개요 탭에 표시되는 정보들을 실제 정보들에 맞게 수정하고, 정보가 너무 많거나 우선순위에 맞지 않는 레이아웃을 조정한다. `Dockerized Ceph cluster bootstrap` 카드는 각 서버별 OSD 슬롯 배치 정보를 보여주는 카드로 바꾸고, `OSD 슬롯 만들기` 버튼은 `+` 아이콘 버튼 형태로 변경한다. 전체적으로 Ceph 대시보드 느낌이 나도록 수정한다.

## 변경 파일

- `src/model/struct/storage.py`
- `src/model/struct/storage_ceph_cluster.py`
- `src/app/page.storage/view.pug`
- `src/app/page.storage/view.ts`
- `tests/api/test_storage_models.py`
- `devlog.md`
- `devlog/2026-06-24/028-storage-overview-ceph-dashboard-layout.md`

## 작업 내용

- Storage overview node summary에 노드별 OSD 슬롯 요약과 슬롯 행 정보를 포함하도록 변경했다.
- Ceph daemon OSD 요약이 cluster metadata보다 현재 DB의 active OSD slot 수를 우선 반영하도록 보정했다.
- 개요 탭을 Health, OSD, Raw, Hosts 핵심 지표와 OSD 배치 중심 레이아웃으로 재구성했다.
- 기존 bootstrap 중심 카드를 OSD 배치 카드로 변경하고, 서버별 슬롯 수/active/raw/slot backing 정보를 표시했다.
- 서버별 OSD 슬롯 생성 버튼을 텍스트 버튼에서 `+` 아이콘 버튼으로 변경했다.
- 기존 bootstrap 문구를 화면에서 제거하고, 테스트 계약을 새 UI 구조에 맞게 갱신했다.

## 확인 결과

- `/opt/conda/envs/docker-infra/bin/python -m unittest tests.api.test_storage_models tests.api.test_migration_schema` 통과.
- WIZ build `main` 성공.
- 브라우저로 `https://infra-dev.nanoha.kr/storage` 접속 후 `season-wiz-project=main`, `season-wiz-devmode=true` 쿠키 조건에서 확인했다.
- 새 `storage-dashboard-metrics`, `storage-osd-placement`, `storage-cluster-server-list` 영역이 렌더링되는 것을 확인했다.
- `mini-new2` 행에서 `osd-0`, `osd-1`, `osd-2` 3개 슬롯과 `3/3 active`, `384.0 GB` raw 표시를 확인했다.
- 이전 `Dockerized Ceph cluster bootstrap` 문구가 화면에 남아 있지 않음을 확인했다.

## 남은 리스크

- Ceph health는 현재 DB에 기록된 `HEALTH_WARN`을 표시한다. 실제 Ceph warning 원인 해소는 별도 운영 조치가 필요하다.
- MON/MGR/MDS 상세 상태는 bootstrap metadata와 role 기반 요약을 사용하며, 실시간 `ceph status` polling으로 직접 갱신하는 기능은 아직 없다.
