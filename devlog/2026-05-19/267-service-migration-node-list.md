# 267. 서비스 마이그레이션 대상 서버 목록 로딩 수정

- 날짜: 2026-05-19
- 리뷰 ID: ulfzlvcnqlewfsvokoruozrxytwvdqiv
- 원 요청: "서비스 마이그레이션 모달에 서버 목록이 뜨질 않아"

## 변경 파일

- `src/app/page.services/api.py`
- `tests/api/test_service_migration.py`
- `devlog.md`
- `devlog/2026-05-19/267-service-migration-node-list.md`

## 작업 내용

- 서비스 관리 화면의 `load` API 응답에 `nodes` 목록을 포함하도록 수정했다.
- 마이그레이션 모달이 이미 참조하던 `this.nodes()` 데이터가 초기 로딩 때 채워지도록 연결했다.
- 서비스 마이그레이션 정적 계약 테스트에 서버 목록 응답 계약을 추가했다.

## 확인 결과

- `/opt/conda/envs/docker-infra/bin/python -m py_compile src/app/page.services/api.py tests/api/test_service_migration.py`
- `/opt/conda/envs/docker-infra/bin/python -m unittest tests.api.test_service_migration`
- `wiz_project_build(projectName="main", clean=false)`

위 확인은 모두 성공했다.
