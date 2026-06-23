# 026. 매크로 스케줄 다중 요일 선택과 실행 이력 표시 보정

## 원문 요청

```text
- 실행 일정에 매주 하나만 선택할 수 있는데, multiple로 선택할 수 있어야 해.
- 실행 대상을 선택했을 때 선택이 되지 않고 있어.
- 해당 스케줄에 대해 실행 이력이 남아야 해. 실행 이력은 현재 오른쪽 부분(선택 옵션들 정리?)을 지우고, 그 자리에 표시하면 돼.
```

## 변경 파일

- `src/app/page.macros/view.pug`
- `src/app/page.macros/view.ts`
- `src/model/struct/macro_schedules.py`
- `src/model/struct/macros_shared.py`
- `src/model/struct/macros_store.py`
- `src/model/db/migrations/022_macro_schedules.sql`
- `src/model/db/migrations/022_macro_schedules.down.sql`
- `tests/api/test_server_macros.py`
- `tests/api/test_migration_schema.py`

## 변경 내용

- 매크로 스케줄에 `schedule_weekdays` JSONB 컬럼을 추가하고 기존 `schedule_weekday` 값은 첫 번째 요일 호환 필드로 유지했다.
- 주간 스케줄 cron 표현식을 여러 요일(`1,3,5` 등)로 생성하도록 변경했다.
- 스케줄 저장/목록 조회 응답에 최근 `operation_logs` 기반 실행 이력을 포함했다.
- 실행 이력 조회용 `operation_logs_macro_schedule_idx` 인덱스를 추가했다.
- 스케줄 모달의 주간 요일 버튼을 복수 선택 토글로 변경했다.
- 실행 대상 선택 UI를 checkbox change 의존 방식에서 버튼 토글 방식으로 변경해 선택 상태가 즉시 반영되도록 했다.
- 기존 오른쪽 요약 패널을 제거하고 최근 실행 이력 패널로 교체했다.

## 확인 결과

- `python -m py_compile src/app/page.macros/api.py src/model/struct/macro_schedules.py src/model/struct/macros_shared.py src/model/struct/macros_store.py`
- `python -m unittest tests.api.test_server_macros.ServerMacrosStaticContractTest tests.api.test_migration_schema.MigrationSchemaStaticContractTest`
- WIZ build `main` 성공
- 쿠키 `season-wiz-project=main; season-wiz-devmode=true` 포함 `/api/system/health` 호출 성공
- 쿠키 포함 `/api/macros/schedules/run` 무토큰 호출 시 앱 응답 코드 `401 INVALID_CRON_TOKEN` 확인

## 남은 리스크

- 현재 런타임 DB health 응답의 `schema_version`은 `021`로 표시된다. 새 `022_macro_schedules` 마이그레이션 적용 전 환경에서는 `ensure_schema()` 경로가 컬럼을 보정한다.
- `DOCKER_INFRA_TEST_PASSWORD` 미설정으로 로그인 후 `/wiz/api/page.macros/load` 실호출 검증은 진행하지 못했다.
- 실제 브라우저 클릭으로 스케줄 대상 선택과 실행 이력 표시를 수동 확인하지는 않았다.
