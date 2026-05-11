# 131. 로컬 AI 서비스 생성 스트림 장시간 대기 보강

## 요청

- 원 요청: "ai 로컬 모델을 사용해서 서비스 생성을 할 때 시간이 너무 오래걸려서 그런지 network error가 뜨고 있어. 원인을 파악하고 수정해줘"
- 리뷰 ID: `xtcbgryxpepnvqtdzhdyttxeyboggbcp`

## 변경 파일

- `src/model/struct/ai_assistant.py`
- `src/app/page.services.create/api.py`
- `src/app/page.services/api.py`
- `devlog.md`
- `devlog/2026-05-11/131-local-ai-service-stream-timeout.md`

## 원인

- 로컬 Ollama 모델은 모델 로딩이나 첫 토큰 생성이 오래 걸릴 수 있는데, AI provider stream을 읽는 동안 브라우저로 추가 SSE 이벤트가 나가지 않아 프록시/브라우저가 유휴 연결로 판단할 수 있었다.
- provider stream socket timeout도 120초로 고정되어 있어, 느린 로컬 모델에서 응답이 끊길 가능성이 있었다.

## 작업 내용

- AI stream provider 읽기를 background thread + queue로 감싸고, provider 응답이 늦어질 때 15초마다 `heartbeat` SSE 이벤트를 내보내도록 했다.
- streaming provider timeout을 900초로 늘리고, Ollama non-stream/stream 요청에도 900초 timeout을 적용했다.
- 서비스 생성/수정 SSE 응답에 `Connection: keep-alive` 헤더를 추가했다.

## 확인

- `py_compile`로 `src/model/struct/ai_assistant.py`, `src/app/page.services.create/api.py`, `src/app/page.services/api.py` 문법 확인 성공
- WIZ `wiz_project_build(projectName="main", clean=false)` 성공
- `git diff --check` 문제 없음

## 남은 리스크

- 실제 로컬 Ollama 모델 호출은 환경의 모델/토큰/노드 설정에 의존하므로 실호출까지는 검증하지 않았다.
