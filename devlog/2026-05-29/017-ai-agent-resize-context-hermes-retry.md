# AI Agent 패널 리사이즈와 Hermes 빈 응답 재시도 보강

- **ID**: 017
- **날짜**: 2026-05-29
- **유형**: 기능/안정성 보강

## 작업 요약
AI Agent 도킹 패널의 너비를 드래그로 조절할 수 있게 하고, 화면 표시명을 선택 Agent 종류와 무관하게 `AI Agent`로 통일했다.
컨텍스트 요약은 URL을 그대로 보여주지 않고 라우트 구조와 화면 텍스트를 기준으로 사용자가 읽기 쉬운 문구로 바꿨다.
스트림이 빈 본문으로 끝나거나 완료 이벤트 없이 끝나는 경우 동기 chat API로 한 번 재확인하는 fallback을 추가해 Hermes 빈 응답 체감 문제를 줄였다.

## 원문 요청사항
```text
에이전트 채팅창은 일단 width를 자유롭게 조정할 수 있어야 해.
그리고 사용자는 이게 헤르메스 에이전트인지, Codex 에이전트인지는 중요하지 않아. 그냥 화면 자체에서는 AI 에이전트라고만 일괄적으로 통일해서 표시하면 돼.
그리고 축약 컨텍스트 표시의 경우에는 라우팅 구조를 확인하고 URL 자체를 표시하지 말고 이미지 관리 상세 화면이면 "이미지 관리 . 서버 로컬 저장소 . local-master" 이런 식으로 실제 사용자가 확인하기 쉬운 정보로 표시를 해야해.
---
헤르메스 에이전트로 했더니 자꾸 AI Agent 응답 본문이 비어 있습니다. 라고 뜨고 답변이 없어. 왜 응답이 비어있는건지 현재 문제점을 확실하게 분석해서 실제 Agent가 동작하도록 개선해줘.
```

## 변경 파일 목록
- `src/angular/app/app.component.pug`: Agent 패널 resize handle 추가 및 dock width CSS 변수 바인딩.
- `src/angular/app/app.component.scss`: dock width CSS 변수, resize handle 스타일, 태블릿 이하 비활성 처리 추가.
- `src/angular/app/app.component.ts`: drag 기반 width 조절, 화면 표시명 `AI Agent` 통일, 사용자 친화 컨텍스트 요약 생성, 스트림 빈 응답 시 동기 호출 fallback 추가.
- `src/model/struct/ai_assistant.py`: 채팅 status/error 라벨을 `AI Agent` 기준으로 통일하고, 프롬프트에 빈 답변/대기 안내 금지 지시 추가.
- `devlog.md`, `devlog/2026-05-29/017-ai-agent-resize-context-hermes-retry.md`: 작업 이력 기록.

## 검증 결과
- `python -m py_compile src/model/struct/ai_assistant.py src/route/api-ai-agent/controller.py src/model/struct/codex_runtime.py` 성공.
- `wiz_project_build(clean=false)` 성공.
- Playwright 브라우저 테스트에서 `/images` 화면 Agent 패널 header가 `AI Agent`로 표시되는 것을 확인했다.
- resize handle 드래그 후 grid column이 `1020px 420px`에서 `926px 514px`로 변경되는 것을 확인했다.
- 이미지 상세 화면 컨텍스트가 `이미지 관리 . 서버 로컬 저장소 . local-master`로 표시되는 것을 확인했다.
- `오래된 이미지 정리 대상을 찾아줘` 실제 질문 실행 결과, 오류 없이 local-master 정리 대상 이미지 목록 답변이 표시되고 provider 표시도 `AI Agent`로 통일되는 것을 확인했다.

## 남은 리스크
- 컨텍스트 요약은 현재 주요 라우트 기준으로 매핑했다. 신규 상세 라우트가 추가되면 사용자용 문구 매핑을 추가해야 한다.
- Hermes CLI가 token 단위 실시간 출력을 직접 제공하지 않는 한, delta 표시는 최종 응답을 받은 뒤 나눠 보여주는 방식이다.
