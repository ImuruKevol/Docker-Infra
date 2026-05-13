# Codex 기반 AI 실행 게이트웨이와 Docker Infra MCP 추가

- 날짜: 2026-05-12
- 작업 번호: 136
- 리뷰 ID: hufvrianlhobxsyvrorjmbvwffdkjioy

## 사용자 원 요청

Codex 소스코드가 GPT 모델만 연동되는 구조라 다른 모델도 연동할 수 있도록 바꾸고, 다른 모델 사용 시 별도 로그인 없이 현재 서비스에 등록된 AI 모델 정보를 선택할 수 있게 한 뒤, 선택한 모델의 모든 AI 호출이 Codex를 통해 이루어지도록 요청했다. 또한 Docker 이미지 탐색, 등록 서버 정보 수집, 에러 로그 수집, SSH 명령 호출 등을 수행할 MCP를 Codex에 붙여 달라고 요청했다.

## 변경 파일

- `src/model/struct.py`
- `src/model/struct/ai_assistant.py`
- `src/model/struct/codex_runtime.py`
- `tools/codex_responses_gateway.py`
- `tools/docker_infra_mcp.py`
- `devlog.md`
- `devlog/2026-05-12/136-codex-ai-gateway-mcp.md`

## 변경 요약

- AI assistant의 직접 provider 호출 경로를 Codex runtime 호출로 전환했다.
- OpenAI, Gemini, Ollama 설정을 Codex `model_provider` 설정으로 연결하는 로컬 Responses API 게이트웨이를 추가했다.
- Codex 실행용 임시 `CODEX_HOME`을 생성하고, 인증 없는 custom provider 설정과 Docker Infra MCP 설정을 주입하는 runtime 모델을 추가했다.
- 등록된 서버 정보를 Codex MCP 컨텍스트로 전달하고, MCP 도구로 `docker_search`, `server_list`, `server_collect`, `ssh_command`를 제공했다.
- 모델 선택 응답에 Codex 실행 엔진 정보를 포함하고, Codex 실행 실패를 AI 보정 불가 오류 범주에 포함했다.

## 확인 결과

- `python -m py_compile project/main/src/model/struct/codex_runtime.py project/main/tools/codex_responses_gateway.py project/main/tools/docker_infra_mcp.py`: 통과
- mock Responses gateway와 `codex exec` 연동 확인: `{"ok":true,"message":"codex-gateway-mock-ok"}` 최종 응답 확인
- MCP stdio `initialize`, `tools/list`, `server_list` 호출 확인: 도구 4개 노출 및 `server_list` 정상 응답
- `wiz_project_build(projectName="main", clean=false)`: 통과
- `python -m unittest tests.api.test_wiz_structure_contract`: 실패. 새 `codex_runtime.py`는 283줄로 기준 안에 있으나, 기존 `ai_assistant.py`, `ai_settings.py`, `local_command_catalog.py` 등 18개 모델 파일이 300줄 제한을 초과해 실패한다.

## 남은 리스크

- 실제 OpenAI, Gemini, Ollama 엔드포인트 호출은 운영 토큰과 모델 서버 연결이 필요해 mock gateway로만 Codex 연동을 검증했다.
- `ssh_command`와 `server_collect`는 등록 서버의 SSH 키와 네트워크 접근 권한에 의존한다.
