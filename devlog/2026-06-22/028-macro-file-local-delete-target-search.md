# 028. 매크로 첨부 파일 삭제 로컬 갱신과 스케줄 대상 검색 추가

## 원문 요청

```text
첨부 파일 삭제시 매크로 화면 전체가 다시 로드되는데, 이건 아니야.
그리고 실행 대상 서버/서비스의 헤더 영역에 남는 공간에 간단한 input을 추가해서 실시간 필터링 검색을 할 수 있도록 해줘.
```

## 변경 파일

- `src/app/page.macros/view.pug`
- `src/app/page.macros/view.ts`
- `tests/api/test_server_macros.py`
- `devlog.md`
- `devlog/2026-06-22/028-macro-file-local-delete-target-search.md`

## 변경 내용

- 첨부 파일 삭제 성공 후 `load()`로 전체 매크로 화면을 다시 불러오지 않고, 현재 `macros` signal에서 해당 파일만 제거하도록 변경했다.
- 스케줄 실행 대상 헤더 영역에 검색 input을 추가했다.
- 검색어가 서버/서비스 대상의 이름, 설명, 값에 대해 즉시 필터링되도록 `scheduleTargetSearch`와 `scheduleTargetItems()` 필터를 추가했다.
- 스케줄 모달을 열거나 닫거나 대상 타입을 바꿀 때 대상 검색어를 초기화하도록 했다.

## 확인 결과

- `python -m py_compile src/app/page.macros/api.py src/model/struct/macros.py src/model/struct/macros_store.py src/model/struct/macro_schedules.py src/model/struct/macros_shared.py`
- `python -m unittest tests.api.test_server_macros.ServerMacrosStaticContractTest tests.api.test_migration_schema.MigrationSchemaStaticContractTest`
- WIZ build `main` 성공
- `deleteMacroFile` 함수 블록에 `await this.load()`가 없고 `removeMacroFileFromState`가 있는 것 확인
- 쿠키 `season-wiz-project=main; season-wiz-devmode=true` 포함 `/api/system/health` 호출 결과 DB `schema_version` 022 확인

## 남은 리스크

- 로그인 테스트 비밀번호가 없어 실제 인증 세션에서 첨부 파일 삭제 후 화면 부분 갱신과 대상 검색을 브라우저로 수동 확인하지는 못했다.
