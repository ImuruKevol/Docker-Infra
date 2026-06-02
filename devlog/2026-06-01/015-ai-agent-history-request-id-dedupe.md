# AI Agent stream/fallback 히스토리 중복 기록 방지

- **ID**: 015
- **날짜**: 2026-06-01
- **유형**: 버그 수정

## 작업 요약
AI Agent UI가 stream 응답 뒤 fallback chat을 호출하는 경우 같은 사용자 요청이 히스토리에 두 번 저장되던 리스크를 보완했다.
프론트엔드에서 TODO 실행마다 `request_id`를 생성해 stream/fallback 요청에 동일하게 전달하고, 백엔드 히스토리 저장 시 같은 Agent와 `request_id` 조합은 기존 행을 재사용하도록 멱등 처리했다.

## 원문 요청사항
```text
남은 리스크를 보완해줘.
```

## 변경 파일 목록
- `src/angular/app/app.component.ts`
  - TODO별 Agent 실행 payload에 `request_id`를 포함.
  - 브라우저 `crypto.randomUUID()` 기반 요청 ID 생성 helper 추가.
- `src/route/api-ai-agent/controller.py`
  - `/api/ai-agent/*` 요청 body에 `request_id`/`idempotency_key` 전달 추가.
- `src/model/struct/ai_history.py`
  - `request_id` 컬럼 ensure-table, 정규화, CSV/export row 노출 추가.
  - 동일 `agent_type + request_id` 기존 행을 `FOR UPDATE`로 잠그고 중복 insert를 방지.
  - 기존 실패 행이 같은 request_id의 성공 응답으로 재호출되면 같은 행을 성공 상태로 갱신.
- `src/model/db/migrations/021_ai_agent_history.sql`
  - `request_id` 컬럼과 부분 인덱스 추가.
- `tests/api/test_ai_agent_history.py`
  - request_id 전달/멱등 기록 정적 계약 추가.
- `tests/api/test_migration_schema.py`
  - migration의 `request_id` 컬럼 계약 추가.
- `devlog.md`
- `devlog/2026-06-01/015-ai-agent-history-request-id-dedupe.md`

## 검증 결과
- 성공: `python -m py_compile src/model/struct/ai_history.py src/route/api-ai-agent/controller.py`
- 성공: `python -m unittest tests.api.test_ai_agent_history tests.api.test_migration_schema`
- 성공: `wiz_project_build(projectName="main", clean=false)`
- 성공: DEV 번들 `https://infra-dev.nanoha.kr/main.js`에서 `request_id`와 `createAgentRequestId` 반영 확인.
- 성공: 실제 브라우저 검증에서 2개 사용자 요청이 stream 2회 + fallback chat 2회로 호출됐지만 히스토리는 2턴만 저장됨 확인.
- 성공: 같은 세션의 두 히스토리 턴이 동일 provider 세션 ID를 사용하고 두 번째 턴의 `session_resumed=true` 확인.

## 남은 리스크
- fallback 호출 자체는 아직 발생한다. 이번 수정은 fallback이 발생해도 히스토리가 중복 저장되지 않도록 멱등 처리한 범위다.
