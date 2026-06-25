# Ceph preflight 비동기 실행과 중간 과정 polling 보강

## 사용자 요청

cluster_preflight가 응답이 올때까지 4분이나 걸리고 있어. 원인을 확인해줘.
그리고 중간 과정에도 뭔가가 중간에 표시가 되어야 할 것 같은데 여기도 그냥 결국엔 마지막에 한 번에 뜨고 있고.

## 변경 파일

- `src/model/struct/storage_ceph_preflight.py`
- `src/model/struct/storage_ceph_cluster.py`
- `src/app/page.storage/view.ts`
- `tests/api/test_storage_models.py`
- `devlog.md`
- `devlog/2026-06-24/011-ceph-preflight-async-progress.md`

## 변경 내용

- `cluster_preflight`가 API 요청 안에서 전체 node 점검을 끝까지 기다리던 구조를 background operation 실행으로 바꿨다.
- preflight node 점검을 순차 실행에서 `ThreadPoolExecutor` 병렬 실행으로 바꾸고, 기본 node 명령 timeout을 180초에서 45초로 줄였다.
- preflight 후보 필터링, 독립 서버 제외, node 점검 시작/완료, global check 결과를 operation output에 진행 로그로 남기도록 `on_progress` callback을 추가했다.
- storage 화면은 사전 점검 버튼 클릭 즉시 모달을 열고, 반환된 operation id를 `operation_status`로 polling해 중간 과정을 갱신하도록 변경했다.
- operation이 완료되면 `result_payload`에서 preflight 결과를 반영해 warning/error 보정 안내가 이어서 표시되도록 했다.

## 확인 결과

- 원인 확인: 기존 `cluster_preflight`는 동기 API였고, `storage_ceph_preflight.run()`이 node별 `storage.ceph.node.preflight`를 순차 실행하면서 각 node timeout을 180초로 잡아 응답이 길게 막혔다. operation output도 `preflight.run()` 종료 뒤 `_log_preflight()`에서 기록되어 마지막에 한 번에 표시됐다.
- `/opt/conda/envs/docker-infra/bin/python -m py_compile src/model/struct/storage_ceph_preflight.py src/model/struct/storage_ceph_cluster.py src/app/page.storage/api.py src/model/struct/storage.py` 통과.
- `/opt/conda/envs/docker-infra/bin/python -m unittest tests.api.test_storage_models.StorageModelStaticContractTest.test_ceph_cluster_preflight_and_bootstrap_contract` 통과.
- `/opt/conda/envs/docker-infra/bin/python -m unittest tests.api.test_storage_models` 통과.
- `wiz_project_build(projectName=main, clean=false)` 통과.
- 개발 쿠키 `season-wiz-project=main`, `season-wiz-devmode=true`를 포함한 `GET /storage`가 로컬 WIZ 서버에서 200 응답을 반환했다.
- Playwright로 `/storage` 접근 시 인증 세션이 없어 로그인 화면으로 이동하는 것까지 확인했다.
