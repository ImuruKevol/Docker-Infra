# AI Agent TODO 기반 순차 매크로 실행 개선

- **ID**: 012
- **날짜**: 2026-06-01
- **유형**: 기능 추가

## 작업 요약
AI Agent가 화면 조작 액션을 실행하기 전에 TODO 목록을 만들고, 각 항목을 순서대로 실행하며 진행/완료/실패 상태를 남기도록 개선했다.
`마스터 노드에서 서버 상태 한눈에 보기 매크로를 실행해줘` 요청은 전역 매크로 보장, 서버 화면 이동, 마스터 노드 선택, 매크로 실행까지 하나의 연속 동작으로 수행하도록 연결했다.

## 원문 요청사항
```text
# ReviewOps Codex 작업 요청

아래 요청을 현재 프로젝트 루트에서 처리하세요. 필요한 파일을 직접 수정하고, 마지막 응답은 한국어로 간결하게 작성하세요.
스트리밍 응답은 사용하지 않습니다. 작업이 끝난 뒤 변경 요약, 확인한 내용, 남은 리스크만 정리하세요.
이 작업의 세션 단위는 아래 리뷰 ID입니다. 리뷰 ID가 같으면 같은 Codex 히스토리 맥락으로 이어서 처리하세요.

## 사용자 요청

아마 Codex나 클루드 코드의 경우엔 따로 요청 없이도 알아서 작업 지시서 내용처럼 해줄 것 같긴 한데, 확인은 필요해. 일단 헤르메스 agent에서는 자동으로 해주진 않은 것으로 보여.
작업 진행해줘.

## 리뷰 요약

- 리뷰 ID: aeojkqoyoqbsrltxovfwocnihdufgnfd
- 제목: AI Agent 동작 개선
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

- 리뷰 ID: aeojkqoyoqbsrltxovfwocnihdufgnfd
- 제목: AI Agent 동작 개선
- 상태: in_progress
- 우선순위: high
- 분류: design
- 프로젝트: Docker Infra DEV
- 프로젝트 종류: web_service
- 요청 링크: https://infra-dev.nanoha.kr/dashboard
- 화면: 1440x900
- 캡처 방식: reviewops-sdk-screenshot-unavailable
- 스크린샷 첨부: no
- 리뷰 첨부 파일: 0개

## 리뷰어 요청 내용

"마스터 노드에서 서버 상태 한눈에 보기 매크로를 실행해줘" 라고 하면 AI Agent에서는 서버 관리 화면으로만 이동하고, 실제 매크로는 실행을 하지 않고 있어.
이에 대해 개선을 해야하는데, 일단 AI Agent가 사용자의 요청에 대해 todo list를 만들도록 해야해. 그리고 그 todo list를 하나씩 수행하면서 위의 예시와 같은 연속된 동작을 요구할 시 순서대로 모두 실행을 할 수 있도록 구조적인 개선을 진행해줘.
```

## 변경 파일 목록
- `src/model/struct/ai_assistant.py`
  - 마스터 노드 서버 상태 매크로 실행 요청을 내장 인식하고, TODO 형식 답변과 `/servers` 이동 후 `server.run_macro` app_event 액션을 반환하도록 추가.
  - 일반 AI Agent 프롬프트에 TODO 작성과 `server.run_macro` 순차 실행 지침을 추가.
- `src/angular/app/app.component.ts`
  - client action 실행 전에 실행 TODO를 만들고, 각 액션의 진행/완료/실패 상태를 순서대로 기록하도록 변경.
  - app_event/API/action 실패가 전체 채팅 흐름을 끊지 않고 해당 TODO 실패로 표시되도록 조정.
- `src/app/page.servers/view.ts`
  - 서버 화면에서 `server.run_macro` Agent app_event를 수신해 마스터 노드 선택, 매크로 탭 이동, 전역 매크로 생성/갱신, 실행까지 수행하도록 추가.
- `tests/api/test_ai_agent_history.py`
  - AI Agent TODO 실행기와 서버 매크로 app_event 연결에 대한 정적 계약 검증을 보강.
- `devlog.md`, `devlog/2026-06-01/012-ai-agent-todo-sequential-macro-run.md`
  - 이번 변경 이력을 기록.

## 검증 결과
- 성공: `/opt/conda/envs/docker-infra/bin/python -m unittest tests/api/test_ai_agent_history.py`
- 성공: `/opt/conda/envs/docker-infra/bin/python -m py_compile src/model/struct/ai_assistant.py`
- 성공: `wiz_project_build(projectName="main", clean=false)`
- 참고: `/opt/conda/envs/docker-infra/bin/python -m unittest tests/api/test_ai_agent_history.py tests/api/test_server_macros.py`는 `tests/api/test_server_macros.py`의 기존 정적 계약이 `src/app/page.servers/view.pug` 내 `nu-monaco-editor` 문자열을 기대하지만 현재 파일에 없어 실패했다. 해당 Pug 파일은 이번 작업에서 수정하지 않았다.
