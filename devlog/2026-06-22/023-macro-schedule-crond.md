# 매크로 다중 스케줄과 cron.d 파일 실행 경로 추가

- **ID**: 023
- **날짜**: 2026-06-22
- **유형**: 기능 추가

## 작업 요약
매크로 관리 화면에 스케줄 버튼과 다중 스케줄 관리 모달을 추가했다. 매주/매월 일정, 다중 서버/서비스 대상, 실행 인자를 저장하고 각 스케줄을 `cron.d` 파일로 동기화해 토큰 보호 라우트가 자동 실행하도록 연결했다.

## 원문 요청사항
```text
# ReviewOps Codex 작업 요청

아래 요청을 현재 프로젝트 루트에서 처리하세요. 필요한 파일을 직접 수정하고, 마지막 응답은 한국어로 간결하게 작성하세요.
스트리밍 응답은 사용하지 않습니다. 작업이 끝난 뒤 변경 요약, 확인한 내용, 남은 리스크만 정리하세요.
이 작업의 세션 단위는 아래 리뷰 ID입니다. 리뷰 ID가 같으면 같은 Codex 히스토리 맥락으로 이어서 처리하세요.

## 사용자 요청

작업 시작.
cron.d 디렉토리같은걸 활용해서 cron 파일로 관리할 수 있도록?

## 리뷰 요약

- 리뷰 ID: eloazjxpmavyjmogxodqnhbqcmzuyhjb
- 제목: 매크로 - 스케줄 기능 추가
- 요청 링크: https://infra-dev.nanoha.kr/access
- Codex 요청자: 권태욱
- 프로젝트 루트: /root/docker-infra
- Codex 세션 ID: 신규
- 스크린샷 컨텍스트: 없음
- 에이전트 작업 지시서 컨텍스트: 포함됨
- HTML 문서 생성 규칙 컨텍스트: 없음
- HTML 문서 설정 컨텍스트: 없음
- HTML 프로젝트 인스트럭션 파일: 없음
- 첨부파일 컨텍스트: 0개

## 에이전트 작업 지시서

매크로 관리 화면에서 매크로를 클릭하면 오른쪽에 정보들이 뜸.
여기에서 수정 버튼 왼쪽에 스케줄 같은 버튼을 하나 추가해줘. 이 버튼을 누르면 시스템 설정의 백업 탭에 있는 실행 일정 설정 부분과 동일한 UI로 해서 매주/매월 해당 매크로를 자동으로 실행할 수 있도록 할 수 있는 기능을 추가해줘.
여기에 더 추가가 되어야 하는 기능들은 아래와 같아.

- cron 스케줄은 한 매크로에 대해 여러 개를 등록할 수 있어야 함.
- cron 스케줄 등록 시 오른쪽 컨텐츠 영역에서 서버/서비스 선택 후 실행하는 기능과 같이 대상 서버/서비스를 지정하여 일정 주기마다 실행할 수 있도록 하는 기능이 있어야 함.
- 스케줄 버튼에는 현재 몇 개의 cron 스케줄이 등록되어있는지 갯수를 표기해야함.
- 스케줄 등록 시 서버/서비스 선택 시 여러 개를 선택할 수 있어야 함.
```

## 변경 파일 목록
- `src/app/page.macros/view.pug`: 선택 매크로 헤더에 스케줄 버튼과 등록 수 배지를 추가하고, 다중 스케줄 관리 모달을 구현.
- `src/app/page.macros/view.ts`: 스케줄 폼 상태, 매주/매월 설정, 다중 대상 선택, 저장/삭제 호출 로직 추가.
- `src/app/page.macros/api.py`: `save_schedule`, `delete_schedule` API 추가.
- `src/model/struct/macro_schedules.py`: 스케줄 CRUD, 대상 정규화, 토큰 검증, cron.d 파일 동기화, 예약 실행 로직 추가.
- `src/model/struct/cron_files.py`: `/etc/cron.d` 기본 경로와 env override 기반 cron 파일 쓰기/삭제 공통 로직 추가.
- `src/route/api-macro-schedule-run/`: cron이 호출하는 `/api/macros/schedules/run` 라우트 추가.
- `src/model/db/migrations/022_macro_schedules.sql`, `022_macro_schedules.down.sql`: `shell_macro_schedules` 테이블과 인덱스/트리거 추가.
- `src/model/struct/macros*.py`, `src/model/struct.py`: 매크로 목록의 스케줄 수/목록 노출, 삭제 시 cron 파일 정리, 스케줄 모델 접근 추가.
- `tests/api/test_server_macros.py`, `tests/api/test_migration_schema.py`: 매크로 스케줄 UI/API/모델/마이그레이션 정적 계약 갱신.

## 확인한 내용
- `wiz_project_build(clean=true)` 성공.
- `python -m py_compile src/model/struct/cron_files.py src/model/struct/macro_schedules.py src/model/struct/macros_shared.py src/model/struct/macros_store.py src/model/struct/macros.py src/app/page.macros/api.py src/route/api-macro-schedule-run/controller.py` 성공.
- `python -m unittest tests.api.test_server_macros.ServerMacrosStaticContractTest tests.api.test_migration_schema.MigrationSchemaStaticContractTest tests.api.test_backup_system_ui.BackupSystemUiStaticContractTest` 성공.
- `curl -b "season-wiz-project=main; season-wiz-devmode=true" http://127.0.0.1:3001/api/system/health` 200 응답 확인.
- `curl -X POST -b "season-wiz-project=main; season-wiz-devmode=true" http://127.0.0.1:3001/api/macros/schedules/run` 토큰 오류 응답 확인.

## 남은 리스크
- 실행 DB의 `schema_migrations`는 검증 시점에 021로 표시되어 022 마이그레이션 적용은 배포/운영 절차에서 필요하다.
- 기본 cron 파일 경로는 `/etc/cron.d`이며, 권한이 없는 런타임에서는 `DOCKER_INFRA_MACRO_CRON_DIR`로 쓰기 가능한 경로를 지정해야 한다.
