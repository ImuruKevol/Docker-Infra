# AI Agent 런타임 진행 스트리밍과 TODO 계획 생성 개선

## 사용자 요청

작업 시작

리뷰 ID: `buqanzpqiscxrtoaakdvceufhfxqhhlz`

리뷰 내용:
- AI Agent가 템플릿 생성 중 15초마다 "Agent가 MCP 조회와 응답 생성을 계속 진행 중입니다." 같은 대기 문구만 표시하지 말고, 중간 진행 과정을 스트리밍으로 보여야 한다.
- TODO 생성이 사용자 원문을 그대로 표시하지 말고, 실제 요청 의도에 맞는 실행 TODO로 정리되어야 한다.
- 예: "방금 만든 템플릿에서 nginx 설치 과정은 필요 없어. 헬스체크도 필요 없고. 그리고 여기에 mariadb도 사용할 수 있도록 추가해줘."는 nginx 설치 제거, 헬스체크 제거, MariaDB 지원 추가처럼 작업 항목화되어야 한다.

## 변경 파일

- `src/model/struct/codex_runtime.py`
  - Codex CLI `--json` stdout 이벤트를 실행 중에 읽는 `complete_json_stream` 경로를 추가했다.
  - 대형 prompt stdin 쓰기와 stdout/stderr 읽기를 분리해 스트림 이벤트가 막히지 않도록 처리했다.
- `src/model/struct/ai_assistant.py`
  - 채팅/템플릿 AI 스트림에서 15초 heartbeat 문구를 제거하고 Codex 런타임 이벤트를 `thinking` 진행 요약으로 변환한다.
  - TODO 계획 단계에서 AI Agent 계획 호출을 사용하고, 원문 복사형 결과는 의도 기반 fallback TODO로 보정한다.
- `src/app/page.templates/view.ts`
  - 템플릿 생성 진행 목록에서 heartbeat 이벤트를 표시하지 않도록 정리했다.
- `src/app/page.templates/view.pug`
  - heartbeat 표시용 스피너 조건을 제거했다.
- `src/angular/app/app.component.ts`
  - `/api/ai-agent/plan` 실패 시에도 원문 TODO 하나로 fallback하지 않고 변경 의도를 추출해 TODO를 만든다.
- `tests/api/test_wiz_structure_contract.py`
  - AI Agent 진행 스트림 계약 검증을 heartbeat 메서드 기준에서 런타임 스트리밍 기준으로 갱신했다.

## 확인 결과

- `/opt/conda/envs/docker-infra/bin/python -m py_compile src/model/struct/ai_assistant.py src/model/struct/codex_runtime.py tests/api/test_wiz_structure_contract.py` 통과.
- `/opt/conda/envs/docker-infra/bin/python -m unittest tests.api.test_wiz_structure_contract.WizStructureContractTest.test_ai_agent_progress_lines_do_not_hide_missing_answer` 통과.
- `wiz_project_build(projectName=main, clean=false)` 통과.
- `tests.api.test_wiz_structure_contract` 전체 실행은 기존 워크트리 상태의 비관련 계약 실패로 실패했다. 확인된 실패 범위는 대형 model 파일 300줄 제한, 도메인 상세 route 기대값, 서버 레이아웃 기대값, `page.servers/api.py` try/except 응답 패턴 등이며 이번 변경 검증 대상은 단일 테스트로 분리해 통과 확인했다.
