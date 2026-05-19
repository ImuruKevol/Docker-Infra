# 235. Codex MCP 핸드셰이크와 DDNS AI 검증 호출 복구

- 날짜: 2026-05-18
- 요청자: 권태욱
- 리뷰 ID: lrmzidmbdswuudpmvcjfayyucjmiofzx

## 원 요청

> 2026. 5. 18. 오후 7:57:47
> ai verification
> Codex 검증 호출이 실패해 등록된 DDNS 서버 정보를 기준으로 자동 수정 단계로 전환합니다.
>
> 이 Codex 검증 호출이 실패하는 이슈부터 해결이 되어야 할 것 같아.
>
> 그리고
> Codex 수정 호출이 실패해 등록된 DDNS 서버와 추천 도메인으로 서비스 도메인을 보정했습니다. DDNS 등록 API 호출을 실행했습니다.
> 이 수정 호출도 실패하는 이슈도 수정해야 하고.

## 변경 요약

- 실제 Codex CLI smoke로 Codex 모델 호출은 정상이고 Docker Infra MCP 서버 핸드셰이크가 30초 타임아웃으로 실패하는 것을 확인했다.
- `tools/docker_infra_mcp.py`가 기존 `Content-Length` 프레이밍뿐 아니라 현재 Codex CLI의 줄 단위 JSON stdio 메시지도 읽고 같은 방식으로 응답하도록 수정했다.
- Codex가 조회할 수 있는 `resources/list`, `resources/templates/list`, `prompts/list`, `ping` 기본 응답을 추가했다.
- non-interactive Codex 실행에서 Docker Infra MCP 도구 호출이 취소되지 않도록 `default_tools_approval_mode = "approve"`를 Codex runtime MCP 설정에 추가했다.
- MCP stdio JSON 핸드셰이크 회귀 테스트를 추가했다.

## 변경 파일

- `tools/docker_infra_mcp.py`
- `src/model/struct/codex_runtime.py`
- `tests/api/test_services_preflight.py`
- `devlog.md`
- `devlog/2026-05-18/235-codex-mcp-handshake-ddns-ai.md`

## 확인한 내용

- MCP 서버 단독 `initialize`, `tools/list`, `resources/list` 줄 단위 JSON 응답 확인
- MCP 서버 단독 `Content-Length` 방식 `initialize` 응답 유지 확인
- 실제 `codex exec` + Docker Infra MCP smoke에서 `infra_context` 도구 호출 성공 및 DDNS endpoint context 반환 확인
- `/opt/conda/envs/docker-infra/bin/python -m py_compile tools/docker_infra_mcp.py src/model/struct/codex_runtime.py src/model/struct/ai_assistant.py`: 통과
- `/opt/conda/envs/docker-infra/bin/python -m unittest tests.api.test_services_preflight`: 13개 테스트 통과
- `wiz_project_build(projectName="main", clean=false)`: 통과
- `git diff --check`: 통과

## 남은 리스크

- 실제 AI 검증/수정 성공은 Codex 로그인 상태, 선택 모델 사용 가능 여부, 외부 DDNS API 응답 상태에 계속 의존한다.
