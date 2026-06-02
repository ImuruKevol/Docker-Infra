# AI Agent 세션 기반 대화 지속과 히스토리 그룹화 추가

## 사용자 요청

- Review ID: `reviburmqyukneaulcnwasygrezixzav`
- 요청: 같은 채팅창에서 이어서 요청해도 AI Agent 히스토리가 별개로 남지 않도록, Codex/Claude Code의 세션 개념을 UI와 백엔드에 agent별로 활용하도록 개선.

## 변경 파일

- `src/model/db/migrations/021_ai_agent_history.sql`
- `src/model/struct/ai_history.py`
- `src/route/api-ai-agent/controller.py`
- `src/model/struct/ai_assistant.py`
- `src/model/struct/codex_runtime.py`
- `src/angular/app/app.component.ts`
- `src/angular/app/app.component.pug`
- `src/angular/app/app.component.scss`
- `tests/api/test_ai_agent_history.py`
- `devlog.md`
- `devlog/2026-06-01/013-ai-agent-session-continuation.md`

## 작업 내용

- AI Agent 히스토리에 `session_id`, `provider_session_id`, `session_title`, `turn_index`를 저장하도록 스키마와 ensure-table 로직을 확장했다.
- 히스토리 목록을 세션 단위로 조회하고, 세션 상세에서 여러 turn을 시간순으로 볼 수 있는 API를 추가했다.
- UI에서 agent별 활성 세션 ID를 localStorage에 유지하고, 새 세션 버튼으로 대화 컨텍스트를 분리하도록 했다.
- Codex 실행은 세션 파일을 유지하고 저장된 provider 세션 ID가 있으면 `codex exec resume`을 사용하도록 연결했다.
- Claude Code 실행은 세션 UUID를 `--session-id`/`--resume` 인자로 전달할 수 있도록 명령 템플릿을 확장했다.

## 확인

- `python -m py_compile src/model/struct/ai_history.py src/model/struct/ai_assistant.py src/model/struct/codex_runtime.py src/route/api-ai-agent/controller.py`
- `python -m unittest tests.api.test_ai_agent_history`
- `python -m unittest tests.api.test_migration_schema tests.api.test_ai_agent_history`
- `wiz_project_build(projectName="main", clean=false)`

## 남은 리스크

- 실제 Codex/Claude CLI 세션 재개는 설치된 CLI와 로그인 상태가 필요한 런타임 검증 영역이라 정적/빌드 검증까지만 수행했다.
