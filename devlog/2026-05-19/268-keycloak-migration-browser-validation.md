# 268. Keycloak 실마이그레이션 검증과 백업 레지스트리 보정

- 날짜: 2026-05-19
- 리뷰 ID: ulfzlvcnqlewfsvokoruozrxytwvdqiv
- 원 요청: "현재 떠있는 keycloak 서비스를 실제 마이그레이션 테스트를 진행해줘. 실제 브라우저로 검증, 테스트해야해."

## 변경 파일

- `src/model/struct/service_image_snapshot_runner.py`
- `src/model/struct/nodes_backup_registry.py`
- `src/model/struct/services_deploy.py`
- `tests/api/test_service_migration.py`
- `tests/api/test_backup_registry_nodes.py`
- `devlog.md`
- `devlog/2026-05-19/268-keycloak-migration-browser-validation.md`

## 작업 내용

- 실제 브라우저에서 서비스 마이그레이션 모달을 열어 대상 서버 목록에 `mini2`가 표시되는지 확인했다.
- Keycloak 마이그레이션 실행 중 원격 소스 노드가 HTTP 백업 레지스트리를 HTTPS로 로그인하는 문제를 확인하고, 스냅샷 생성 전에 소스 노드 백업 레지스트리 설정을 적용하도록 수정했다.
- 배포 매니저 노드가 원격 백업 레지스트리를 로그인할 때도 insecure registry 설정을 적용하도록 수정했다.
- 매니저 Docker 재시작으로 Harbor가 중지될 수 있어, 매니저 레지스트리 설정 후 백업 저장소 실행 상태를 다시 보장하도록 수정했다.
- 실패 후 이미 생성된 Keycloak 스냅샷과 대상 서버 설정을 이용해 복구 배포를 실행했고, Keycloak 서비스를 `mini2`에서 기동하도록 완료했다.

## 확인 결과

- `/opt/conda/envs/docker-infra/bin/python -m py_compile src/model/struct/service_image_snapshot_runner.py tests/api/test_service_migration.py`
- `/opt/conda/envs/docker-infra/bin/python -m py_compile src/model/struct/nodes_backup_registry.py src/model/struct/services_deploy.py tests/api/test_backup_registry_nodes.py`
- `/opt/conda/envs/docker-infra/bin/python -m unittest tests.api.test_backup_registry_nodes tests.api.test_service_migration`
- `wiz_project_build(projectName="main", clean=false)`
- Playwright 브라우저 검증:
  - `/services?service_id=c0a01940-9327-4939-81da-8f5f01a0a998` 접속 및 마이그레이션 모달 대상 서버 목록 확인
  - 복구 배포 작업 `6b4ac9f1-29b0-42c1-b238-0613beb2191e` 성공
  - Keycloak, Postgres 컨테이너가 `mini2`에서 `healthy` 상태로 실행 중임을 확인
  - `https://keycloak.imurukevol.com` 브라우저 접속 결과 HTTP 200 및 `Sign in to Keycloak` 화면 확인

위 확인은 모두 성공했다.
