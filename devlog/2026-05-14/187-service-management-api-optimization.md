# 187. 서비스 관리 API 상세/목록 경량화와 지연 로딩 최적화

- 날짜: 2026-05-14
- 리뷰 ID: hkblkduxsbonwxilnwihscqejduswxuj
- 요청자: 권태욱

## 사용자 원문

최적화를 진행해줘.

detail_service API가 여전히 2초 이상 걸리고 있어. 가져오는 정보들을 적절히 나눠서 최적화해줘. 그리고 사용하지 않는 정보들은 가져올 필요도 없고. 이 API 뿐만이 아니라 서비스 관리의 다른 API들도 최적화할 점이 있으면 최적화해줘.

## 변경 파일

- `src/app/page.services/api.py`
- `src/app/page.services/view.ts`
- `src/model/struct/services_runtime.py`
- `src/model/struct/infra_catalog_registry.py`
- `src/model/db/migrations/014_service_management_api_indexes.sql`
- `src/model/db/migrations/014_service_management_api_indexes.down.sql`
- `devlog.md`
- `devlog/2026-05-14/187-service-management-api-optimization.md`

## 변경 내용

- `detail_service` 초기 응답에서 Compose 원문 파일 읽기와 YAML component 파싱을 제거하고, 즉시 필요한 overview 데이터만 반환하도록 정리했다.
- Compose/Nginx 원문, 서비스 파일, 버전 이력처럼 무거운 정보는 `detail_service_advanced` 경로에서만 로드하도록 응답 경계를 분리했다.
- 배포/컨테이너 제어/서비스 수정 이후에는 전체 상세를 다시 만들지 않고 overview 또는 advanced 필요한 부분만 갱신하도록 API 응답을 줄였다.
- 서비스 목록 load API는 화면에서 쓰지 않는 domains, operations, counts 조회를 제거하고 service 목록만 반환하도록 경량화했다.
- 서비스 목록의 도메인/버전 count 조회는 최근 service 80개 기준 lateral join으로 제한해 불필요한 전체 group scan을 피하도록 바꿨다.
- operation log 조회는 우선 `target_type = 'service'`, `target_id` 조건을 사용하고, overview에서는 JSONB legacy fallback scan을 생략하도록 분리했다.
- AI 모델 옵션은 화면 진입 시 즉시 호출하지 않고 AI 섹션/AI 실행 시점에만 lazy-load하도록 변경했다.
- 서비스 관리 조회 패턴에 맞춘 PostgreSQL index migration과 down migration을 추가했다.

## 확인 결과

- `python -m py_compile project/main/src/app/page.services/api.py project/main/src/model/struct/services_runtime.py project/main/src/model/struct/infra_catalog_registry.py` 성공
- `python -m py_compile src/app/page.services/api.py src/model/struct/services_runtime.py src/model/struct/infra_catalog_registry.py` 성공
- `wiz_project_build(projectName="main", clean=false)` 성공
- `python -m unittest tests.api.test_migration_schema` 성공
- `git -C project/main diff --check` 성공

## 남은 리스크

- 실제 운영 데이터 기준의 `detail_service` 네트워크 시간은 배포 후 브라우저/ReviewOps에서 재측정해야 한다.
- 새 index 효과는 `014_service_management_api_indexes.sql` migration 적용 이후에 반영된다.
- 기존 서비스 preflight/구조 contract 테스트 일부는 이번 변경 전부터 맞지 않는 UI 토큰(`runtimeContainerRows`, `원문 설정`) 및 기존 파일 크기/try 응답 위치 규칙으로 실패해 별도 정리가 필요하다.
