# 266. 서비스 스냅샷 기반 서버 마이그레이션 추가

- 날짜: 2026-05-19
- 리뷰 ID: ulfzlvcnqlewfsvokoruozrxytwvdqiv
- 원 요청: "서비스가 실행 중인 서버에서 다른 서버로 마이그레이션할 수 있는 기능을 추가해줘. 스냅샷 기능을 그대로 활용하면 될 것 같아. 마이그레이션 시 스냅샷을 자동으로 생성하고, 그 후에 다른 서버에서 그 스냅샷을 그대로 활용하면 될 것 같아."

## 변경 파일

- `src/model/struct/services_migration.py`
- `src/model/struct/services.py`
- `src/app/page.services/api.py`
- `src/app/page.services/view.ts`
- `src/app/page.services/view.pug`
- `tests/api/test_service_migration.py`
- `devlog.md`
- `devlog/2026-05-19/266-service-migration-snapshot-redeploy.md`

## 작업 내용

- 서비스 마이그레이션 백그라운드 작업 `service.migrate`를 추가했다.
- 마이그레이션 시작 시 현재 실행 컨테이너 스냅샷을 자동 생성하고, 최신 스냅샷 이미지 ref를 Compose 이미지로 반영하도록 했다.
- 대상 서버의 `target_node_policy`와 placement metadata를 갱신한 뒤 stack을 재생성 배포하도록 연결했다.
- 서비스 상세 상단에 마이그레이션 버튼과 대상 서버 선택 모달을 추가했다.
- 정적 계약 테스트로 API, UI, 모델 연결을 검증했다.

## 확인 결과

- `/opt/conda/envs/docker-infra/bin/python -m py_compile src/model/struct/services_migration.py src/app/page.services/api.py tests/api/test_service_migration.py`
- `/opt/conda/envs/docker-infra/bin/python -m unittest tests.api.test_service_migration tests.api.test_backup_system_ui`
- `wiz_project_build(projectName="main", clean=false)`

위 확인은 모두 성공했다.
