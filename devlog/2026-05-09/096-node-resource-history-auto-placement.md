# 096. 서버 리소스 모니터링 CSV 기록과 자동 배치 점수화 적용

## 사용자 원 요청

서비스 생성 시 서버를 자동으로 선택할 때 로직을 확인해줘. 컨테이너 갯수 및 리소스 현황(cpu, mem, storage)을 종합적으로 확인 후 자동으로 선택하도록 해야 해. 이를 위해서 일단 각 서버 별로 리소스 사용 모니터링을 기록하는 로직이 필요해. 기록만 간단하게 csv나 txt 형식으로 쭉 쌓아놓고, 필요할 때 바로 사용할 수 있도록 일자별로 저장을 하던지 일정 용량마다 자르던지 해서 대시보드에서도 활용할 수 있도록 하면 좋을 것 같아.

## 변경 내용

- 기존 서비스 자동 배치 흐름을 확인하고, 단순 local master fallback 중심이던 선택 로직을 CPU, 메모리, 스토리지, 컨테이너 수를 함께 보는 점수 기반 추천 로직으로 보강했다.
- 노드 metric DB 기록 시점에 일자별 CSV 이력을 함께 쌓도록 `node-metrics/YYYY-MM-DD/{node_id}.csv` 기록기를 추가했다.
- reporter ingest와 local master metric write 경로에서 동일한 CSV 기록기를 호출하도록 연결했다.
- 서비스 생성, preflight, 배포 실행 경로에서 자동 추천 결과를 사용하고, 선택 근거를 서비스 metadata와 `target_node_policy`에 저장하도록 했다.
- 대시보드 서버 카드에서 최신 CPU/메모리/디스크/컨테이너 수와 metric 기록 파일 요약을 볼 수 있도록 했다.
- 자동 배치와 metric 기록 계약을 확인하는 테스트를 보강했다.

## 변경 파일

- `src/model/struct/nodes_metric_history.py`
- `src/model/struct/services_placement.py`
- `src/model/struct/nodes_local_master.py`
- `src/model/struct/nodes_reporter.py`
- `src/model/struct/services.py`
- `src/model/struct/services_deploy.py`
- `src/model/struct/services_preflight.py`
- `src/model/struct/infra_catalog_registry.py`
- `src/model/struct.py`
- `src/app/page.dashboard/view.ts`
- `src/app/page.dashboard/view.pug`
- `tests/api/test_node_reporter.py`
- `tests/api/test_services_preflight.py`
- `devlog.md`
- `devlog/2026-05-09/096-node-resource-history-auto-placement.md`

## 검증 결과

- 성공: `/opt/conda/envs/docker-infra/bin/python -m py_compile src/model/struct/nodes_metric_history.py src/model/struct/services_placement.py src/model/struct/nodes_local_master.py src/model/struct/nodes_reporter.py src/model/struct/services.py src/model/struct/services_deploy.py src/model/struct/services_preflight.py src/model/struct/infra_catalog_registry.py`
- 성공: `/opt/conda/envs/docker-infra/bin/python -m unittest tests.api.test_node_reporter tests.api.test_services_preflight`
  - 결과: `Ran 11 tests in 0.012s OK (skipped=1)`
- 성공: WIZ build (`wiz_project_build`, `clean=false`)
  - 출력 위치: `/root/docker-infra/project/main/build/dist/build`
