# AI Agent TODO 패널과 계획 후 TODO별 실행 흐름 분리

- **ID**: 014
- **날짜**: 2026-06-01
- **유형**: 기능 추가

## 작업 요약
AI Agent 대화 흐름을 먼저 사용자 요청의 개념적 TODO 목록을 생성하고, 이후 TODO 하나마다 별도 Agent 요청을 순차 실행하는 구조로 변경했다.
TODO 진행 상태는 Response 카드 뒤의 상태 메시지가 아니라 메시지 입력 영역 위의 전용 TODO 패널에서 대기/진행/완료/실패로 갱신되도록 정리했다.

## 원문 요청사항
```text
# ReviewOps Codex 작업 요청

아래 요청을 현재 프로젝트 루트에서 처리하세요. 필요한 파일을 직접 수정하고, 마지막 응답은 한국어로 간결하게 작성하세요.
스트리밍 응답은 사용하지 않습니다. 작업이 끝난 뒤 변경 요약, 확인한 내용, 남은 리스크만 정리하세요.
이 작업의 세션 단위는 아래 리뷰 ID입니다. 리뷰 ID가 같으면 같은 Codex 히스토리 맥락으로 이어서 처리하세요.

## 사용자 요청

첨부한 스크린샷에 보면 Response 카드 이후로 동작들이 쭉 전부 나오는데, VS Code의 copilot처럼 메시지 입력 부분 위에 todo list가 리스팅되고, 실제 동작 수행 시 그 리스트의 상태가 변경되도록 해줘.
그리고 ai agent 플로우를 나눠야 해. 첫 번째로 사용자 요청에 대한 todo list를 만들어서 먼저 화면에 반영하고, 그 다음으로 todo에 따라 순차적으로 ai agent에 todo 하나당 요청 하나를 하는 식으로 플로우가 정리되어야 해. 이러면 내가 실행했던 "마스터 노드에서 서버 상태 한눈에 보기 매크로를 실행해줘" 요청의 경우엔 현재는 todo가 2개(서버 관리 화면으로 이동, 마스터 노드에서 서버 상태 한눈에 보기 매크로 실행)로 작성이 되는데, 하나의 todo로 묶여야겠지. 그러니까 todo는 하나의 개념적인 묶음으로 구성이 되어야 해. todo 하나에 많은 이벤트가 있을 수도 있는거고.

## 리뷰 요약

- 리뷰 ID: aeojkqoyoqbsrltxovfwocnihdufgnfd
- 제목: AI Agent 동작 개선
- 요청 링크: https://infra-dev.nanoha.kr/dashboard
- Codex 요청자: 권태욱
- 프로젝트 루트: /root/docker-infra
- Codex 세션 ID: 019e8224-b26d-7350-889f-ca2efaf4ea2d
- 스크린샷 컨텍스트: 없음
- 에이전트 작업 지시서 컨텍스트: 없음
- HTML 문서 생성 규칙 컨텍스트: 없음
- HTML 문서 설정 컨텍스트: 없음
- HTML 프로젝트 인스트럭션 파일: 없음
- 첨부파일 컨텍스트: 1개

## 세션 처리

저장된 Codex 세션을 resume해 이전 대화 맥락을 우선 사용하세요. 이전 Codex 히스토리는 이 요청에 포함되지 않습니다.


## 첨부파일 컨텍스트

선택한 첨부파일은 Codex 작업 서버의 아래 경로에서 사용할 수 있습니다.

- 스크린샷 2026-06-01 오후 5.43.18.png (리뷰 첨부, image/png, 208.6KB): `/tmp/reviewops-codex-efc452e733db4ff785b351129c7c2ac7/attachments/01-스크린샷 2026-06-01 오후 5.43.18.png`
```

## 변경 파일 목록
- `src/model/struct/ai_assistant.py`
  - `/api/ai-agent/plan`에서 사용할 TODO 계획 생성 로직과 프롬프트를 추가.
  - 마스터 노드 서버 상태 매크로 실행 요청은 하나의 개념적 TODO로 묶이도록 내장 계획을 추가.
  - 실행 응답에서는 TODO 목록을 반복하지 않고 현재 TODO 결과만 설명하도록 조정.
- `src/route/api-ai-agent/controller.py`
  - `plan` API 경로를 연결.
- `src/angular/app/app.component.ts`
  - 사용자 요청 → TODO 계획 → TODO별 Agent 요청 → action 실행 순서로 플로우를 분리.
  - action 진행 상태를 채팅 메시지 대신 TODO 항목의 detail/status에 반영.
- `src/angular/app/app.component.pug`
  - 메시지 입력 영역 위에 TODO 패널을 추가.
- `src/angular/app/app.component.scss`
  - TODO 패널과 상태별 스타일을 추가.
- `tests/api/test_ai_agent_history.py`
  - TODO 계획 API, TODO 패널, TODO별 실행 흐름 정적 계약을 보강.
- `docs/api/openapi.json`
  - AI Agent TODO 계획 API 경로와 응답 스키마를 문서화.

## 검증 결과
- 성공: 첨부 스크린샷 확인.
- 성공: `/opt/conda/envs/docker-infra/bin/python -m unittest tests/api/test_ai_agent_history.py`
- 성공: `/opt/conda/envs/docker-infra/bin/python -m py_compile src/model/struct/ai_assistant.py src/route/api-ai-agent/controller.py`
- 성공: `/opt/conda/envs/docker-infra/bin/python -m json.tool docs/api/openapi.json >/tmp/openapi-check.json`
- 성공: `git diff --check -- docs/api/openapi.json src/model/struct/ai_assistant.py src/route/api-ai-agent/controller.py src/angular/app/app.component.ts src/angular/app/app.component.pug src/angular/app/app.component.scss tests/api/test_ai_agent_history.py`
- 성공: `wiz_project_build(projectName="main", clean=false)`
- 참고: `/opt/conda/envs/docker-infra/bin/python -m unittest tests/api/test_ai_agent_history.py tests/api/test_openapi_contract.py`는 `openapi_validator` 모듈이 현재 환경에 없어 `test_openapi_contract.py` import 단계에서 실패.
