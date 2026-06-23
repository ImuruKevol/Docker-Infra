# 016. 서비스 상세 상태 확인 경량화와 무료 SSL 섹션 로드 보정

## 원 요청

- 리뷰 ID: `kmdgruktrnujxsiakyaeutwuyxbaxzik`
- 요청: 상태 확인 버튼 클릭 시 실제 화면에서 쓰는 데이터보다 과도한 데이터가 포함되어 6초가 걸리므로 1초 미만으로 최적화하고, 무료 SSL 인증서 섹션이 표시될 때도 있고 표시되지 않을 때도 있는 문제를 확인/수정.

## 변경 파일

- `src/model/struct/local_command_catalog.py`
  - 서비스 단위 컨테이너 조회용 `docker.containers.service` 명령을 추가했다.
  - `service.stack.ps`를 실행 중 목표 상태 작업만 조회하도록 줄였다.
- `src/model/struct/nodes_runtime.py`
  - 전체 컨테이너 목록 대신 서비스 이름 기준으로 필터링된 컨테이너만 조회하는 `service_containers`를 추가했다.
- `src/model/struct/services_status.py`
  - 상태 갱신 시 전체 노드/전체 컨테이너 조회를 피하고, 배포 대상 노드와 기존 런타임 노드만 대상으로 병렬 조회하도록 변경했다.
  - Stack service/task payload를 화면에서 쓰는 주요 필드로 축소했다.
- `src/app/page.services/api.py`
  - `refresh_deploy_status` 응답의 중복 `result` 전체 payload를 요약 정보로 축소했다.
- `src/app/page.services/view.ts`
  - 서비스 상세 로드 직후 `detail_service_extras`를 비동기로 호출해 무료 SSL 인증서 섹션 대상이 안정적으로 채워지도록 했다.
  - 상태 확인 후 extras가 아직 없으면 추가 로드를 보장했다.
- `tests/api/test_services_preflight.py`
  - 서비스 상태 갱신 경량화와 extras 자동 로드 계약을 반영했다.

## 확인 결과

- `python -m py_compile src/app/page.services/api.py src/model/struct/local_command_catalog.py src/model/struct/nodes_runtime.py src/model/struct/services_status.py` 성공.
- `python -m unittest tests.api.test_services_preflight.ServicesPreflightStaticContractTest.test_deploy_status_refresh_and_self_signed_ssl_test_path_are_wired tests.api.test_services_preflight.ServicesPreflightStaticContractTest.test_service_detail_splits_slow_extras_from_initial_overview` 성공.
- WIZ build(`clean=false`) 성공.
- 참고: `python -m unittest tests.api.test_services_preflight` 전체 실행은 기존 정적 계약과 현재 `page.services.create` 템플릿 사이 불일치(`변수 {{editableTemplateFields().length}}개` 문구 누락 등)로 실패했다.

## 남은 리스크

- 실제 운영/개발 서버의 Docker 노드 수와 SSH 지연 조건에서 1초 미만 응답 시간은 실측하지 못했다.
- 작업 전부터 존재하던 다른 파일 변경과 미추적 파일은 유지했다.
