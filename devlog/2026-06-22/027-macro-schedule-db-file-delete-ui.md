# 027. 매크로 스케줄 DB 반영과 대상 목록/첨부 파일 삭제 UX 보정

## 원문 요청

```text
- DB 스키마 변경점이 있으면 실제 DB에 반영해줘.
- 실행 일정 바로 밑에 선택된 것을 다시 리스팅해서 보여주는 회색 글자("매주 월요일, 화요일, 수요일, 목요일, 금요일, 토요일, 일요일 02:00" 부분) 삭제
- 서버/서비스 선택 부분이 다단이 아니라 한줄씩 길게 표시되도록 해야해.

---

번외로 매크로 상세 부분에 첨부파일에 대해 리스팅은 되는데 첨부파일 삭제 기능이 없네. 추가해줘.
```

## 변경 파일

- `src/app/page.macros/api.py`
- `src/app/page.macros/view.pug`
- `src/app/page.macros/view.ts`
- `src/model/db/migrations/022_macro_schedules.sql`
- `src/model/struct/macros.py`
- `src/model/struct/macros_store.py`
- `tests/api/test_server_macros.py`
- `devlog.md`
- `devlog/2026-06-22/027-macro-schedule-db-file-delete-ui.md`

## 변경 내용

- 실제 DB에 022 `macro_schedules` 마이그레이션을 적용해 `schema_version`을 022로 올렸다.
- 022 마이그레이션이 기존 `shell_macro_schedules` 테이블에도 `schedule_weekdays` 컬럼을 보강하도록 `ALTER TABLE`과 backfill을 추가했다.
- 스케줄 모달의 실행 일정 제목 아래 회색 요약 문구를 제거했다.
- 스케줄 실행 대상 목록을 2단 그리드에서 1열 전체 폭 리스트로 변경했다.
- 매크로 상세 첨부 파일 목록에 삭제 버튼을 추가했다.
- `delete_macro_file` page API와 `macros.delete_file`/`macros_store.delete_file` 경로를 추가했다.

## 확인 결과

- `python -m py_compile src/app/page.macros/api.py src/model/struct/macros.py src/model/struct/macros_store.py src/model/struct/macro_schedules.py src/model/struct/macros_shared.py`
- `python -m unittest tests.api.test_server_macros.ServerMacrosStaticContractTest tests.api.test_migration_schema.MigrationSchemaStaticContractTest`
- WIZ build `main` 성공
- 쿠키 `season-wiz-project=main; season-wiz-devmode=true` 포함 `/api/system/health` 호출 결과 DB `schema_version` 022 확인
- 실제 DB에서 `shell_macro_schedules.schedule_weekdays` JSONB 컬럼과 `operation_logs_macro_schedule_idx` 인덱스 존재 확인

## 남은 리스크

- 기존 적용된 021 마이그레이션은 현재 파일과 checksum이 불일치하는 상태로 남아 있다. 이번 작업의 022 적용과 컬럼 반영은 완료됐다.
- `DOCKER_INFRA_TEST_PASSWORD`가 없어 로그인 후 매크로 화면 API의 실제 파일 삭제 플로우는 실호출하지 못했다.
- 실제 브라우저에서 스케줄 모달 레이아웃과 첨부 파일 삭제 버튼 클릭은 수동 확인하지 못했다.
