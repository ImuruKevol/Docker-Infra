# AI Agent 스트림 멈춤과 빈 응답 표시 보강

- **ID**: 016
- **날짜**: 2026-05-29
- **유형**: 버그 수정

## 작업 요약
이미지 관리 화면에서 Agent 답변 후 UI가 계속 대기 상태처럼 보이는 문제를 브라우저로 재현했다.
SSE 종료 신호가 늦거나 누락될 때 프론트가 무한 대기하지 않도록 idle/max timeout 처리를 추가하고, 본문이 비어 있으면 일반 assistant 메시지가 아니라 error 메시지로 표시하도록 수정했다.
스트림 완료 후 `done` 이벤트도 함께 보내도록 보강했다.

## 원문 요청사항
```text
이미지 관리 화면에서 "오래된 이미지 정리 대상을 찾아줘" 라고 했더니 "서버들의 상태와 이미지를 분석하여 정리 대상을 확인하는 중입니다. 잠시만 기다려 주세요." 답변에서 멈춘 후 응답이 없어.
최소한 에러가 났으면 에러가 났다고 표시를 해주던가, 생각 중에 있으면 생각 과정을 표시를 해주던가 해야하는데 아직 제대로 동작하지 않는 것 같아.
실제 브라우저 화면을 기반으로 테스트해줘.
```

## 변경 파일 목록
- `src/angular/app/app.component.ts`: Agent 스트림 read에 1초 tick, 30초 idle timeout, 240초 max timeout, 빈 본문 error 표시, 불완전 스트림 status 메시지 처리를 추가.
- `src/model/struct/ai_assistant.py`: 채팅 스트림 완료 후 `done` 이벤트를 추가로 발행.
- `src/model/struct/codex_runtime.py`: 이전 작업의 안정 Agent home 고정 변경이 이번 검증에서 유지됨.
- `devlog.md`, `devlog/2026-05-29/016-ai-agent-stream-timeout-empty-response.md`: 작업 이력 기록.

## 검증 결과
- `python -m py_compile src/model/struct/ai_assistant.py src/route/api-ai-agent/controller.py src/model/struct/codex_runtime.py` 성공.
- `wiz_project_build(clean=false)` 성공.
- Playwright로 `/images` 실제 브라우저 화면에서 `오래된 이미지 정리 대상을 찾아줘` 추천 질문을 실행했다.
- 수정 전 재현: 답변 본문이 표시되어도 전송 상태가 끝나지 않는 상태를 확인했다.
- 수정 후 검증: 빈 본문 케이스가 일반 메시지가 아니라 `AI Agent 응답 본문이 비어 있습니다.` error 메시지로 표시되고, 입력 textarea가 다시 활성화되는 것을 확인했다.
- 같은 이미지 화면 기반 `/api/ai-agent/stream` 직접 호출에서는 `provider/status/heartbeat/delta/complete/done` 이벤트가 반환되고, 오래된 이미지 정리 후보 답변이 정상 delta로 수신되는 것을 확인했다.

## 남은 리스크
- Hermes/Gemini 응답은 동일 질문에서도 간헐적으로 빈 JSON 또는 빈 답변을 반환할 수 있다. UI는 더 이상 멈추지 않고 error로 표시하지만, 모델 출력 품질은 Agent 쪽 응답 안정성에 영향을 받는다.
- 현재 Hermes CLI가 token 단위 실시간 출력을 직접 제공하지 않아, 실제 delta는 최종 응답을 받은 뒤 UI 표시용으로 분할한 것이다.
