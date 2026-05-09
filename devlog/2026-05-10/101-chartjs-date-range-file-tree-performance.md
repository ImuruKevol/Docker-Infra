# 101. 자원 차트 Chart.js 전환과 기간 조회·파일 트리 성능 최적화

## 요청 원문

차트는 chartjs를 사용해서 그려줘. 그리고 크게 보기 모달에서 시작일, 종료일 선택 시 시간값이 0으로 들어가서 그런지 제대로 조회가 되지 않아. 확인해줘.

파일 트리에서 파일 및 폴더 목록이 아직도 가져오는 속도가 많이 느려. 원인을 확실하게 파악하고 확실하게 최적화해줘.

## 변경 파일

- `src/app/page.servers/api.py`
- `src/app/page.servers/view.ts`
- `src/app/page.servers/view.pug`
- `src/app/page.dashboard/view.ts`
- `src/app/page.dashboard/view.pug`
- `src/model/struct/nodes_metric_history.py`
- `src/model/struct/file_tree.py`
- `src/model/struct/nodes_runtime_files.py`
- `src/model/struct/local_command_catalog.py`
- `src/model/struct/ssh_executor.py`
- `tests/api/test_node_reporter.py`
- `tests/api/test_images_templates_catalog.py`
- `devlog.md`
- `devlog/2026-05-10/101-chartjs-date-range-file-tree-performance.md`

## 원인

- 자원 차트는 SVG path를 직접 계산하고 있어 Chart.js 요구사항과 맞지 않았다.
- 날짜 선택값을 날짜 문자열 중심으로 넘기면 브라우저/서버 시간대 경계에서 시작일 또는 종료일의 일부 데이터가 조회 범위 밖으로 밀릴 수 있었다.
- 원격 서버 파일 목록은 SSH 실행 전마다 `ssh-keyscan`과 known_hosts 갱신을 반복했다.
- local-master 파일 목록도 같은 머신의 파일을 별도 executor 프로세스로 다시 조회했고, 숨김 파일 필터링과 파일 stat 호출도 스캔 이후 비용을 키웠다.

## 작업 내용

- 서버 상세 크게 보기 모달과 대시보드 자원 추이 차트를 `chart.js/auto` 기반 line chart로 전환했다.
- 크게 보기 모달의 시작일/종료일을 브라우저 로컬 기준 하루 시작/끝 시각의 ISO 값(`start_at`, `end_at`)으로 함께 전송하도록 변경했다.
- 자원 기록 조회/삭제 모델에서 `start_at`, `end_at`을 UTC aware datetime으로 파싱하고 실제 `reported_at` 기준으로 필터링하도록 보강했다.
- 대시보드 기본 자원 차트 범위를 "오늘"이 아니라 최근 24시간 기준으로 조회하도록 조정했다.
- SSH executor가 이미 알고 있는 host key가 있으면 known_hosts 재생성을 건너뛰도록 `known_hosts_for_run` 경로를 추가했다.
- local-master 파일 목록은 local executor를 거치지 않고 in-process `os.scandir`로 직접 조회하도록 바꿨다.
- 원격/로컬 파일 목록 스크립트에서 숨김 파일 필터링을 스캔 중에 수행하고, 디렉터리는 크기 stat 호출을 생략하도록 바꿨다.
- 공통 파일 트리 모델도 `Path.iterdir()` 기반 순회를 `os.scandir` 기반으로 전환하고 목록 제한/소요 시간/잘림 여부를 반환하도록 했다.
- 정적 계약 테스트에 Chart.js, 시간 범위 조회, 파일 트리 최적화 경로 검증을 추가했다.

## 검증

- `python -m py_compile src/model/struct/nodes_metric_history.py src/model/struct/nodes_runtime_files.py src/model/struct/local_command_catalog.py src/model/struct/ssh_executor.py src/model/struct/file_tree.py src/app/page.servers/api.py`
- `python -m unittest tests.api.test_node_reporter.NodeReporterStaticContractTest tests.api.test_images_templates_catalog.ImagesTemplatesStaticContractTest`
- 임시 데이터 디렉토리 기반 `nodes_metric_history` `start_at/end_at` 조회 및 삭제 경계 확인
- 임시 데이터 디렉토리 기반 공통 파일 트리 local list 동작 확인
- `git diff --check`
- `wiz_project_build(projectName="main", clean=false)`
