# 133. AI 서비스 생성 스트림 heartbeat 전달 누락 수정

## 요청

- 원 요청: "만약 timeout 관련 문제라면 ollama로 호출 시에는 생성해야하는 output을 쪼개서 첫 번재 요청에서 일부 output을 받고, 다음 요청에서 다른 부분 output을 받고 하는 설계를 생각해볼 것. 아니라면 에러 원인을 파악해서 수정할 것."
- 리뷰 ID: `lvzxjnujqysqobymwcncwklhsvxssxoq`

## 변경 파일

- `src/model/struct/ai_assistant.py`
- `devlog.md`
- `devlog/2026-05-12/133-ai-service-stream-heartbeat-forwarding.md`

## 원인

- 로컬 Ollama 장시간 생성 대기를 위해 `_iter_with_heartbeat()`가 15초마다 `heartbeat` 이벤트를 만들고 있었지만, `_stream_json_with_provider()`가 `delta` 이벤트만 클라이언트로 전달하고 `heartbeat`를 버리고 있었다.
- 그 결과 첫 토큰 생성 전 또는 provider 응답이 잠시 멈춘 동안 SSE 응답이 유휴 상태가 되어 프록시/브라우저에서 `network error`로 끊길 수 있었다.
- 스크린샷의 `0자` 상태는 output 토큰 초과보다 첫 토큰 전 유휴 연결 종료 가능성이 더 높다.

## 작업 내용

- AI provider stream 루프에서 `heartbeat` 이벤트를 SSE 이벤트로 그대로 전달하도록 수정했다.
- 기존 output 생성/검증 계약과 Ollama 요청 timeout 값은 유지했다.

## 확인

- `/opt/conda/envs/docker-infra/bin/python -m py_compile src/model/struct/ai_assistant.py` 성공
- `git diff --check` 성공
- WIZ `wiz_project_build(projectName="main", clean=false)` 성공

## 남은 리스크

- 실제 Ollama 모델 실호출은 현재 환경의 AI 설정, 모델 로딩 시간, 노드 상태에 의존하므로 브라우저에서 재현 검증하지 못했다.
- heartbeat로 유휴 연결 종료는 방지하지만, 모델 자체가 900초 안에 완료하지 못하거나 JSON을 끝까지 생성하지 못하면 provider timeout 또는 JSON 검증 오류로 표시될 수 있다.
