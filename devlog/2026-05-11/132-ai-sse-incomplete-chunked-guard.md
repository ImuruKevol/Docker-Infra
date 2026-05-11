# 132. AI SSE chunked 응답 중단 방어

## 요청

- 원 요청: "`/wiz/api/page.services.create/stream_service_ai:1 Failed to load resource: net::ERR_INCOMPLETE_CHUNKED_ENCODING` 위 에러가 떴어."
- 리뷰 ID: `xtcbgryxpepnvqtdzhdyttxeyboggbcp`

## 변경 파일

- `src/app/page.services.create/api.py`
- `src/app/page.services/api.py`
- `devlog.md`
- `devlog/2026-05-11/132-ai-sse-incomplete-chunked-guard.md`

## 원인

- SSE 응답이 시작된 뒤 이벤트 생성 중 예외가 밖으로 전파되면 chunked 응답이 정상 종료되지 않아 브라우저에서 `ERR_INCOMPLETE_CHUNKED_ENCODING`으로 보일 수 있었다.
- hop-by-hop 성격의 `Connection: keep-alive` 헤더는 프록시 환경에서 이득보다 혼선을 줄 수 있어 제거하고, heartbeat 이벤트로 연결 유지를 맡기도록 정리했다.

## 작업 내용

- 서비스 생성/수정 AI SSE generator에 시작/종료 comment frame을 추가했다.
- 이벤트 직렬화 실패와 stream 생성 중 예외를 SSE `error` 이벤트로 변환해 응답이 정상적으로 닫히도록 방어했다.
- 클라이언트 연결 종료 계열 예외는 추가 오류 없이 종료하도록 처리했다.

## 확인

- `py_compile`로 `src/model/struct/ai_assistant.py`, `src/app/page.services.create/api.py`, `src/app/page.services/api.py` 문법 확인 성공
- WIZ `wiz_project_build(projectName="main", clean=false)` 성공
- `git diff --check` 문제 없음

## 남은 리스크

- 브라우저에서 실제 로컬 모델 장시간 생성 요청을 재현하는 검증은 하지 못했다.
