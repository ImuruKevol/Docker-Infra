# 서비스 생성/수정 AI를 수정된 Codex CLI 직접 실행 플로우로 전환

- 날짜: 2026-05-12
- ID: 137
- 리뷰 ID: hufvrianlhobxsyvrorjmbvwffdkjioy

## 사용자 원문 요청

이 Docker Infra에서 서비스 생성 및 수정 시 AI 동작이 변경한 codex 소스코드를 사용하는 방식으로 수정해줘. 로직, 플로우 등 전부 변경한 codex쪽에 맞는 로직으로 변경해야해.

## 변경 파일

- `src/model/struct/codex_runtime.py`
- `src/model/struct/ai_assistant.py`
- `src/model/struct.py`
- `tools/codex_responses_gateway.py` 삭제
- `devlog.md`
- `devlog/2026-05-12/137-codex-cli-direct-ai-runtime.md`

## 변경 내용

- 서비스 생성과 서비스 수정 AI 생성 경로가 OpenAI/Gemini/Ollama API를 직접 호출하지 않고 수정된 Codex CLI를 실행하도록 전환했다.
- `codex exec --json --ephemeral --model-provider ... -m ...` 실행에 맞춰 임시 `CODEX_HOME`, provider별 `config.toml`, 선택 모델, 토큰 환경변수, Docker Infra MCP 설정을 구성하도록 정리했다.
- 이전 Python 기반 Codex Responses 게이트웨이 파일과 `ai_assistant`의 provider별 직접 HTTP 호출/스트리밍 구현을 제거했다.
- 스트리밍 API는 기존 SSE 계약을 유지하면서 Codex 최종 응답을 검증/적용하는 방식으로 연결했고, MCP 컨텍스트 생성에 WIZ env가 전달되도록 맞췄다.

## 확인 결과

- `python -m py_compile project/main/src/model/struct/codex_runtime.py project/main/src/model/struct/ai_assistant.py project/main/tools/docker_infra_mcp.py` 성공.
- 기존 게이트웨이/직접 provider 호출 문자열 검색 결과 대상 파일에서 잔존 항목 없음.
- `wiz_project_build(clean=false)` 성공.
- `pkg-config` 및 `libssl-dev`를 설치해 OpenSSL 탐색 실패는 해소했다.
- `cargo build --release -p codex-cli`는 `codex-core` 릴리스 컴파일 중 rustc가 SIGKILL로 종료되어 산출물을 만들지 못했다.
- `cargo build -p codex-cli -j 1` debug 빌드도 시도했지만 요청 재진입으로 빌드 프로세스가 중단되었고 현재 release/debug Codex 바이너리는 없다. 실제 AI 호출은 `/root/docker-infra/codex/codex-rs` 빌드 완료 또는 `DOCKER_INFRA_CODEX_BIN` 지정 후 가능하다.
