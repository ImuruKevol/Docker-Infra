# 002. 매크로 스케줄 대상 높이 고정과 실행 이력 결과 펼침 추가

## 원문 요청

```text
- 실행 대상 height를 고정해서 대상 검색에 입력해도 모달의 height가 널뛰기하지 않게 해줘.
- 첨부한 스크린샷을 보면 실행 이력의 아랫부분이 화면에 보이는 영역보다 훨씬 좁게 표시되고 있어.
- 실행 이력의 각 이력을 클릭하면 결과가 보이도록 해줘.
```

## 변경 파일

- `src/app/page.macros/view.pug`
- `src/app/page.macros/view.ts`
- `src/model/struct/macro_schedules.py`
- `src/model/struct/macros_shared.py`
- `src/model/struct/macros_store.py`
- `tests/api/test_server_macros.py`
- `devlog.md`
- `devlog/2026-06-23/002-macro-schedule-history-detail-layout.md`

## 변경 내용

- 스케줄 실행 대상 목록과 빈 검색 결과 영역을 `h-72`로 고정해 검색 결과 수가 변해도 모달 높이가 흔들리지 않도록 했다.
- 실행 이력 패널을 `flex h-full` 구조로 변경하고 이력 목록이 남은 높이를 채우도록 했다.
- 스케줄 이력 조회 응답에 `operation_logs.output`을 포함했다.
- 스케줄 이력 정규화 결과에 `output`을 포함했다.
- 실행 이력 항목 클릭 시 선택 상태를 저장하고, 해당 항목 아래에 output과 result payload를 펼쳐 보여주도록 했다.

## 확인 결과

- 첨부 스크린샷에서 실행 이력 목록 하단에 큰 빈 영역이 생기는 형태를 확인했다.
- `python -m py_compile src/app/page.macros/api.py src/model/struct/macros.py src/model/struct/macros_store.py src/model/struct/macro_schedules.py src/model/struct/macros_shared.py`
- `python -m unittest tests.api.test_server_macros.ServerMacrosStaticContractTest tests.api.test_migration_schema.MigrationSchemaStaticContractTest`
- WIZ build `main` 성공
- 쿠키 `season-wiz-project=main; season-wiz-devmode=true` 포함 `/api/system/health` 호출 결과 DB `schema_version` 022 확인

## 남은 리스크

- 로그인 테스트 비밀번호가 없어 실제 브라우저에서 검색 입력 시 모달 높이 안정성, 실행 이력 영역 높이, 이력 클릭 결과 표시를 수동 확인하지는 못했다.
