# OSD 슬롯 구성 마법사 다중 슬롯 개수 조정 지원

- 날짜: 2026-06-24
- 요청: "OSD 슬롯 구성 마법사에서는 슬롯을 하나만 만드는게 아니라 남은 용량을 고려하여 여러 개를 만들 수 있어야 해. 물론 사용자가 수정할 수 있어야 하고."

## 변경 파일

- `src/model/struct/storage_ceph_osd_plan.py`
- `src/app/page.storage/view.ts`
- `src/app/page.storage/view.pug`
- `tests/api/test_storage_models.py`
- `devlog.md`
- `devlog/2026-06-24/026-storage-osd-multi-slot-count.md`

## 변경 내용

- OSD plan 용량 산정에서 block device가 없는 managed loop 구성도 남은 용량 기준으로 여러 슬롯을 자동 산정하도록 변경했다.
- plan payload의 `slot_count` 요청값을 받아 자동 최대 개수 안에서 clamp하고, `auto_slot_count`, `max_slot_count`, `requested_slot_count`를 capacity metadata로 반환하도록 했다.
- Storage OSD 마법사에 슬롯 개수 스테퍼/숫자 입력을 추가하고, 사용자가 개수를 수정하면 plan을 다시 계산하도록 연결했다.
- 작업 plan의 구성 슬롯 표시를 선택 개수와 최대 가능 개수를 함께 보여주도록 보정했다.

## 확인

- `/opt/conda/envs/docker-infra/bin/python -m py_compile src/model/struct/storage_ceph_osd_plan.py tests/api/test_storage_models.py`: 성공
- `/opt/conda/envs/docker-infra/bin/python -m unittest tests.api.test_storage_models`: 성공
- `wiz_project_build(projectName="main", clean=false)`: 성공
- Playwright로 `https://infra-dev.nanoha.kr/storage`에 `season-wiz-project=main`, `season-wiz-devmode=true` 쿠키와 관리자 세션으로 접속해 `mini-new2` OSD 마법사를 열고, 슬롯 개수가 최대 3개로 산정된 뒤 감소 버튼으로 2개 plan으로 재계산되는 것을 확인했다. 실제 `생성 및 활성화`는 실행하지 않았다.

## 남은 리스크

- 실제 OSD 생성은 디스크/loop device를 만드는 파괴적 작업이므로 이번 검증에서는 실행하지 않았다.
