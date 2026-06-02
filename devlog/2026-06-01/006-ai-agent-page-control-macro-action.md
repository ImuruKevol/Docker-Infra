# AI Agent 화면 제어 액션과 서버 상태 매크로 생성 명령 연결

- **ID**: 006
- **날짜**: 2026-06-01
- **유형**: 기능 추가

## 작업 요약
AI Agent가 답변만 표시하지 않고 브라우저 화면 액션을 순서대로 실행할 수 있도록 액션 실행기를 확장했다.
특히 "서버 상태를 한눈에 확인할 수 있는 매크로를 추가해줘" 요청은 `/macros` 화면으로 이동한 뒤 `macro.create_global` 페이지 명령을 실행해 전역 매크로를 생성하거나 같은 이름의 기존 매크로를 갱신한다.

## 원문 요청사항
```text
# ReviewOps Codex 작업 요청

아래 요청을 현재 프로젝트 루트에서 처리하세요. 필요한 파일을 직접 수정하고, 마지막 응답은 한국어로 간결하게 작성하세요.
스트리밍 응답은 사용하지 않습니다. 작업이 끝난 뒤 변경 요약, 확인한 내용, 남은 리스크만 정리하세요.
이 작업의 세션 단위는 아래 리뷰 ID입니다. 리뷰 ID가 같으면 같은 Codex 히스토리 맥락으로 이어서 처리하세요.

## 사용자 요청

작업 시작

## 리뷰 요약

- 리뷰 ID: wsymtidsrimcycxuxkiohaxivncfmbix
- 제목: AI Agent 기능 개선
- 요청 링크: https://infra-dev.nanoha.kr/dashboard
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

# 에이전트 작업 지시서

## 리뷰 정보

- 리뷰 ID: wsymtidsrimcycxuxkiohaxivncfmbix
- 제목: AI Agent 기능 개선
- 상태: open
- 우선순위: high
- 분류: design
- 프로젝트: Docker Infra DEV
- 프로젝트 종류: web_service
- 요청 링크: https://infra-dev.nanoha.kr/dashboard
- 화면: 1440x900
- 캡처 방식: browser-display-capture-element
- 스크린샷 첨부: yes
- 리뷰 첨부 파일: 0개

## 리뷰어 요청 내용

현재 AI Agent에 채팅을 하면 그냥 답변만 해주고 있음. 간단한 화면 이동은 할 수 있는 것 같은데, 제일 필요한 기능이 동작하지 않음.
"서버 상태를 한눈에 확인할 수 있는 매크로를 추가해줘" 라고 채팅을 치면 AI Agent가 직접 화면 이동 및 컨트롤을 하면서 실제 이 서비스를 컨트롤할 수 있어야 함. 모든 화면에 대해 이런 동작을 할 수 있도록 분석하고 기능을 추가해줘.
```

## 변경 파일 목록
- `src/model/struct/ai_assistant.py`
  - `app_event`, `wait` 액션 계약을 추가하고, 이동 후 의미 기반 대상 또는 페이지 명령을 사용할 수 있도록 Agent 프롬프트를 보강했다.
  - 서버 상태 매크로 생성 요청을 내장 명령으로 감지해 `/macros` 이동과 `macro.create_global` 실행 액션을 반환하도록 했다.
- `src/angular/app/app.component.ts`
  - Agent 액션을 순차 실행하고, 라우트 이동 후 대기, 의미 기반 요소 탐색, 페이지 이벤트 디스패치를 지원하도록 확장했다.
  - 삭제, 초기화, 종료 등 되돌리기 어려운 액션은 프론트 실행기에서 추가로 차단하도록 했다.
- `src/app/page.macros/view.ts`
  - `docker-infra-agent-action` 이벤트를 수신해 `macro.create_global` 명령으로 전역 매크로를 생성하거나 기존 동일 이름 매크로를 갱신하도록 연결했다.
- `tests/api/test_ai_agent_history.py`
  - AI Agent 페이지 제어 액션 계약과 매크로 페이지 명령 핸들러 정적 검증을 추가했다.
- `devlog.md`, `devlog/2026-06-01/006-ai-agent-page-control-macro-action.md`
  - 작업 이력을 기록했다.

## 검증 결과
- `/opt/conda/envs/docker-infra/bin/python -m py_compile src/model/struct/ai_assistant.py tests/api/test_ai_agent_history.py` 성공.
- `/opt/conda/envs/docker-infra/bin/python -m unittest tests.api.test_ai_agent_history.AIAgentHistoryStaticContractTest` 성공.
- `wiz_project_build(clean=false, projectName=main)` 성공.
- `git diff --check -- src/model/struct/ai_assistant.py src/angular/app/app.component.ts src/app/page.macros/view.ts tests/api/test_ai_agent_history.py devlog.md devlog/2026-06-01/006-ai-agent-page-control-macro-action.md` 성공.
- 쿠키 `season-wiz-project=main`, `season-wiz-devmode=true`를 포함한 로컬 API/UI curl 검증을 시도했으나, 현재 로컬 `127.0.0.1:3000`은 미실행, `127.0.0.1:80`/`:5000`은 해당 WIZ 라우트 404로 실제 브라우저 동작 검증은 수행하지 못했다.
