# 서버 상세 등록 서비스 매칭 복구

- 날짜: 2026-05-13
- 리뷰 ID: ggggrislgzxlhijifqwjujikfkylpykg
- 요청: "작업 진행해줘."
- 리뷰 내용: 서비스 관리에서는 `bbb` 서비스가 `mini3` 서버에서 실행 중으로 표시되지만, 서버 관리 상세 개요의 등록 서비스에는 표시되지 않는 문제 수정.

## 변경 파일

- `src/model/struct/nodes_shared.py`
- `src/model/struct/nodes_runtime.py`
- `src/model/struct/local_command_scripts.py`
- `src/model/struct/local_command_catalog.py`
- `tests/api/test_node_reporter.py`
- `devlog.md`
- `devlog/2026-05-13/177-server-detail-service-matching.md`

## 변경 내용

- 캐시된 컨테이너 항목에 Docker label이 없어도 Swarm/Compose 컨테이너 이름에서 runtime service name과 서비스 namespace를 복원하도록 공통 정규화 함수를 추가했다.
- 서버 상세의 등록 서비스 그룹 매칭에서 namespace/stack_name prefix 기반 fallback을 사용하도록 보강했다.
- 노드 metric collector가 앞으로 컨테이너 label을 저장하도록 collector payload를 확장하고 agent version을 갱신했다.
- label 없는 컨테이너 이름(`bbb_web.1.*`, `bbb-web-1`)과 underscore namespace(`my_app_web.1.*`) 매칭 회귀 테스트를 추가했다.

## 확인 결과

- `/opt/conda/envs/docker-infra/bin/python -m py_compile src/model/struct/nodes_shared.py src/model/struct/nodes_runtime.py src/model/struct/local_command_scripts.py src/model/struct/local_command_catalog.py` 통과.
- `/opt/conda/envs/docker-infra/bin/python -m unittest tests/api/test_node_reporter.py` 통과. (3 tests, 1 skipped)
- `wiz_project_build(projectName="main", clean=false)` 통과.

## 남은 리스크

- 이미 배포된 metric collector는 agent version 갱신 후 모니터링 구성/점검 경로가 실행되어야 label 수집 스크립트로 교체된다.
- 기존 캐시에 컨테이너 항목 자체가 비어 있는 경우에는 서버 상세에서 즉시 표시하려면 컨테이너 새로고침 또는 다음 collector 보고가 필요하다.
