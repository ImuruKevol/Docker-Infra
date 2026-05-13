# 173. CPU/Memory 자원 차트 hover tooltip min-max 표시 보강

- 날짜: 2026-05-13
- 리뷰 ID: nbrvcwxngnanwumbnczuyfsvnolkzvzn
- 요청: CPU/Memory 차트 hover 시 Average만 표시되는 문제를 수정하고, min/max 값까지 tooltip에 같이 표시한다.

## 변경 파일

- `src/app/page.dashboard/view.ts`
- `src/app/page.servers/view.ts`
- `tests/api/test_node_reporter.py`

## 변경 내용

- CPU/Memory ApexCharts에 custom tooltip을 적용해 동일한 포인트의 Min, Average, Max를 한 말풍선에 표시하도록 했다.
- 기존 날짜/시간 표시와 local timezone 표시를 유지하면서 tooltip HTML을 직접 렌더링하도록 했다.
- tooltip 텍스트 escape 처리를 추가해 custom HTML 삽입 시 값 표시가 안전하게 동작하도록 했다.
- 정적 계약 테스트에 range tooltip helper와 Min/Average/Max 표시 검증을 추가했다.

## 확인

- `/opt/conda/envs/docker-infra/bin/python -m unittest tests.api.test_node_reporter.NodeReporterStaticContractTest`
- `wiz_project_build(projectName="main", clean=false)`
