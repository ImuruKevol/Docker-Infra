# AI Agent 히스토리 저장·다운로드·삭제 관리 추가

- **ID**: 002
- **날짜**: 2026-06-01
- **유형**: 개선

## 작업 요약
AI Agent 대화 이력을 Agent 종류와 무관한 공통 포맷으로 자동 저장하도록 추가했다.
저장된 히스토리는 전역 AI Agent 패널의 히스토리 모드에서 조회, 단건 삭제, 기간 삭제, JSON/CSV 다운로드가 가능하도록 연결했다.
히스토리 메타데이터에는 요청 IP, User-Agent 기반 브라우저/플랫폼, 화면 경로와 화면 요약을 포함했다.

## 원문 요청사항
```text
당연하지만 히스토리 내용을 다운로드받을 수 있는 기능과 기간으로 삭제하거나 그냥 단건을 삭제할 수 있는 기능이 필요함.
그리고 히스토리엔 IP, 브라우저 종류 등 메타데이터도 포함되어야 함.
```

## 변경 파일 목록
- `src/model/db/migrations/021_ai_agent_history.sql`: `ai_agent_histories` 테이블, 조회 인덱스, updated_at 트리거 추가.
- `src/model/db/migrations/021_ai_agent_history.down.sql`: 히스토리 테이블 롤백 추가.
- `src/model/struct/ai_history.py`: 히스토리 저장소, 조회, 상세, 단건 삭제, 기간 삭제, JSON/CSV export 구현.
- `src/model/struct.py`: `ai_history` struct 접근자 추가.
- `src/model/struct/ai_assistant.py`: 일반/스트리밍 채팅 성공·실패 자동 기록 연결.
- `src/route/api-ai-agent/controller.py`: 히스토리 조회, 상세, 다운로드, 단건/기간 삭제 API와 IP/User-Agent 메타데이터 수집 추가.
- `src/angular/app/app.component.ts`: 히스토리 패널 상태, 조회/다운로드/삭제 동작 추가.
- `src/angular/app/app.component.pug`: AI Agent 패널에 대화/히스토리 전환과 관리 UI 추가.
- `src/angular/app/app.component.scss`: 히스토리 관리 UI 스타일과 다크모드 스타일 추가.
- `tests/api/test_ai_agent_history.py`: 히스토리 저장소/API/UI 정적 계약 테스트 추가.
- `tests/api/test_migration_schema.py`: 021 마이그레이션과 `ai_agent_histories` 테이블 계약 반영.
- `devlog.md`, `devlog/2026-06-01/002-ai-agent-history-management.md`: 작업 이력 기록.

## 검증 결과
- `/opt/conda/envs/docker-infra/bin/python -m unittest tests.api.test_ai_agent_history tests.api.test_migration_schema.MigrationSchemaStaticContractTest` 성공.
- `/opt/conda/envs/docker-infra/bin/python -m py_compile src/model/struct/ai_history.py src/model/struct/ai_assistant.py src/route/api-ai-agent/controller.py` 성공.
- `git diff --check` 대상 파일 검사 성공.
- `wiz_project_build(clean=false)` 성공.
