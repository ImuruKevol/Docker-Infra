# 매크로 스케줄 실행 이력 결과 모달 전환

## 요청

실행 이력 패널은 실행 결과가 항상 표시되면 안돼. 기본적으로는 어떤 서버/서비스에 몇 시에 실행을 해서 성공/실패 여부만 쭉 컴팩트하게 출력하면 돼. 그리고 클릭하면 일단은 모달 위에 모달을 띄워서 결과를 확인할 수 있게 해줘. 그리고 JSON 형식의 실행 이력 raw 데이터는 필요 없어. stdout, stderr만 있으면 돼.

## 변경 내용

- 매크로 스케줄 실행 이력 패널에서 인라인 결과 펼침을 제거하고 대상, 실행 시각, 상태만 보이는 컴팩트 목록으로 정리했다.
- 실행 이력 항목 클릭 시 스케줄 모달 위에 결과 모달을 띄우도록 상태와 핸들러를 추가했다.
- 결과 모달에서는 실행 로그를 stdout, stderr 영역으로만 분리해서 표시하고 JSON raw payload 표시 경로를 제거했다.
- 매크로 정적 계약 테스트를 새 UI 계약에 맞게 갱신했다.

## 변경 파일

- `src/app/page.macros/view.pug`
- `src/app/page.macros/view.ts`
- `tests/api/test_server_macros.py`
- `devlog.md`
- `devlog/2026-06-23/006-macro-schedule-history-result-modal.md`

## 확인 결과

- `/opt/conda/envs/docker-infra/bin/python -m py_compile src/app/page.macros/api.py src/model/struct/macros.py src/model/struct/macros_store.py src/model/struct/macro_schedules.py src/model/struct/macros_shared.py`
- `/opt/conda/envs/docker-infra/bin/python -m unittest tests.api.test_server_macros.ServerMacrosStaticContractTest tests.api.test_migration_schema.MigrationSchemaStaticContractTest`
- WIZ build `main` 성공
- 쿠키 `season-wiz-project=main; season-wiz-devmode=true` 포함 `/api/system/health` 호출 결과 DB `schema_version` 022 확인

## 남은 리스크

- 로그인 테스트 비밀번호가 없어 실제 브라우저에서 이력 항목 클릭 후 결과 모달 표시를 수동 확인하지는 못했다.
